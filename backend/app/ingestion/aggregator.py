"""Aggregates data from multiple exchanges into a single clean snapshot."""
import asyncio
import time
from typing import Dict, Optional
import structlog
from app.ingestion.base import RawMarketData, AggregatedMarketData
from app.ingestion import binance, bybit, okx, coingecko
from app.ingestion import liquidation_tracker
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

    binance_src = next((s for s in sources if s.source == "binance"), None)
    bybit_src   = next((s for s in sources if s.source == "bybit"), None)
    okx_src     = next((s for s in sources if s.source == "okx"), None)
    cg_src      = next((s for s in sources if s.source == "coingecko"), None)

    # Price: prefer Binance, then Bybit, then CoinGecko
    price = _best(
        binance_src.price if binance_src else None,
        bybit_src.price if bybit_src else None,
        cg_src.price if cg_src else None,
    ) or 0.0

    # Futures data: prefer Bybit when Binance is 0/None (geo-blocked)
    # Bybit is the most reliable non-geo-restricted futures source
    oi = _best(
        bybit_src.open_interest if bybit_src else None,
        binance_src.open_interest if binance_src else None,
        okx_src.open_interest if okx_src else None,
    )
    oi_change_1h = _best(
        bybit_src.oi_change_1h if bybit_src else None,
        binance_src.oi_change_1h if binance_src else None,
    )
    oi_change_4h = _best(
        bybit_src.oi_change_4h if bybit_src else None,
        binance_src.oi_change_4h if binance_src else None,
    )

    # Funding rate: average across available sources
    funding_values = [s.funding_rate for s in sources if s.funding_rate is not None and s.funding_rate != 0]
    avg_funding = sum(funding_values) / len(funding_values) if funding_values else None

    # Volume: prefer Bybit (futures volume), fallback to Binance
    volume_24h = _best(
        bybit_src.volume_24h if bybit_src else None,
        binance_src.volume_24h if binance_src else None,
    )
    volume_1h = _best(
        bybit_src.volume_1h if bybit_src else None,
        binance_src.volume_1h if binance_src else None,
    )

    # Klines: prefer Bybit (it's working), fallback to Binance
    klines = []
    if bybit_src and bybit_src.klines_1h:
        klines = bybit_src.klines_1h
    elif binance_src and binance_src.klines_1h:
        klines = binance_src.klines_1h

    # Price changes: prefer Bybit
    price_change_1h = _best(
        bybit_src.price_change_1h if bybit_src else None,
        binance_src.price_change_1h if binance_src else None,
    )
    price_change_4h = _best(
        bybit_src.price_change_4h if bybit_src else None,
        binance_src.price_change_4h if binance_src else None,
    )
    price_change_24h = _best(
        bybit_src.price_change_24h if bybit_src else None,
        binance_src.price_change_24h if binance_src else None,
        cg_src.price_change_24h if cg_src else None,
    )

    # Long/short ratio — average Binance + Bybit for best accuracy
    ls_values = [
        bybit_src.long_short_ratio if bybit_src else None,
        binance_src.long_short_ratio if binance_src else None,
    ]
    long_short_ratio = _avg(*ls_values) or _best(*ls_values)

    # Liquidations — prefer real WebSocket tracker, fall back to estimates
    tracker_long, tracker_short = liquidation_tracker.get_liquidations_1h(symbol)
    if tracker_long > 0 or tracker_short > 0:
        long_liq  = tracker_long
        short_liq = tracker_short
    else:
        long_liq = _best(
            bybit_src.long_liquidations_1h if bybit_src else None,
            binance_src.long_liquidations_1h if binance_src else None,
        )
        short_liq = _best(
            bybit_src.short_liquidations_1h if bybit_src else None,
            binance_src.short_liquidations_1h if binance_src else None,
        )
    next_funding = _best(
        bybit_src.next_funding_time if bybit_src else None,
        binance_src.next_funding_time if binance_src else None,
    )

    return AggregatedMarketData(
        symbol=symbol,
        price=price,
        price_change_1h=price_change_1h,
        price_change_4h=price_change_4h,
        price_change_24h=price_change_24h,
        volume_24h=volume_24h,
        volume_1h=volume_1h,
        open_interest=oi,
        oi_change_1h=oi_change_1h,
        oi_change_4h=oi_change_4h,
        funding_rate=avg_funding,
        next_funding_time=next_funding,
        long_liquidations_1h=long_liq,
        short_liquidations_1h=short_liq,
        long_short_ratio=long_short_ratio,
        klines_1h=klines,
        sources=source_names,
        fetched_at=time.time(),
    )


async def fetch_and_aggregate() -> Dict[str, AggregatedMarketData]:
    """Fetch from all sources and return per-symbol aggregated data."""
    symbols = settings.SUPPORTED_SYMBOLS

    # Fetch from Binance, Bybit, and OKX in parallel
    binance_task = asyncio.create_task(binance.fetch_all(symbols))
    bybit_task   = asyncio.create_task(bybit.fetch_all(symbols))
    okx_task     = asyncio.create_task(okx.fetch_all(symbols))

    binance_results, bybit_results, okx_results = await asyncio.gather(
        binance_task, bybit_task, okx_task, return_exceptions=True
    )

    if isinstance(okx_results, Exception):
        logger.warning("okx_fetch_failed", error=str(okx_results))
        okx_results = []

    # Group by symbol
    symbol_data: Dict[str, list[RawMarketData]] = {sym: [] for sym in symbols}

    for source_results in [binance_results, bybit_results, okx_results]:
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
