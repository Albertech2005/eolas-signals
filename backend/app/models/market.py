from sqlalchemy import Column, String, Float, DateTime, JSON, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid


class MarketData(Base):
    """Latest market snapshot for each symbol — upserted on every fetch."""
    __tablename__ = "market_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, unique=True, index=True)

    # Price
    price = Column(Float, nullable=False)
    price_change_1h = Column(Float, nullable=True)    # %
    price_change_4h = Column(Float, nullable=True)    # %
    price_change_24h = Column(Float, nullable=True)   # %

    # Volume
    volume_24h = Column(Float, nullable=True)
    volume_1h = Column(Float, nullable=True)
    avg_volume_7d = Column(Float, nullable=True)

    # Open Interest
    open_interest = Column(Float, nullable=True)          # USDT
    oi_change_1h = Column(Float, nullable=True)           # %
    oi_change_4h = Column(Float, nullable=True)           # %

    # Funding rate (as decimal, e.g. 0.0001 = 0.01%)
    funding_rate = Column(Float, nullable=True)
    next_funding_time = Column(DateTime(timezone=True), nullable=True)

    # Liquidations (last 1h, USDT)
    long_liquidations_1h = Column(Float, nullable=True)
    short_liquidations_1h = Column(Float, nullable=True)

    # Long/Short ratio
    long_short_ratio = Column(Float, nullable=True)   # >1 means more longs

    # ATR (14-period, hourly candles)
    atr_1h = Column(Float, nullable=True)
    atr_pct = Column(Float, nullable=True)  # ATR as % of price

    # Raw data snapshot (for debugging)
    raw_snapshot = Column(JSON, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "price_change_1h": self.price_change_1h,
            "price_change_4h": self.price_change_4h,
            "price_change_24h": self.price_change_24h,
            "volume_24h": self.volume_24h,
            "volume_1h": self.volume_1h,
            "open_interest": self.open_interest,
            "oi_change_1h": self.oi_change_1h,
            "oi_change_4h": self.oi_change_4h,
            "funding_rate": self.funding_rate,
            "long_liquidations_1h": self.long_liquidations_1h,
            "short_liquidations_1h": self.short_liquidations_1h,
            "long_short_ratio": self.long_short_ratio,
            "atr_pct": self.atr_pct,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SignalPerformanceCache(Base):
    """Aggregated performance stats per symbol — refreshed periodically."""
    __tablename__ = "signal_performance"

    symbol = Column(String(20), primary_key=True)
    total_signals = Column(BigInteger, default=0)
    winning_signals = Column(BigInteger, default=0)
    losing_signals = Column(BigInteger, default=0)
    win_rate = Column(Float, default=0.0)
    avg_confidence = Column(Float, default=0.0)
    avg_pnl_pct = Column(Float, default=0.0)
    best_pnl_pct = Column(Float, default=0.0)
    worst_pnl_pct = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
