from __future__ import annotations

import hashlib
import hmac
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from supabase import Client, create_client

AUTHORIZE_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
TOKEN_URL = "https://api.bling.com.br/Api/v3/oauth/token"
API_BASE_URL = "https://api.bling.com.br/Api/v3"

# Contas Bling conectadas neste dashboard. Cada uma tem seu próprio app
# OAuth (client_id/client_secret/redirect_uri, configurados em
# st.secrets["bling"][conta]) e seu próprio conjunto de tokens — os
# pedido_id/item_id do Bling são internos de cada conta e podem colidir
# entre elas, por isso "conta" é parte da chave em toda tabela que guarda
# pedido/item.
CONTAS_BLING = ["marketplaces", "loja_oficial"]

NOMES_CONTA = {
    "marketplaces": "Marketplaces",
    "loja_oficial": "Loja Oficial",
    "manual": "B2B Manual",
}

# Pseudo-conta usada pelos pedidos de B2B cadastrados manualmente (não vêm
# do Bling, então não tem OAuth nem client_id/secret em st.secrets — por
# isso fica de fora de CONTAS_BLING).
CONTA_MANUAL = "manual"

# IDs de situação confirmados manualmente no Bling do cliente (a API não
# expõe o nome da situação sem o escopo "Situações", que este app não tem).
SITUACOES_CANCELADAS = {12}

NOMES_SITUACAO_CONHECIDAS = {
    9: "Atendido",
    12: "Cancelado",
}

# Mapeamento manual: a API não expõe nome de canal sem o escopo
# "Canais de venda", que este app não tem (exigiria reautorizar). Aninhado
# por conta porque o mesmo número de loja_id pode existir em contas Bling
# diferentes sem ser o mesmo canal.
NOMES_CANAL_CONHECIDOS: dict[str, dict[str, str]] = {
    "marketplaces": {
        "205971033": "Amazon",
        "205939074": "Shopee",
        "205971561": "Mercado Livre",
    },
    "loja_oficial": {},
}

# Agrupamentos usados para metas que cobrem mais de um canal ao mesmo
# tempo (ex.: uma meta única de "Marketplace" para Shopee + Mercado Livre).
# Também aninhado por conta — agrupar canais de contas diferentes numa
# mesma meta não é suportado hoje.
GRUPOS_CANAL: dict[str, dict[str, list[str]]] = {
    "marketplaces": {
        "Marketplace": ["205939074", "205971561"],
    },
    "loja_oficial": {},
}


def nome_canal(conta: str, loja_id: Any) -> str:
    if loja_id is None:
        return "Sem canal"

    chave = str(loja_id)
    nomes_conhecidos = NOMES_CANAL_CONHECIDOS.get(conta, {})
    grupos = GRUPOS_CANAL.get(conta, {})

    if chave in nomes_conhecidos:
        return nomes_conhecidos[chave]

    if chave in grupos or not chave.isdigit():
        return chave

    return f"Canal {chave}"


def canais_do_grupo(conta: str, canal: str) -> list[str]:
    return GRUPOS_CANAL.get(conta, {}).get(canal, [canal])


# Valor especial de "canal" pra uma meta cobrir a conta inteira (todos os
# canais, incluindo os que ainda não existem hoje), em vez de um único
# canal ou grupo fixo de canais. Não é um loja_id nem precisa estar em
# NOMES_CANAL_CONHECIDOS/GRUPOS_CANAL — nome_canal já devolve qualquer
# texto que não seja dígito puro, então nenhuma outra mudança é necessária
# pra exibir esse rótulo.
CANAL_CONTA_INTEIRA = "Conta inteira"


def nome_situacao(situacao_id: int | None) -> str:
    if situacao_id is None:
        return "Não informada"

    return NOMES_SITUACAO_CONHECIDAS.get(
        situacao_id,
        f"Situação {situacao_id}",
    )


