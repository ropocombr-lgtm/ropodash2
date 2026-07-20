from __future__ import annotations

import base64
import calendar
from datetime import date, datetime, time, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_core import (
    SITUACOES_CANCELADAS,
    agora_sao_paulo,
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
)

SEGUNDOS_POR_CARD = 7

CAMINHO_SOM_VENDA = Path(__file__).parent.parent / "assets" / "som_venda.wav"


@st.cache_data(show_spinner=False)
def carregar_som_venda() -> bytes:
    return CAMINHO_SOM_VENDA.read_bytes()

NOMES_DIA_SEMANA_CURTO = {
    0: "Seg",
    1: "Ter",
    2: "Qua",
    3: "Qui",
    4: "Sex",
    5: "Sáb",
    6: "Dom",
}

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

        /* Só queremos o som da corneta a cada venda nova, não o player
        visível (barra de áudio) ocupando espaço na tela da TV. */
        [data-testid="stAudio"] {
            position: absolute;
            width: 1px;
            height: 1px;
            overflow: hidden;
            opacity: 0;
        }

        /* Botão de teste da buzina: canto discreto, não disputa espaço com
        os cards giratórios. */
        [data-testid="stButton"] {
            position: fixed;
            bottom: 18px;
            right: 18px;
            z-index: 1000;
            width: auto;
        }

        [data-testid="stButton"] button {
            background: rgba(15, 31, 52, 0.85);
            border: 1px solid var(--tv-border);
            color: var(--tv-text);
            border-radius: 8px;
            padding: 10px 16px;
            font-weight: 700;
            font-size: 0.95rem;
            box-shadow: 0 10px 26px rgba(0, 0, 0, 0.25);
        }

        [data-testid="stButton"] button:hover {
            border-color: var(--tv-blue);
            color: var(--tv-blue);
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

        /*
        Cards com gráfico embutido cedem espaço do "número gigante" (pensado
        pra cards de KPI único) pro gráfico, senão o conteúdo empilhado
        (label + número + detalhe + gráfico + lista + chip) estoura a altura
        fixa do .tv-card, que tem overflow:hidden — o gráfico simplesmente
        some, cortado, sem nenhum erro visível.
        */
        .tv-chart-card {
            padding: clamp(20px, 2.5vw, 44px);
        }

        .tv-chart-card .tv-card-label {
            font-size: clamp(0.95rem, 1.3vw, 1.6rem);
        }

        .tv-chart-card .tv-card-value {
            font-size: clamp(2.6rem, 5.4vw, 7.4rem);
            margin: 8px 0;
        }

        .tv-chart-card .tv-card-detail {
            font-size: clamp(1rem, 1.5vw, 1.8rem);
        }

        .tv-chart-card .tv-chart-wrap {
            margin-top: 12px;
        }

        .tv-chart-card .tv-list {
            margin-top: 12px;
            gap: 6px;
        }

        .tv-chart-card .tv-list-item {
            padding: 6px 10px;
            font-size: clamp(0.85rem, 1vw, 1.1rem);
        }

        .tv-chart-card .tv-chip {
            margin-top: 14px;
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

        .tv-chart-bar-label {
            fill: var(--tv-muted);
            font-size: 27px;
        }

        .tv-chart-bar-value {
            fill: var(--tv-text);
            font-weight: 800;
            font-size: 27px;
        }

        .tv-incentivo-card {
            border: 2px solid var(--tv-good);
            background: linear-gradient(180deg, rgba(34, 197, 94, 0.16), rgba(15, 31, 52, 0.96));
        }

        .tv-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 18px;
        }

        .tv-list-item {
            background: rgba(226, 232, 240, 0.08);
            border: 1px solid rgba(226, 232, 240, 0.14);
            border-radius: 8px;
            padding: 10px 12px;
            color: var(--tv-text);
            font-size: clamp(0.95rem, 1.2vw, 1.3rem);
            line-height: 1.35;
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


def variacao_percentual(atual: float, anterior: float) -> float | None:
    if not anterior:
        return None

    return (atual - anterior) / anterior


def mascara_cliente(nome: str | None) -> str:
    if not nome:
        return "Cliente"

    nome = str(nome).strip()
    if len(nome) <= 2:
        return nome

    return f"{nome[0]}***"


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


def card_tv_lista(
    titulo: str,
    valor: str,
    detalhe: str = "",
    itens: list[str] | None = None,
    chip: str = "",
    chip_tipo: str = "neutral",
    extra_html: str = "",
    classe_extra: str = "",
) -> str:
    lista_html = ""
    if itens:
        linhas = "".join(
            f'<div class="tv-list-item">{escape(item)}</div>'
            for item in itens
        )
        lista_html = f'<div class="tv-list">{linhas}</div>'

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
        f"{extra_html}"
        f'{lista_html}'
        f'{chip_html}'
        '</div>'
    )


def _truncar_texto(texto: str, maximo: int = 46) -> str:
    texto = str(texto)

    if len(texto) <= maximo:
        return texto

    return texto[: maximo - 1].rstrip() + "…"


def _imagem_svg(
    svg_interno: str,
    largura: int,
    altura: int,
    altura_css: str,
    aria_label: str,
) -> str:
    # st.html() nesta versão do Streamlit remove qualquer <svg> inline da
    # página (confirmado: sobrava um <div class="tv-chart-wrap"> vazio, sem
    # nenhum <svg> dentro). A saída é embutir o SVG como imagem base64 — um
    # <img> nunca é removido. Por isso todo o SVG abaixo usa cor/fonte fixas
    # em vez de classes CSS: uma imagem embutida não enxerga o <style> da
    # página.
    # width/height explícitos (não só viewBox) evitam um problema conhecido
    # do Chromium: <img> apontando pra um SVG sem tamanho intrínseco
    # explícito pode combinar mal com object-fit e desenhar o conteúdo
    # deslocado dentro da própria caixa da imagem.
    # preserveAspectRatio="none": confirmado por teste isolado que, sem
    # isso, o padrão ("xMidYMid meet") centraliza o desenho original
    # (1000x{altura}) dentro da caixa esticada do <img> em vez de esticar
    # junto — sobrava uma faixa vazia grande à esquerda e à direita do
    # gráfico, mesmo com object-fit:fill no <img>.
    svg_completo = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" preserveAspectRatio="none" '
        f'role="img" aria-label="{escape(aria_label)}">'
        f"{svg_interno}"
        "</svg>"
    )

    b64 = base64.b64encode(svg_completo.encode("utf-8")).decode("ascii")

    # width:100% + altura fixa preenche o card de ponta a ponta (o que
    # importa aqui é o gráfico aparecer visível e legível). object-fit:contain
    # foi tentado, mas como o viewBox interno (pensado pra unidades de
    # desenho, não pra proporção final na tela) é bem mais "quadrado" que o
    # card (bem largo e baixo), contain encolhia o gráfico numa ilha pequena
    # no meio do card em vez de preencher a largura. Um esticamento leve é
    # aceitável pra barras/linhas/texto — não é uma foto.
    return (
        f'<img src="data:image/svg+xml;base64,{b64}" '
        f'alt="{escape(aria_label)}" '
        f'style="display:block;width:100%;height:{altura_css};" />'
    )


