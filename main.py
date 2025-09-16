import streamlit as st
import asyncio
import aiohttp
from datetime import datetime, date

# Imports locais
import services
import ui

async def run_full_analysis(token, dt_inicio, dt_fim, placeholder):
    """Orquestra as chamadas de API para ambos os relatórios de forma assíncrona."""
    headers = {"Authorization": f"Bearer {token}"}
    
    params_payments = {
        "startDate": dt_inicio.strftime('%Y-%m-%d'),
        "endDate": dt_fim.strftime('%Y-%m-%d'),
        "status": "SUCCEEDED"
    }
    
    async with aiohttp.ClientSession() as session:
        task_vendas = asyncio.create_task(services.run_report_fetching(token, dt_inicio, dt_fim, placeholder))
        task_pagamentos = asyncio.create_task(services.fetch_payments_data_async(session, headers, params_payments))
        vendas_result, payments_data = await asyncio.gather(task_vendas, task_pagamentos)
        
    pedidos, totais_vendas, page_info = vendas_result
    return pedidos, totais_vendas, payments_data, page_info

def main():
    """Função principal que executa a aplicação Streamlit."""
    st.set_page_config(page_title="Relatório de Vendas no delivery + Taxa de Serviço", page_icon="📈", layout="wide")
    st.markdown("<h1 style='text-align: center;'>📈 Relatório de Vendas no delivery + Taxa de Serviço - Yooga</h1>", unsafe_allow_html=True)

    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False

    with st.sidebar:
        st.header("Configurações")
        token = st.text_input("Cole aqui o Token JWT", type="password")
        today = date.today()
        data_inicio = st.date_input("Data de Início", today, format="DD/MM/YYYY")
        data_fim = st.date_input("Data de Fim", today, format="DD/MM/YYYY")
        buscar = st.button("🔍 Buscar Vendas")

    if buscar:
        for key in ['analysis_complete', 'pedidos_data', 'totais_vendas', 'payments_data', 'totals_data']:
            if key in st.session_state:
                del st.session_state[key]
        if not token:
            st.warning("Por favor, insira o Token JWT antes de buscar.")
        elif data_inicio > data_fim:
            st.error("A data de início não pode ser posterior à data de fim.")
        else:
            payload = services.validate_jwt_token(token)
            if not payload:
                st.error("Token JWT inválido ou expirado.")
            else:
                try:
                    status_placeholder = st.empty()
                    with st.spinner(f"Buscando dados de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}..."):
                        dt_inicio = datetime.combine(data_inicio, datetime.min.time())
                        dt_fim = datetime.combine(data_fim, datetime.max.time())
                        pedidos, totais_vendas, payments, page_info = asyncio.run(run_full_analysis(token, dt_inicio, dt_fim, status_placeholder))
                    
                    status_placeholder.empty()
                    st.success(f"Análise concluída! Foram processadas {page_info['fetched']} de {page_info['total']} páginas de dados.")
                    if page_info['skipped']:
                        st.warning(f"As seguintes páginas não puderam ser baixadas: {', '.join(map(str, page_info['skipped']))}")
                    st.session_state.pedidos_data = pedidos
                    st.session_state.payments_data = payments
                    st.session_state.totals_data = services.calculate_totals(pedidos, totais_vendas, payments)
                    st.session_state.analysis_complete = True
                except Exception as e:
                    st.error(f"Ocorreu um erro inesperado durante a análise: {e}")
                    st.exception(e)

    if st.session_state.get('analysis_complete', False):
        ui.display_totals(
            st.session_state.get('pedidos_data'),
            st.session_state.get('payments_data'),
            st.session_state.get('totals_data')
        )

if __name__ == "__main__":
    main()