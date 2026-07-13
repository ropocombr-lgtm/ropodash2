from __future__ import annotations

import streamlit as st

from bling_core import moeda_br

CORES = {
    "primaria": "#2563EB",
    "primaria_escura": "#1D4ED8",
    "secundaria": "#7C3AED",
    "sucesso": "#16A34A",
    "alerta": "#D97706",
    "erro": "#DC2626",
    "texto": "#0F172A",
    "texto_secundario": "#64748B",
    "borda": "#E2E8F0",
    "fundo": "#F8FAFC",
    "card": "#FFFFFF",
    "cinza_grafico": "#94A3B8",
}

ALTURA_GRAFICO_PRINCIPAL = 390
ALTURA_GRAFICO_SECUNDARIO = 340


def injetar_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --primary: #2563EB;
            --primary-dark: #1D4ED8;
            --success: #16A34A;
            --warning: #D97706;
            --danger: #DC2626;
            --text: #0F172A;
            --text-secondary: #64748B;
            --border: #E2E8F0;
            --background: #F8FAFC;
            --card: #FFFFFF;
        }

        .stApp {
            background-color: var(--background);
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1500px;
        }

        h1, h2, h3, h4 {
            color: var(--text);
            letter-spacing: -0.02em;
        }

        .dashboard-header {
            background: linear-gradient(
                135deg,
                #0F172A 0%,
                #1E3A8A 55%,
                #2563EB 100%
            );
            border-radius: 20px;
            padding: 24px 28px;
            margin-bottom: 18px;
            color: white;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.15);
        }

        .dashboard-header-title {
            font-size: 1.7rem;
            line-height: 1.15;
            font-weight: 750;
            margin-bottom: 6px;
        }

        .dashboard-header-subtitle {
            font-size: 0.92rem;
            color: rgba(255, 255, 255, 0.78);
        }

        .dashboard-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 22px;
        }

        .dashboard-badge {
            background: white;
            border: 1px solid var(--border);
            border-radius: 999px;
            color: var(--text-secondary);
            font-size: 0.78rem;
            padding: 6px 11px;
        }

        .section-header {
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
            margin-top: 28px;
            margin-bottom: 16px;
        }

        .section-icon {
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #EFF6FF;
            border-radius: 10px;
            font-size: 1rem;
        }

        .section-title {
            color: var(--text);
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .section-description {
            color: var(--text-secondary);
            font-size: 0.78rem;
            margin-top: 2px;
        }

        .kpi-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 17px 18px;
            min-height: 128px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.04);
        }

        .small-label {
            color: var(--text-secondary);
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.025em;
            text-transform: uppercase;
        }

        .big-number {
            color: var(--text);
            font-size: 1.75rem;
            font-weight: 750;
            letter-spacing: -0.035em;
            line-height: 1.15;
            margin: 7px 0 5px;
        }

        .kpi-subtitle {
            color: var(--text-secondary);
            font-size: 0.76rem;
            line-height: 1.3;
            min-height: 20px;
        }

        .delta {
            display: inline-flex;
            align-items: center;
            width: fit-content;
            border-radius: 999px;
            padding: 4px 8px;
            font-size: 0.72rem;
            font-weight: 700;
            margin-top: 7px;
        }

        .delta.good {
            color: #15803D;
            background: #DCFCE7;
        }

        .delta.bad {
            color: #B91C1C;
            background: #FEE2E2;
        }

        .delta.warning {
            color: #B45309;
            background: #FEF3C7;
        }

        .delta.neutral {
            color: #475569;
            background: #F1F5F9;
        }

        .insight-card {
            background: white;
            border: 1px solid var(--border);
            border-left: 4px solid var(--primary);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 10px;
        }

        .insight-title {
            color: var(--text);
            font-size: 0.85rem;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .insight-text {
            color: var(--text-secondary);
            font-size: 0.82rem;
            line-height: 1.45;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background: white;
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 5px;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 10px;
            padding: 9px 16px;
            height: auto;
            font-weight: 600;
        }

        .stTabs [aria-selected="true"] {
            background: var(--primary) !important;
            color: white !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--border);
        }

        div[data-testid="stExpander"] {
            background: white;
            border-color: var(--border);
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def cabecalho_dashboard(titulo: str, subtitulo: str) -> None:
    st.markdown(
        f"""
        <div class="dashboard-header">
            <div class="dashboard-header-title">{titulo}</div>
            <div class="dashboard-header-subtitle">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badges_dashboard(itens: list[str]) -> None:
    badges_html = "".join(
        f'<div class="dashboard-badge">{item}</div>' for item in itens
    )

    st.markdown(
        f'<div class="dashboard-badges">{badges_html}</div>',
        unsafe_allow_html=True,
    )


def cabecalho_secao(
    titulo: str,
    descricao: str = "",
    icone: str = "📊",
) -> None:
    st.markdown(
        f"""
        <div class="section-header">
            <div class="section-icon">{icone}</div>
            <div>
                <div class="section-title">{titulo}</div>
                <div class="section-description">{descricao}</div>
            </div>
        </div>
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
    icones_delta = {
        "good": "▲",
        "bad": "▼",
        "warning": "●",
        "neutral": "—",
    }

    delta_html = ""

    if delta:
        icone = icones_delta.get(delta_tipo, "—")

        delta_html = f"""
        <div class="delta {delta_tipo}">
            {icone} {delta}
        </div>
        """

    st.markdown(
        f"""
        <div class="kpi-card">
            <div>
                <div class="small-label">{titulo}</div>
                <div class="big-number">{valor}</div>
                <div class="kpi-subtitle">{subtitulo or "&nbsp;"}</div>
            </div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_insight(titulo: str, texto: str, tipo: str = "primary") -> None:
    cores_insight = {
        "primary": CORES["primaria"],
        "good": CORES["sucesso"],
        "warning": CORES["alerta"],
        "bad": CORES["erro"],
    }

    cor = cores_insight.get(tipo, cores_insight["primary"])

    st.markdown(
        f"""
        <div class="insight-card" style="border-left-color: {cor};">
            <div class="insight-title">{titulo}</div>
            <div class="insight-text">{texto}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def aplicar_padrao_grafico(
    figura,
    altura: int = ALTURA_GRAFICO_SECUNDARIO,
    moeda_eixo_y: bool = False,
    percentual_eixo_y: bool = False,
    moeda_eixo_x: bool = False,
    percentual_eixo_x: bool = False,
):
    figura.update_layout(
        template="plotly_white",
        height=altura,
        font={
            "family": "Inter, Arial, sans-serif",
            "color": CORES["texto"],
            "size": 12,
        },
        title={
            "font": {"size": 16, "color": CORES["texto"]},
            "x": 0,
            "xanchor": "left",
        },
        margin={"l": 20, "r": 20, "t": 58, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hoverlabel={
            "bgcolor": "#0F172A",
            "font_color": "#FFFFFF",
            "bordercolor": "#0F172A",
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "title_text": "",
        },
    )

    figura.update_xaxes(
        showgrid=False,
        linecolor=CORES["borda"],
        tickfont={"color": CORES["texto_secundario"]},
        title_font={"color": CORES["texto_secundario"]},
    )

    figura.update_yaxes(
        gridcolor="#F1F5F9",
        zeroline=False,
        tickfont={"color": CORES["texto_secundario"]},
        title_font={"color": CORES["texto_secundario"]},
    )

    if moeda_eixo_y:
        figura.update_yaxes(tickprefix="R$ ", separatethousands=True)

    if percentual_eixo_y:
        figura.update_yaxes(tickformat=".0%")

    if moeda_eixo_x:
        figura.update_xaxes(tickprefix="R$ ", separatethousands=True)

    if percentual_eixo_x:
        figura.update_xaxes(tickformat=".0%")

    return figura


def card_meta(
    canal: str,
    realizado: float,
    meta: float,
    classificacao: str,
    subtitulo: str = "",
) -> None:
    atingimento = realizado / meta if meta else 0
    progresso = min(max(atingimento, 0), 1)

    cores_status = {
        "Acima da meta": CORES["sucesso"],
        "Dentro do ritmo": CORES["primaria"],
        "Risco moderado": CORES["alerta"],
        "Risco alto": CORES["erro"],
        "Período encerrado": CORES["texto_secundario"],
        "Sem meta": CORES["texto_secundario"],
        "—": CORES["texto_secundario"],
    }

    cor = cores_status.get(classificacao, CORES["texto_secundario"])

    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="small-label">{canal}</div>
            <div class="big-number">{moeda_br(realizado)}</div>
            <div class="kpi-subtitle">
                Meta: {moeda_br(meta)}
                {f" · {subtitulo}" if subtitulo else ""}
            </div>
            <div style="
                height: 8px;
                background: #E2E8F0;
                border-radius: 999px;
                overflow: hidden;
                margin: 12px 0 8px;
            ">
                <div style="
                    width: {progresso * 100:.0f}%;
                    height: 100%;
                    background: {cor};
                    border-radius: 999px;
                "></div>
            </div>
            <div style="
                display: flex;
                justify-content: space-between;
                color: #64748B;
                font-size: 0.75rem;
            ">
                <span>{atingimento:.0%} atingido</span>
                <span style="color: {cor}; font-weight: 700;">
                    {classificacao}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