def grafico_barras_svg(
    itens: list[tuple[str, float]],
    cor_barra: str = "#38bdf8",
) -> str:
    if not itens:
        return ""

    largura = 1000
    altura_item = 72
    altura = altura_item * len(itens)
    # Limite conservador: o card tem altura fixa e overflow:hidden (label +
    # número + detalhe + gráfico + chip todos disputam o mesmo espaço), então
    # um gráfico "alto demais" simplesmente some cortado, sem erro nenhum.
    altura_px = min(48 * len(itens) + 16, 260)
    maior_valor = max((valor for _, valor in itens), default=0.0) or 1.0
    largura_max_barra = largura - 230

    partes = [
        f'<line x1="{largura_max_barra * 0.33:.1f}" y1="0" '
        f'x2="{largura_max_barra * 0.33:.1f}" y2="{altura}" '
        'stroke="rgba(226,232,240,0.11)" stroke-width="1" />',
        f'<line x1="{largura_max_barra * 0.66:.1f}" y1="0" '
        f'x2="{largura_max_barra * 0.66:.1f}" y2="{altura}" '
        'stroke="rgba(226,232,240,0.11)" stroke-width="1" />',
        f'<line x1="0" y1="0" x2="0" y2="{altura}" '
        'stroke="rgba(226,232,240,0.28)" stroke-width="2" />',
    ]

    for indice, (rotulo, valor) in enumerate(itens):
        y_base = indice * altura_item
        largura_barra = max((valor / maior_valor) * largura_max_barra, 8)

        partes.append(
            f'<text x="0" y="{y_base + 20}" fill="#a7b7cc" font-size="27" '
            f'font-family="Arial, sans-serif">'
            f'{escape(_truncar_texto(rotulo))}</text>'
            f'<rect x="0" y="{y_base + 30}" width="{largura_barra:.1f}" height="26" '
            f'rx="6" fill="{cor_barra}" />'
            f'<text x="{largura_barra + 16:.1f}" y="{y_base + 49}" '
            f'fill="#f8fafc" font-weight="800" font-size="27" '
            f'font-family="Arial, sans-serif">{escape(moeda_br(valor))}</text>'
        )

    imagem = _imagem_svg(
        "".join(partes),
        largura,
        altura,
        f"{altura_px}px",
        "Gráfico de barras",
    )

    return f'<div class="tv-chart-wrap tv-chart-wrap-bars">{imagem}</div>'


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

    resultado = (
        df_validos.dropna(subset=["data"])
        .assign(dia=lambda dados: pd.to_datetime(dados["data"]).dt.normalize())
        .groupby("dia", as_index=False)
        .agg(faturamento=("total", "sum"), pedidos=("id", "nunique"))
        .sort_values("dia")
    )

    resultado["dia"] = pd.to_datetime(resultado["dia"])
    return resultado


