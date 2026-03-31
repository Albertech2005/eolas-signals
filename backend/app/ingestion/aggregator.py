"""Aggregates data from multiple exchanges into a single clean snapshot."""
import asyncio
import time
from typing import Dict, Optional
import structlog
from app.ingestion.base import RawMarketData, AggregatedMarketData
from app.ingestion import binance, bybit, okx, coinglass, coingecko
from app.config import settings

logger = structlog.get_logger(__name__)

# In-memory cache of latest aggregated data
_market_cache: Dict[str, AggregatedMarketData] = {}
_last_fetch_time: float = 0
_last_known_prices: Dict[str, float] = {}  # never let prices drop to 0


def _avg(*vals) -> Optional[float]:
    clean = [v for v in vals if v is not None]
    return sum(clean) / len(clean) if clean else None


def _best(*vals, prefer_nonzero=True) -> Optional[float]:
    """Pick the first non-None, non-zero value."""
    for v in vals:
        if v is not None and (not prefer_nonzero or v != 0):
            return v
    return None


def aggregate(sources: list[RawMarketData]) -> AggregatedMarketData:
    """Merge data from multiple sources into one clean object."""
    if not sources:
        raise ValueError("No sources to aggregate")

    symbol = sources[0].symbol
    source_names = [s.source for s in sources]

    # Price: use Binance as primary, Bybit as fallback
    binance_src = next((s for s in sources if s.source == "binance"), None)
    bybit_src = next((s for s in sources if s.source == "bybit"), None)
    okx_src = next((s for s in sources if s.source == "okx"), None)
    primary = binance_src or bybit_src or sources[0]

    # Average funding rates across exchanges for a more robust signal
    funding_values = [s.funding_rate for s in sources if s.funding_rate is not None]
    avg_funding = sum(funding_values) / len(funding_values) if funding_values else None

    # OI: prefer Binance (most liquid), average if needed
    oi = _best(
        binance_src.open_interest if binance_src else None,
        bybit_src.open_interest if bybit_src else None,
    )

    # Klines: prefer Binance
    klines = (binance_src or bybit_src or sources[0]).klines_1h

    return AggregatedMarketData(
        symbol=symbol,
        price=primary.price,
        price_change_1h=_best(primary.price_change_1h, *(s.price_change_1h for s in sources)),
        price_change_4h=_best(primary.price_change_4h, *(s.price_change_4h for s in sources)),
        price_change_24h=_best(primary.price_change_24h, *(s.price_change_24h for s in sources)),
        volume_24h=_best(primary.volume_24h, *(s.volume_24h for s in sources)),
        volume_1h=_best(primary.volume_1h, *(s.volume_1h for s in sources)),
        open_interest=oi,
        oi_change_1h=_best(primary.oi_change_1h, *(s.oi_change_1h for s in sources)),
        oi_change_4h=_best(primary.oi_change_4h, *(s.oi_change_4h for s in sources)),
        funding_rate=avg_funding,
        next_funding_time=primary.next_funding_time,
        long_liquidations_1h=_best(
            primary.long_liquidations_1h, *(s.long_liquidations_1h for s in sources)
        ),
        short_liquidations_1h=_best(
            primary.short_liquidations_1h, *(s.short_liquidations_1h for s in sources)
        ),
        long_short_ratio=_best(
            primary.long_short_ratio, *(s.long_short_ratio for s in sources)
        ),
        klines_1h=klines,
        sources=source_names,
        fetched_at=time.time(),
    )


async def fetch_and_aggregate() -> Dict[str, AggregatedMarketData]:
    """Fetch from all sources and return per-symbol aggregated data."""
    symbols = settings.SUPPORTED_SYMBOLS

    # Fetch from Binance (primary) and Bybit (secondary) in parallel
    binance_task = asyncio.create_task(binance.fetch_all(symbols))
    bybit_task = asyncio.create_task(bybit.fetch_all(symbols))

    binance_results, bybit_results = await asyncio.gather(
        binance_task, bybit_task, return_exceptions=True
    )

    # Group by symbol
    symbol_data: Dict[str, list[RawMarketData]] = {sym: [] for sym in symbols}

    for source_results in [binance_results, bybit_results]:
        if isinstance(source_results, list):
            for item in source_results:
                if isinstance(item, RawMarketData) and item.symbol in symbol_data:
                    symbol_data[item.symbol].append(item)

    # Final aggregation
    result: Dict[str, AggregatedMarketData] = {}
    for sym, sources in symbol_data.items():
        if sources:
            try:
                agg = aggregate(sources)
                result[sym] = agg
            except Exception as e:
                logger.error("aggregation_error", symbol=sym, error=str(e))

    # CoinGecko fallback — patch in real prices if exchange data returned 0
    zero_price_syms = [s for s, d in result.items() if d.price == 0.0]
    missing_syms = [s for s in symbols if s not in result]
    needs_cg = zero_price_syms + missing_syms

    if needs_cg:
        logger.warning("price_fallback_triggered", symbols=needs_cg)
        cg_prices = await coingecko.fetch_prices(needs_cg)
        for sym, price_data in cg_prices.items():
            if sym in result:
                result[sym].price = price_data["price"]
                if result[sym].price_change_24h is None:
                    result[sym].price_change_24h = price_data["price_change_24h"]
            else:
                # Create a minimal market entry from CoinGecko data only
                from app.ingestion.base import AggregatedMarketData
                result[sym] = AggregatedMarketData(
                    symbol=sym,
                    price=price_data["price"],
                    price_change_24h=price_data["price_change_24h"],
                    sources=["coingecko"],
                    fetched_at=time.time(),
                )

    # Never let prices drop to 0 — restore last known good price if fallback also failed
    global _market_cache, _last_fetch_time, _last_known_prices
    for sym, data in result.items():
        if data.price > 0:
            _last_known_prices[sym] = data.price  # save good price
        elif sym in _last_known_prices:
            data.price = _last_known_prices[sym]  # restore last known good price
            logger.warning("price_restored_from_cache", symbol=sym, price=data.price)

    _market_cache = result
    _last_fetch_time = time.time()

    logger.info("market_data_refreshed", symbols=list(result.keys()))
    return result


def get_cached() -> Dict[str, AggregatedMarketData]:
    """Return last cached market data (for fast access from signal engine)."""
    return _market_cache


def get_cache_age() -> float:
    """Return how old the cache is in seconds."""
    return time.time() - _last_fetch_time if _last_fetch_time else float("inf")
