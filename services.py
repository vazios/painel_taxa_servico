import streamlit as st
import jwt
from datetime import datetime
import asyncio
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
import pytz
import random

# Imports locais
import config

def return_none_on_failure(retry_state):
    """Função de callback para o Tenacity que retorna None após esgotar as tentativas."""
    st.error(f"Erro final: Não foi possível buscar os dados da página após {retry_state.attempt_number} tentativas.")
    return None

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=60), # Aumenta o tempo de espera máximo
    before_sleep=lambda retry_state: st.warning(
        f"Falha ao buscar página. Tentando novamente em {int(retry_state.next_action.sleep)}s... (Tentativa {retry_state.attempt_number})"
    ),
    retry_error_callback=return_none_on_failure
)
async def fetch_page_async(session, page, headers, params_base):
    """
    Busca uma única página de relatório. Timeout 90s. Trata rate limit e timeout.
    """
    import aiohttp
    params = {**params_base, "page": page}
    try:
        rate_limit_msg = None
        async with session.get(config.API_REPORT, headers=headers, params=params, timeout=90) as response:
            if response.status == 429:
                rate_limit_msg = st.empty()
                rate_limit_msg.warning(f"Rate limit atingido na página {page}. Aguardando 30s antes de tentar novamente...")
                await asyncio.sleep(30)
                rate_limit_msg.empty()  # Remove a mensagem
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message="Rate limit",
                    headers=response.headers
                )
            response.raise_for_status()
            return await response.json()
    except asyncio.TimeoutError:
        timeout_msg = st.empty()
        timeout_msg.warning(f"Timeout ao buscar página {page}. Aguardando 20s antes de tentar novamente...")
        await asyncio.sleep(20)
        timeout_msg.empty()  # Remove a mensagem
        raise

async def run_report_fetching(_token, data_inicio, data_fim):
    """
    Orquestra a busca de relatórios de forma concorrente, controlada e robusta.
    """
    headers = {"Authorization": f"Bearer {_token}"}
    params_base = {
        "inverse": "true",
        "data_inicio": data_inicio.strftime('%Y-%m-%d'),
        "data_fim": data_fim.strftime('%Y-%m-%d'),
        "tipo": 2,
        "pedido_status": "FINISHED"
    }
    
    pedidos_totais = []
    totais_finais = {}
    page_info = {"fetched": 0, "total": 0, "skipped": []}

    # O semáforo será o controlador principal da concorrência
    connector = aiohttp.TCPConnector(limit_per_host=5) # Limite de conexões por host
    async with aiohttp.ClientSession(connector=connector) as session:
        
        # Helper para controlar a concorrência com semáforo e adicionar um delay
        async def fetch_with_control(page_num, semaphore):
            async with semaphore:
                await asyncio.sleep(random.uniform(0.5, 1.5)) # Pausa aleatória
                return await fetch_page_async(session, page_num, headers, params_base)

        # 1. Pega a primeira página para saber o total (sem concorrência)
        first_page_response = None
        first_page_error = None
        for attempt in range(3):
            try:
                first_page_response = await fetch_page_async(session, 1, headers, params_base)
                if first_page_response and first_page_response.get("data"):
                    break
            except Exception as e:
                first_page_error = e
                st.warning(f"Tentativa {attempt+1} de buscar a primeira página falhou: {e}")
                await asyncio.sleep(10 * (attempt+1))
        if not first_page_response or not first_page_response.get("data"):
            st.error(f"Falha crítica: Não foi possível buscar a primeira página de dados após várias tentativas. Motivo: {first_page_error}. Por favor, tente novamente em alguns minutos.")
            return [], {}, page_info

        last_page = first_page_response.get("lastPage", 1)
        page_info["total"] = last_page
        
        all_pages_data = [first_page_response]
        if first_page_response.get("totais"):
            totais_finais = first_page_response.get("totais")

        # 2. Busca as páginas restantes com controle de concorrência
        if last_page > 1:
            semaphore = asyncio.Semaphore(2) # Limita a 2 requisições simultâneas (mais seguro)
            tasks = [fetch_with_control(page_num, semaphore) for page_num in range(2, last_page + 1)]
            results = await asyncio.gather(*tasks)
            all_pages_data.extend(results)

        # 3. Processa todos os resultados
        for i, page_response in enumerate(all_pages_data):
            page_num = i + 1
            if page_response and page_response.get("data"):
                pedidos_totais.extend(page_response.get("data", []))
                page_info["fetched"] += 1
            elif page_num > 1:
                page_info["skipped"].append(page_num)

    return pedidos_totais, totais_finais, page_info

async def fetch_payments_data_async(session, headers, params):
    # ... (código existente, sem alterações) ...
    all_transactions = []
    total_liquid_value = 0
    total_value = 0
    current_page = 1
    total_pages = 1
    while current_page <= total_pages:
        params["page"] = current_page
        try:
            async with session.get(config.API_PAYMENTS, headers=headers, params=params, timeout=30) as response:
                if response.status >= 400:
                    if current_page == 1: return {'totalValue': 0, 'totalLiquidValue': 0, 'transactions': []}
                    else: break
                data = await response.json()
                if current_page == 1:
                    total_value = data.get('totalValue', 0)
                    total_liquid_value = data.get('totalLiquidValue', 0)
                    total_pages = data.get('totalPages', 1)
                transactions = data.get('transactions', [])
                if not transactions: break
                all_transactions.extend(transactions)
                current_page += 1
        except aiohttp.ClientError:
            if current_page == 1: return {'totalValue': 0, 'totalLiquidValue': 0, 'transactions': []}
            else: break
    return {'totalValue': total_value, 'totalLiquidValue': total_liquid_value, 'transactions': all_transactions}

def validate_jwt_token(token):
    # ... (código existente, sem alterações) ...
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        if 'uid' not in payload: raise ValueError("Campo 'uid' ausente no token.")
        if 'exp' in payload:
            exp_datetime = datetime.fromtimestamp(payload['exp'], tz=pytz.UTC)
            if exp_datetime < datetime.now(pytz.UTC): raise ValueError("Token expirado.")
        return payload
    except (jwt.exceptions.DecodeError, ValueError): return None

def calculate_totals(pedidos, totais_vendas_api, payments_data):
    """Recalcula os totais com base nos dados baixados para garantir precisão."""
    if not pedidos:
        return {"valor_recebido": 0, "tpv": 0, "valor_liquido": 0, "total_pedidos": 0, "total_taxa_servico": 0, "valor_repasse": 0}

    # --- CORREÇÃO FINAL E DEFINITIVA ---
    # Recalcula os totais a partir dos dados que foram baixados com sucesso.
    valor_recebido = sum(p.get('total', 0) for p in pedidos if p)
    total_pedidos = len(pedidos)
    total_taxa_servico = sum(p.get('additional_fee_total', 0) for p in pedidos if p)

    tpv = payments_data.get('totalValue', 0) if payments_data else 0
    valor_liquido = payments_data.get('totalLiquidValue', 0) if payments_data else 0
    valor_repasse = valor_liquido - total_taxa_servico
    
    return {
        "valor_recebido": valor_recebido, "tpv": tpv,
        "valor_liquido": valor_liquido, "total_pedidos": total_pedidos,
        "total_taxa_servico": total_taxa_servico, "valor_repasse": valor_repasse
    }