def faturamento_periodo(
    faturamento_diario: pd.DataFrame,
    inicio: date,
    fim: date,
) -> float:
    if faturamento_diario.empty:
        return 0.0

    coluna_dia = pd.to_datetime(faturamento_diario["dia"]).dt.normalize()
    inicio_dt = pd.Timestamp(inicio)
    fim_dt = pd.Timestamp(fim)

    filtro = (coluna_dia >= inicio_dt) & (coluna_dia <= fim_dt)

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
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" '
        'fill="#22c55e" stroke="#0f1f34" stroke-width="4" />'
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

    svg_interno = (
        f'<line x1="{margem_x}" y1="{margem_y}" x2="{largura - margem_x}" y2="{margem_y}" '
        'stroke="rgba(226,232,240,0.11)" stroke-width="1" />'
        f'<line x1="{margem_x}" y1="{altura / 2}" x2="{largura - margem_x}" y2="{altura / 2}" '
        'stroke="rgba(226,232,240,0.11)" stroke-width="1" />'
        f'<line x1="{margem_x}" y1="{altura - margem_y}" x2="{largura - margem_x}" y2="{altura - margem_y}" '
        'stroke="rgba(226,232,240,0.28)" stroke-width="2" />'
        f'<polyline points="{polilinha}" fill="none" stroke="#38bdf8" '
        'stroke-width="7" stroke-linecap="round" stroke-linejoin="round" />'
        f"{dots}"
    )

    imagem = _imagem_svg(
        svg_interno,
        largura,
        altura,
        "min(34vh, 310px)",
        "Evolução do faturamento",
    )

    grafico = f"""
    <div class="tv-chart-wrap">
        {imagem}
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

    # Também serve pra "destravar" o autoplay de áudio do navegador: a
    # maioria dos navegadores só libera som automático numa aba depois de
    # uma interação manual do usuário — clicar aqui uma vez faz isso.
    if st.button("🔊 Testar buzina", key="testar_buzina"):
        st.audio(carregar_som_venda(), format="audio/wav", autoplay=True)

    agora = agora_sao_paulo()
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
        try:
            df = carregar_dataframe(inicio_busca.isoformat(), hoje.isoformat())
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
        st.info("Nenhum pedido encontrado para exibir na televisão.")
        return

    salvar_historico_diario(calcular_historico_diario(df))

    cancelados = df["situacao_id"].isin(SITUACOES_CANCELADAS)
    df_validos = df.loc[~cancelados].copy()
    df_hoje = df_validos.loc[df_validos["data"].dt.date == hoje].copy()
    faturamento_hoje = float(df_hoje["total"].sum())
    pedidos_hoje = int(df_hoje["id"].nunique())
    ticket_medio_hoje = (
        faturamento_hoje / pedidos_hoje if pedidos_hoje else 0.0
    )

    # Toca a corneta só quando aparece um pedido novo desde o último
    # carregamento desta aba — não no primeiro carregamento do dia (senão
    # tocaria em rajada pra cada venda já existente) nem pra pedidos
    # cancelados. st.session_state é por aba/sessão de navegador, então cada
    # TV que ficar com a página aberta detecta suas próprias vendas novas.
    ids_vendas_hoje = frozenset(df_hoje["id"].dropna().astype(int))

    if "ids_vendas_conhecidas" in st.session_state:
        vendas_novas = ids_vendas_hoje - st.session_state.ids_vendas_conhecidas

        if vendas_novas:
            st.audio(carregar_som_venda(), format="audio/wav", autoplay=True)

    st.session_state.ids_vendas_conhecidas = ids_vendas_hoje

    df_cancelados_hoje = df.loc[
        (cancelados) & (df["data"].dt.date == hoje)
    ].copy()
    quantidade_cancelados_hoje = int(df_cancelados_hoje["id"].nunique())
    valor_cancelado_hoje = float(df_cancelados_hoje["total"].sum())

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
        df_hoje.assign(canal=lambda dados: dados["loja_id"].apply(nome_canal))
        .groupby("canal", as_index=False)
        .agg(faturamento=("total", "sum"), pedidos=("id", "nunique"))
        .sort_values("faturamento", ascending=False)
    )

    if not receita_por_canal.empty:
        receita_por_canal["ticket_medio"] = (
            receita_por_canal["faturamento"] / receita_por_canal["pedidos"]
        )
        receita_por_canal["participacao"] = (
            receita_por_canal["faturamento"] / faturamento_hoje
            if faturamento_hoje
            else 0.0
        )

    itens_periodo = ler_itens_pedidos(hoje, hoje)

    # itens_periodo["situacao_id"] é uma foto tirada na sincronização e nunca
    # é atualizada depois; usamos a situação atual de "df" para não divergir
    # dos números por pedido se um pedido for cancelado (ou reativado) depois.
    situacao_atual_por_pedido = df.set_index("id")["situacao_id"]
    situacao_atual_itens = (
        itens_periodo["pedido_id"]
        .map(situacao_atual_por_pedido)
        .fillna(itens_periodo["situacao_id"])
    )

    itens_validos = itens_periodo.loc[
        ~situacao_atual_itens.isin(SITUACOES_CANCELADAS)
    ].copy()

    if not itens_validos.empty:
        itens_validos["total_item"] = (
            itens_validos["quantidade"] * itens_validos["valor_unitario"]
            - itens_validos["desconto"]
        )
        ranking_produtos = (
            itens_validos.groupby(["sku", "descricao"], as_index=False)
            .agg(
                faturamento=("total_item", "sum"),
                unidades=("quantidade", "sum"),
                pedidos=("pedido_id", "nunique"),
            )
            .sort_values("faturamento", ascending=False)
        )
        produto_campeao = ranking_produtos.iloc[0] if not ranking_produtos.empty else None
        unidades_vendidas_hoje = float(itens_validos["quantidade"].sum())
    else:
        ranking_produtos = pd.DataFrame(columns=["sku", "descricao", "faturamento", "unidades", "pedidos"])
        produto_campeao = None
        unidades_vendidas_hoje = 0.0

    historico = ler_historico_diario(inicio_busca)
    metas_df = ler_metas()
    comparativo = montar_comparativo(metas_df, historico, hoje)

    metas_ativas = comparativo.loc[comparativo["periodo_ativo_agora"]].copy() if not comparativo.empty else pd.DataFrame()

    # Ritmo esperado por loja: média diária de faturamento válido nos dias
    # anteriores (excluindo hoje, que está parcial), escalada pela fração do
    # dia já transcorrida. Usa a janela inteira como denominador (não só os
    # dias com venda) para não superestimar canais com vendas esparsas.
    dias_janela_baseline = max((hoje - inicio_busca).days, 1)
    baseline_historico = historico.loc[historico["data"] < hoje].copy()

    if not baseline_historico.empty:
        baseline_historico["canal_nome"] = baseline_historico["canal"].apply(nome_canal)
        baseline_por_canal = (
            baseline_historico.groupby("canal_nome", as_index=False)
            .agg(faturamento_total=("faturamento_valido", "sum"))
        )
        baseline_por_canal["media_diaria"] = (
            baseline_por_canal["faturamento_total"] / dias_janela_baseline
        )
    else:
        baseline_por_canal = pd.DataFrame(columns=["canal_nome", "media_diaria"])

    if not receita_por_canal.empty:
        receita_por_canal = receita_por_canal.merge(
            baseline_por_canal[["canal_nome", "media_diaria"]].rename(
                columns={"canal_nome": "canal"}
            ),
            on="canal",
            how="left",
        )
        receita_por_canal["media_diaria"] = receita_por_canal["media_diaria"].fillna(0.0)
        receita_por_canal["ritmo_esperado"] = (
            receita_por_canal["media_diaria"] * percentual_dia
        )
        receita_por_canal["razao_pacing"] = receita_por_canal.apply(
            lambda linha: (
                linha["faturamento"] / linha["ritmo_esperado"]
                if linha["ritmo_esperado"]
                else float("nan")
            ),
            axis=1,
        )

    ontem = hoje - timedelta(days=1)
    df_ontem = carregar_dataframe(ontem.isoformat(), ontem.isoformat())
    df_ontem_validos = df_ontem.loc[~df_ontem["situacao_id"].isin(SITUACOES_CANCELADAS)].copy()
    faturamento_ontem = float(df_ontem_validos["total"].sum())
    variacao_ontem = variacao_percentual(faturamento_hoje, faturamento_ontem)

    semana_passada = hoje - timedelta(days=7)
    df_semana_passada = carregar_dataframe(semana_passada.isoformat(), semana_passada.isoformat())
    df_semana_passada_validos = df_semana_passada.loc[~df_semana_passada["situacao_id"].isin(SITUACOES_CANCELADAS)].copy()
    faturamento_semana_passada = float(df_semana_passada_validos["total"].sum())
    variacao_semana_passada = variacao_percentual(faturamento_hoje, faturamento_semana_passada)

    ultimos_dias = faturamento_diario.tail(14).copy()
    if len(ultimos_dias) >= 14:
        media_ultimos_7 = float(ultimos_dias["faturamento"].tail(7).mean())
        media_7_anteriores = float(ultimos_dias["faturamento"].iloc[-14:-7].mean())
        aceleracao = variacao_percentual(media_ultimos_7, media_7_anteriores)
        if aceleracao is None:
            tendencia_texto = "estável"
            tendencia_tipo = "neutral"
        elif aceleracao > 0.02:
            tendencia_texto = "subindo"
            tendencia_tipo = "good"
        elif aceleracao < -0.02:
            tendencia_texto = "caindo"
            tendencia_tipo = "bad"
        else:
            tendencia_texto = "estável"
            tendencia_tipo = "warning"
    else:
        tendencia_texto = "estável"
        tendencia_tipo = "neutral"

    # O Bling só devolve a data do pedido, sem horário (mesma limitação já
    # documentada em 1_🕐_Tempo_Real.py). A checagem abaixo é por segurança:
    # se algum dia a API passar a incluir horário, o recorte liga sozinho.
    horario_disponivel = (
        not df_hoje.empty
        and df_hoje["data"].dropna().dt.time.ne(time(0, 0)).any()
    )

    if horario_disponivel:
        vendas_por_hora = (
            df_hoje.dropna(subset=["data"])
            .copy()
            .assign(hora=lambda dados: dados["data"].dt.hour)
            .groupby("hora", as_index=False)
            .agg(vendas=("id", "nunique"), faturamento=("total", "sum"))
            .sort_values("hora")
        )
    else:
        vendas_por_hora = pd.DataFrame(columns=["hora", "vendas", "faturamento"])

    # Sem horário real do pedido, "data" é igual para tudo no mesmo dia; o id
    # do Bling (sequencial) é usado como critério de desempate para que
    # "últimas vendas" reflita a ordem real de chegada dos pedidos.
    ultimas_vendas = (
        df_hoje.dropna(subset=["data"])
        .sort_values(["data", "id"], ascending=[False, False])
        .head(5)
        .copy()
    )

    mes_historico = faturamento_diario.loc[
        (faturamento_diario["dia"].dt.month == hoje.month)
        & (faturamento_diario["dia"].dt.year == hoje.year)
    ].copy()
    melhor_dia_mes = (
        mes_historico.loc[mes_historico["faturamento"].idxmax()]
        if not mes_historico.empty
        else None
    )
    falta_para_recorde = (
        max(float(melhor_dia_mes["faturamento"]) - faturamento_hoje, 0.0)
        if melhor_dia_mes is not None
        else 0.0
    )

    cards = []

    cards.append(
        card_tv_lista(
            "Status operacional",
            moeda_br(faturamento_hoje),
            f"{pedidos_hoje} vendas válidas hoje",
            [
                f"Atualizado às {agora.strftime('%H:%M')}",
                "Bling conectado",
                (
                    "Sem vendas novas"
                    if pedidos_hoje == 0
                    else f"{pedidos_hoje} vendas novas até agora"
                ),
            ],
            chip="Resumo do dia",
            chip_tipo="good" if pedidos_hoje else "warning",
        )
    )

    # Mensagem fixa (não calculada) para o time — peça para eu trocar o
    # texto sempre que quiser, não depende de nenhum dado do Bling.
    cards.append(
        card_tv_lista(
            "Incentivo do time",
            "Toda venda conta!",
            "Um lembrete para o time ROPO:",
            [
                "Consistência todo dia vale mais que um pico isolado.",
                "Cada pedido bem atendido é cliente que volta a comprar.",
                "O resultado do time é maior que a soma das partes — bora juntos! 🚀",
            ],
            chip="Time ROPO",
            chip_tipo="good",
            classe_extra="tv-incentivo-card",
        )
    )

    cards.append(
        card_tv_lista(
            "Resumo operacional",
            f"{pedidos_hoje} pedidos",
            f"Ticket médio {moeda_br(ticket_medio_hoje)}",
            [
                f"Vendas válidas: {pedidos_hoje}",
                f"Canceladas: {quantidade_cancelados_hoje}",
                f"Valor cancelado: {moeda_br(valor_cancelado_hoje)}",
                f"Unidades vendidas: {unidades_vendidas_hoje:,.0f}".replace(",", "."),
            ],
            chip="Operação",
            chip_tipo="neutral",
        )
    )

    if produto_campeao is not None:
        cards.append(
            card_tv_lista(
                "Top produto do dia",
                produto_campeao["descricao"],
                f"{int(produto_campeao['unidades'])} unidades · {moeda_br(float(produto_campeao['faturamento']))}",
                [
                    f"Produto campeão: {produto_campeao['descricao']}",
                    f"Unidades: {int(produto_campeao['unidades'])}",
                    f"Faturamento: {moeda_br(float(produto_campeao['faturamento']))}",
                    f"Pedidos: {int(produto_campeao['pedidos'])}",
                ],
                chip="Produto campeão",
                chip_tipo="good",
            )
        )
    else:
        cards.append(
            card_tv(
                "Top produto do dia",
                "—",
                "Ainda não há itens sincronizados para hoje.",
                chip="Produto campeão",
                chip_tipo="neutral",
            )
        )

    if not ranking_produtos.empty:
        top_produtos_grafico = ranking_produtos.head(5)
        cards.append(
            card_tv(
                "Top produtos do dia",
                moeda_br(float(top_produtos_grafico["faturamento"].sum())),
                "Faturamento em itens dos produtos mais vendidos",
                extra_html=grafico_barras_svg(
                    list(
                        zip(
                            top_produtos_grafico["descricao"],
                            top_produtos_grafico["faturamento"].astype(float),
                        )
                    ),
                    cor_barra="#a78bfa",
                ),
                chip="Ranking de produtos",
                chip_tipo="neutral",
                classe_extra="tv-chart-card",
            )
        )

    if not receita_por_canal.empty:
        top_lojas = receita_por_canal.head(3).copy()
        # Rank e faturamento já aparecem no gráfico; a lista só acrescenta o
        # que o gráfico não mostra (vendas e ticket médio), então fica curta
        # de propósito pra não estourar a altura fixa do card.
        linhas_lojas = [
            f"{linha['canal']}: {int(linha['pedidos'])} vendas · "
            f"ticket médio {moeda_br(float(linha['ticket_medio']))}"
            for _, linha in top_lojas.iterrows()
        ]
        melhor_loja = top_lojas.iloc[0] if not top_lojas.empty else None
        cards.append(
            card_tv_lista(
                "Ranking de lojas",
                melhor_loja["canal"] if melhor_loja is not None else "—",
                "Melhor loja do dia",
                linhas_lojas,
                extra_html=grafico_barras_svg(
                    list(
                        zip(
                            top_lojas["canal"],
                            top_lojas["faturamento"].astype(float),
                        )
                    )
                ),
                chip="Faturamento / vendas",
                chip_tipo="good",
                classe_extra="tv-chart-card",
            )
        )
    else:
        cards.append(
            card_tv(
                "Ranking de lojas",
                "—",
                "Sem vendas válidas hoje.",
                chip="Melhor loja do dia",
                chip_tipo="neutral",
            )
        )

    if not receita_por_canal.empty:
        linhas_participacao = [
            f"{linha['canal']}: {pct_texto(float(linha['participacao']))} do faturamento"
            for _, linha in receita_por_canal.iterrows()
        ]
        cards.append(
            card_tv_lista(
                "Participação por loja",
                moeda_br(faturamento_hoje),
                "Share do faturamento do dia",
                linhas_participacao,
                chip="Participação",
                chip_tipo="neutral",
            )
        )
    else:
        cards.append(
            card_tv(
                "Participação por loja",
                "—",
                "Sem participação para exibir.",
                chip="Share",
                chip_tipo="neutral",
            )
        )

    if not metas_ativas.empty:
        linhas_metas = []
        for _, linha in metas_ativas.head(3).iterrows():
            titulo = linha["rotulo"] or nome_canal(linha["canal"])
            atingido = float(linha["atingido"]) if pd.notna(linha["atingido"]) else 0.0
            status, status_tipo = status_por_razao(atingido)
            linhas_metas.append(
                f"{titulo}: {moeda_br(float(linha['realizado']))}/{moeda_br(float(linha['meta']))} ({pct_texto(atingido)}) · {status}"
            )
        cards.append(
            card_tv_lista(
                "Meta do dia por loja",
                moeda_br(float(metas_ativas["meta"].sum())) if not metas_ativas.empty else "—",
                "Realizado x meta e pacing",
                linhas_metas,
                chip="Metas ativas",
                chip_tipo="good" if metas_ativas["atingido"].ge(0.9).any() else "warning",
            )
        )
    else:
        cards.append(
            card_tv(
                "Meta do dia por loja",
                "—",
                "Nenhuma meta ativa para hoje.",
                chip="Metas",
                chip_tipo="neutral",
            )
        )

    if not receita_por_canal.empty and receita_por_canal["razao_pacing"].notna().any():
        linhas_pacing = [
            f"{linha['canal']}: {pct_texto(linha['razao_pacing'])} do ritmo esperado · "
            f"{status_por_razao(linha['razao_pacing'])[0]}"
            for _, linha in receita_por_canal.iterrows()
        ]
        pior_pacing = float(receita_por_canal["razao_pacing"].min())
        cards.append(
            card_tv_lista(
                "Pacing por loja",
                pct_texto(pior_pacing),
                "Ritmo de hoje vs. média histórica no mesmo momento do dia",
                linhas_pacing,
                chip="Pior ritmo",
                chip_tipo=status_por_razao(pior_pacing)[1],
            )
        )
    else:
        cards.append(
            card_tv(
                "Pacing por loja",
                "—",
                "Ainda sem histórico suficiente para calcular o ritmo esperado.",
                chip="Ritmo",
                chip_tipo="neutral",
            )
        )

    cards.append(
        card_tv_lista(
            "Comparativos",
            moeda_br(faturamento_hoje),
            f"Hoje x ontem x semana passada",
            [
                f"Hoje: {moeda_br(faturamento_hoje)}",
                f"Ontem: {moeda_br(faturamento_ontem)} ({pct_texto(variacao_ontem)})",
                f"Semana passada: {moeda_br(faturamento_semana_passada)} ({pct_texto(variacao_semana_passada)})",
            ],
            chip="Comparação",
            chip_tipo="good" if (variacao_ontem or 0) >= 0 else "bad",
        )
    )

    dados_semana_atual = faturamento_diario.loc[
        (pd.to_datetime(faturamento_diario["dia"]).dt.date >= inicio_semana)
        & (pd.to_datetime(faturamento_diario["dia"]).dt.date <= hoje)
    ].copy()

    if not dados_semana_atual.empty:
        dados_semana_atual["dia_semana_idx"] = pd.to_datetime(
            dados_semana_atual["dia"]
        ).dt.weekday
        dados_semana_atual = dados_semana_atual.sort_values("dia")

        itens_semana = [
            (
                f"{NOMES_DIA_SEMANA_CURTO[linha['dia_semana_idx']]} "
                f"{pd.to_datetime(linha['dia']).strftime('%d/%m')}",
                float(linha["faturamento"]),
            )
            for _, linha in dados_semana_atual.iterrows()
        ]

        cards.append(
            card_tv(
                "Evolução da semana",
                moeda_br(float(dados_semana_atual["faturamento"].sum())),
                f"Faturamento diário de {inicio_semana.strftime('%d/%m')} até hoje",
                extra_html=grafico_barras_svg(itens_semana, cor_barra="#22c55e"),
                chip="Semana atual",
                chip_tipo="neutral",
                classe_extra="tv-chart-card",
            )
        )
    else:
        cards.append(
            card_tv(
                "Evolução da semana",
                "—",
                "Ainda sem faturamento registrado nesta semana.",
                chip="Semana atual",
                chip_tipo="neutral",
            )
        )

    cards.append(
        card_tv_lista(
            "Recorde do mês",
            moeda_br(float(melhor_dia_mes["faturamento"])) if melhor_dia_mes is not None else "—",
            "Melhor dia do mês até agora",
            [
                f"Melhor dia: {melhor_dia_mes['dia'].strftime('%d/%m') if melhor_dia_mes is not None else '—'}",
                f"Falta para bater: {moeda_br(falta_para_recorde)}",
                f"Tendência: ritmo {tendencia_texto}",
            ],
            chip="Recorde",
            chip_tipo="good" if falta_para_recorde == 0 else "warning",
        )
    )

    cards.append(
        card_tv(
            "Curva de tendência",
            tendencia_texto.capitalize(),
            "Média móvel de 7 dias vs. os 7 dias anteriores.",
            chip=f"Ritmo {tendencia_texto}",
            chip_tipo=tendencia_tipo,
        )
    )

    if not receita_por_canal.empty:
        linhas_projecao = []
        for _, linha in receita_por_canal.head(3).iterrows():
            nome = str(linha["canal"])
            previsao_loja = float(linha["faturamento"]) / percentual_dia if percentual_dia > 0 else float(linha["faturamento"])
            linhas_projecao.append(
                f"{nome}: {moeda_br(previsao_loja)} de fechamento · {pct_texto(float(linha['participacao']))} do dia"
            )
        cards.append(
            card_tv_lista(
                "Projeção por loja",
                moeda_br(previsao_dia),
                "Amazon / Shopee / Mercado Livre",
                linhas_projecao,
                chip="Fechamento estimado",
                chip_tipo="neutral",
            )
        )
    else:
        cards.append(
            card_tv(
                "Projeção por loja",
                moeda_br(previsao_dia),
                "Sem canal com vendas no dia.",
                chip="Fechamento",
                chip_tipo="neutral",
            )
        )

    if not vendas_por_hora.empty:
        linhas_hora = [
            f"{int(linha['hora'])}h: {int(linha['vendas'])} vendas · {moeda_br(float(linha['faturamento']))}"
            for _, linha in vendas_por_hora.head(6).iterrows()
        ]
        cards.append(
            card_tv_lista(
                "Vendas por hora",
                f"{int(vendas_por_hora['vendas'].sum())} vendas",
                "Evolução do dia",
                linhas_hora,
                chip="Pico de vendas",
                chip_tipo="neutral",
            )
        )
    elif df_hoje.empty:
        cards.append(
            card_tv(
                "Vendas por hora",
                "—",
                "Nenhuma venda registrada ainda hoje.",
                chip="Evolução",
                chip_tipo="neutral",
            )
        )
    else:
        cards.append(
            card_tv(
                "Vendas por hora",
                f"{pedidos_hoje} vendas hoje",
                "O Bling não informa o horário do pedido, só a data — "
                "este recorte por hora não está disponível.",
                chip="Sem granularidade horária",
                chip_tipo="neutral",
            )
        )

    if not ultimas_vendas.empty:
        linhas_ultimas = []
        for _, linha in ultimas_vendas.iterrows():
            prefixo_horario = (
                f"{linha['data'].strftime('%H:%M')} · " if horario_disponivel else ""
            )
            linhas_ultimas.append(
                f"{prefixo_horario}{nome_canal(linha['loja_id'])} · {moeda_br(float(linha['total']))} · {mascara_cliente(linha['cliente'])}"
            )
        cards.append(
            card_tv_lista(
                "Últimas vendas",
                f"{len(ultimas_vendas)} pedidos",
                "Sem dados sensíveis em tela pública",
                linhas_ultimas,
                chip="Recentes",
                chip_tipo="neutral",
            )
        )
    else:
        cards.append(
            card_tv(
                "Últimas vendas",
                "—",
                "Nenhum pedido válido para hoje.",
                chip="Recentes",
                chip_tipo="neutral",
            )
        )

    cards.append(
        card_tv_lista(
            "Faltam para a meta",
            moeda_br(max(float(metas_ativas["meta"].sum()) - faturamento_hoje, 0.0)) if not metas_ativas.empty else "—",
            "Valor necessário para alcançar a meta do período",
            [
                f"Meta diária: {moeda_br(float(metas_ativas['meta_diaria'].sum()) if not metas_ativas.empty else 0.0)}",
                f"Meta semanal: {moeda_br(previsao_semana)}",
                f"Meta mensal: {moeda_br(previsao_mes)}",
            ],
            chip="Meta",
            chip_tipo="warning",
        )
    )

    if not receita_por_canal.empty and receita_por_canal["razao_pacing"].notna().any():
        alertas = [
            f"{linha['canal']}: {pct_texto(linha['razao_pacing'])} do ritmo esperado"
            for _, linha in receita_por_canal.iterrows()
            if pd.notna(linha["razao_pacing"]) and linha["razao_pacing"] < 0.7
        ]
        cards.append(
            card_tv_lista(
                "Alerta de baixa performance",
                f"{len(alertas)} loja(s) abaixo do ritmo",
                "Abaixo de 70% do ritmo esperado para o momento do dia",
                alertas or ["Nenhuma loja abaixo do ritmo esperado."],
                chip="Pacing",
                chip_tipo="warning" if alertas else "good",
            )
        )

    cards.append(card_evolucao(faturamento_diario, hoje, faturamento_hoje))

    if not cards:
        cards = [
            card_tv(
                "Sem vendas por loja hoje",
                moeda_br(faturamento_hoje),
                "Nenhum pedido válido encontrado no dia.",
            )
        ]

    duracao_total = max(len(cards) * SEGUNDOS_POR_CARD, 1)
    slides_partes = []
    animacoes_partes = []

    if len(cards) == 1:
        slides = f'<div class="tv-slide">{cards[0]}</div>'
        animacoes = ""
    else:
        transicao_pct = min(1.8 / duracao_total * 100, 4)

        for indice, card in enumerate(cards):
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
                        Vendas, metas, canais, produtos e operação em tempo real.
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

    st.caption("Painel de televisão com status, metas, top produtos, lojas, projeções e últimas vendas.")


@st.fragment(run_every="2m")
def exibir_televisao() -> None:
    renderizar_tv()


exibir_televisao()
