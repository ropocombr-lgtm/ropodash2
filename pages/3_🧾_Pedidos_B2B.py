from __future__ import annotations

from datetime import timedelta

from bling_core import (
    excluir_pedido_manual,
    hoje_sao_paulo,
    ler_pedidos_manuais_bruto,
    moeda_br,
    salvar_pedido_manual,
)
from ui import (
    cabecalho_dashboard,
    cabecalho_secao,
    card_kpi,
    injetar_css,
)
import streamlit as st

st.set_page_config(
    page_title="Pedidos B2B - Dashboard Bling",
    page_icon="🧾",
    layout="wide",
)

injetar_css()

cabecalho_dashboard(
    "🧾 Pedidos B2B (manual)",
    "Cadastre pedidos de B2B fechados fora do Bling — eles entram "
    "automaticamente no faturamento do Dashboard, Tempo Real e Televisão.",
)

hoje = hoje_sao_paulo()

pedidos_existentes = ler_pedidos_manuais_bruto()

canais_existentes = (
    sorted(pedidos_existentes["canal"].dropna().unique().tolist())
    if not pedidos_existentes.empty
    else []
)

cabecalho_secao(
    "Resumo",
    "Faturamento e volume dos pedidos B2B manuais no período filtrado.",
    "📊",
)

if pedidos_existentes.empty:
    st.info(
        "Nenhum pedido B2B manual cadastrado ainda. Use \"Cadastrar "
        "pedido\" abaixo."
    )
    pedidos_filtrados = pedidos_existentes
else:
    coluna_filtro_1, coluna_filtro_2 = st.columns(2)

    data_inicial_filtro = coluna_filtro_1.date_input(
        "De",
        value=hoje - timedelta(days=90),
    )

    data_final_filtro = coluna_filtro_2.date_input(
        "Até",
        value=hoje,
    )

    if data_inicial_filtro > data_final_filtro:
        st.error("A data inicial não pode ser posterior à data final.")
        st.stop()

    pedidos_filtrados = pedidos_existentes.loc[
        (pedidos_existentes["data"] >= data_inicial_filtro)
        & (pedidos_existentes["data"] <= data_final_filtro)
    ].copy()

    cancelados_filtro = pedidos_filtrados["situacao"] == "Cancelado"
    faturamento_valido = float(
        pedidos_filtrados.loc[~cancelados_filtro, "total"].sum()
    )
    quantidade_valida = int((~cancelados_filtro).sum())
    quantidade_cancelada = int(cancelados_filtro.sum())
    ticket_medio = (
        faturamento_valido / quantidade_valida if quantidade_valida else 0.0
    )

    coluna_kpi_1, coluna_kpi_2, coluna_kpi_3, coluna_kpi_4 = st.columns(4)

    with coluna_kpi_1:
        card_kpi(
            "Faturamento B2B manual",
            moeda_br(faturamento_valido),
            "Período filtrado",
        )

    with coluna_kpi_2:
        card_kpi("Pedidos válidos", str(quantidade_valida))

    with coluna_kpi_3:
        card_kpi("Ticket médio", moeda_br(ticket_medio))

    with coluna_kpi_4:
        card_kpi("Cancelados", str(quantidade_cancelada))

    cabecalho_secao(
        "Pedidos cadastrados",
        "Todos os pedidos B2B manuais no período, mais recentes primeiro.",
        "📋",
    )

    with st.container(border=True):
        tabela = pedidos_filtrados.sort_values(
            "data", ascending=False
        ).copy()

        tabela["data"] = tabela["data"].apply(
            lambda valor: valor.strftime("%d/%m/%Y")
        )
        tabela["total"] = tabela["total"].apply(moeda_br)

        st.dataframe(
            tabela[
                [
                    "data",
                    "cliente",
                    "canal",
                    "situacao",
                    "total",
                    "observacoes",
                ]
            ].rename(
                columns={
                    "data": "Data",
                    "cliente": "Cliente",
                    "canal": "Canal",
                    "situacao": "Situação",
                    "total": "Total",
                    "observacoes": "Observações",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

coluna_form, coluna_excluir = st.columns(2)

with coluna_form, st.expander("Cadastrar pedido", expanded=True):
    # Fora do st.form: widgets dentro de um form só reprocessam no submit,
    # então o canal precisa ficar fora para que o campo de texto do "novo
    # canal" apareça/suma assim que o usuário troca a opção escolhida.
    opcao_canal = st.selectbox(
        "Canal / origem do B2B",
        options=canais_existentes + ["+ Novo canal"],
        key="opcao_canal_manual",
    )

    if opcao_canal == "+ Novo canal":
        canal_pedido = st.text_input(
            "Nome do novo canal",
            placeholder="ex.: Distribuidor ABC, Atacado, WhatsApp",
            key="novo_canal_manual",
        )
    else:
        canal_pedido = opcao_canal

    with st.form("form_pedido_manual"):
        coluna_data, coluna_situacao = st.columns(2)

        data_pedido = coluna_data.date_input(
            "Data do pedido",
            value=hoje,
        )

        situacao_pedido = coluna_situacao.selectbox(
            "Situação",
            options=["Atendido", "Cancelado"],
        )

        cliente_pedido = st.text_input("Cliente")

        valor_pedido = st.number_input(
            "Valor total (R$)",
            min_value=0.0,
            step=50.0,
        )

        observacoes_pedido = st.text_area(
            "Observações (opcional)",
        )

        enviar_pedido = st.form_submit_button("Salvar pedido")

        if enviar_pedido:
            if not canal_pedido:
                st.error("Informe o canal / origem do pedido.")
            elif not cliente_pedido:
                st.error("Informe o cliente do pedido.")
            elif valor_pedido <= 0:
                st.error("O valor do pedido deve ser maior que zero.")
            else:
                salvar_pedido_manual(
                    data_pedido,
                    cliente_pedido,
                    canal_pedido,
                    valor_pedido,
                    situacao_pedido,
                    observacoes_pedido,
                )

                st.success("Pedido salvo com sucesso.")
                st.rerun()

with coluna_excluir, st.expander("Excluir pedido", expanded=True):
    if pedidos_existentes.empty:
        st.caption("Nenhum pedido cadastrado.")
    else:
        opcoes_exclusao = {
            (
                f"{linha['data'].strftime('%d/%m/%Y')} · {linha['cliente']} "
                f"· {linha['canal']} · {moeda_br(float(linha['total']))}"
            ): linha["id"]
            for _, linha in pedidos_existentes.iterrows()
        }

        escolha_exclusao = st.selectbox(
            "Pedido a excluir",
            options=list(opcoes_exclusao.keys()),
        )

        if st.button("Excluir pedido selecionado"):
            excluir_pedido_manual(opcoes_exclusao[escolha_exclusao])
            st.success("Pedido excluído.")
            st.rerun()
