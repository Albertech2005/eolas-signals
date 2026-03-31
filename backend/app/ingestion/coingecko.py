"""Price fallback: Binance Spot API first, CoinGecko as final backup.
Both work from any server worldwide (not geo-restricted like Binance Futures).
"""
import aiohttp
import structlog
from typing import Dict

logger = structlog.get_logger(__name__)

SPOT_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "ARB": "ARBUSDT",
    "OP": "OPUSDT",
}

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "ARB": "arbitrum",
    "OP": "optimism",
}


async def fetch_prices(symbols: list[str]) -> Dict[str, dict]:
    """Fetch USD prices. Tries Binance Spot first, falls back to CoinGecko."""
    result = await _fetch_binance_spot(symbols)

    # Fill in any missing symbols with CoinGecko
    missing = [s for s in symbols if s not in result or result[s]["price"] == 0]
    if missing:
        logger.warning("binance_spot_fallback_to_coingecko", symbols=missing)
        cg = await _fetch_coingecko(missing)
        result.update(cg)

    return result


async def _fetch_binance_spot(symbols: list[str]) -> Dict[str, dict]:
    """Fetch prices from Binance Spot API (globally accessible)."""
    spot_syms = [SPOT_SYMBOLS[s] for s in symbols if s in SPOT_SYMBOLS]
    if not spot_syms:
        return {}

    import json
    params = {"symbols": json.dumps(spot_syms)}
    url = "https://api.binance.com/api/v3/ticker/24hr"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
                r.raise_for_status()
                data = await r.json()

        reverse = {v: k for k, v in SPOT_SYMBOLS.items()}
        result = {}
        for item in data:
            sym = reverse.get(item["symbol"])
            if sym:
                result[sym] = {
                    "price": float(item.get("lastPrice", 0)),
                    "price_change_24h": float(item.get("priceChangePercent", 0)),
                }
        logger.info("binance_spot_prices_fetched", count=len(result))
        return result

    except Exception as e:
        logger.error("binance_spot_fetch_error", error=str(e))
        return {}


async def _fetch_coingecko(symbols: list[str]) -> Dict[str, dict]:
    """CoinGecko fallback."""
    ids = [COINGECKO_IDS[s] for s in symbols if s in COINGECKO_IDS]
    if not ids:
        return {}

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": ",".join(ids), "vs_currencies": "usd", "include_24hr_change": "true"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
                r.raise_for_status()
                data = await r.json()

        reverse = {v: k for k, v in COINGECKO_IDS.items()}
        result = {}
        for cg_id, values in data.items():
            sym = reverse.get(cg_id)
            if sym:
                result[sym] = {
                    "price": float(values.get("usd", 0)),
                    "price_change_24h": float(values.get("usd_24h_change", 0)),
                }
        logger.info("coingecko_prices_fetched", count=len(result))
        return result

    except Exception as e:
        logger.error("coingecko_fetch_error", error=str(e))
        return {}
