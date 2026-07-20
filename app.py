from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from bling_core import (
    GRUPOS_CANAL,
    SITUACOES_CANCELADAS,
    calcular_historico_diario,
    carregar_dataframe,
    carregar_historico_completo,
    excluir_meta,
    gerar_url_autorizacao,
    hoje_sao_paulo,
    ler_historico_diario,
    ler_itens_pedidos,
    ler_metas,
    ler_tokens,
    moeda_br,
    montar_comparativo,
    nome_canal,
    processar_callback_oauth,
    salvar_historico_diario,
    salvar_meta,
    sincronizar_itens_pedidos,
)
from ui import (
    ALTURA_GRAFICO_PRINCIPAL,
    CORES,
    aplicar_padrao_grafico,
    badges_dashboard,
    cabecalho_dashboard,
    cabecalho_secao,
    card_insight,
    card_kpi,
    card_meta,
    injetar_css,
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

injetar_css()


processar_callback_oauth()


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

cabecalho_dashboard(
    "📊 Dashboard Comercial ROPO",
    "Acompanhamento de vendas, canais, produtos, metas e projeções.",
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

    hoje = hoje_sao_paulo()

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
    # Renderizado dentro do fragment (e não no corpo do módulo) para que o
    # horário mostrado acompanhe o auto-refresh a cada 5 minutos, em vez de
    # ficar parado no horário do último carregamento completo da página.
    badges_dashboard(
        [
            f"📅 {data_inicial.strftime('%d/%m/%Y')} a "
            f"{data_final.strftime('%d/%m/%Y')}",
            "🔄 Atualizado em "
            f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}",
            "🟢 Bling conectado",
        ]
    )

    if atualizar:
        carregar_dataframe.clear()

    with st.spinner("Consultando os dados do Bling..."):
        try:
            df = carregar_dataframe(
                data_inicial.isoformat(),
                data_final.isoformat(),
            )
        except RuntimeError:
            st.error(
                "A conexão com o Bling expirou e não foi possível renová-la "
                "automaticamente."
            )
            st.link_button(
                "Reconectar ao Bling",
                gerar_url_autorizacao(),
                type="primary",
            )
            st.stop()

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

    metas_df = ler_metas()
    historico_metas = ler_historico_diario()
    comparativo = montar_comparativo(metas_df, historico_metas, hoje)

    aba_comercial, aba_produto, aba_preditivo, aba_metas = st.tabs(
        ["📈 Comercial", "🛒 Produto", "🔮 Preditivo", "🎯 Metas"]
    )

    with aba_comercial:
        if not comparativo.empty:
            metas_ativas = comparativo.loc[
                comparativo["periodo_ativo_agora"]
            ]

            if not metas_ativas.empty:
                cabecalho_secao(
                    "Pacing das metas ativas",
                    "O que está em andamento agora, antes de qualquer "
                    "outro número.",
                    "🎯",
                )

                colunas_pacing = st.columns(len(metas_ativas))

                for coluna_pacing, (_, linha_meta) in zip(
                    colunas_pacing, metas_ativas.iterrows()
                ):
                    with coluna_pacing:
                        card_meta(
                            linha_meta["rotulo"]
                            or nome_canal(linha_meta["canal"]),
                            linha_meta["realizado"],
                            linha_meta["meta"],
                            linha_meta["classificacao"],
                            subtitulo=(
                                f"até "
                                f"{linha_meta['referencia_fim'].strftime('%d/%m')}"
                            ),
                        )

                st.markdown("<br>", unsafe_allow_html=True)

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

        cabecalho_secao(
            "Resumo executivo",
            "Faturamento, pedidos, ticket médio e cancelamento do "
            "período selecionado.",
            "📊",
        )

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

        cabecalho_secao(
            "Evolução de vendas",
            "Comportamento diário do faturamento no período selecionado.",
            "📈",
        )

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
                color_discrete_sequence=[CORES["primaria"]],
                labels={"dia": "", "faturamento": ""},
            )

            grafico_faturamento.update_traces(
                line={"width": 3},
                marker={"size": 7, "line": {"width": 2, "color": "white"}},
                hovertemplate=(
                    "<b>%{x|%d/%m/%Y}</b><br>"
                    "Faturamento: R$ %{y:,.2f}<extra></extra>"
                ),
            )

            aplicar_padrao_grafico(
                grafico_faturamento,
                altura=ALTURA_GRAFICO_PRINCIPAL,
                moeda_eixo_y=True,
            )

            st.plotly_chart(
                grafico_faturamento,
                use_container_width=True,
                config={"displayModeBar": False},
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

        cabecalho_secao(
            "Comparativos",
            "Acumulado do mês e projeção simples de fechamento.",
            "🧮",
        )

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

        cabecalho_secao(
            "Operação",
            "Pedidos por situação e principais clientes do período.",
            "⚙️",
        )

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
                color_discrete_sequence=[CORES["primaria"]],
                labels={"situacao": "", "pedidos": ""},
            )

            aplicar_padrao_grafico(grafico_status)

            st.plotly_chart(
                grafico_status,
                use_container_width=True,
                config={"displayModeBar": False},
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
                color_discrete_sequence=[CORES["secundaria"]],
                labels={"cliente": "", "faturamento": ""},
            )

            aplicar_padrao_grafico(grafico_clientes, moeda_eixo_x=True)

            st.plotly_chart(
                grafico_clientes,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        cabecalho_secao(
            "Canais",
            "Receita, ticket médio, participação e cancelamento por canal.",
            "🛰️",
        )

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
                    color_discrete_sequence=[CORES["primaria"]],
                    labels={"canal": "", "faturamento": ""},
                )

                aplicar_padrao_grafico(grafico_canal, moeda_eixo_y=True)

                st.plotly_chart(
                    grafico_canal,
                    use_container_width=True,
                    config={"displayModeBar": False},
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
                    color_discrete_sequence=[CORES["erro"]],
                    labels={"canal": "", "taxa_cancelamento": ""},
                )

                aplicar_padrao_grafico(
                    grafico_cancelamento,
                    percentual_eixo_y=True,
                )

                st.plotly_chart(
                    grafico_cancelamento,
                    use_container_width=True,
                    config={"displayModeBar": False},
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

        cabecalho_secao(
            "Dia da semana",
            "Faturamento e cancelamento por dia da semana.",
            "📅",
        )

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
                color_discrete_sequence=[CORES["primaria"]],
                labels={"dia_semana": "", "faturamento": ""},
            )

            aplicar_padrao_grafico(grafico_dia_semana, moeda_eixo_y=True)

            st.plotly_chart(
                grafico_dia_semana,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        cabecalho_secao(
            "Clientes",
            "Novos vs. recorrentes e taxa de recompra.",
            "👥",
        )

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

        cabecalho_secao(
            "Pedidos do período",
            "Lista detalhada de todos os pedidos no filtro selecionado.",
            "🧾",
        )

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
            # itens_periodo["situacao_id"] é uma foto tirada no momento da
            # sincronização e nunca é atualizada depois (sincronizar_itens_
            # pedidos não reprocessa pedido já sincronizado). Se um pedido
            # for cancelado (ou reativado) no Bling depois desse momento,
            # aqui usamos a situação atual vinda de "df" em vez da foto
            # antiga, para não divergir dos números por pedido.
            situacao_atual_por_pedido = df.set_index("id")["situacao_id"]

            situacao_atual_itens = (
                itens_periodo["pedido_id"]
                .map(situacao_atual_por_pedido)
                .fillna(itens_periodo["situacao_id"])
            )

            itens_validos = itens_periodo.loc[
                ~situacao_atual_itens.isin(SITUACOES_CANCELADAS)
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

            cabecalho_secao(
                "Resumo de produtos",
                f"Baseado em {pedidos_sincronizados_periodo} pedido(s) "
                "já sincronizado(s) neste período (pode não ser 100% "
                "dos pedidos — veja a sincronização acima).",
                "🛒",
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

            cabecalho_secao(
                "Ranking de produtos",
                "Top produtos por faturamento no período.",
                "🏆",
            )

            with st.container(border=True):
                top_produtos = ranking.head(10)

                grafico_ranking = px.bar(
                    top_produtos,
                    x="faturamento",
                    y="descricao",
                    orientation="h",
                    title="Top 10 produtos por faturamento",
                    color_discrete_sequence=[CORES["primaria"]],
                    labels={"descricao": "", "faturamento": ""},
                )

                grafico_ranking.update_yaxes(
                    categoryorder="total ascending"
                )

                aplicar_padrao_grafico(
                    grafico_ranking,
                    altura=ALTURA_GRAFICO_PRINCIPAL,
                    moeda_eixo_x=True,
                )

                st.plotly_chart(
                    grafico_ranking,
                    use_container_width=True,
                    config={"displayModeBar": False},
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

            cabecalho_secao(
                "Curva ABC",
                "Classificação dos produtos por participação acumulada "
                "na receita.",
                "🔤",
            )

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
                        color_discrete_map={
                            "A": CORES["primaria"],
                            "B": CORES["secundaria"],
                            "C": CORES["cinza_grafico"],
                        },
                        labels={"descricao": "", "acumulado": ""},
                    )

                    aplicar_padrao_grafico(
                        grafico_abc,
                        percentual_eixo_y=True,
                    )

                    grafico_abc.update_xaxes(showticklabels=False)

                    st.plotly_chart(
                        grafico_abc,
                        use_container_width=True,
                        config={"displayModeBar": False},
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

            cabecalho_secao(
                "Produtos comprados juntos",
                "Pares de produtos que aparecem no mesmo pedido.",
                "🧩",
            )

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
        historico = ler_historico_diario()

        if historico.empty:
            st.info(
                "Ainda não há histórico diário suficiente. Ele vai se "
                "acumulando automaticamente a cada acesso ao dashboard."
            )
        elif historico["data"].nunique() < 14:
            st.info(
                "Ainda há menos de 14 dias de histórico diário "
                "acumulado — volte em alguns dias para ver projeções "
                "mais confiáveis."
            )
        else:
            diario_total = (
                historico.groupby("data", as_index=False)
                .agg(
                    faturamento=("faturamento_valido", "sum"),
                    pedidos=("pedidos", "sum"),
                )
                .sort_values("data")
            )

            diario_total["mm7"] = (
                diario_total["faturamento"]
                .rolling(7, min_periods=1)
                .mean()
            )

            diario_total["mm14"] = (
                diario_total["faturamento"]
                .rolling(14, min_periods=1)
                .mean()
            )

            media_ultimos_7 = float(
                diario_total["faturamento"].tail(7).mean()
            )

            media_7_anteriores = (
                float(diario_total["faturamento"].iloc[-14:-7].mean())
                if len(diario_total) >= 14
                else None
            )

            aceleracao = variacao_percentual(
                media_ultimos_7,
                media_7_anteriores,
            ) if media_7_anteriores else None

            hoje_pred = diario_total["data"].max()
            inicio_mes_pred = hoje_pred.replace(day=1)
            dias_no_mes_pred = calendar.monthrange(
                hoje_pred.year, hoje_pred.month
            )[1]
            dias_restantes_mes_pred = max(
                dias_no_mes_pred - hoje_pred.day, 0
            )

            acumulado_mes_pred = float(
                diario_total.loc[
                    diario_total["data"] >= inicio_mes_pred, "faturamento"
                ].sum()
            )

            projecao_semanal_base = media_ultimos_7 * 7
            projecao_mensal_base = (
                acumulado_mes_pred
                + media_ultimos_7 * dias_restantes_mes_pred
            )
            projecao_mensal_otimista = (
                acumulado_mes_pred
                + (media_ultimos_7 * 1.1) * dias_restantes_mes_pred
            )
            projecao_mensal_pessimista = (
                acumulado_mes_pred
                + (media_ultimos_7 * 0.9) * dias_restantes_mes_pred
            )
            projecao_anual_base = media_ultimos_7 * 365

            cabecalho_secao(
                "Cenários",
                "Base = média dos últimos 7 dias. Otimista/pessimista "
                "= base ±10%. Não considera sazonalidade ou campanhas.",
                "🔮",
            )

            coluna_pr1, coluna_pr2, coluna_pr3, coluna_pr4 = st.columns(4)

            with coluna_pr1:
                card_kpi(
                    "Projeção semanal",
                    moeda_br(projecao_semanal_base),
                    "Próximos 7 dias, ritmo atual",
                )

            with coluna_pr2:
                card_kpi(
                    "Projeção mensal",
                    moeda_br(projecao_mensal_base),
                    "Fechamento do mês, cenário base",
                )

            with coluna_pr3:
                card_kpi(
                    "Cenário otimista (mês)",
                    moeda_br(projecao_mensal_otimista),
                    "Ritmo +10%",
                    delta_tipo="good",
                )

            with coluna_pr4:
                card_kpi(
                    "Cenário pessimista (mês)",
                    moeda_br(projecao_mensal_pessimista),
                    "Ritmo -10%",
                    delta_tipo="bad",
                )

            st.markdown("<br>", unsafe_allow_html=True)

            coluna_pr5, coluna_pr6 = st.columns(2)

            with coluna_pr5:
                card_kpi(
                    "Média diária (últimos 7 dias)",
                    moeda_br(media_ultimos_7),
                    delta=(
                        f"{aceleracao:+.1%} vs. 7 dias anteriores"
                        if aceleracao is not None
                        else None
                    ),
                    delta_tipo=(
                        "good"
                        if (aceleracao or 0) >= 0
                        else "bad"
                    ),
                )

            with coluna_pr6:
                card_kpi(
                    "Projeção anualizada",
                    moeda_br(projecao_anual_base),
                    "Média diária recente × 365",
                )

            cabecalho_secao(
                "Tendência",
                "Faturamento diário e médias móveis de 7 e 14 dias.",
                "📉",
            )

            with st.container(border=True):
                dados_grafico = diario_total.tail(90).melt(
                    id_vars=["data"],
                    value_vars=["faturamento", "mm7", "mm14"],
                    var_name="serie",
                    value_name="valor",
                )

                nomes_serie = {
                    "faturamento": "Faturamento diário",
                    "mm7": "Média móvel 7 dias",
                    "mm14": "Média móvel 14 dias",
                }

                dados_grafico["serie"] = dados_grafico["serie"].map(
                    nomes_serie
                )

                grafico_tendencia = px.line(
                    dados_grafico,
                    x="data",
                    y="valor",
                    color="serie",
                    title="Faturamento diário e médias móveis (últimos 90 dias)",
                    color_discrete_map={
                        "Faturamento diário": CORES["cinza_grafico"],
                        "Média móvel 7 dias": CORES["primaria"],
                        "Média móvel 14 dias": CORES["secundaria"],
                    },
                    labels={"data": "", "valor": "", "serie": ""},
                )

                aplicar_padrao_grafico(
                    grafico_tendencia,
                    altura=ALTURA_GRAFICO_PRINCIPAL,
                    moeda_eixo_y=True,
                )

                st.plotly_chart(
                    grafico_tendencia,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

            cabecalho_secao(
                "Tendência por canal",
                "Mesma série, separada por canal.",
                "🛰️",
            )

            with st.container(border=True):
                historico_recente = historico.loc[
                    historico["data"]
                    >= (hoje_pred - timedelta(days=60))
                ].copy()

                historico_recente["canal_nome"] = historico_recente[
                    "canal"
                ].apply(nome_canal)

                grafico_canal_tendencia = px.line(
                    historico_recente.sort_values("data"),
                    x="data",
                    y="faturamento_valido",
                    color="canal_nome",
                    title="Faturamento diário por canal (últimos 60 dias)",
                    labels={
                        "data": "",
                        "faturamento_valido": "",
                        "canal_nome": "",
                    },
                )

                aplicar_padrao_grafico(
                    grafico_canal_tendencia,
                    moeda_eixo_y=True,
                )

                st.plotly_chart(
                    grafico_canal_tendencia,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

            cabecalho_secao(
                "Insights",
                "Leitura automática da tendência recente.",
                "💡",
            )

            tendencia_texto = (
                "em alta" if (aceleracao or 0) > 0.02
                else "em queda" if (aceleracao or 0) < -0.02
                else "estável"
            )

            tipo_tendencia = (
                "good" if (aceleracao or 0) > 0.02
                else "bad" if (aceleracao or 0) < -0.02
                else "primary"
            )

            texto_ritmo = (
                f"Média de {moeda_br(media_ultimos_7)}/dia nos últimos "
                "7 dias"
                + (
                    f", {aceleracao:+.1%} em relação aos 7 dias anteriores."
                    if aceleracao is not None
                    else "."
                )
            )

            texto_projecao = (
                "Se esse ritmo continuar, a projeção é de "
                f"{moeda_br(projecao_semanal_base)} na próxima semana e "
                f"{moeda_br(projecao_mensal_base)} no fechamento deste "
                f"mês (entre {moeda_br(projecao_mensal_pessimista)} no "
                f"cenário pessimista e {moeda_br(projecao_mensal_otimista)} "
                "no otimista)."
            )

            # card_insight renderiza dentro de uma <div> HTML pura, então
            # o "$" não é interpretado como LaTeX (isso só acontece em
            # texto markdown puro, como em st.markdown sem HTML).
            card_insight(
                f"Ritmo {tendencia_texto}",
                texto_ritmo,
                tipo_tendencia,
            )

            card_insight(
                "Projeção se o ritmo continuar",
                texto_projecao,
                "primary",
            )

    with aba_metas:
        if comparativo.empty:
            st.info(
                "Nenhuma meta cadastrada ainda. Use \"Cadastrar meta\" "
                "abaixo."
            )
        else:
            cabecalho_secao(
                "Progresso por meta",
                "Realizado vs. meta de cada período cadastrado.",
                "🎯",
            )

            linhas_card = list(comparativo.iterrows())

            for inicio in range(0, len(linhas_card), 3):
                colunas_meta = st.columns(3)

                for coluna_meta, (_, linha) in zip(
                    colunas_meta, linhas_card[inicio : inicio + 3]
                ):
                    with coluna_meta:
                        rotulo_exibido = (
                            linha["rotulo"] or nome_canal(linha["canal"])
                        )

                        card_meta(
                            rotulo_exibido,
                            linha["realizado"],
                            linha["meta"],
                            linha["classificacao"],
                            subtitulo=(
                                f"{linha['referencia_inicio'].strftime('%d/%m')} "
                                f"a {linha['referencia_fim'].strftime('%d/%m')}"
                            ),
                        )

            st.markdown("<br>", unsafe_allow_html=True)
            cabecalho_secao(
                "Detalhamento",
                "Todos os campos calculados, por meta cadastrada.",
                "📋",
            )

            tabela_comparativo = comparativo.copy()

            tabela_comparativo["canal"] = tabela_comparativo[
                "canal"
            ].apply(nome_canal)

            tabela_comparativo["periodo"] = (
                tabela_comparativo["referencia_inicio"].apply(
                    lambda valor: valor.strftime("%d/%m")
                )
                + " a "
                + tabela_comparativo["referencia_fim"].apply(
                    lambda valor: valor.strftime("%d/%m/%Y")
                )
            )

            for coluna in ("realizado", "meta", "meta_diaria"):
                tabela_comparativo[coluna] = tabela_comparativo[
                    coluna
                ].apply(moeda_br)

            tabela_comparativo["gap"] = tabela_comparativo["gap"].apply(
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
                    f"{moeda_br(valor)}/dia" if pd.notna(valor) else "—"
                )
            )

            with st.container(border=True):
                st.dataframe(
                    tabela_comparativo.rename(
                        columns={
                            "canal": "Canal",
                            "rotulo": "Rótulo",
                            "periodo": "Período",
                            "realizado": "Realizado",
                            "meta": "Meta",
                            "meta_diaria": "Meta diária",
                            "gap": "Gap",
                            "atingido": "Atingido",
                            "ritmo_necessario": "Ritmo necessário",
                            "classificacao": "Situação",
                        }
                    )[
                        [
                            "Canal",
                            "Rótulo",
                            "Período",
                            "Realizado",
                            "Meta",
                            "Meta diária",
                            "Gap",
                            "Atingido",
                            "Ritmo necessário",
                            "Situação",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        coluna_form, coluna_excluir = st.columns(2)

        with coluna_form, st.expander("Cadastrar meta", expanded=True):
            with st.form("form_meta"):
                canais_disponiveis = sorted(
                    df_validos["loja_id"].dropna().astype(str).unique()
                ) + list(GRUPOS_CANAL.keys())

                canal_meta = st.selectbox(
                    "Canal",
                    options=canais_disponiveis or ["Sem canal"],
                    format_func=nome_canal,
                )

                rotulo_meta = st.text_input(
                    "Rótulo (opcional, ex.: \"Semana 1\")",
                )

                coluna_data_1, coluna_data_2 = st.columns(2)

                referencia_inicio_meta = coluna_data_1.date_input(
                    "Início do período",
                    value=hoje,
                    key="referencia_inicio_meta",
                )

                referencia_fim_meta = coluna_data_2.date_input(
                    "Fim do período",
                    value=hoje,
                    key="referencia_fim_meta",
                )

                valor_meta = st.number_input(
                    "Valor da meta (R$)",
                    min_value=0.0,
                    step=100.0,
                )

                enviar_meta = st.form_submit_button("Salvar meta")

                if enviar_meta:
                    if referencia_fim_meta < referencia_inicio_meta:
                        st.error(
                            "O fim do período não pode ser antes do "
                            "início."
                        )
                    else:
                        salvar_meta(
                            canal_meta,
                            referencia_inicio_meta,
                            referencia_fim_meta,
                            valor_meta,
                            rotulo_meta,
                        )

                        st.success("Meta salva com sucesso.")
                        st.rerun()

        with coluna_excluir, st.expander("Excluir meta", expanded=True):
            if metas_df.empty:
                st.caption("Nenhuma meta cadastrada.")
            else:
                opcoes_exclusao = {
                    (
                        f"{nome_canal(linha['canal'])} — "
                        f"{linha['referencia_inicio'].strftime('%d/%m')} "
                        f"a {linha['referencia_fim'].strftime('%d/%m/%Y')}"
                        + (f" ({linha['rotulo']})" if linha["rotulo"] else "")
                    ): linha["id"]
                    for _, linha in metas_df.iterrows()
                }

                escolha_exclusao = st.selectbox(
                    "Meta a excluir",
                    options=list(opcoes_exclusao.keys()),
                )

                if st.button("Excluir meta selecionada"):
                    excluir_meta(opcoes_exclusao[escolha_exclusao])
                    st.success("Meta excluída.")
                    st.rerun()


exibir_dashboard()
