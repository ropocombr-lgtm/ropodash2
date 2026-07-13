from __future__ import annotations

import hashlib
import hmac
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import Client, create_client


# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="Dashboard Bling",
    page_icon="📊",
    layout="wide",
)

AUTHORIZE_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
TOKEN_URL = "https://api.bling.com.br/Api/v3/oauth/token"
API_BASE_URL = "https://api.bling.com.br/Api/v3"

TOKEN_ROW_ID = 1


# =========================================================
# SEGREDOS
# =========================================================

def carregar_configuracoes() -> dict[str, str]:
    try:
        return {
            "client_id": st.secrets["bling"]["client_id"],
            "client_secret": st.secrets["bling"]["client_secret"],
            "redirect_uri": st.secrets["bling"]["redirect_uri"],
            "supabase_url": st.secrets["supabase"]["url"],
            "supabase_key": st.secrets["supabase"]["service_role_key"],
        }
    except (KeyError, StreamlitSecretNotFoundError) as erro:
        st.error(
            "As credenciais ainda não foram configuradas nos Secrets "
            "do Streamlit."
        )
        st.code(str(erro))
        st.stop()


CONFIG = carregar_configuracoes()


# =========================================================
# SUPABASE
# =========================================================

@st.cache_resource
def conectar_supabase() -> Client:
    return create_client(
        CONFIG["supabase_url"],
        CONFIG["supabase_key"],
    )


supabase = conectar_supabase()


