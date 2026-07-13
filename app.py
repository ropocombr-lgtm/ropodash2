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
    gerar_url_autorizacao,
    ler_tokens,
    moeda_br,
    nome_canal,
    processar_callback_oauth,
    salvar_historico_diario,
    supabase,
)

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Dashboard Bling",
    page_icon="📊",
    layout="wide",
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

st.title("📊 Dashboard Bling")
st.caption("Vendas, pedidos, ticket médio e evolução diária.")

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

    aba_comercial, aba_produto, aba_preditivo, aba_metas = st.tabs(
        ["📈 Comercial", "🛒 Produto", "🔮 Preditivo", "🎯 Metas"]
    )

    with aba_comercial:
        coluna_1, coluna_2, coluna_3, coluna_4 = st.columns(4)

        coluna_1.metric(
            "Faturamento",
            moeda_br(faturamento),
        )

        coluna_2.metric(
            "Pedidos",
            f"{quantidade_pedidos:,}".replace(",", "."),
        )

        coluna_3.metric(
            "Ticket médio",
            moeda_br(ticket_medio),
        )

        coluna_4.metric(
            "Cancelados",
            f"{quantidade_cancelados:,}".replace(",", "."),
        )

        st.caption(
            "Comparações com o período anterior e com o ano anterior"
        )

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

        coluna_5, coluna_6 = st.columns(2)

        coluna_5.metric(
            "Vs. período anterior",
            (
                f"{crescimento_periodo:+.1%}"
                if crescimento_periodo is not None
                else "Sem base de comparação"
            ),
        )

        coluna_6.metric(
            "Vs. mesmo período ano anterior",
            (
                f"{crescimento_ano:+.1%}"
                if crescimento_ano is not None
                else "Sem base de comparação"
            ),
        )

        st.divider()

        vendas_diarias = (
            df_validos.dropna(subset=["data"])
            .assign(dia=lambda dados: dados["data"].dt.date)
            .groupby("dia", as_index=False)
            .agg(
                faturamento=("total", "sum"),
                pedidos=("id", "nunique"),
            )
        )

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
            media_diaria = faturamento / vendas_diarias["dia"].nunique()

            coluna_7, coluna_8, coluna_9 = st.columns(3)

            coluna_7.metric(
                f"Melhor dia ({melhor_dia['dia'].strftime('%d/%m')})",
                moeda_br(melhor_dia["faturamento"]),
            )

            coluna_8.metric(
                f"Pior dia ({pior_dia['dia'].strftime('%d/%m')})",
                moeda_br(pior_dia["faturamento"]),
            )

            coluna_9.metric(
                "Média diária",
                moeda_br(media_diaria),
            )

        st.divider()

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

        coluna_10.metric(
            "Acumulado do mês",
            moeda_br(faturamento_mes_atual),
        )

        coluna_11.metric(
            "Projeção de fechamento do mês",
            moeda_br(projecao_mes),
        )

        st.caption(
            "Projeção simples (acumulado ÷ dias transcorridos × dias do "
            "mês). Não considera sazonalidade nem campanhas."
        )

        st.divider()

        coluna_status, coluna_clientes = st.columns(2)

        with coluna_status:
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

        with coluna_clientes:
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

        coluna_canal, coluna_cancelamento_canal = st.columns(2)

        with coluna_canal:
            receita_por_canal = (
                df_validos.assign(
                    canal=lambda d: d["loja_id"].apply(nome_canal)
                )
                .groupby("canal", as_index=False)
                .agg(faturamento=("total", "sum"))
                .sort_values("faturamento", ascending=False)
            )

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

        st.subheader("Pedidos do período")

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
        st.info(
            "Em construção. O Bling só devolve SKU, quantidade e valor "
            "dos itens no endpoint de detalhe do pedido (1 chamada de "
            "API por pedido, não por página). Antes de implementar o "
            "ranking de produtos, curva ABC e cesta de compra, vamos "
            "combinar um período padrão (ex.: últimos 90 dias) para não "
            "estourar o limite diário de requisições do Bling."
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

                st.dataframe(
                    tabela_comparativo.rename(
                        columns={
                            "canal": "Canal",
                            "referencia": "Início do período",
                            "realizado": "Realizado",
                            "meta": "Meta",
                            "gap": "Gap",
                            "atingido": "Atingido",
                        }
                    ),
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
