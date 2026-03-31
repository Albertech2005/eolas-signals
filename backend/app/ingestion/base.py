from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class RawMarketData:
    """Normalized market data from any exchange."""
    symbol: str                       # e.g. "BTC"
    source: str                       # e.g. "binance", "bybit"
    price: float = 0.0
    price_change_1h: Optional[float] = None
    price_change_4h: Optional[float] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_1h: Optional[float] = None
    open_interest: Optional[float] = None
    oi_change_1h: Optional[float] = None
    oi_change_4h: Optional[float] = None
    funding_rate: Optional[float] = None
    next_funding_time: Optional[float] = None   # unix ts
    long_liquidations_1h: Optional[float] = None
    short_liquidations_1h: Optional[float] = None
    long_short_ratio: Optional[float] = None
    klines_1h: list = field(default_factory=list)  # list of OHLCV dicts
    fetched_at: float = field(default_factory=time.time)
    raw: dict = field(default_factory=dict)


@dataclass
class AggregatedMarketData:
    """Merged data from multiple sources."""
    symbol: str
    price: float
    price_change_1h: Optional[float] = None
    price_change_4h: Optional[float] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_1h: Optional[float] = None
    open_interest: Optional[float] = None
    oi_change_1h: Optional[float] = None
    oi_change_4h: Optional[float] = None
    funding_rate: Optional[float] = None
    next_funding_time: Optional[float] = None
    long_liquidations_1h: Optional[float] = None
    short_liquidations_1h: Optional[float] = None
    long_short_ratio: Optional[float] = None
    klines_1h: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    fetched_at: float = field(default_factory=time.time)
