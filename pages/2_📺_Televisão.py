from __future__ import annotations

import calendar
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
    ler_tokens,
    moeda_br,
    nome_canal,
    salvar_historico_diario,
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

        .tv-chart-card .tv-card-value {
            font-size: clamp(2.6rem, 5.4vw, 7.4rem);
            margin-bottom: 10px;
        }

        .tv-chart-wrap {
            margin-top: 26px;
            width: 100%;
        }

        .tv-chart-wrap svg {
            display: block;
            width: 100%;
            height: min(34vh, 310px);
        }

        .tv-chart-axis {
            stroke: rgba(226, 232, 240, 0.28);
            stroke-width: 2;
        }

        .tv-chart-grid {
            stroke: rgba(226, 232, 240, 0.11);
            stroke-width: 1;
        }

        .tv-chart-line {
            fill: none;
            stroke: var(--tv-blue);
            stroke-width: 7;
            stroke-linecap: round;
            stroke-linejoin: round;
        }

        .tv-chart-dot {
            fill: var(--tv-good);
            stroke: #0f1f34;
            stroke-width: 4;
        }

        .tv-chart-labels {
            display: flex;
            justify-content: space-between;
            color: var(--tv-muted);
            font-size: clamp(0.9rem, 1.1vw, 1.2rem);
            margin-top: 8px;
        }

        .tv-slide {
            position: absolute;
            inset: 0;
            opacity: 0;
            transform: translateX(6%);
        }

        .tv-slide:first-child:last-child {
            opacity: 1;
            transform: none;
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
    extra_html: str = "",
    classe_extra: str = "",
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
        f'<div class="tv-card {escape(classe_extra)}">'
        f'<div class="tv-card-label">{escape(titulo)}</div>'
        f'<div class="tv-card-value">{escape(valor)}</div>'
        f'<div class="tv-card-detail">{escape(detalhe)}</div>'
        f"{progresso_html}"
        f"{extra_html}"
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


def segundos_passados_no_dia(agora: datetime) -> float:
    inicio_dia = datetime.combine(
        agora.date(),
        time.min,
        tzinfo=agora.tzinfo,
    )

    return max((agora - inicio_dia).total_seconds(), 0)


def agregar_faturamento_diario(df_validos: pd.DataFrame) -> pd.DataFrame:
    if df_validos.empty:
        return pd.DataFrame(columns=["dia", "faturamento", "pedidos"])

    return (
        df_validos.dropna(subset=["data"])
        .assign(dia=lambda dados: dados["data"].dt.date)
        .groupby("dia", as_index=False)
        .agg(faturamento=("total", "sum"), pedidos=("id", "nunique"))
        .sort_values("dia")
    )


def faturamento_periodo(
    faturamento_diario: pd.DataFrame,
    inicio: date,
    fim: date,
) -> float:
    if faturamento_diario.empty:
        return 0.0

    filtro = (
        (faturamento_diario["dia"] >= inicio)
        & (faturamento_diario["dia"] <= fim)
    )

    return float(faturamento_diario.loc[filtro, "faturamento"].sum())


def card_evolucao(
    faturamento_diario: pd.DataFrame,
    hoje: date,
    faturamento_hoje: float,
) -> str:
    ultimos_dias = faturamento_diario.tail(14).copy()

    if ultimos_dias.empty:
        return card_tv(
            "Evolução do faturamento",
            moeda_br(faturamento_hoje),
            "Ainda sem histórico suficiente para desenhar o gráfico.",
            chip="KPI de hoje",
            chip_tipo="neutral",
            classe_extra="tv-chart-card",
        )

    valores = ultimos_dias["faturamento"].astype(float).tolist()
    maior = max(max(valores), 1.0)
    largura = 1000
    altura = 300
    margem_x = 28
    margem_y = 28
    area_w = largura - margem_x * 2
    area_h = altura - margem_y * 2

    pontos = []
    total_pontos = max(len(valores) - 1, 1)

    for indice, valor in enumerate(valores):
        x = margem_x + (indice / total_pontos) * area_w
        y = margem_y + (1 - (valor / maior)) * area_h
        pontos.append((x, y))

    polilinha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pontos)
    dots = "".join(
        f'<circle class="tv-chart-dot" cx="{x:.1f}" cy="{y:.1f}" r="8" />'
        for x, y in pontos
    )

    inicio = ultimos_dias.iloc[0]["dia"]
    fim = ultimos_dias.iloc[-1]["dia"]
    media_7 = float(ultimos_dias["faturamento"].tail(7).mean())
    comparacao = (
        faturamento_hoje / media_7 - 1
        if media_7
        else None
    )
    status, status_tipo = status_por_razao(
        faturamento_hoje / media_7 if media_7 else None
    )

    grafico = f"""
    <div class="tv-chart-wrap">
        <svg viewBox="0 0 {largura} {altura}" role="img" aria-label="Evolução do faturamento">
            <line class="tv-chart-grid" x1="{margem_x}" y1="{margem_y}" x2="{largura - margem_x}" y2="{margem_y}" />
            <line class="tv-chart-grid" x1="{margem_x}" y1="{altura / 2}" x2="{largura - margem_x}" y2="{altura / 2}" />
            <line class="tv-chart-axis" x1="{margem_x}" y1="{altura - margem_y}" x2="{largura - margem_x}" y2="{altura - margem_y}" />
            <polyline class="tv-chart-line" points="{polilinha}" />
            {dots}
        </svg>
        <div class="tv-chart-labels">
            <span>{inicio.strftime('%d/%m')}</span>
            <span>Media 7 dias: {moeda_br(media_7)}</span>
            <span>{fim.strftime('%d/%m')}</span>
        </div>
    </div>
    """

    detalhe = (
        f"{status} vs. media 7 dias"
        if comparacao is not None
        else "KPI de hoje"
    )

    return card_tv(
        "Evolução do faturamento",
        moeda_br(faturamento_hoje),
        detalhe,
        chip=(
            f"{comparacao:+.0%} vs. media 7 dias"
            if comparacao is not None
            else "KPI de hoje"
        ),
        chip_tipo=status_tipo,
        extra_html=grafico,
        classe_extra="tv-chart-card",
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
    inicio_mes = hoje.replace(day=1)
    inicio_busca = min(hoje - timedelta(days=13), inicio_mes)

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
    faturamento_diario = agregar_faturamento_diario(df_validos)

    percentual_dia = min(
        max(segundos_passados_no_dia(agora) / (24 * 60 * 60), 0),
        1,
    )
    previsao_dia = (
        faturamento_hoje / percentual_dia
        if percentual_dia > 0
        else faturamento_hoje
    )

    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    realizado_semana = faturamento_periodo(
        faturamento_diario,
        inicio_semana,
        hoje,
    )
    dias_semana_corridos = (hoje - inicio_semana).days + 1
    previsao_semana = (
        realizado_semana / dias_semana_corridos * 7
        if dias_semana_corridos
        else realizado_semana
    )

    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    fim_mes = hoje.replace(day=dias_no_mes)
    realizado_mes = faturamento_periodo(faturamento_diario, inicio_mes, hoje)
    dias_mes_corridos = hoje.day
    previsao_mes = (
        realizado_mes / dias_mes_corridos * dias_no_mes
        if dias_mes_corridos
        else realizado_mes
    )

    receita_por_canal = (
        df_validos.loc[df_validos["data"].dt.date == hoje]
        .assign(canal=lambda dados: dados["loja_id"].apply(nome_canal))
        .groupby("canal", as_index=False)
        .agg(faturamento=("total", "sum"), pedidos=("id", "nunique"))
        .sort_values("faturamento", ascending=False)
    )

    cards_lojas = [
        card_tv(
            str(canal["canal"]),
            moeda_br(float(canal["faturamento"])),
            f"{int(canal['pedidos'])} venda(s) hoje",
            chip="Faturamento por loja",
            chip_tipo="neutral",
        )
        for _, canal in receita_por_canal.iterrows()
    ]

    cards_previsao = [
        card_tv(
            "Previsão diária",
            moeda_br(previsao_dia),
            (
                f"Hoje realizado: {moeda_br(faturamento_hoje)} · "
                f"{pct_texto(percentual_dia)} do dia"
            ),
            chip="Fechamento estimado do dia",
            chip_tipo="good",
        ),
        card_tv(
            "Previsão semanal",
            moeda_br(previsao_semana),
            (
                f"Realizado {inicio_semana.strftime('%d/%m')} a "
                f"{hoje.strftime('%d/%m')}: {moeda_br(realizado_semana)}"
            ),
            chip=f"Semana ate {fim_semana.strftime('%d/%m')}",
            chip_tipo="neutral",
        ),
        card_tv(
            "Previsão mensal",
            moeda_br(previsao_mes),
            (
                f"Realizado {inicio_mes.strftime('%d/%m')} a "
                f"{hoje.strftime('%d/%m')}: {moeda_br(realizado_mes)}"
            ),
            chip=f"Mes ate {fim_mes.strftime('%d/%m')}",
            chip_tipo="neutral",
        ),
    ]

    todos_cards = cards_lojas + cards_previsao + [
        card_evolucao(faturamento_diario, hoje, faturamento_hoje)
    ]

    if not todos_cards:
        todos_cards = [
            card_tv(
                "Sem vendas por loja hoje",
                moeda_br(faturamento_hoje),
                "Nenhum pedido válido encontrado no dia.",
            )
        ]

    duracao_total = max(len(todos_cards) * SEGUNDOS_POR_CARD, 1)
    slides_partes = []
    animacoes_partes = []

    if len(todos_cards) == 1:
        slides = f'<div class="tv-slide">{todos_cards[0]}</div>'
        animacoes = ""
    else:
        transicao_pct = min(1.8 / duracao_total * 100, 4)

        for indice, card in enumerate(todos_cards):
            inicio_pct = indice * SEGUNDOS_POR_CARD / duracao_total * 100
            fim_pct = (indice + 1) * SEGUNDOS_POR_CARD / duracao_total * 100
            entra_pct = min(inicio_pct + transicao_pct, fim_pct)
            sai_pct = max(fim_pct - transicao_pct, entra_pct)
            nome_animacao = f"tv-slide-{indice}"

            if indice == 0:
                animacoes_partes.append(
                    f"""
                    @keyframes {nome_animacao} {{
                        0% {{ opacity: 1; transform: translateX(0) scale(1); }}
                        {sai_pct:.3f}% {{ opacity: 1; transform: translateX(0) scale(1); }}
                        {fim_pct:.3f}% {{ opacity: 0; transform: translateX(-6%) scale(0.985); }}
                        100% {{ opacity: 0; transform: translateX(-6%) scale(0.985); }}
                    }}
                    """
                )
            else:
                animacoes_partes.append(
                    f"""
                    @keyframes {nome_animacao} {{
                        0% {{ opacity: 0; transform: translateX(6%) scale(0.985); }}
                        {inicio_pct:.3f}% {{ opacity: 0; transform: translateX(6%) scale(0.985); }}
                        {entra_pct:.3f}% {{ opacity: 1; transform: translateX(0) scale(1); }}
                        {sai_pct:.3f}% {{ opacity: 1; transform: translateX(0) scale(1); }}
                        {fim_pct:.3f}% {{ opacity: 0; transform: translateX(-6%) scale(0.985); }}
                        100% {{ opacity: 0; transform: translateX(-6%) scale(0.985); }}
                    }}
                    """
                )
            slides_partes.append(
                (
                    '<div class="tv-slide" '
                    f'style="animation: {nome_animacao} {duracao_total}s '
                    f'infinite ease-in-out;">{card}</div>'
                )
            )

        slides = "".join(slides_partes)
        animacoes = f"<style>{''.join(animacoes_partes)}</style>"

    st.html(
        f"""
        {animacoes}
        <div class="tv-shell">
            <div class="tv-topbar">
                <div>
                    <h1 class="tv-title">Televisão ROPO</h1>
                    <div class="tv-subtitle">
                        Vendas e faturamento de hoje por loja.
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

    st.caption("Cada card mostra o faturamento e o número de vendas de hoje por loja.")


@st.fragment(run_every="2m")
def exibir_televisao() -> None:
    renderizar_tv()


exibir_televisao()