def ler_tokens() -> dict[str, Any] | None:
    resposta = (
        supabase.table("bling_tokens")
        .select("*")
        .eq("id", TOKEN_ROW_ID)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return None

    return resposta.data[0]


def salvar_tokens(tokens: dict[str, Any]) -> None:
    expires_in = int(tokens.get("expires_in", 3600))

    # Renova um pouco antes do vencimento real.
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=max(expires_in - 120, 60))
    )

    registro = {
        "id": TOKEN_ROW_ID,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    (
        supabase.table("bling_tokens")
        .upsert(registro, on_conflict="id")
        .execute()
    )


# =========================================================
# PROTEÇÃO DO OAUTH STATE
# =========================================================

def criar_oauth_state() -> str:
    timestamp = str(int(time.time()))

    assinatura = hmac.new(
        CONFIG["client_secret"].encode("utf-8"),
        timestamp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{timestamp}.{assinatura}"


def validar_oauth_state(state: str, validade_segundos: int = 600) -> bool:
    try:
        timestamp, assinatura_recebida = state.split(".", maxsplit=1)
        momento = int(timestamp)

        if abs(int(time.time()) - momento) > validade_segundos:
            return False

        assinatura_esperada = hmac.new(
            CONFIG["client_secret"].encode("utf-8"),
            timestamp.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(
            assinatura_recebida,
            assinatura_esperada,
        )

    except (ValueError, AttributeError):
        return False


def gerar_url_autorizacao() -> str:
    parametros = {
        "response_type": "code",
        "client_id": CONFIG["client_id"],
        "state": criar_oauth_state(),
    }

    return f"{AUTHORIZE_URL}?{urlencode(parametros)}"


# =========================================================
# TOKENS DO BLING
# =========================================================

def solicitar_token(dados: dict[str, str]) -> dict[str, Any]:
    resposta = requests.post(
        TOKEN_URL,
        data=dados,
        auth=(
            CONFIG["client_id"],
            CONFIG["client_secret"],
        ),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "enable-jwt": "1",
        },
        timeout=30,
    )

    if not resposta.ok:
        raise RuntimeError(
            f"Erro ao solicitar token: "
            f"{resposta.status_code} - {resposta.text}"
        )

    return resposta.json()


def trocar_codigo_por_token(code: str) -> None:
    tokens = solicitar_token(
        {
            "grant_type": "authorization_code",
            "code": code,
        }
    )

    salvar_tokens(tokens)


def renovar_access_token(refresh_token: str) -> str:
    tokens = solicitar_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )

    salvar_tokens(tokens)

    return tokens["access_token"]


def interpretar_data_iso(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def obter_access_token(forcar_renovacao: bool = False) -> str:
    tokens = ler_tokens()

    if not tokens:
        raise RuntimeError("O dashboard ainda não foi conectado ao Bling.")

    expires_at = interpretar_data_iso(tokens["expires_at"])
    agora = datetime.now(timezone.utc)

    token_valido = expires_at > agora + timedelta(minutes=2)

    if token_valido and not forcar_renovacao:
        return tokens["access_token"]

    return renovar_access_token(tokens["refresh_token"])


# =========================================================
# CALLBACK DO BLING
# =========================================================

def processar_callback_oauth() -> None:
    code = st.query_params.get("code")
    state = st.query_params.get("state")
    erro = st.query_params.get("error")

    if erro:
        st.error(f"O Bling não autorizou a conexão: {erro}")
        st.query_params.clear()
        st.stop()

    if not code:
        return

    if not state or not validar_oauth_state(state):
        st.error("A validação de segurança da conexão falhou.")
        st.query_params.clear()
        st.stop()

    try:
        trocar_codigo_por_token(code)

        # Impede que o mesmo authorization code seja usado novamente.
        st.query_params.clear()

        st.success("Bling conectado com sucesso.")
        st.rerun()

    except Exception as erro_callback:
        st.error("Não foi possível finalizar a conexão com o Bling.")
        st.exception(erro_callback)
        st.stop()


processar_callback_oauth()


# =========================================================
# CLIENTE DA API
# =========================================================

def consultar_bling(
    endpoint: str,
    parametros: dict[str, Any] | None = None,
) -> dict[str, Any]:
    access_token = obter_access_token()

    for tentativa in range(2):
        resposta = requests.get(
            f"{API_BASE_URL}{endpoint}",
            params=parametros,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "enable-jwt": "1",
            },
            timeout=40,
        )

        if resposta.status_code == 401 and tentativa == 0:
            access_token = obter_access_token(forcar_renovacao=True)
            continue

        if resposta.status_code == 429:
            raise RuntimeError(
                "O limite de requisições do Bling foi atingido. "
                "Aguarde alguns instantes antes de atualizar novamente."
            )

        if not resposta.ok:
            raise RuntimeError(
                f"Erro na API do Bling: "
                f"{resposta.status_code} - {resposta.text}"
            )

        return resposta.json()

    raise RuntimeError("Não foi possível autenticar a requisição no Bling.")


def buscar_pedidos(
    data_inicial: date,
    data_final: date,
) -> list[dict[str, Any]]:
    pagina = 1
    pedidos: list[dict[str, Any]] = []

    while True:
        resposta = consultar_bling(
            "/pedidos/vendas",
            {
                "dataInicial": data_inicial.isoformat(),
                "dataFinal": data_final.isoformat(),
                "pagina": pagina,
                "limite": 100,
            },
        )

        lote = resposta.get("data", [])

        if not lote:
            break

        pedidos.extend(lote)

        if len(lote) < 100:
            break

        pagina += 1

        # Mantém o consumo abaixo de três chamadas por segundo.
        time.sleep(0.4)

    return pedidos


# =========================================================
# TRATAMENTO DOS DADOS
# =========================================================

def transformar_pedidos(
    pedidos: list[dict[str, Any]],
) -> pd.DataFrame:
    registros = []

    for pedido in pedidos:
        contato = pedido.get("contato") or {}
        situacao = pedido.get("situacao") or {}
        loja = pedido.get("loja") or {}

        registros.append(
            {
                "id": pedido.get("id"),
                "numero": pedido.get("numero"),
                "data": pedido.get("data"),
                "cliente": contato.get("nome", "Não informado"),
                "situacao": situacao.get("valor", "Não informada"),
                "loja_id": loja.get("id"),
                "total_produtos": pedido.get("totalProdutos", 0),
                "total": pedido.get("total", 0),
            }
        )

    dataframe = pd.DataFrame(registros)

    if dataframe.empty:
        return dataframe

    dataframe["data"] = pd.to_datetime(
        dataframe["data"],
        errors="coerce",
    )

    dataframe["total"] = pd.to_numeric(
        dataframe["total"],
        errors="coerce",
    ).fillna(0)

    dataframe["total_produtos"] = pd.to_numeric(
        dataframe["total_produtos"],
        errors="coerce",
    ).fillna(0)

    return dataframe


@st.cache_data(ttl=300, show_spinner=False)
def carregar_dataframe(
    data_inicial_iso: str,
    data_final_iso: str,
) -> pd.DataFrame:
    pedidos = buscar_pedidos(
        date.fromisoformat(data_inicial_iso),
        date.fromisoformat(data_final_iso),
    )

    return transformar_pedidos(pedidos)


def moeda_br(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


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

    situacao_normalizada = (
        df["situacao"]
        .fillna("")
        .astype(str)
        .str.lower()
    )

    cancelados = situacao_normalizada.str.contains(
        "cancel",
        regex=False,
    )

    df_validos = df.loc[~cancelados].copy()

    quantidade_pedidos = int(df_validos["id"].nunique())
    faturamento = float(df_validos["total"].sum())

    ticket_medio = (
        faturamento / quantidade_pedidos
        if quantidade_pedidos
        else 0
    )

    quantidade_cancelados = int(df.loc[cancelados, "id"].nunique())

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


exibir_dashboard()
