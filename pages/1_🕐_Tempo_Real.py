from __future__ import annotations

from datetime import date, datetime, timedelta

import plotly.express as px
import streamlit as st

from bling_core import (
    SITUACOES_CANCELADAS,
    carregar_dataframe,
    gerar_url_autorizacao,
    ler_tokens,
    moeda_br,
)

st.set_page_config(
    page_title="Tempo Real - Dashboard Bling",
    page_icon="🕐",
    layout="wide",
)

st.title("🕐 Tempo Real")
st.caption("Faturamento diário, atualizado automaticamente a cada 1 hora.")

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

    coluna_1, coluna_2 = st.columns(2)

    coluna_1.metric(
        "Faturamento de hoje",
        moeda_br(faturamento_hoje),
    )

    coluna_2.metric(
        "Pedidos hoje",
        f"{pedidos_hoje:,}".replace(",", "."),
    )

    st.divider()

    grafico = px.bar(
        faturamento_diario,
        x="dia",
        y="faturamento",
        title=f"Faturamento diário (últimos {DIAS_HISTORICO + 1} dias)",
        labels={
            "dia": "Data",
            "faturamento": "Faturamento",
        },
    )

    st.plotly_chart(
        grafico,
        use_container_width=True,
    )

    st.caption(
        "Última atualização: "
        f"{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} "
        "— esta tela se atualiza automaticamente a cada 1 hora "
        "enquanto ficar aberta."
    )


exibir_tempo_real()
