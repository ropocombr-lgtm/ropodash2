from __future__ import annotations

from datetime import date, datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from bling_core import (
    SITUACOES_CANCELADAS,
    calcular_historico_diario,
    carregar_dataframe,
    gerar_url_autorizacao,
    ler_historico_diario,
    ler_itens_pedidos,
    ler_metas,
    ler_tokens,
    moeda_br,
    montar_comparativo,
    nome_canal,
    salvar_historico_diario,
    sincronizar_itens_pedidos,
)

FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")
SEGUNDOS_POR_CARD = 7

st.set_page_config(
    page_title="Televisão - Dashboard Bling",
    page_icon="📺",
    layout="wide",
)


def injetar_css_tv() -> None:
    st.markdown(
        """
        <style>
        :root {
            --tv-bg: #07111f;
            --tv-panel: #0f1f34;
            --tv-panel-soft: #142942;
            --tv-border: rgba(226, 232, 240, 0.18);
            --tv-text: #f8fafc;
            --tv-muted: #a7b7cc;
            --tv-good: #22c55e;
            --tv-warn: #f59e0b;
            --tv-bad: #ef4444;
            --tv-blue: #38bdf8;
            --tv-purple: #a78bfa;
        }

        .stApp {
            background:
                radial-gradient(circle at 18% 10%, rgba(56, 189, 248, 0.16), transparent 28%),
                linear-gradient(135deg, #07111f 0%, #0b1627 48%, #111827 100%);
            color: var(--tv-text);
        }

        [data-testid="stSidebar"], [data-testid="stHeader"],
        [data-testid="stToolbar"], footer {
            display: none;
        }

        .block-container {
            max-width: none;
            padding: 1.25rem 1.6rem;
        }

        .tv-shell {
            min-height: calc(100vh - 2.5rem);
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .tv-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 22px;
        }

        .tv-title {
            color: var(--tv-text);
            font-size: clamp(1.55rem, 2.7vw, 3.6rem);
            line-height: 0.95;
            font-weight: 850;
            letter-spacing: 0;
            margin: 0;
        }

        .tv-subtitle {
            color: var(--tv-muted);
            font-size: clamp(0.88rem, 1.05vw, 1.15rem);
            margin-top: 6px;
        }

        .tv-clock {
            color: var(--tv-text);
            background: rgba(15, 31, 52, 0.78);
            border: 1px solid var(--tv-border);
            border-radius: 8px;
            padding: 10px 14px;
            min-width: 215px;
            text-align: right;
            box-shadow: 0 18px 50px rgba(0, 0, 0, 0.2);
        }

        .tv-clock-time {
            font-size: clamp(1.35rem, 2vw, 2.5rem);
            font-weight: 820;
            line-height: 1;
        }

        .tv-clock-date {
            color: var(--tv-muted);
            font-size: 0.95rem;
            margin-top: 6px;
        }

        .tv-stage {
            position: relative;
            flex: 1 1 auto;
            min-height: min(74vh, 760px);
            overflow: hidden;
        }

        .tv-card {
            background: linear-gradient(180deg, rgba(20, 41, 66, 0.96), rgba(15, 31, 52, 0.96));
            border: 1px solid var(--tv-border);
            border-radius: 8px;
            padding: clamp(28px, 4vw, 72px);
            min-height: 100%;
            box-shadow: 0 22px 54px rgba(0, 0, 0, 0.24);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .tv-card-label {
            color: var(--tv-muted);
            font-size: clamp(1.1rem, 1.65vw, 2rem);
            font-weight: 760;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        .tv-card-value {
            color: var(--tv-text);
            font-size: clamp(3.9rem, 9.4vw, 12.8rem);
            font-weight: 870;
            line-height: 1.02;
            margin: 26px 0 18px;
            overflow-wrap: anywhere;
        }

        .tv-card-detail {
            color: var(--tv-muted);
            font-size: clamp(1.2rem, 2vw, 2.65rem);
            line-height: 1.35;
        }

        .tv-chip {
            display: inline-flex;
            align-items: center;
            width: fit-content;
            margin-top: 28px;
            border-radius: 8px;
            padding: 10px 15px;
            font-weight: 800;
            font-size: clamp(1rem, 1.45vw, 1.75rem);
            color: #07111f;
            background: var(--tv-blue);
        }

        .tv-chip.good { background: var(--tv-good); }
        .tv-chip.warning { background: var(--tv-warn); }
        .tv-chip.bad { background: var(--tv-bad); color: white; }
        .tv-chip.neutral { background: #cbd5e1; }

        .tv-progress {
            height: 20px;
            width: 100%;
            background: rgba(226, 232, 240, 0.16);
            border-radius: 999px;
            overflow: hidden;
            margin-top: 34px;
        }

        .tv-progress-bar {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--tv-blue), var(--tv-good));
        }

        .tv-slide {
            position: absolute;
            inset: 0;
            opacity: 0;
            transform: translateX(6%);
            animation: tv-slide-cycle var(--tv-cycle) infinite ease-in-out;
            animation-delay: var(--tv-delay);
        }

        .tv-slide:first-child:last-child {
            opacity: 1;
            transform: none;
            animation: none;
        }

        @keyframes tv-slide-cycle {
            0% { opacity: 0; transform: translateX(6%) scale(0.985); }
            4% { opacity: 1; transform: translateX(0) scale(1); }
            16% { opacity: 1; transform: translateX(0) scale(1); }
            20% { opacity: 0; transform: translateX(-6%) scale(0.985); }
            100% { opacity: 0; transform: translateX(-6%) scale(0.985); }
        }

        @media (max-width: 1100px) {
            .tv-topbar { flex-direction: column; }
            .tv-clock { text-align: left; width: 100%; }
            .tv-stage { min-height: 68vh; }
        }

        @media (max-width: 640px) {
            .block-container { padding: 1rem; }
            .tv-card { padding: 24px; }
            .tv-card-value { font-size: clamp(3rem, 18vw, 6rem); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def pct_texto(valor: float | None, casas: int = 0) -> str:
    if valor is None or pd.isna(valor):
        return "—"

    return f"{valor:.{casas}%}"


def status_por_razao(razao: float | None) -> tuple[str, str]:
    if razao is None or pd.isna(razao):
        return "Sem base", "neutral"
    if razao >= 1:
        return "Acima", "good"
    if razao >= 0.9:
        return "No ritmo", "good"
    if razao >= 0.7:
        return "Atenção", "warning"
    return "Abaixo", "bad"


def card_tv(
    titulo: str,
    valor: str,
    detalhe: str = "",
    chip: str = "",
    chip_tipo: str = "neutral",
    progresso: float | None = None,
) -> str:
    progresso_html = ""

    if progresso is not None:
        largura = min(max(progresso, 0), 1) * 100
        progresso_html = (
            '<div class="tv-progress">'
            f'<div class="tv-progress-bar" style="width: {largura:.0f}%;"></div>'
            "</div>"
        )

    chip_html = (
        f'<div class="tv-chip {escape(chip_tipo)}">{escape(chip)}</div>'
        if chip
        else ""
    )

    return (
        '<div class="tv-card">'
        f'<div class="tv-card-label">{escape(titulo)}</div>'
        f'<div class="tv-card-value">{escape(valor)}</div>'
        f'<div class="tv-card-detail">{escape(detalhe)}</div>'
        f"{progresso_html}"
        f"{chip_html}"
        "</div>"
    )


def resumo_dia(df_validos: pd.DataFrame, hoje: date) -> tuple[float, int]:
    if df_validos.empty:
        return 0.0, 0

    pedidos_hoje = df_validos.loc[
        df_validos["data"].dt.date == hoje
    ].copy()

    return (
        float(pedidos_hoje["total"].sum()),
        int(pedidos_hoje["id"].nunique()),
    )


def realizado_periodo(
    historico: pd.DataFrame,
    inicio: date,
    fim: date,
    canal: str | None = None,
) -> float:
    if historico.empty:
        return 0.0

    filtro = (historico["data"] >= inicio) & (historico["data"] <= fim)

    if canal is not None:
        from bling_core import canais_do_grupo

        filtro = filtro & historico["canal"].isin(canais_do_grupo(canal))

    return float(historico.loc[filtro, "faturamento_valido"].sum())


def calcular_cards_metas(
    comparativo: pd.DataFrame,
    historico: pd.DataFrame,
    hoje: date,
) -> tuple[list[str], float, float, float, float]:
    if comparativo.empty:
        return [], 0.0, 0.0, 0.0, 0.0

    metas_ativas = comparativo.loc[
        comparativo["periodo_ativo_agora"]
    ].copy()

    if metas_ativas.empty:
        return [], 0.0, 0.0, 0.0, 0.0

    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    cards = []
    meta_diaria_total = 0.0
    meta_semanal_total = 0.0
    realizado_semana_total = 0.0

    for _, meta in metas_ativas.iterrows():
        meta_diaria = float(meta["meta_diaria"])
        inicio_meta = meta["referencia_inicio"]
        fim_meta = meta["referencia_fim"]
        inicio_semana_meta = max(inicio_semana, inicio_meta)
        fim_semana_meta = min(fim_semana, fim_meta)
        dias_semana_meta = (
            (fim_semana_meta - inicio_semana_meta).days + 1
            if fim_semana_meta >= inicio_semana_meta
            else 0
        )
        meta_semanal = meta_diaria * dias_semana_meta
        realizado_dia = realizado_periodo(
            historico,
            hoje,
            hoje,
            meta["canal"],
        )
        realizado_semana = realizado_periodo(
            historico,
            inicio_semana_meta,
            hoje,
            meta["canal"],
        )
        atingimento_semana = (
            realizado_semana / meta_semanal if meta_semanal else None
        )
        status, status_tipo = status_por_razao(atingimento_semana)
        titulo = meta["rotulo"] or nome_canal(meta["canal"])

        meta_diaria_total += meta_diaria
        meta_semanal_total += meta_semanal
        realizado_semana_total += realizado_semana

        cards.append(
            card_tv(
                f"{titulo} · meta diária",
                moeda_br(meta_diaria),
                f"Realizado hoje: {moeda_br(realizado_dia)}",
                chip=f"{pct_texto(realizado_dia / meta_diaria if meta_diaria else None)} do dia",
                chip_tipo=status_por_razao(
                    realizado_dia / meta_diaria if meta_diaria else None
                )[1],
                progresso=realizado_dia / meta_diaria if meta_diaria else None,
            )
        )

        cards.append(
            card_tv(
                f"{titulo} · meta semanal",
                moeda_br(meta_semanal),
                (
                    f"Semana {inicio_semana_meta.strftime('%d/%m')} a "
                    f"{fim_semana_meta.strftime('%d/%m')} · realizado "
                    f"{moeda_br(realizado_semana)}"
                ),
                chip=f"{status} · {pct_texto(atingimento_semana)}",
                chip_tipo=status_tipo,
                progresso=atingimento_semana,
            )
        )

        cards.append(
            card_tv(
                f"{titulo} · período",
                moeda_br(float(meta["realizado"])),
                (
                    f"Meta {moeda_br(float(meta['meta']))} · "
                    f"{meta['referencia_inicio'].strftime('%d/%m')} a "
                    f"{meta['referencia_fim'].strftime('%d/%m')}"
                ),
                chip=str(meta["classificacao"]),
                chip_tipo=status_por_razao(meta["atingido"])[1],
                progresso=meta["atingido"],
            )
        )

    return (
        cards,
        meta_diaria_total,
        meta_semanal_total,
        realizado_semana_total,
        float(metas_ativas["realizado"].sum()),
    )


def renderizar_tv() -> None:
    injetar_css_tv()

    agora = datetime.now(FUSO_SAO_PAULO)
    hoje = agora.date()
    inicio_busca = hoje - timedelta(days=13)

    if not ler_tokens():
        st.warning("O dashboard ainda não está conectado ao Bling.")
        st.link_button(
            "Conectar ao Bling",
            gerar_url_autorizacao(),
            type="primary",
        )
        st.stop()

    with st.spinner("Atualizando dados da televisão..."):
        df = carregar_dataframe(inicio_busca.isoformat(), hoje.isoformat())

    if df.empty:
        st.info("Nenhum pedido encontrado para exibir na televisão.")
        return

    salvar_historico_diario(calcular_historico_diario(df))

    cancelados = df["situacao_id"].isin(SITUACOES_CANCELADAS)
    df_validos = df.loc[~cancelados].copy()
    faturamento_hoje, pedidos_hoje = resumo_dia(df_validos, hoje)

    pedidos_hoje_df = df.loc[df["data"].dt.date == hoje]
    sincronizar_itens_pedidos(pedidos_hoje_df, pausa_segundos=0.6)

    itens_hoje = ler_itens_pedidos(hoje, hoje)
    unidades_hoje = 0.0
    produto_lider = "Sem itens sincronizados"

    if not itens_hoje.empty:
        itens_validos_hoje = itens_hoje.loc[
            ~itens_hoje["situacao_id"].isin(SITUACOES_CANCELADAS)
        ].copy()

        if not itens_validos_hoje.empty:
            unidades_hoje = float(itens_validos_hoje["quantidade"].sum())
            ranking_produtos = (
                itens_validos_hoje.groupby("descricao", as_index=False)
                .agg(quantidade=("quantidade", "sum"))
                .sort_values("quantidade", ascending=False)
            )
            produto_lider = str(ranking_produtos.iloc[0]["descricao"])

    historico = ler_historico_diario(inicio_busca)
    comparativo = montar_comparativo(ler_metas(), historico, hoje)

    cards_metas, meta_diaria_total, meta_semanal_total, realizado_semana, _ = (
        calcular_cards_metas(comparativo, historico, hoje)
    )

    segundos_dia = 24 * 60 * 60
    segundos_passados = (
        datetime.combine(hoje, agora.time())
        - datetime.combine(hoje, time.min)
    ).total_seconds()
    percentual_dia = min(max(segundos_passados / segundos_dia, 0), 1)
    esperado_agora = meta_diaria_total * percentual_dia
    pacing_dia = faturamento_hoje / esperado_agora if esperado_agora else None
    status_pacing, tipo_pacing = status_por_razao(pacing_dia)

    faturamento_14_dias = (
        df_validos.dropna(subset=["data"])
        .assign(dia=lambda dados: dados["data"].dt.date)
        .groupby("dia", as_index=False)
        .agg(faturamento=("total", "sum"), pedidos=("id", "nunique"))
        .sort_values("dia")
    )

    media_7 = (
        float(faturamento_14_dias["faturamento"].tail(7).mean())
        if not faturamento_14_dias.empty
        else 0.0
    )

    receita_por_canal = (
        df_validos.loc[df_validos["data"].dt.date == hoje]
        .assign(canal=lambda dados: dados["loja_id"].apply(nome_canal))
        .groupby("canal", as_index=False)
        .agg(faturamento=("total", "sum"), pedidos=("id", "nunique"))
        .sort_values("faturamento", ascending=False)
    )

    cards_extras = [
        card_tv(
            "Pacing do dia",
            status_pacing,
            (
                f"Esperado até agora: {moeda_br(esperado_agora)} · "
                f"realizado: {moeda_br(faturamento_hoje)}"
            ),
            chip=f"{pct_texto(pacing_dia)} do ritmo esperado",
            chip_tipo=tipo_pacing,
            progresso=pacing_dia,
        ),
        card_tv(
            "Meta diária total",
            moeda_br(meta_diaria_total),
            "Soma das metas ativas para hoje",
            chip=f"{pct_texto(faturamento_hoje / meta_diaria_total if meta_diaria_total else None)} atingido",
            chip_tipo=status_por_razao(
                faturamento_hoje / meta_diaria_total if meta_diaria_total else None
            )[1],
            progresso=faturamento_hoje / meta_diaria_total
            if meta_diaria_total
            else None,
        ),
        card_tv(
            "Meta semanal total",
            moeda_br(meta_semanal_total),
            f"Realizado na semana: {moeda_br(realizado_semana)}",
            chip=f"{pct_texto(realizado_semana / meta_semanal_total if meta_semanal_total else None)} atingido",
            chip_tipo=status_por_razao(
                realizado_semana / meta_semanal_total
                if meta_semanal_total
                else None
            )[1],
            progresso=realizado_semana / meta_semanal_total
            if meta_semanal_total
            else None,
        ),
        card_tv(
            "Média diária 7 dias",
            moeda_br(media_7),
            "Base de ritmo recente",
            chip="Histórico recente",
            chip_tipo="neutral",
        ),
    ]

    for _, canal in receita_por_canal.iterrows():
        cards_extras.append(
            card_tv(
                f"Canal · {canal['canal']}",
                moeda_br(float(canal["faturamento"])),
                f"{int(canal['pedidos'])} pedido(s) hoje",
                chip="Hoje",
                chip_tipo="neutral",
            )
        )

    cards_principais = [
        card_tv(
            "Faturamento hoje",
            moeda_br(faturamento_hoje),
            "Pedidos válidos do dia",
            chip=f"{pedidos_hoje} pedido(s)",
            chip_tipo="neutral",
        ),
        card_tv(
            "Pedidos hoje",
            f"{pedidos_hoje:,}".replace(",", "."),
            "Pedidos não cancelados",
            chip="Tempo real",
            chip_tipo="good",
        ),
        card_tv(
            "Unidades hoje",
            f"{unidades_hoje:,.0f}".replace(",", "."),
            f"Produto líder: {produto_lider}",
            chip="Itens",
            chip_tipo="neutral",
        ),
        card_tv(
            "Pacing",
            status_pacing,
            f"{pct_texto(percentual_dia)} do dia transcorrido",
            chip=f"{pct_texto(pacing_dia)} do esperado",
            chip_tipo=tipo_pacing,
            progresso=pacing_dia,
        ),
    ]

    todos_cards = cards_principais + cards_metas + cards_extras

    if not todos_cards:
        todos_cards = [
            card_tv(
                "Sem metas ativas",
                moeda_br(faturamento_hoje),
                "Cadastre uma meta para acompanhar pacing diário e semanal.",
            )
        ]

    duracao_total = max(len(todos_cards) * SEGUNDOS_POR_CARD, 1)
    slides = "".join(
        (
            '<div class="tv-slide" '
            f'style="--tv-cycle: {duracao_total}s; '
            f'--tv-delay: {indice * SEGUNDOS_POR_CARD}s;">'
            f"{card}</div>"
        )
        for indice, card in enumerate(todos_cards)
    )

    st.html(
        f"""
        <div class="tv-shell">
            <div class="tv-topbar">
                <div>
                    <h1 class="tv-title">Televisão ROPO</h1>
                    <div class="tv-subtitle">
                        Resultados de hoje, meta diária, meta semanal e pacing
                        em tela cheia.
                    </div>
                </div>
                <div class="tv-clock">
                    <div class="tv-clock-time">{agora.strftime('%H:%M')}</div>
                    <div class="tv-clock-date">
                        {hoje.strftime('%d/%m/%Y')} · São Paulo GMT-3
                    </div>
                </div>
            </div>

            <div class="tv-stage">
                {slides}
            </div>
        </div>
        """
    )

    st.caption(
        "Pacing do dia compara faturamento de hoje com a meta diária "
        "proporcional ao horário atual."
    )


@st.fragment(run_every="2m")
def exibir_televisao() -> None:
    renderizar_tv()


exibir_televisao()
