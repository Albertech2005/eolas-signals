"""Binance Futures data ingestion (REST + WebSocket)."""
import asyncio
import aiohttp
import time
from typing import Optional, List
import structlog
from app.ingestion.base import RawMarketData
from app.config import settings

logger = structlog.get_logger(__name__)

BASE = settings.BINANCE_REST_URL
SYMBOL_MAP = {
    "BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT",
    "BNB": "BNBUSDT", "ARB": "ARBUSDT", "OP": "OPUSDT",
}


async def _get(session: aiohttp.ClientSession, path: str, params: dict = None) -> dict | list:
    url = f"{BASE}{path}"
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
        r.raise_for_status()
        return await r.json()


async def fetch_symbol(session: aiohttp.ClientSession, symbol: str) -> Optional[RawMarketData]:
    """Fetch complete futures data for a single symbol from Binance."""
    fut_symbol = SYMBOL_MAP.get(symbol)
    if not fut_symbol:
        return None

    try:
        # Parallel fetch: ticker, OI, funding, klines
        ticker_task = asyncio.create_task(_get(session, "/fapi/v1/ticker/24hr", {"symbol": fut_symbol}))
        oi_task = asyncio.create_task(_get(session, "/fapi/v1/openInterest", {"symbol": fut_symbol}))
        funding_task = asyncio.create_task(_get(session, "/fapi/v1/premiumIndex", {"symbol": fut_symbol}))
        klines_task = asyncio.create_task(_get(session, "/fapi/v1/klines", {
            "symbol": fut_symbol, "interval": "1h", "limit": 48
        }))
        ls_ratio_task = asyncio.create_task(_get(session, "/futures/data/globalLongShortAccountRatio", {
            "symbol": fut_symbol, "period": "1h", "limit": 1
        }))

        ticker, oi_data, funding_data, klines, ls_data = await asyncio.gather(
            ticker_task, oi_task, funding_task, klines_task, ls_ratio_task,
            return_exceptions=True
        )

        data = RawMarketData(symbol=symbol, source="binance")

        # --- Price ---
        if not isinstance(ticker, Exception):
            data.price = float(ticker.get("lastPrice", 0))
            data.price_change_24h = float(ticker.get("priceChangePercent", 0))
            data.volume_24h = float(ticker.get("quoteVolume", 0))

        # --- OI ---
        if not isinstance(oi_data, Exception):
            data.open_interest = float(oi_data.get("openInterest", 0)) * data.price

        # --- Funding ---
        if not isinstance(funding_data, Exception):
            data.funding_rate = float(funding_data.get("lastFundingRate", 0))
            data.next_funding_time = int(funding_data.get("nextFundingTime", 0)) / 1000

        # --- Klines ---
        if not isinstance(klines, Exception) and klines:
            processed = []
            for k in klines:
                processed.append({
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "ts": int(k[0]),
                })
            data.klines_1h = processed

            # Compute 1h and 4h price change from klines
            if len(processed) >= 2:
                data.price_change_1h = (
                    (processed[-1]["close"] - processed[-2]["close"]) / processed[-2]["close"]
                ) * 100

            if len(processed) >= 5:
                data.price_change_4h = (
                    (processed[-1]["close"] - processed[-5]["close"]) / processed[-5]["close"]
                ) * 100

            # Volume last 1h
            data.volume_1h = processed[-1]["volume"] * processed[-1]["close"]

            # OI change: compare current OI vs estimated from klines volume
            # We'll estimate oi_change from historical OI endpoint below

        # --- Long/Short Ratio ---
        if not isinstance(ls_data, Exception) and ls_data:
            entry = ls_data[0] if isinstance(ls_data, list) else ls_data
            data.long_short_ratio = float(entry.get("longShortRatio", 1.0))

        # --- OI change (historical) ---
        try:
            oi_hist = await _get(session, "/futures/data/openInterestHist", {
                "symbol": fut_symbol, "period": "1h", "limit": 5
            })
            if oi_hist and len(oi_hist) >= 2:
                oi_now = float(oi_hist[-1]["sumOpenInterest"]) * data.price
                oi_1h_ago = float(oi_hist[-2]["sumOpenInterest"]) * data.price
                oi_4h_ago = float(oi_hist[0]["sumOpenInterest"]) * data.price if len(oi_hist) >= 5 else None
                if oi_1h_ago > 0:
                    data.oi_change_1h = ((oi_now - oi_1h_ago) / oi_1h_ago) * 100
                if oi_4h_ago and oi_4h_ago > 0:
                    data.oi_change_4h = ((oi_now - oi_4h_ago) / oi_4h_ago) * 100
                data.open_interest = oi_now
        except Exception as e:
            logger.debug("oi_hist_error", symbol=symbol, error=str(e))

        return data

    except Exception as e:
        logger.error("binance_fetch_error", symbol=symbol, error=str(e))
        return None


