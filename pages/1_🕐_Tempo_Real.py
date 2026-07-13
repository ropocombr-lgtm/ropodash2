from __future__ import annotations

from datetime import date, datetime, timedelta

import plotly.express as px
import streamlit as st

from bling_core import (
    SITUACOES_CANCELADAS,
    carregar_dataframe,
    gerar_url_autorizacao,
    ler_historico_diario,
    ler_itens_pedidos,
    ler_metas,
    ler_tokens,
    moeda_br,
    montar_comparativo,
    sincronizar_itens_pedidos,
)
from ui import (
    ALTURA_GRAFICO_PRINCIPAL,
    CORES,
    aplicar_padrao_grafico,
    badges_dashboard,
    cabecalho_dashboard,
    cabecalho_secao,
    card_kpi,
    card_meta,
    injetar_css,
)

st.set_page_config(
    page_title="Tempo Real - Dashboard Bling",
    page_icon="🕐",
    layout="wide",
)

injetar_css()

cabecalho_dashboard(
    "🕐 Tempo Real",
    "Faturamento e vendas de hoje, atualizado automaticamente a cada 1 "
    "hora.",
)

if not ler_tokens():
    st.warning("O dashboard ainda não está conectado ao Bling.")

    st.link_button(
        "Conectar ao Bling",
        gerar_url_autorizacao(),
        type="primary",
    )

    st.stop()

DIAS_HISTORICO = 13


@st.fragment(run_every="1h")
def exibir_tempo_real() -> None:
    hoje = date.today()
    inicio_historico = hoje - timedelta(days=DIAS_HISTORICO)

    badges_dashboard(
        [
            f"🔄 Atualizado em "
            f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}",
            "🟢 Bling conectado",
        ]
    )

    with st.spinner("Consultando os dados do Bling..."):
        df = carregar_dataframe(
            inicio_historico.isoformat(),
            hoje.isoformat(),
        )

    if df.empty:
        st.info("Nenhum pedido encontrado nos últimos dias.")
        return

    cancelados = df["situacao_id"].isin(SITUACOES_CANCELADAS)
    df_validos = df.loc[~cancelados].copy()

    faturamento_diario = (
        df_validos.dropna(subset=["data"])
        .assign(dia=lambda dados: dados["data"].dt.date)
        .groupby("dia", as_index=False)
        .agg(
            faturamento=("total", "sum"),
            pedidos=("id", "nunique"),
        )
    )

    linha_hoje = faturamento_diario.loc[faturamento_diario["dia"] == hoje]

    faturamento_hoje = float(linha_hoje["faturamento"].sum())
    pedidos_hoje = int(linha_hoje["pedidos"].sum())

    # Sincroniza só os pedidos de hoje (poucos, então é rápido e não
    # disputa a cota de requisições do Bling com outras telas).
    pedidos_hoje_df = df.loc[df["data"].dt.date == hoje]
    sincronizar_itens_pedidos(pedidos_hoje_df, pausa_segundos=0.6)

    itens_hoje = ler_itens_pedidos(hoje, hoje)

    unidades_hoje = 0.0
    produto_lider_hoje = "—"

    if not itens_hoje.empty:
        itens_validos_hoje = itens_hoje.loc[
            ~itens_hoje["situacao_id"].isin(SITUACOES_CANCELADAS)
        ]

        if not itens_validos_hoje.empty:
            unidades_hoje = float(itens_validos_hoje["quantidade"].sum())

            ranking_hoje = (
                itens_validos_hoje.groupby("descricao", as_index=False)
                .agg(quantidade=("quantidade", "sum"))
                .sort_values("quantidade", ascending=False)
            )

            produto_lider_hoje = ranking_hoje.iloc[0]["descricao"]

    metas_df = ler_metas()
    historico_metas = ler_historico_diario()
    comparativo = montar_comparativo(metas_df, historico_metas, hoje)

    meta_hoje = None

    if not comparativo.empty:
        metas_ativas = comparativo.loc[comparativo["periodo_ativo_agora"]]

        if not metas_ativas.empty:
            meta_hoje = metas_ativas.sort_values(
                "meta_diaria"
            ).iloc[0]

    cabecalho_secao(
        "Agora",
        "Faturamento, unidades e ritmo do dia de hoje.",
        "⚡",
    )

    coluna_1, coluna_2, coluna_3 = st.columns(3)

    with coluna_1:
        card_kpi(
            "Faturamento de hoje",
            moeda_br(faturamento_hoje),
        )

    with coluna_2:
        card_kpi(
            "Pedidos hoje",
            f"{pedidos_hoje:,}".replace(",", "."),
        )

    with coluna_3:
        card_kpi(
            "Unidades vendidas hoje",
            f"{unidades_hoje:,.0f}".replace(",", "."),
            "Produto líder: " + produto_lider_hoje
            if produto_lider_hoje != "—"
            else "Ainda sem itens sincronizados",
        )

    if meta_hoje is not None:
        st.markdown("<br>", unsafe_allow_html=True)

        # Sem hora do pedido (o Bling só devolve a data), não dá pra
        # saber se é justo classificar risco no meio do dia — por isso
        # não aplicamos "Risco alto" etc. aqui, só o total corrido.
        card_meta(
            f"Meta do dia ({meta_hoje['rotulo'] or 'período ativo'})",
            faturamento_hoje,
            float(meta_hoje["meta_diaria"]),
            "—",
            subtitulo=(
                "meta diária média do período em andamento — compare "
                "só ao final do dia"
            ),
        )

    cabecalho_secao(
        "Histórico recente",
        f"Faturamento diário nos últimos {DIAS_HISTORICO + 1} dias.",
        "📊",
    )

    with st.container(border=True):
        grafico = px.bar(
            faturamento_diario,
            x="dia",
            y="faturamento",
            title=f"Faturamento diário (últimos {DIAS_HISTORICO + 1} dias)",
            color_discrete_sequence=[CORES["primaria"]],
            labels={"dia": "", "faturamento": ""},
        )

        aplicar_padrao_grafico(
            grafico,
            altura=ALTURA_GRAFICO_PRINCIPAL,
            moeda_eixo_y=True,
        )

        st.plotly_chart(
            grafico,
            use_container_width=True,
            config={"displayModeBar": False},
        )

    st.caption(
        "Esta tela se atualiza automaticamente a cada 1 hora enquanto "
        "ficar aberta."
    )


exibir_tempo_real()
