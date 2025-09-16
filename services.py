import streamlit as st
import jwt
from datetime import datetime
import asyncio
import aiohttp
import pytz
import random

# Imports locais
import config

async def fetch_page_async(session, page, headers, params_base, placeholder):
    """
    Busca uma única página de relatório. Timeout 90s. Trata rate limit e timeout.
    """
    params = {**params_base, "page": page}
    try:
        async with session.get(config.API_REPORT, headers=headers, params=params, timeout=90) as response:
            if response.status == 429:
                placeholder.warning(f"Rate limit atingido na página {page}. Aguardando 30s antes de tentar novamente...")
                await asyncio.sleep(30)
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
        placeholder.warning(f"Timeout ao buscar página {page}. Aguardando 20s antes de tentar novamente...")
        await asyncio.sleep(20)
        raise

async def fetch_page_with_retry_async(session, page, headers, params_base, placeholder):
    """Tenta buscar uma página com várias tentativas e espera exponencial."""
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            if attempt > 0:
                placeholder.empty()
            return await fetch_page_async(session, page, headers, params_base, placeholder)
        except Exception:
            if attempt + 1 == max_attempts:
                placeholder.error(f"Erro final: Não foi possível buscar os dados da página {page} após {max_attempts} tentativas.")
                return None
            
            wait_time = 2 ** (attempt + 1) + random.uniform(0, 1)
            placeholder.warning(f"Falha ao buscar página {page}. Tentando novamente em {int(wait_time)}s... (Tentativa {attempt + 1}/{max_attempts})")
            await asyncio.sleep(wait_time)

async def run_report_fetching(_token, data_inicio, data_fim, placeholder):
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

    connector = aiohttp.TCPConnector(limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        
        async def fetch_with_control(page_num, semaphore):
            async with semaphore:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                return await fetch_page_with_retry_async(session, page_num, headers, params_base, placeholder)

        first_page_response = await fetch_page_with_retry_async(session, 1, headers, params_base, placeholder)

        if not first_page_response or not first_page_response.get("data"):
            placeholder.error("Falha crítica: Não foi possível buscar a primeira página de dados. A análise não pode continuar.")
            return [], {}, page_info

        last_page = first_page_response.get("lastPage", 1)
        page_info["total"] = last_page
        
        all_pages_data = [first_page_response]
        if first_page_response.get("totais"):
            totais_finais = first_page_response.get("totais")

        if last_page > 1:
            semaphore = asyncio.Semaphore(2)
            tasks = [fetch_with_control(page_num, semaphore) for page_num in range(2, last_page + 1)]
            results = await asyncio.gather(*tasks)
            all_pages_data.extend(results)

        placeholder.empty()
        for i, page_response in enumerate(all_pages_data):
            page_num = i + 1
            if page_response and page_response.get("data"):
                pedidos_totais.extend(page_response.get("data", []))
                page_info["fetched"] += 1
            elif page_num > 1:
                page_info["skipped"].append(page_num)

    return pedidos_totais, totais_finais, page_info

async def fetch_payments_data_async(session, headers, params):
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