async def fetch_liquidations(session: aiohttp.ClientSession, symbol: str) -> tuple[float, float]:
    """Estimate long/short liquidation pressure from long/short ratio + OI change.
    Binance allForceOrders requires an API key, so we derive from public data instead.
    Returns (long_liq_estimate, short_liq_estimate) in USDT.
    """
    fut_symbol = SYMBOL_MAP.get(symbol)
    if not fut_symbol:
        return 0.0, 0.0
    try:
        # Use top trader long/short ratio as liquidation proxy (public endpoint)
        data = await _get(session, "/futures/data/topLongShortAccountRatio", {
            "symbol": fut_symbol, "period": "1h", "limit": 2
        })
        if not data or len(data) < 1:
            return 0.0, 0.0

        latest = data[-1]
        long_ratio = float(latest.get("longAccount", 0.5))
        short_ratio = float(latest.get("shortAccount", 0.5))

        # Fetch OI change to estimate liquidation size
        oi_data = await _get(session, "/futures/data/openInterestHist", {
            "symbol": fut_symbol, "period": "1h", "limit": 2
        })
        oi_change_usd = 0.0
        if oi_data and len(oi_data) >= 2:
            # Get current price for conversion
            ticker = await _get(session, "/fapi/v1/ticker/price", {"symbol": fut_symbol})
            price = float(ticker.get("price", 0))
            oi_now = float(oi_data[-1]["sumOpenInterest"]) * price
            oi_prev = float(oi_data[-2]["sumOpenInterest"]) * price
            oi_change_usd = abs(oi_now - oi_prev)

        # When OI drops, positions were closed/liquidated — distribute by ratio
        if oi_change_usd > 0:
            long_liq = oi_change_usd * short_ratio   # OI drop in long-heavy market = long liquidations
            short_liq = oi_change_usd * long_ratio
            return long_liq, short_liq

        return 0.0, 0.0
    except Exception as e:
        logger.debug("liquidation_fetch_error", symbol=symbol, error=str(e))
        return 0.0, 0.0


async def fetch_all(symbols: List[str]) -> List[RawMarketData]:
    """Fetch all symbols from Binance concurrently."""
    connector = aiohttp.TCPConnector(limit=20)
    headers = {}
    if settings.BINANCE_API_KEY:
        headers["X-MBX-APIKEY"] = settings.BINANCE_API_KEY

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        tasks = [fetch_symbol(session, sym) for sym in symbols]
        liq_tasks = [fetch_liquidations(session, sym) for sym in symbols]

        results, liq_results = await asyncio.gather(
            asyncio.gather(*tasks, return_exceptions=True),
            asyncio.gather(*liq_tasks, return_exceptions=True),
        )

        output = []
        for sym, result, liq in zip(symbols, results, liq_results):
            if isinstance(result, RawMarketData) and result:
                if not isinstance(liq, Exception):
                    result.long_liquidations_1h = liq[0]
                    result.short_liquidations_1h = liq[1]
                output.append(result)
        return output