# O Bling é um ERP brasileiro e as datas dos pedidos seguem o calendário de
# São Paulo. Usar a hora local do servidor (`date.today()`) sem fuso horário
# faz o dashboard "virar o dia" cedo demais sempre que o servidor roda em
# UTC, escondendo as últimas horas de vendas de cada dia.
FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def agora_sao_paulo() -> datetime:
    return datetime.now(FUSO_SAO_PAULO)


def hoje_sao_paulo() -> date:
    return agora_sao_paulo().date()


# =========================================================
# SEGREDOS
# =========================================================

def carregar_configuracoes() -> dict[str, Any]:
    try:
        bling_contas = {
            conta: {
                "client_id": st.secrets["bling"][conta]["client_id"],
                "client_secret": st.secrets["bling"][conta]["client_secret"],
                "redirect_uri": st.secrets["bling"][conta]["redirect_uri"],
            }
            for conta in CONTAS_BLING
        }

        return {
            "bling": bling_contas,
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


def ler_tokens(conta: str) -> dict[str, Any] | None:
    resposta = (
        supabase.table("bling_tokens")
        .select("*")
        .eq("conta", conta)
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return None

    return resposta.data[0]


def salvar_tokens(conta: str, tokens: dict[str, Any]) -> None:
    expires_in = int(tokens.get("expires_in", 3600))

    # Renova um pouco antes do vencimento real.
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=max(expires_in - 120, 60))
    )

    registro = {
        "conta": conta,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": expires_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    (
        supabase.table("bling_tokens")
        .upsert(registro, on_conflict="conta")
        .execute()
    )


def contas_conectadas() -> list[str]:
    return [conta for conta in CONTAS_BLING if ler_tokens(conta) is not None]


# =========================================================
# PROTEÇÃO DO OAUTH STATE
# =========================================================

