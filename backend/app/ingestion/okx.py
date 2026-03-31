"""OKX Futures data ingestion — funding rate supplement."""
import asyncio
import aiohttp
from typing import Optional, List
import structlog
from app.ingestion.base import RawMarketData
from app.config import settings

logger = structlog.get_logger(__name__)

BASE = settings.OKX_REST_URL
SYMBOL_MAP = {
    "BTC": "BTC-USDT-SWAP", "ETH": "ETH-USDT-SWAP", "SOL": "SOL-USDT-SWAP",
    "BNB": "BNB-USDT-SWAP", "ARB": "ARB-USDT-SWAP", "OP": "OP-USDT-SWAP",
}


async def _get(session: aiohttp.ClientSession, path: str, params: dict = None) -> dict:
    url = f"{BASE}{path}"
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
        r.raise_for_status()
        return await r.json()


async def fetch_symbol(session: aiohttp.ClientSession, symbol: str) -> Optional[RawMarketData]:
    inst_id = SYMBOL_MAP.get(symbol)
    if not inst_id:
        return None

    try:
        # Funding rate
        funding_resp = await _get(session, "/api/v5/public/funding-rate", {"instId": inst_id})
        funding_list = funding_resp.get("data", [])
        if not funding_list:
            return None
        funding_data = funding_list[0]

        data = RawMarketData(symbol=symbol, source="okx")
        fr = funding_data.get("fundingRate")
        if fr:
            data.funding_rate = float(fr)

        # OI
        try:
            oi_resp = await _get(session, "/api/v5/public/open-interest", {"instId": inst_id})
            oi_list = oi_resp.get("data", [])
            if oi_list:
                oi_usd = oi_list[0].get("oiUsd")
                if oi_usd:
                    data.open_interest = float(oi_usd)
        except Exception:
            pass

        return data

    except Exception as e:
        logger.debug("okx_fetch_error", symbol=symbol, error=str(e))
        return None


async def fetch_all(symbols: List[str]) -> List[RawMarketData]:
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_symbol(session, sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, RawMarketData) and r]
