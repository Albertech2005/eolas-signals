"""Coinglass data ingestion — liquidation data and OI analytics."""
import asyncio
import aiohttp
from typing import Optional, List
import structlog
from app.ingestion.base import RawMarketData
from app.config import settings

logger = structlog.get_logger(__name__)

BASE = settings.COINGLASS_REST_URL
COINGLASS_SYMBOL_MAP = {
    "BTC": "BTC", "ETH": "ETH", "SOL": "SOL",
    "BNB": "BNB", "ARB": "ARB", "OP": "OP",
}


async def _get(session: aiohttp.ClientSession, path: str, params: dict = None) -> dict:
    url = f"{BASE}{path}"
    headers = {}
    if settings.COINGLASS_API_KEY:
        headers["coinglassSecret"] = settings.COINGLASS_API_KEY
    async with session.get(url, params=params, headers=headers,
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status == 429:
            logger.warning("coinglass_rate_limited")
            return {}
        r.raise_for_status()
        return await r.json()


async def fetch_liquidations(session: aiohttp.ClientSession, symbol: str) -> tuple[float, float]:
    """Fetch 1h liquidation data from Coinglass. Returns (long_liq_usd, short_liq_usd)."""
    cg_symbol = COINGLASS_SYMBOL_MAP.get(symbol)
    if not cg_symbol:
        return 0.0, 0.0
    try:
        resp = await _get(session, "/api/pro/v1/futures/liquidation/info", {
            "symbol": cg_symbol
        })
        if not resp or resp.get("code") != "0":
            return 0.0, 0.0
        data = resp.get("data", {})
        long_liq = float(data.get("longLiquidationUsd24h", 0)) / 24  # estimate 1h from 24h
        short_liq = float(data.get("shortLiquidationUsd24h", 0)) / 24
        return long_liq, short_liq
    except Exception as e:
        logger.debug("coinglass_liquidation_error", symbol=symbol, error=str(e))
        return 0.0, 0.0


async def fetch_long_short_ratio(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Fetch global long/short ratio from Coinglass."""
    cg_symbol = COINGLASS_SYMBOL_MAP.get(symbol)
    if not cg_symbol:
        return None
    try:
        resp = await _get(session, "/api/pro/v1/futures/longShortAccountRatio/chart", {
            "symbol": cg_symbol, "interval": "h1", "limit": 1
        })
        if not resp or resp.get("code") != "0":
            return None
        data_list = resp.get("data", {}).get("list", [])
        if not data_list:
            return None
        latest = data_list[-1]
        long_rate = float(latest.get("longRatio", 0.5))
        short_rate = float(latest.get("shortRatio", 0.5))
        return long_rate / max(short_rate, 0.001)
    except Exception as e:
        logger.debug("coinglass_ls_error", symbol=symbol, error=str(e))
        return None


async def enrich_with_coinglass(data_map: dict[str, RawMarketData]) -> None:
    """Enrich existing RawMarketData objects with Coinglass data in-place."""
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        symbols = list(data_map.keys())
        liq_tasks = [fetch_liquidations(session, sym) for sym in symbols]
        ls_tasks = [fetch_long_short_ratio(session, sym) for sym in symbols]

        liq_results, ls_results = await asyncio.gather(
            asyncio.gather(*liq_tasks, return_exceptions=True),
            asyncio.gather(*ls_tasks, return_exceptions=True),
        )

        for sym, liq, ls in zip(symbols, liq_results, ls_results):
            if sym in data_map:
                md = data_map[sym]
                if not isinstance(liq, Exception):
                    # Override if Coinglass has better data
                    if liq[0] > 0 or liq[1] > 0:
                        md.long_liquidations_1h = liq[0]
                        md.short_liquidations_1h = liq[1]
                if not isinstance(ls, Exception) and ls is not None:
                    md.long_short_ratio = ls