def criar_oauth_state(conta: str) -> str:
    timestamp = str(int(time.time()))
    segredo = CONFIG["bling"][conta]["client_secret"]

    assinatura = hmac.new(
        segredo.encode("utf-8"),
        f"{conta}.{timestamp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{conta}.{timestamp}.{assinatura}"


def validar_oauth_state(state: str, validade_segundos: int = 600) -> str | None:
    try:
        conta, timestamp, assinatura_recebida = state.split(".", maxsplit=2)

        if conta not in CONFIG["bling"]:
            return None

        momento = int(timestamp)

        if abs(int(time.time()) - momento) > validade_segundos:
            return None

        segredo = CONFIG["bling"][conta]["client_secret"]

        assinatura_esperada = hmac.new(
            segredo.encode("utf-8"),
            f"{conta}.{timestamp}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
            return None

        return conta

    except (ValueError, AttributeError):
        return None


def gerar_url_autorizacao(conta: str) -> str:
    parametros = {
        "response_type": "code",
        "client_id": CONFIG["bling"][conta]["client_id"],
        "state": criar_oauth_state(conta),
    }

    return f"{AUTHORIZE_URL}?{urlencode(parametros)}"


# =========================================================
# TOKENS DO BLING
# =========================================================

def solicitar_token(conta: str, dados: dict[str, str]) -> dict[str, Any]:
    resposta = requests.post(
        TOKEN_URL,
        data=dados,
        auth=(
            CONFIG["bling"][conta]["client_id"],
            CONFIG["bling"][conta]["client_secret"],
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


def trocar_codigo_por_token(conta: str, code: str) -> None:
    tokens = solicitar_token(
        conta,
        {
            "grant_type": "authorization_code",
            "code": code,
        },
    )

    salvar_tokens(conta, tokens)


def renovar_access_token(conta: str, refresh_token: str) -> str:
    tokens = solicitar_token(
        conta,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    salvar_tokens(conta, tokens)

    return tokens["access_token"]


def interpretar_data_iso(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def obter_access_token(conta: str, forcar_renovacao: bool = False) -> str:
    tokens = ler_tokens(conta)

    if not tokens:
        raise RuntimeError(
            f"A conta \"{NOMES_CONTA.get(conta, conta)}\" ainda não foi "
            "conectada ao Bling."
        )

    expires_at = interpretar_data_iso(tokens["expires_at"])
    agora = datetime.now(timezone.utc)

    token_valido = expires_at > agora + timedelta(minutes=2)

    if token_valido and not forcar_renovacao:
        return tokens["access_token"]

    try:
        return renovar_access_token(conta, tokens["refresh_token"])
    except RuntimeError:
        # Várias páginas (dashboard, tempo real, televisão) renovam o mesmo
        # token compartilhado sem trava. Se outra sessão já rotacionou o
        # refresh_token entre a leitura acima e esta chamada, esta tentativa
        # falha; antes de propagar o erro, relê o banco — se outra sessão já
        # salvou um token válido nesse meio-tempo, usamos ele.
        tokens_atuais = ler_tokens(conta)

        if tokens_atuais:
            expires_at_atual = interpretar_data_iso(tokens_atuais["expires_at"])

            if expires_at_atual > datetime.now(timezone.utc) + timedelta(minutes=2):
                return tokens_atuais["access_token"]

        raise


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

    conta = validar_oauth_state(state) if state else None

    if conta is None:
        st.error("A validação de segurança da conexão falhou.")
        st.query_params.clear()
        st.stop()

    try:
        trocar_codigo_por_token(conta, code)

        # Impede que o mesmo authorization code seja usado novamente.
        st.query_params.clear()

        st.success(
            f"Bling ({NOMES_CONTA.get(conta, conta)}) conectado com sucesso."
        )
        st.rerun()

    except Exception as erro_callback:
        st.error("Não foi possível finalizar a conexão com o Bling.")
        st.exception(erro_callback)
        st.stop()


# =========================================================
# CLIENTE DA API
# =========================================================

MAX_TENTATIVAS_429 = 6


def consultar_bling(
    conta: str,
    endpoint: str,
    parametros: dict[str, Any] | None = None,
) -> dict[str, Any]:
    access_token = obter_access_token(conta)

    tentativa_auth_usada = False
    tentativas_429 = 0

    while True:
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

        if resposta.status_code == 401 and not tentativa_auth_usada:
            tentativa_auth_usada = True
            access_token = obter_access_token(conta, forcar_renovacao=True)
            continue

        if resposta.status_code == 429:
            tentativas_429 += 1

            if tentativas_429 > MAX_TENTATIVAS_429:
                raise RuntimeError(
                    "O limite de requisições do Bling foi atingido "
                    "repetidamente. Aguarde alguns minutos antes de "
                    "atualizar novamente."
                )

            espera = float(
                resposta.headers.get("Retry-After", 5 * tentativas_429)
            )

            time.sleep(espera)
            continue

        if not resposta.ok:
            raise RuntimeError(
                f"Erro na API do Bling: "
                f"{resposta.status_code} - {resposta.text}"
            )

        return resposta.json()


def buscar_pedidos(
    conta: str,
    data_inicial: date,
    data_final: date,
) -> list[dict[str, Any]]:
    pagina = 1
    pedidos: list[dict[str, Any]] = []

    while True:
        resposta = consultar_bling(
            conta,
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
    conta: str,
) -> pd.DataFrame:
    registros = []

    for pedido in pedidos:
        contato = pedido.get("contato") or {}
        situacao = pedido.get("situacao") or {}
        loja = pedido.get("loja") or {}

        situacao_id = situacao.get("id")

        registros.append(
            {
                "id": pedido.get("id"),
                "conta": conta,
                "numero": pedido.get("numero"),
                "data": pedido.get("data"),
                "cliente_id": contato.get("id"),
                "cliente": contato.get("nome", "Não informado"),
                "situacao_id": situacao_id,
                "situacao": nome_situacao(situacao_id),
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
    conta: str,
    data_inicial_iso: str,
    data_final_iso: str,
) -> pd.DataFrame:
    pedidos = buscar_pedidos(
        conta,
        date.fromisoformat(data_inicial_iso),
        date.fromisoformat(data_final_iso),
    )

    return transformar_pedidos(pedidos, conta)


def carregar_dataframe_multi(
    contas: list[str],
    data_inicial_iso: str,
    data_final_iso: str,
) -> pd.DataFrame:
    partes = [
        carregar_dataframe(conta, data_inicial_iso, data_final_iso)
        for conta in contas
    ]

    partes_validas = [parte for parte in partes if not parte.empty]

    if not partes_validas:
        return pd.DataFrame()

    return pd.concat(partes_validas, ignore_index=True)


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_historico_completo(
    conta: str,
    data_final_iso: str,
    anos: int,
) -> pd.DataFrame:
    data_final = date.fromisoformat(data_final_iso)
    inicio_total = data_final.replace(year=data_final.year - anos)

    partes = []
    cursor = inicio_total

    # O Bling recomenda não enviar filtros de data acima de 1 ano numa
    # única consulta, então buscamos em janelas anuais.
    while cursor <= data_final:
        fim_janela = min(
            cursor + timedelta(days=364),
            data_final,
        )

        partes.append(
            carregar_dataframe(
                conta,
                cursor.isoformat(),
                fim_janela.isoformat(),
            )
        )

        cursor = fim_janela + timedelta(days=1)

    partes_validas = [parte for parte in partes if not parte.empty]

    if not partes_validas:
        return pd.DataFrame()

    return pd.concat(partes_validas, ignore_index=True)


def carregar_historico_completo_multi(
    contas: list[str],
    data_final_iso: str,
    anos: int,
) -> pd.DataFrame:
    partes = [
        carregar_historico_completo(conta, data_final_iso, anos)
        for conta in contas
    ]

    partes_validas = [parte for parte in partes if not parte.empty]

    if not partes_validas:
        return pd.DataFrame()

    return pd.concat(partes_validas, ignore_index=True)


def moeda_br(valor: float) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


# =========================================================
# HISTÓRICO DIÁRIO DE KPIS
# =========================================================

def calcular_historico_diario(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "dia",
                "conta",
                "canal",
                "pedidos",
                "cancelados",
                "faturamento_bruto",
                "faturamento_valido",
            ]
        )

    dados = df.dropna(subset=["data"]).copy()
    dados["dia"] = dados["data"].dt.date
    dados["canal"] = dados["loja_id"].fillna("Sem canal").astype(str)
    dados["cancelado"] = dados["situacao_id"].isin(SITUACOES_CANCELADAS)

    agregado = (
        dados.groupby(["dia", "conta", "canal"], as_index=False)
        .agg(
            pedidos=("id", "nunique"),
            cancelados=("cancelado", "sum"),
            faturamento_bruto=("total", "sum"),
        )
    )

    faturamento_valido = (
        dados.loc[~dados["cancelado"]]
        .groupby(["dia", "conta", "canal"], as_index=False)
        .agg(faturamento_valido=("total", "sum"))
    )

    agregado = agregado.merge(
        faturamento_valido,
        on=["dia", "conta", "canal"],
        how="left",
    )

    agregado["faturamento_valido"] = agregado["faturamento_valido"].fillna(
        0
    )

    return agregado


def salvar_historico_diario(agregado: pd.DataFrame) -> None:
    if agregado.empty:
        return

    registros = [
        {
            "data": linha["dia"].isoformat(),
            "conta": linha["conta"],
            "canal": linha["canal"],
            "pedidos": int(linha["pedidos"]),
            "cancelados": int(linha["cancelados"]),
            "faturamento_bruto": float(linha["faturamento_bruto"]),
            "faturamento_valido": float(linha["faturamento_valido"]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        for _, linha in agregado.iterrows()
    ]

    supabase.table("historico_diario").upsert(
        registros,
        on_conflict="data,canal,conta",
    ).execute()


def ler_historico_diario(
    data_inicial: date | None = None,
    conta: str | None = None,
) -> pd.DataFrame:
    consulta = supabase.table("historico_diario").select("*")

    if data_inicial is not None:
        consulta = consulta.gte("data", data_inicial.isoformat())

    if conta is not None:
        consulta = consulta.eq("conta", conta)

    resposta = consulta.execute()
    dados = resposta.data or []

    colunas = [
        "data",
        "conta",
        "canal",
        "pedidos",
        "cancelados",
        "faturamento_bruto",
        "faturamento_valido",
    ]

    if not dados:
        return pd.DataFrame(columns=colunas)

    historico = pd.DataFrame(dados)
    historico["data"] = pd.to_datetime(historico["data"]).dt.date

    return historico[colunas]


# =========================================================
# ITENS DOS PEDIDOS (produto)
# =========================================================

def buscar_detalhe_pedido(conta: str, pedido_id: int) -> dict[str, Any]:
    resposta = consultar_bling(conta, f"/pedidos/vendas/{pedido_id}")
    return resposta.get("data", {})


def pedidos_ja_sincronizados(conta: str, pedido_ids: list[int]) -> set[int]:
    sincronizados: set[int] = set()

    for lote in range(0, len(pedido_ids), 500):
        pedaco = pedido_ids[lote : lote + 500]

        resposta = (
            supabase.table("pedidos_sincronizados")
            .select("pedido_id")
            .eq("conta", conta)
            .in_("pedido_id", pedaco)
            .execute()
        )

        sincronizados.update(
            linha["pedido_id"] for linha in (resposta.data or [])
        )

    return sincronizados


def sincronizar_itens_pedidos(
    df: pd.DataFrame,
    conta: str,
    limite_pedidos: int | None = None,
    progresso: Any = None,
    pausa_segundos: float = 0.4,
) -> int:
    if df.empty:
        return 0

    pedidos_unicos = (
        df.dropna(subset=["id"])
        .drop_duplicates(subset=["id"])
        .set_index("id")
    )

    pendentes = sorted(
        set(pedidos_unicos.index)
        - pedidos_ja_sincronizados(conta, list(pedidos_unicos.index))
    )

    if limite_pedidos is not None:
        pendentes = pendentes[:limite_pedidos]

    total_pendentes = len(pendentes)

    for indice, pedido_id in enumerate(pendentes):
        contexto = pedidos_unicos.loc[pedido_id]

        detalhe = buscar_detalhe_pedido(conta, pedido_id)
        itens = detalhe.get("itens") or []

        registros_item = [
            {
                "conta": conta,
                "pedido_id": int(pedido_id),
                "item_id": item.get("id"),
                "produto_id": (item.get("produto") or {}).get("id"),
                "sku": item.get("codigo"),
                "descricao": item.get("descricao"),
                "quantidade": item.get("quantidade", 0),
                "valor_unitario": item.get("valor", 0),
                "desconto": item.get("desconto", 0),
                "data": contexto["data"].date().isoformat(),
                "canal": str(contexto["loja_id"]),
                "situacao_id": (
                    int(contexto["situacao_id"])
                    if pd.notna(contexto["situacao_id"])
                    else None
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            for item in itens
            if item.get("id") is not None
        ]

        if registros_item:
            supabase.table("itens_pedidos").upsert(
                registros_item,
                on_conflict="conta,pedido_id,item_id",
            ).execute()

        supabase.table("pedidos_sincronizados").upsert(
            {
                "conta": conta,
                "pedido_id": int(pedido_id),
                "sincronizado_em": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="conta,pedido_id",
        ).execute()

        if progresso is not None:
            progresso(indice + 1, total_pendentes)

        time.sleep(pausa_segundos)

    return total_pendentes


def sincronizar_itens_pedidos_multi(
    df: pd.DataFrame,
    limite_pedidos: int | None = None,
    progresso: Any = None,
    pausa_segundos: float = 0.4,
) -> int:
    if df.empty or "conta" not in df.columns:
        return 0

    total_sincronizados = 0

    for conta, grupo in df.groupby("conta"):
        # Pedidos manuais (conta "manual") não existem no Bling — não têm
        # detalhe de itens pra buscar e não têm client_id/secret configurado,
        # então tentar sincronizá-los quebraria com KeyError/RuntimeError.
        if conta not in CONTAS_BLING:
            continue

        total_sincronizados += sincronizar_itens_pedidos(
            grupo,
            conta,
            limite_pedidos=limite_pedidos,
            progresso=progresso,
            pausa_segundos=pausa_segundos,
        )

    return total_sincronizados


@st.cache_data(ttl=300, show_spinner=False)
def ler_itens_pedidos(
    data_inicial: date,
    data_final: date,
    conta: str | None = None,
) -> pd.DataFrame:
    consulta = (
        supabase.table("itens_pedidos")
        .select("*")
        .gte("data", data_inicial.isoformat())
        .lte("data", data_final.isoformat())
    )

    if conta is not None:
        consulta = consulta.eq("conta", conta)

    resposta = consulta.execute()

    dados = resposta.data or []

    colunas = [
        "pedido_id",
        "conta",
        "produto_id",
        "sku",
        "descricao",
        "quantidade",
        "valor_unitario",
        "desconto",
        "data",
        "canal",
        "situacao_id",
    ]

    if not dados:
        return pd.DataFrame(columns=colunas)

    itens = pd.DataFrame(dados)
    itens["data"] = pd.to_datetime(itens["data"]).dt.date

    return itens[colunas]


# =========================================================
# METAS DE VENDAS
# =========================================================

def ler_metas() -> pd.DataFrame:
    resposta = supabase.table("metas").select("*").execute()
    dados = resposta.data or []

    colunas = [
        "id",
        "conta",
        "canal",
        "referencia_inicio",
        "referencia_fim",
        "valor",
        "rotulo",
    ]

    if not dados:
        return pd.DataFrame(columns=colunas)

    metas = pd.DataFrame(dados)
    metas["referencia_inicio"] = pd.to_datetime(
        metas["referencia_inicio"]
    ).dt.date
    metas["referencia_fim"] = pd.to_datetime(metas["referencia_fim"]).dt.date
    metas["rotulo"] = metas["rotulo"].fillna("")

    return metas[colunas]


def salvar_meta(
    conta: str,
    canal: str,
    referencia_inicio: date,
    referencia_fim: date,
    valor: float,
    rotulo: str = "",
) -> None:
    registro = {
        "conta": conta,
        "canal": canal,
        "referencia_inicio": referencia_inicio.isoformat(),
        "referencia_fim": referencia_fim.isoformat(),
        "valor": valor,
        "rotulo": rotulo or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    (
        supabase.table("metas")
        .upsert(
            registro,
            on_conflict="conta,canal,referencia_inicio,referencia_fim",
        )
        .execute()
    )


def excluir_meta(meta_id: int) -> None:
    supabase.table("metas").delete().eq("id", meta_id).execute()


def excluir_todas_metas() -> None:
    supabase.table("metas").delete().gte("id", 0).execute()


def calcular_realizado_meta(
    historico: pd.DataFrame,
    conta: str,
    canal: str,
    referencia_inicio: date,
    referencia_fim: date,
) -> float:
    if historico.empty:
        return 0.0

    filtro = (
        (historico["conta"] == conta)
        & (historico["data"] >= referencia_inicio)
        & (historico["data"] <= referencia_fim)
    )

    if canal != CANAL_CONTA_INTEIRA:
        lojas = canais_do_grupo(conta, canal)
        filtro = filtro & historico["canal"].isin(lojas)

    return float(historico.loc[filtro, "faturamento_valido"].sum())


def montar_comparativo(
    metas: pd.DataFrame,
    historico: pd.DataFrame,
    hoje: date,
) -> pd.DataFrame:
    colunas = [
        "id",
        "conta",
        "canal",
        "rotulo",
        "referencia_inicio",
        "referencia_fim",
        "realizado",
        "meta",
        "meta_diaria",
        "gap",
        "atingido",
        "ritmo_necessario",
        "projecao",
        "classificacao",
        "periodo_ativo_agora",
    ]

    if metas.empty:
        return pd.DataFrame(columns=colunas)

    linhas = []

    for _, linha_meta in metas.iterrows():
        conta_meta = linha_meta["conta"]
        referencia_inicio = linha_meta["referencia_inicio"]
        referencia_fim = linha_meta["referencia_fim"]
        valor_meta = float(linha_meta["valor"])

        realizado = calcular_realizado_meta(
            historico,
            conta_meta,
            linha_meta["canal"],
            referencia_inicio,
            referencia_fim,
        )

        dias_totais = (referencia_fim - referencia_inicio).days + 1
        periodo_em_andamento = referencia_fim >= hoje
        periodo_ativo_agora = referencia_inicio <= hoje <= referencia_fim

        fim_considerado = min(hoje, referencia_fim)
        dias_transcorridos = (
            (fim_considerado - referencia_inicio).days + 1
            if fim_considerado >= referencia_inicio
            else 0
        )

        dias_restantes = max(dias_totais - dias_transcorridos, 0)

        gap = realizado - valor_meta if valor_meta > 0 else None
        atingido = realizado / valor_meta if valor_meta > 0 else None

        meta_restante = max(valor_meta - realizado, 0)

        ritmo_necessario = (
            meta_restante / dias_restantes
            if valor_meta > 0
            and periodo_em_andamento
            and dias_restantes > 0
            else None
        )

        projecao = (
            realizado / dias_transcorridos * dias_totais
            if periodo_em_andamento and dias_transcorridos > 0
            else None
        )

        if valor_meta <= 0:
            classificacao = "Sem meta"
        elif not periodo_em_andamento:
            classificacao = "Período encerrado"
        elif projecao is None:
            classificacao = "—"
        else:
            razao = projecao / valor_meta

            if razao >= 1:
                classificacao = "Acima da meta"
            elif razao >= 0.9:
                classificacao = "Dentro do ritmo"
            elif razao >= 0.7:
                classificacao = "Risco moderado"
            else:
                classificacao = "Risco alto"

        linhas.append(
            {
                "id": linha_meta["id"],
                "conta": conta_meta,
                "canal": linha_meta["canal"],
                "rotulo": linha_meta.get("rotulo") or "",
                "referencia_inicio": referencia_inicio,
                "referencia_fim": referencia_fim,
                "realizado": realizado,
                "meta": valor_meta,
                "meta_diaria": (
                    valor_meta / dias_totais if dias_totais else 0
                ),
                "gap": gap,
                "atingido": atingido,
                "ritmo_necessario": ritmo_necessario,
                "projecao": projecao,
                "classificacao": classificacao,
                "periodo_ativo_agora": periodo_ativo_agora,
            }
        )

    return pd.DataFrame(linhas, columns=colunas).sort_values(
        ["referencia_inicio", "conta", "canal"],
        ascending=[True, True, True],
    )


# =========================================================
# PEDIDOS B2B MANUAIS (não integrados automaticamente com o Bling)
# =========================================================

# Mesmos IDs de situação já usados para os pedidos do Bling (linha 34-41
# acima), reaproveitados aqui para que um pedido manual cancelado seja
# automaticamente excluído do faturamento válido em toda a lógica existente
# (SITUACOES_CANCELADAS, cartões de KPI, gráficos etc.) sem precisar
# duplicar essa regra.
SITUACAO_ID_MANUAL_ATENDIDO = 9
SITUACAO_ID_MANUAL_CANCELADO = 12

SITUACAO_ID_MANUAL = {
    "Atendido": SITUACAO_ID_MANUAL_ATENDIDO,
    "Cancelado": SITUACAO_ID_MANUAL_CANCELADO,
}

COLUNAS_PEDIDOS_MANUAIS = [
    "id",
    "data",
    "cliente",
    "canal",
    "situacao",
    "total",
    "observacoes",
]


def salvar_pedido_manual(
    data_pedido: date,
    cliente: str,
    canal: str,
    total: float,
    situacao: str = "Atendido",
    observacoes: str = "",
) -> None:
    registro = {
        "data": data_pedido.isoformat(),
        "cliente": cliente,
        "canal": canal,
        "situacao": situacao,
        "total": total,
        "observacoes": observacoes or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    supabase.table("pedidos_manuais").insert(registro).execute()


def excluir_pedido_manual(pedido_id: int) -> None:
    supabase.table("pedidos_manuais").delete().eq("id", pedido_id).execute()


def ler_pedidos_manuais_bruto(
    data_inicial: date | None = None,
    data_final: date | None = None,
) -> pd.DataFrame:
    consulta = supabase.table("pedidos_manuais").select("*")

    if data_inicial is not None:
        consulta = consulta.gte("data", data_inicial.isoformat())

    if data_final is not None:
        consulta = consulta.lte("data", data_final.isoformat())

    resposta = consulta.order("data", desc=True).execute()
    dados = resposta.data or []

    if not dados:
        return pd.DataFrame(columns=COLUNAS_PEDIDOS_MANUAIS)

    pedidos = pd.DataFrame(dados)
    pedidos["data"] = pd.to_datetime(pedidos["data"]).dt.date
    pedidos["observacoes"] = pedidos["observacoes"].fillna("")

    return pedidos[COLUNAS_PEDIDOS_MANUAIS]


def transformar_pedidos_manuais(pedidos_manuais: pd.DataFrame) -> pd.DataFrame:
    colunas = [
        "id",
        "conta",
        "numero",
        "data",
        "cliente_id",
        "cliente",
        "situacao_id",
        "situacao",
        "loja_id",
        "total_produtos",
        "total",
    ]

    if pedidos_manuais.empty:
        return pd.DataFrame(columns=colunas)

    total = pd.to_numeric(pedidos_manuais["total"], errors="coerce").fillna(0)

    dataframe = pd.DataFrame(
        {
            # Negativo pra nunca colidir com um pedido_id real do Bling (que
            # é sempre positivo) quando os dois forem concatenados.
            "id": -pedidos_manuais["id"].astype(int),
            "conta": CONTA_MANUAL,
            "numero": "B2B-" + pedidos_manuais["id"].astype(str),
            "data": pd.to_datetime(pedidos_manuais["data"]),
            "cliente_id": None,
            "cliente": pedidos_manuais["cliente"],
            "situacao_id": pedidos_manuais["situacao"].map(SITUACAO_ID_MANUAL),
            "situacao": pedidos_manuais["situacao"],
            "loja_id": pedidos_manuais["canal"],
            "total_produtos": total,
            "total": total,
        }
    )

    return dataframe[colunas]


@st.cache_data(ttl=60, show_spinner=False)
def carregar_pedidos_manuais(
    data_inicial_iso: str,
    data_final_iso: str,
) -> pd.DataFrame:
    pedidos_manuais = ler_pedidos_manuais_bruto(
        date.fromisoformat(data_inicial_iso),
        date.fromisoformat(data_final_iso),
    )

    return transformar_pedidos_manuais(pedidos_manuais)


# Ponto único que soma pedidos manuais aos do Bling — trocar
# carregar_dataframe_multi por esta função é o que faz os pedidos B2B
# manuais aparecerem automaticamente em todo o dashboard, sem precisar
# tocar em cada gráfico/KPI individualmente.
def carregar_dados_completos_multi(
    contas: list[str],
    data_inicial_iso: str,
    data_final_iso: str,
) -> pd.DataFrame:
    partes = [
        carregar_dataframe_multi(contas, data_inicial_iso, data_final_iso),
        carregar_pedidos_manuais(data_inicial_iso, data_final_iso),
    ]

    partes_validas = [parte for parte in partes if not parte.empty]

    if not partes_validas:
        return pd.DataFrame()

    return pd.concat(partes_validas, ignore_index=True)
