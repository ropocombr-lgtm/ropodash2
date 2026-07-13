from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from bling_core import (
    SITUACOES_CANCELADAS,
    calcular_historico_diario,
    carregar_dataframe,
    carregar_historico_completo,
    gerar_url_autorizacao,
    ler_itens_pedidos,
    ler_tokens,
    moeda_br,
    nome_canal,
    processar_callback_oauth,
    salvar_historico_diario,
    sincronizar_itens_pedidos,
    supabase,
)

NOMES_DIA_SEMANA = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Dashboard Bling",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    h1, h2, h3 {
        color: #0F172A;
    }

    .dashboard-subtitle {
        color: #64748B;
        font-size: 0.95rem;
        margin-top: -8px;
        margin-bottom: 4px;
    }

    .dashboard-badges {
        color: #64748B;
        font-size: 0.85rem;
        margin-bottom: 20px;
    }

    .kpi-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
        height: 100%;
    }

    .small-label {
        font-size: 0.8rem;
        color: #64748B;
        margin-bottom: 6px;
    }

    .big-number {
        font-size: 1.7rem;
        font-weight: 700;
        color: #0F172A;
        line-height: 1.2;
    }

    .delta {
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 4px;
    }

    .delta.good {
        color: #16A34A;
    }

    .delta.bad {
        color: #DC2626;
    }

    .delta.neutral {
        color: #64748B;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background: #EFF6FF;
        border-radius: 12px;
        padding: 10px 16px;
        height: auto;
    }

    .stTabs [aria-selected="true"] {
        background: #2563EB !important;
        color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def card_kpi(
    titulo: str,
    valor: str,
    subtitulo: str = "",
    delta: str | None = None,
    delta_tipo: str = "neutral",
) -> None:
    delta_html = (
        f'<div class="delta {delta_tipo}">{delta}</div>' if delta else ""
    )

    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="small-label">{titulo}</div>
            <div class="big-number">{valor}</div>
            <div class="small-label">{subtitulo}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


processar_callback_oauth()


# =========================================================
# METAS DE VENDAS
# =========================================================

def inicio_semana(data: date) -> date:
    return data - timedelta(days=data.weekday())


def inicio_mes(data: date) -> date:
    return data.replace(day=1)


def ler_metas() -> pd.DataFrame:
    resposta = supabase.table("metas").select("*").execute()
    dados = resposta.data or []

    colunas = ["canal", "periodicidade", "referencia", "valor"]

    if not dados:
        return pd.DataFrame(columns=colunas)

    metas = pd.DataFrame(dados)
    metas["referencia"] = pd.to_datetime(metas["referencia"]).dt.date

    return metas[colunas]


def salvar_meta(
    canal: str,
    periodicidade: str,
    referencia: date,
    valor: float,
) -> None:
    registro = {
        "canal": canal,
        "periodicidade": periodicidade,
        "referencia": referencia.isoformat(),
        "valor": valor,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    (
        supabase.table("metas")
        .upsert(registro, on_conflict="canal,periodicidade,referencia")
        .execute()
    )


def calcular_realizado_por_periodo(
    df_validos: pd.DataFrame,
    periodicidade: str,
) -> pd.DataFrame:
    dados = df_validos.dropna(subset=["data"]).copy()
    dados["canal"] = dados["loja_id"].fillna("Sem canal").astype(str)

    calcular_referencia = (
        inicio_semana if periodicidade == "semanal" else inicio_mes
    )

    dados["referencia"] = dados["data"].dt.date.apply(calcular_referencia)

    return (
        dados.groupby(["canal", "referencia"], as_index=False)
        .agg(realizado=("total", "sum"))
    )


def montar_comparativo(
    realizado: pd.DataFrame,
    metas: pd.DataFrame,
    periodicidade: str,
) -> pd.DataFrame:
    metas_filtradas = metas.loc[metas["periodicidade"] == periodicidade]

    comparativo = realizado.merge(
        metas_filtradas[["canal", "referencia", "valor"]],
        on=["canal", "referencia"],
        how="left",
    ).rename(columns={"valor": "meta"})

    tem_meta = comparativo["meta"].notna()

    comparativo["gap"] = (
        comparativo["realizado"] - comparativo["meta"]
    ).where(tem_meta)

    comparativo["atingido"] = (
        comparativo["realizado"] / comparativo["meta"]
    ).where(tem_meta)

    comparativo["meta"] = comparativo["meta"].fillna(0)

    return comparativo.sort_values(
        ["referencia", "canal"],
        ascending=[False, True],
    )


def fim_periodo(referencia: date, periodicidade: str) -> date:
    if periodicidade == "semanal":
        return referencia + timedelta(days=6)

    dias_no_mes = calendar.monthrange(referencia.year, referencia.month)[1]
    return referencia.replace(day=dias_no_mes)


def enriquecer_comparativo_com_ritmo(
    comparativo: pd.DataFrame,
    periodicidade: str,
    hoje: date,
) -> pd.DataFrame:
    enriquecido = comparativo.copy()

    enriquecido["fim_periodo"] = enriquecido["referencia"].apply(
        lambda referencia: fim_periodo(referencia, periodicidade)
    )

    enriquecido["dias_totais"] = [
        (fim - referencia).days + 1
        for fim, referencia in zip(
            enriquecido["fim_periodo"], enriquecido["referencia"]
        )
    ]

    enriquecido["periodo_em_andamento"] = enriquecido["fim_periodo"] >= hoje

    def _dias_transcorridos(linha: pd.Series) -> int:
        fim_considerado = min(hoje, linha["fim_periodo"])

        if fim_considerado < linha["referencia"]:
            return 0

        return (fim_considerado - linha["referencia"]).days + 1

    enriquecido["dias_transcorridos"] = enriquecido.apply(
        _dias_transcorridos, axis=1
    )

    enriquecido["dias_restantes"] = (
        enriquecido["dias_totais"] - enriquecido["dias_transcorridos"]
    ).clip(lower=0)

    meta_restante = (enriquecido["meta"] - enriquecido["realizado"]).clip(
        lower=0
    )

    pode_calcular_ritmo = (
        (enriquecido["meta"] > 0)
        & enriquecido["periodo_em_andamento"]
        & (enriquecido["dias_restantes"] > 0)
    )

    dias_restantes_seguro = enriquecido["dias_restantes"].where(
        enriquecido["dias_restantes"] > 0
    )

    enriquecido["ritmo_necessario"] = (
        meta_restante / dias_restantes_seguro
    ).where(pode_calcular_ritmo)

    dias_transcorridos_seguro = enriquecido["dias_transcorridos"].where(
        enriquecido["dias_transcorridos"] > 0
    )

    enriquecido["projecao"] = (
        enriquecido["realizado"]
        / dias_transcorridos_seguro
        * enriquecido["dias_totais"]
    ).where(enriquecido["periodo_em_andamento"])

    def _classificar(linha: pd.Series) -> str:
        if linha["meta"] <= 0:
            return "Sem meta"

        if not linha["periodo_em_andamento"]:
            return "Período encerrado"

        if pd.isna(linha["projecao"]):
            return "—"

        razao = linha["projecao"] / linha["meta"]

        if razao >= 1:
            return "Acima da meta"

        if razao >= 0.9:
            return "Dentro do ritmo"

        if razao >= 0.7:
            return "Risco moderado"

        return "Risco alto"

    enriquecido["classificacao"] = enriquecido.apply(_classificar, axis=1)

    return enriquecido


# =========================================================
# ANÁLISE COMERCIAL
# =========================================================

def faturamento_valido(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0

    cancelados = df["situacao_id"].isin(SITUACOES_CANCELADAS)

    return float(df.loc[~cancelados, "total"].sum())


def variacao_percentual(atual: float, anterior: float) -> float | None:
    if not anterior:
        return None

    return (atual - anterior) / anterior


# =========================================================
# INTERFACE
# =========================================================

st.markdown("## 📊 Dashboard Comercial ROPO")
st.markdown(
    '<div class="dashboard-subtitle">'
    "Vendas, performance por canal, metas e projeções."
    "</div>",
    unsafe_allow_html=True,
)

tokens_existentes = ler_tokens()

if not tokens_existentes:
    st.warning("O dashboard ainda não está conectado ao Bling.")

    st.link_button(
        "Conectar ao Bling",
        gerar_url_autorizacao(),
        type="primary",
    )

    st.stop()


with st.sidebar:
    st.header("Filtros")

    hoje = date.today()

    data_inicial = st.date_input(
        "Data inicial",
        value=hoje - timedelta(days=30),
    )

    data_final = st.date_input(
        "Data final",
        value=hoje,
    )

    if data_inicial > data_final:
        st.error("A data inicial não pode ser posterior à data final.")
        st.stop()

    atualizar = st.button(
        "Atualizar agora",
        use_container_width=True,
    )

    st.divider()

    if st.button(
        "Reconectar ao Bling",
        use_container_width=True,
    ):
        st.link_button(
            "Autorizar novamente",
            gerar_url_autorizacao(),
            type="primary",
        )


st.markdown(
    '<div class="dashboard-badges">'
    f"📅 Período: {data_inicial.strftime('%d/%m/%Y')} a "
    f"{data_final.strftime('%d/%m/%Y')}"
    " &nbsp;·&nbsp; 🔄 Última atualização: "
    f"{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"
    " &nbsp;·&nbsp; 🟢 Bling conectado"
    "</div>",
    unsafe_allow_html=True,
)


@st.fragment(run_every="5m")
def exibir_dashboard() -> None:
    if atualizar:
        carregar_dataframe.clear()

    with st.spinner("Consultando os dados do Bling..."):
        df = carregar_dataframe(
            data_inicial.isoformat(),
            data_final.isoformat(),
        )

    if df.empty:
        st.info("Nenhum pedido foi encontrado no período selecionado.")
        return

    salvar_historico_diario(calcular_historico_diario(df))

    cancelados = df["situacao_id"].isin(SITUACOES_CANCELADAS)

    df_validos = df.loc[~cancelados].copy()

    quantidade_pedidos = int(df_validos["id"].nunique())
    faturamento = float(df_validos["total"].sum())

    ticket_medio = (
        faturamento / quantidade_pedidos
        if quantidade_pedidos
        else 0
    )

    quantidade_cancelados = int(df.loc[cancelados, "id"].nunique())
    quantidade_pedidos_totais = int(df["id"].nunique())
    valor_cancelado = float(df.loc[cancelados, "total"].sum())

    taxa_cancelamento = (
        quantidade_cancelados / quantidade_pedidos_totais
        if quantidade_pedidos_totais
        else 0
    )

    aba_comercial, aba_produto, aba_preditivo, aba_metas = st.tabs(
        ["📈 Comercial", "🛒 Produto", "🔮 Preditivo", "🎯 Metas"]
    )

    with aba_comercial:
        duracao_periodo = (data_final - data_inicial).days + 1

        periodo_anterior_final = data_inicial - timedelta(days=1)
        periodo_anterior_inicial = periodo_anterior_final - timedelta(
            days=duracao_periodo - 1
        )

        # Aproximação simples de "mesmo período do ano anterior";
        # não ajusta para o dia da semana nem para anos bissextos.
        ano_anterior_inicial = data_inicial - timedelta(days=365)
        ano_anterior_final = data_final - timedelta(days=365)

        df_periodo_anterior = carregar_dataframe(
            periodo_anterior_inicial.isoformat(),
            periodo_anterior_final.isoformat(),
        )

        df_ano_anterior = carregar_dataframe(
            ano_anterior_inicial.isoformat(),
            ano_anterior_final.isoformat(),
        )

        crescimento_periodo = variacao_percentual(
            faturamento,
            faturamento_valido(df_periodo_anterior),
        )

        crescimento_ano = variacao_percentual(
            faturamento,
            faturamento_valido(df_ano_anterior),
        )

        def _delta_tipo(valor: float | None) -> str:
            if valor is None:
                return "neutral"
            return "good" if valor >= 0 else "bad"

        st.markdown("#### Resumo executivo")

        coluna_1, coluna_2, coluna_3, coluna_4 = st.columns(4)

        with coluna_1:
            card_kpi(
                "Faturamento",
                moeda_br(faturamento),
                "Período selecionado",
                delta=(
                    f"{crescimento_periodo:+.1%} vs. período anterior"
                    if crescimento_periodo is not None
                    else None
                ),
                delta_tipo=_delta_tipo(crescimento_periodo),
            )

        with coluna_2:
            card_kpi(
                "Pedidos",
                f"{quantidade_pedidos:,}".replace(",", "."),
            )

        with coluna_3:
            card_kpi(
                "Ticket médio",
                moeda_br(ticket_medio),
            )

        with coluna_4:
            card_kpi(
                "Cancelados",
                f"{quantidade_cancelados:,}".replace(",", "."),
                f"{taxa_cancelamento:.1%} dos pedidos",
                delta=f"{moeda_br(valor_cancelado)} em valor",
                delta_tipo="bad" if quantidade_cancelados else "neutral",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        coluna_5, coluna_6 = st.columns(2)

        with coluna_5:
            card_kpi(
                "Vs. período anterior",
                (
                    f"{crescimento_periodo:+.1%}"
                    if crescimento_periodo is not None
                    else "—"
                ),
                (
                    "Sem base de comparação"
                    if crescimento_periodo is None
                    else "Mesma duração, imediatamente antes"
                ),
                delta_tipo=_delta_tipo(crescimento_periodo),
            )

        with coluna_6:
            card_kpi(
                "Vs. mesmo período ano anterior",
                (
                    f"{crescimento_ano:+.1%}"
                    if crescimento_ano is not None
                    else "—"
                ),
                (
                    "Sem base de comparação"
                    if crescimento_ano is None
                    else "Aproximação: 365 dias atrás"
                ),
                delta_tipo=_delta_tipo(crescimento_ano),
            )

        st.divider()
        st.markdown("#### Evolução de vendas")

        vendas_diarias = (
            df_validos.dropna(subset=["data"])
            .assign(dia=lambda dados: dados["data"].dt.date)
            .groupby("dia", as_index=False)
            .agg(
                faturamento=("total", "sum"),
                pedidos=("id", "nunique"),
            )
        )

        with st.container(border=True):
            grafico_faturamento = px.line(
                vendas_diarias,
                x="dia",
                y="faturamento",
                markers=True,
                title="Evolução do faturamento",
                labels={
                    "dia": "Data",
                    "faturamento": "Faturamento",
                },
            )

            st.plotly_chart(
                grafico_faturamento,
                use_container_width=True,
            )

            if not vendas_diarias.empty:
                melhor_dia = vendas_diarias.loc[
                    vendas_diarias["faturamento"].idxmax()
                ]
                pior_dia = vendas_diarias.loc[
                    vendas_diarias["faturamento"].idxmin()
                ]
                media_diaria = (
                    faturamento / vendas_diarias["dia"].nunique()
                )

                coluna_7, coluna_8, coluna_9 = st.columns(3)

                with coluna_7:
                    card_kpi(
                        f"Melhor dia ({melhor_dia['dia'].strftime('%d/%m')})",
                        moeda_br(melhor_dia["faturamento"]),
                    )

                with coluna_8:
                    card_kpi(
                        f"Pior dia ({pior_dia['dia'].strftime('%d/%m')})",
                        moeda_br(pior_dia["faturamento"]),
                    )

                with coluna_9:
                    card_kpi(
                        "Média diária",
                        moeda_br(media_diaria),
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Comparativos")

        inicio_mes_atual = hoje.replace(day=1)

        df_mes_atual = carregar_dataframe(
            inicio_mes_atual.isoformat(),
            hoje.isoformat(),
        )

        faturamento_mes_atual = faturamento_valido(df_mes_atual)
        dias_transcorridos = (hoje - inicio_mes_atual).days + 1
        dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]

        projecao_mes = (
            faturamento_mes_atual / dias_transcorridos * dias_no_mes
            if dias_transcorridos
            else 0
        )

        coluna_10, coluna_11 = st.columns(2)

        with coluna_10:
            card_kpi(
                "Acumulado do mês",
                moeda_br(faturamento_mes_atual),
            )

        with coluna_11:
            card_kpi(
                "Projeção de fechamento do mês",
                moeda_br(projecao_mes),
                "Acumulado ÷ dias transcorridos × dias do mês",
            )

        st.caption(
            "Projeção simples. Não considera sazonalidade nem campanhas."
        )

        st.divider()
        st.markdown("#### Operação")

        coluna_status, coluna_clientes = st.columns(2)

        with coluna_status, st.container(border=True):
            por_situacao = (
                df.groupby("situacao", as_index=False)
                .agg(pedidos=("id", "nunique"))
                .sort_values("pedidos", ascending=False)
            )

            grafico_status = px.bar(
                por_situacao,
                x="situacao",
                y="pedidos",
                title="Pedidos por situação",
                labels={
                    "situacao": "Situação",
                    "pedidos": "Pedidos",
                },
            )

            st.plotly_chart(
                grafico_status,
                use_container_width=True,
            )

        with coluna_clientes, st.container(border=True):
            principais_clientes = (
                df_validos.groupby("cliente", as_index=False)
                .agg(
                    faturamento=("total", "sum"),
                    pedidos=("id", "nunique"),
                )
                .sort_values("faturamento", ascending=False)
                .head(10)
            )

            grafico_clientes = px.bar(
                principais_clientes,
                x="faturamento",
                y="cliente",
                orientation="h",
                title="Principais clientes",
                labels={
                    "cliente": "Cliente",
                    "faturamento": "Faturamento",
                },
            )

            st.plotly_chart(
                grafico_clientes,
                use_container_width=True,
            )

        st.divider()
        st.markdown("#### Canais")

        receita_por_canal = (
            df_validos.assign(
                canal=lambda d: d["loja_id"].apply(nome_canal)
            )
            .groupby("canal", as_index=False)
            .agg(
                faturamento=("total", "sum"),
                pedidos=("id", "nunique"),
            )
            .sort_values("faturamento", ascending=False)
        )

        receita_por_canal["ticket_medio"] = (
            receita_por_canal["faturamento"] / receita_por_canal["pedidos"]
        )

        receita_por_canal["participacao"] = (
            receita_por_canal["faturamento"] / faturamento
            if faturamento
            else 0
        )

        if df_periodo_anterior.empty:
            receita_por_canal["faturamento_anterior"] = 0.0
        else:
            faturamento_anterior_por_canal = (
                df_periodo_anterior.loc[
                    ~df_periodo_anterior["situacao_id"].isin(
                        SITUACOES_CANCELADAS
                    )
                ]
                .assign(canal=lambda d: d["loja_id"].apply(nome_canal))
                .groupby("canal", as_index=False)
                .agg(faturamento_anterior=("total", "sum"))
            )

            receita_por_canal = receita_por_canal.merge(
                faturamento_anterior_por_canal,
                on="canal",
                how="left",
            )

            receita_por_canal["faturamento_anterior"] = receita_por_canal[
                "faturamento_anterior"
            ].fillna(0)

        receita_por_canal["crescimento"] = receita_por_canal.apply(
            lambda linha: variacao_percentual(
                linha["faturamento"],
                linha["faturamento_anterior"],
            ),
            axis=1,
        )

        with st.container(border=True):
            coluna_canal, coluna_cancelamento_canal = st.columns(2)

            with coluna_canal:
                grafico_canal = px.bar(
                    receita_por_canal,
                    x="canal",
                    y="faturamento",
                    title="Receita por canal",
                    labels={
                        "canal": "Canal",
                        "faturamento": "Faturamento",
                    },
                )

                st.plotly_chart(
                    grafico_canal,
                    use_container_width=True,
                )

            with coluna_cancelamento_canal:
                cancelamento_por_canal = (
                    df.assign(
                        canal=lambda d: d["loja_id"].apply(nome_canal),
                        cancelado=cancelados,
                    )
                    .groupby("canal", as_index=False)
                    .agg(
                        total_pedidos=("id", "nunique"),
                        cancelados=("cancelado", "sum"),
                    )
                )

                cancelamento_por_canal["taxa_cancelamento"] = (
                    cancelamento_por_canal["cancelados"]
                    / cancelamento_por_canal["total_pedidos"]
                )

                grafico_cancelamento = px.bar(
                    cancelamento_por_canal,
                    x="canal",
                    y="taxa_cancelamento",
                    title="Taxa de cancelamento por canal",
                    labels={
                        "canal": "Canal",
                        "taxa_cancelamento": "Taxa de cancelamento",
                    },
                )

                grafico_cancelamento.update_yaxes(tickformat=".0%")

                st.plotly_chart(
                    grafico_cancelamento,
                    use_container_width=True,
                )

            tabela_canal = receita_por_canal.copy()

            tabela_canal["faturamento"] = tabela_canal[
                "faturamento"
            ].apply(moeda_br)
            tabela_canal["ticket_medio"] = tabela_canal[
                "ticket_medio"
            ].apply(moeda_br)
            tabela_canal["participacao"] = tabela_canal[
                "participacao"
            ].apply(lambda valor: f"{valor:.1%}")
            tabela_canal["crescimento"] = tabela_canal["crescimento"].apply(
                lambda valor: (
                    f"{valor:+.1%}"
                    if pd.notna(valor)
                    else "Sem base anterior"
                )
            )

            st.dataframe(
                tabela_canal[
                    [
                        "canal",
                        "faturamento",
                        "pedidos",
                        "ticket_medio",
                        "participacao",
                        "crescimento",
                    ]
                ].rename(
                    columns={
                        "canal": "Canal",
                        "faturamento": "Faturamento",
                        "pedidos": "Pedidos",
                        "ticket_medio": "Ticket médio",
                        "participacao": "Participação",
                        "crescimento": "Vs. período anterior",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        st.divider()
        st.markdown("#### Dia da semana")

        dados_semana = df.dropna(subset=["data"]).copy()
        dados_semana["dia_semana_idx"] = dados_semana["data"].dt.dayofweek
        dados_semana["cancelado"] = dados_semana["situacao_id"].isin(
            SITUACOES_CANCELADAS
        )

        por_dia_semana = dados_semana.groupby(
            "dia_semana_idx", as_index=False
        ).agg(
            pedidos=("id", "nunique"),
            cancelados=("cancelado", "sum"),
        )

        faturamento_por_dia_semana = (
            dados_semana.loc[~dados_semana["cancelado"]]
            .groupby("dia_semana_idx", as_index=False)
            .agg(faturamento=("total", "sum"))
        )

        por_dia_semana = por_dia_semana.merge(
            faturamento_por_dia_semana,
            on="dia_semana_idx",
            how="left",
        )

        por_dia_semana["faturamento"] = por_dia_semana[
            "faturamento"
        ].fillna(0)

        por_dia_semana["taxa_cancelamento"] = (
            por_dia_semana["cancelados"] / por_dia_semana["pedidos"]
        )

        por_dia_semana["dia_semana"] = por_dia_semana[
            "dia_semana_idx"
        ].map(NOMES_DIA_SEMANA)

        por_dia_semana = por_dia_semana.sort_values("dia_semana_idx")

        with st.container(border=True):
            grafico_dia_semana = px.bar(
                por_dia_semana,
                x="dia_semana",
                y="faturamento",
                title="Faturamento por dia da semana",
                labels={
                    "dia_semana": "Dia da semana",
                    "faturamento": "Faturamento",
                },
            )

            st.plotly_chart(
                grafico_dia_semana,
                use_container_width=True,
            )

        st.divider()
        st.markdown("#### Clientes")
        st.caption("Novos vs. recorrentes")

        historico_completo = carregar_historico_completo(
            data_final.isoformat(),
            3,
        )

        if (
            historico_completo.empty
            or "cliente_id" not in historico_completo.columns
            or df_validos["cliente_id"].dropna().empty
        ):
            st.info(
                "Ainda não há histórico suficiente de clientes para essa "
                "análise."
            )
        else:
            primeira_compra = (
                historico_completo.dropna(subset=["cliente_id", "data"])
                .groupby("cliente_id")["data"]
                .min()
                .dt.date
            )

            pedidos_por_cliente_historico = (
                historico_completo.dropna(subset=["cliente_id"])
                .groupby("cliente_id")["id"]
                .nunique()
            )

            df_status_cliente = df_validos.dropna(
                subset=["cliente_id"]
            ).copy()

            df_status_cliente["primeira_compra"] = df_status_cliente[
                "cliente_id"
            ].map(primeira_compra)

            df_status_cliente["cliente_novo"] = (
                df_status_cliente["primeira_compra"] >= data_inicial
            )

            resumo_status = (
                df_status_cliente.groupby("cliente_novo")
                .agg(
                    clientes=("cliente_id", "nunique"),
                    pedidos=("id", "nunique"),
                    receita=("total", "sum"),
                )
            )

            def _linha_status(novo: bool) -> tuple:
                if novo not in resumo_status.index:
                    return (0, 0, 0.0, 0.0)

                linha = resumo_status.loc[novo]
                ticket = (
                    linha["receita"] / linha["pedidos"]
                    if linha["pedidos"]
                    else 0.0
                )

                return (
                    int(linha["clientes"]),
                    int(linha["pedidos"]),
                    float(linha["receita"]),
                    ticket,
                )

            clientes_novos, pedidos_novos, receita_novos, ticket_novos = (
                _linha_status(True)
            )

            (
                clientes_recorrentes,
                pedidos_recorrentes,
                receita_recorrentes,
                ticket_recorrentes,
            ) = _linha_status(False)

            with st.container(border=True):
                coluna_novo, coluna_recorrente = st.columns(2)

                with coluna_novo:
                    st.markdown("**Clientes novos**")
                    card_kpi("Clientes", str(clientes_novos))
                    card_kpi("Receita", moeda_br(receita_novos))
                    card_kpi("Ticket médio", moeda_br(ticket_novos))

                with coluna_recorrente:
                    st.markdown("**Clientes recorrentes**")
                    card_kpi("Clientes", str(clientes_recorrentes))
                    card_kpi("Receita", moeda_br(receita_recorrentes))
                    card_kpi("Ticket médio", moeda_br(ticket_recorrentes))

                clientes_2_ou_mais = int(
                    (pedidos_por_cliente_historico >= 2).sum()
                )
                clientes_3_ou_mais = int(
                    (pedidos_por_cliente_historico >= 3).sum()
                )
                total_clientes_historico = int(
                    pedidos_por_cliente_historico.shape[0]
                )

                taxa_recompra = (
                    clientes_2_ou_mais / total_clientes_historico
                    if total_clientes_historico
                    else 0
                )

                st.caption(
                    f"Taxa de recompra (últimos 3 anos): "
                    f"{taxa_recompra:.1%} — {clientes_2_ou_mais} com 2+ "
                    f"pedidos e {clientes_3_ou_mais} com 3+ pedidos, de "
                    f"{total_clientes_historico} clientes únicos."
                )

        st.divider()
        st.markdown("#### Pedidos do período")

        with st.container(border=True):
            tabela = df.sort_values(
                "data",
                ascending=False,
            ).copy()

            tabela["data"] = tabela["data"].dt.strftime("%d/%m/%Y")
            tabela["total"] = tabela["total"].apply(moeda_br)

            st.dataframe(
                tabela[
                    [
                        "numero",
                        "data",
                        "cliente",
                        "situacao",
                        "total",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "Última atualização exibida: "
                f"{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"
            )

    with aba_produto:
        itens_periodo = ler_itens_pedidos(data_inicial, data_final)

        with st.expander("Sincronização de itens"):
            st.caption(
                "Os itens de cada pedido exigem 1 chamada de API por "
                "pedido (o Bling não devolve isso na lista). Pedidos já "
                "sincronizados ficam salvos no Supabase e não são "
                "buscados de novo."
            )

            if st.button("Sincronizar itens do período selecionado"):
                barra = st.progress(0.0)

                def _atualizar_barra(atual: int, total: int) -> None:
                    if total:
                        barra.progress(atual / total)

                novos = sincronizar_itens_pedidos(
                    df,
                    progresso=_atualizar_barra,
                )

                st.success(
                    f"{novos} pedido(s) sincronizado(s). "
                    "Atualize a página para ver os dados novos."
                )
                ler_itens_pedidos.clear()

        if itens_periodo.empty:
            st.info(
                "Nenhum item sincronizado para este período ainda. Use "
                "\"Sincronizar itens do período selecionado\" acima."
            )
        else:
            itens_validos = itens_periodo.loc[
                ~itens_periodo["situacao_id"].isin(SITUACOES_CANCELADAS)
            ].copy()

            itens_validos["total_item"] = (
                itens_validos["quantidade"]
                * itens_validos["valor_unitario"]
                - itens_validos["desconto"]
            )

            faturamento_produtos = float(
                itens_validos["total_item"].sum()
            )

            ranking = (
                itens_validos.groupby(
                    ["sku", "descricao"], as_index=False
                )
                .agg(
                    faturamento=("total_item", "sum"),
                    unidades=("quantidade", "sum"),
                    pedidos=("pedido_id", "nunique"),
                )
                .sort_values("faturamento", ascending=False)
            )

            skus_ativos = int(itens_validos["sku"].nunique())
            unidades_vendidas = float(itens_validos["quantidade"].sum())
            pedidos_sincronizados_periodo = int(
                itens_validos["pedido_id"].nunique()
            )

            produto_lider = (
                ranking.iloc[0]["descricao"] if not ranking.empty else "—"
            )

            st.markdown("#### Resumo de produtos")
            st.caption(
                f"Baseado em {pedidos_sincronizados_periodo} pedido(s) "
                "já sincronizado(s) neste período (pode não ser 100% "
                "dos pedidos do período — veja a sincronização acima)."
            )

            coluna_p1, coluna_p2, coluna_p3, coluna_p4 = st.columns(4)

            with coluna_p1:
                card_kpi("SKUs ativos", str(skus_ativos))

            with coluna_p2:
                card_kpi(
                    "Unidades vendidas",
                    f"{unidades_vendidas:,.0f}".replace(",", "."),
                )

            with coluna_p3:
                card_kpi("Faturamento em itens", moeda_br(faturamento_produtos))

            with coluna_p4:
                card_kpi("Produto líder", produto_lider)

            st.divider()
            st.markdown("#### Ranking de produtos")

            with st.container(border=True):
                top_produtos = ranking.head(10)

                grafico_ranking = px.bar(
                    top_produtos,
                    x="faturamento",
                    y="descricao",
                    orientation="h",
                    title="Top 10 produtos por faturamento",
                    labels={
                        "descricao": "Produto",
                        "faturamento": "Faturamento",
                    },
                )

                grafico_ranking.update_yaxes(
                    categoryorder="total ascending"
                )

                st.plotly_chart(
                    grafico_ranking,
                    use_container_width=True,
                )

                tabela_ranking = ranking.copy()
                tabela_ranking["faturamento"] = tabela_ranking[
                    "faturamento"
                ].apply(moeda_br)

                st.dataframe(
                    tabela_ranking.rename(
                        columns={
                            "sku": "SKU",
                            "descricao": "Produto",
                            "faturamento": "Faturamento",
                            "unidades": "Unidades",
                            "pedidos": "Pedidos",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            st.divider()
            st.markdown("#### Curva ABC (por faturamento)")

            with st.container(border=True):
                curva_abc = ranking.copy()

                curva_abc["participacao"] = (
                    curva_abc["faturamento"] / faturamento_produtos
                    if faturamento_produtos
                    else 0
                )

                curva_abc["acumulado"] = curva_abc["participacao"].cumsum()

                curva_abc["classe"] = curva_abc["acumulado"].apply(
                    lambda acumulado: (
                        "A"
                        if acumulado <= 0.8
                        else ("B" if acumulado <= 0.95 else "C")
                    )
                )

                resumo_abc = (
                    curva_abc.groupby("classe", as_index=False)
                    .agg(
                        produtos=("sku", "nunique"),
                        faturamento=("faturamento", "sum"),
                    )
                )

                resumo_abc["participacao"] = (
                    resumo_abc["faturamento"] / faturamento_produtos
                    if faturamento_produtos
                    else 0
                )

                coluna_abc, coluna_abc_tabela = st.columns([2, 1])

                with coluna_abc:
                    grafico_abc = px.bar(
                        curva_abc,
                        x="descricao",
                        y="acumulado",
                        color="classe",
                        title="Participação acumulada na receita",
                        labels={
                            "descricao": "Produto",
                            "acumulado": "Participação acumulada",
                        },
                    )

                    grafico_abc.update_yaxes(tickformat=".0%")
                    grafico_abc.update_xaxes(
                        showticklabels=False,
                    )

                    st.plotly_chart(
                        grafico_abc,
                        use_container_width=True,
                    )

                with coluna_abc_tabela:
                    tabela_abc = resumo_abc.copy()
                    tabela_abc["faturamento"] = tabela_abc[
                        "faturamento"
                    ].apply(moeda_br)
                    tabela_abc["participacao"] = tabela_abc[
                        "participacao"
                    ].apply(lambda valor: f"{valor:.1%}")

                    st.dataframe(
                        tabela_abc.rename(
                            columns={
                                "classe": "Classe",
                                "produtos": "Produtos",
                                "faturamento": "Faturamento",
                                "participacao": "Participação",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            st.divider()
            st.markdown("#### Produtos comprados juntos")

            with st.container(border=True):
                pares_encontrados: dict[tuple[str, str], int] = {}

                for _, grupo in itens_validos.groupby("pedido_id"):
                    skus_pedido = sorted(
                        grupo["sku"].dropna().unique().tolist()
                    )

                    for i in range(len(skus_pedido)):
                        for j in range(i + 1, len(skus_pedido)):
                            par = (skus_pedido[i], skus_pedido[j])
                            pares_encontrados[par] = (
                                pares_encontrados.get(par, 0) + 1
                            )

                if not pares_encontrados:
                    st.info(
                        "Nenhum pedido com mais de um produto diferente "
                        "neste período."
                    )
                else:
                    cesta = pd.DataFrame(
                        [
                            {
                                "produto_a": par[0],
                                "produto_b": par[1],
                                "pedidos_juntos": contagem,
                            }
                            for par, contagem in pares_encontrados.items()
                        ]
                    ).sort_values("pedidos_juntos", ascending=False)

                    st.dataframe(
                        cesta.head(15).rename(
                            columns={
                                "produto_a": "Produto A",
                                "produto_b": "Produto B",
                                "pedidos_juntos": "Pedidos juntos",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

    with aba_preditivo:
        st.info(
            "Em construção. As projeções semanal, mensal e anual serão "
            "calculadas a partir do histórico diário já usado na aba "
            "Comercial — sem custo extra de API. Chegam na próxima "
            "atualização."
        )

    with aba_metas:
        metas_df = ler_metas()

        aba_semanal, aba_mensal = st.tabs(["Semanal", "Mensal"])

        for aba, periodicidade in (
            (aba_semanal, "semanal"),
            (aba_mensal, "mensal"),
        ):
            with aba:
                realizado = calcular_realizado_por_periodo(
                    df_validos,
                    periodicidade,
                )

                comparativo = montar_comparativo(
                    realizado,
                    metas_df,
                    periodicidade,
                )

                if comparativo.empty:
                    st.info(
                        "Nenhum dado de venda no período para comparar."
                    )
                    continue

                comparativo = enriquecer_comparativo_com_ritmo(
                    comparativo,
                    periodicidade,
                    hoje,
                )

                tabela_comparativo = comparativo.copy()

                tabela_comparativo["canal"] = tabela_comparativo[
                    "canal"
                ].apply(nome_canal)

                tabela_comparativo["referencia"] = tabela_comparativo[
                    "referencia"
                ].apply(lambda valor: valor.strftime("%d/%m/%Y"))

                for coluna in ("realizado", "meta"):
                    tabela_comparativo[coluna] = tabela_comparativo[
                        coluna
                    ].apply(moeda_br)

                tabela_comparativo["gap"] = tabela_comparativo[
                    "gap"
                ].apply(
                    lambda valor: (
                        moeda_br(valor) if pd.notna(valor) else "Sem meta"
                    )
                )

                tabela_comparativo["atingido"] = tabela_comparativo[
                    "atingido"
                ].apply(
                    lambda valor: (
                        f"{valor:.0%}" if pd.notna(valor) else "Sem meta"
                    )
                )

                tabela_comparativo["ritmo_necessario"] = tabela_comparativo[
                    "ritmo_necessario"
                ].apply(
                    lambda valor: (
                        f"{moeda_br(valor)}/dia"
                        if pd.notna(valor)
                        else "—"
                    )
                )

                with st.container(border=True):
                    st.dataframe(
                        tabela_comparativo.rename(
                            columns={
                                "canal": "Canal",
                                "referencia": "Início do período",
                                "realizado": "Realizado",
                                "meta": "Meta",
                                "gap": "Gap",
                                "atingido": "Atingido",
                                "ritmo_necessario": "Ritmo necessário",
                                "classificacao": "Situação",
                            }
                        )[
                            [
                                "Canal",
                                "Início do período",
                                "Realizado",
                                "Meta",
                                "Gap",
                                "Atingido",
                                "Ritmo necessário",
                                "Situação",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

        with st.expander("Cadastrar ou atualizar meta"):
            with st.form("form_meta"):
                canais_disponiveis = sorted(
                    df_validos["loja_id"].dropna().astype(str).unique()
                )

                canal_meta = st.selectbox(
                    "Canal",
                    options=canais_disponiveis or ["Sem canal"],
                    format_func=nome_canal,
                )

                periodicidade_meta = st.radio(
                    "Periodicidade",
                    options=["semanal", "mensal"],
                    horizontal=True,
                )

                referencia_meta = st.date_input(
                    "Uma data dentro do período "
                    "(semana: qualquer dia dela; mês: qualquer dia dele)",
                    value=date.today(),
                    key="referencia_meta",
                )

                valor_meta = st.number_input(
                    "Valor da meta (R$)",
                    min_value=0.0,
                    step=100.0,
                )

                enviar_meta = st.form_submit_button("Salvar meta")

                if enviar_meta:
                    referencia_normalizada = (
                        inicio_semana(referencia_meta)
                        if periodicidade_meta == "semanal"
                        else inicio_mes(referencia_meta)
                    )

                    salvar_meta(
                        canal_meta,
                        periodicidade_meta,
                        referencia_normalizada,
                        valor_meta,
                    )

                    st.success("Meta salva com sucesso.")
                    st.rerun()


exibir_dashboard()
