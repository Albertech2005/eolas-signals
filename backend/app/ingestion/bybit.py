"""Bybit V5 Futures data ingestion (supplement/fallback)."""
import asyncio
import aiohttp
from typing import Optional, List
import structlog
from app.ingestion.base import RawMarketData
from app.config import settings

logger = structlog.get_logger(__name__)

BASE = settings.BYBIT_REST_URL
SYMBOL_MAP = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
    "BNB": "BNBUSDT", "ARB": "ARBUSDT", "OP": "OPUSDT",
}


async def _get(session: aiohttp.ClientSession, path: str, params: dict = None) -> dict:
    url = f"{BASE}{path}"
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
        r.raise_for_status()
        return await r.json()


async def fetch_symbol(session: aiohttp.ClientSession, symbol: str) -> Optional[RawMarketData]:
    fut_symbol = SYMBOL_MAP.get(symbol)
    if not fut_symbol:
        return None

    try:
        # Ticker
        ticker_resp = await _get(session, "/v5/market/tickers", {
            "category": "linear", "symbol": fut_symbol
        })
        ticker = ticker_resp.get("result", {}).get("list", [{}])[0]

        data = RawMarketData(symbol=symbol, source="bybit")
        data.price = float(ticker.get("lastPrice", 0))
        data.price_change_24h = float(ticker.get("price24hPcnt", 0)) * 100
        data.volume_24h = float(ticker.get("turnover24h", 0))
        data.open_interest = float(ticker.get("openInterestValue", 0))
        data.funding_rate = float(ticker.get("fundingRate", 0))

        # Klines for momentum
        klines_resp = await _get(session, "/v5/market/kline", {
            "category": "linear", "symbol": fut_symbol,
            "interval": "60", "limit": 48
        })
        klines = klines_resp.get("result", {}).get("list", [])
        processed = []
        for k in reversed(klines):  # Bybit returns newest first
            processed.append({
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "ts": int(k[0]),
            })
        data.klines_1h = processed

        if len(processed) >= 2:
            data.price_change_1h = (
                (processed[-1]["close"] - processed[-2]["close"]) / processed[-2]["close"]
            ) * 100
        if len(processed) >= 5:
            data.price_change_4h = (
                (processed[-1]["close"] - processed[-5]["close"]) / processed[-5]["close"]
            ) * 100
        if processed:
            data.volume_1h = processed[-1]["volume"] * processed[-1]["close"]

        # Long/short ratio
        ls_resp = await _get(session, "/v5/market/account-ratio", {
            "category": "linear", "symbol": fut_symbol,
            "period": "1h", "limit": 1
        })
        ls_list = ls_resp.get("result", {}).get("list", [])
        if ls_list:
            buy_ratio = float(ls_list[0].get("buyRatio", 0.5))
            sell_ratio = float(ls_list[0].get("sellRatio", 0.5))
            data.long_short_ratio = buy_ratio / sell_ratio if sell_ratio > 0 else 1.0

        return data

    except Exception as e:
        logger.error("bybit_fetch_error", symbol=symbol, error=str(e))
        return None


async def fetch_all(symbols: List[str]) -> List[RawMarketData]:
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_symbol(session, sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, RawMarketData) and r]
