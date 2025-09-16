import streamlit as st
from datetime import datetime
import config

def display_totals(pedidos, payments_data, totals_data):
    """Exibe os totais da campanha em métricas."""
    st.header("📊 Resumo do Período")

    if pedidos is None or payments_data is None:
        st.error("A busca de dados falhou. Nenhuma métrica pôde ser calculada.")
        return
    
    if not pedidos and not payments_data.get("transactions"):
        st.warning("Nenhuma venda ou pagamento encontrado nesse período.")
        return

    # --- Primeira Linha de Métricas (Valores Principais) ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Valor Bruto Recebido",
            value=f"R$ {totals_data['valor_recebido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

    with col2:
        st.metric(
            label="TPV (Pagamento Online)",
            value=f"R$ {totals_data['tpv']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            help="Volume Total de Pagamentos (TPV) processado online via Yooga Pay, antes das taxas."
        )
    
    with col3:
        st.metric(
            label="Valor Líquido Recebido",
            value=f"R$ {totals_data['valor_liquido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            help="Valor total dos pagamentos online após as taxas da Yooga Pay."
        )
    
    with col4:
        st.metric(
            label="Valor a Repassar",
            value=f"R$ {totals_data['valor_repasse']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            help="Valor líquido subtraindo a taxa de serviço de R$ 0,99 por pedido (pós-set/25)."
        )

    st.divider()

    # --- Segunda Linha de Métricas (Detalhes) ---
    col5, col6 = st.columns(2)

    with col5:
        st.metric(
            label="Total de Pedidos",
            value=totals_data['total_pedidos']
        )
        
    with col6:
        st.metric(
            label="Taxa de Serviço",
            value=f"R$ {totals_data['total_taxa_servico']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            help="Soma da taxa de serviço de R$ 0,99 por pedido (pós-set/25)."
        )

def convert_to_local(dt_str):
    if not dt_str:
        return None
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt.astimezone(config.TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")