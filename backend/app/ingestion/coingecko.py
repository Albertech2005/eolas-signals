"""CoinGecko price fallback — no API key required, globally accessible."""
import aiohttp
import structlog
from typing import Dict, Optional

logger = structlog.get_logger(__name__)

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "ARB": "arbitrum",
    "OP": "optimism",
}

BASE = "https://api.coingecko.com/api/v3"


async def fetch_prices(symbols: list[str]) -> Dict[str, float]:
    """Fetch USD prices for all symbols from CoinGecko."""
    ids = [COINGECKO_IDS[s] for s in symbols if s in COINGECKO_IDS]
    if not ids:
        return {}

    url = f"{BASE}/simple/price"
    params = {"ids": ",".join(ids), "vs_currencies": "usd", "include_24hr_change": "true"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
                r.raise_for_status()
                data = await r.json()

        result = {}
        reverse_map = {v: k for k, v in COINGECKO_IDS.items()}
        for cg_id, values in data.items():
            symbol = reverse_map.get(cg_id)
            if symbol:
                result[symbol] = {
                    "price": float(values.get("usd", 0)),
                    "price_change_24h": float(values.get("usd_24h_change", 0)),
                }
        logger.info("coingecko_prices_fetched", count=len(result))
        return result

    except Exception as e:
        logger.error("coingecko_fetch_error", error=str(e))
        return {}
