from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, Enum, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


class SignalDirection(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class SignalStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    HIT_TP1 = "HIT_TP1"
    HIT_TP2 = "HIT_TP2"
    HIT_SL = "HIT_SL"
    EXPIRED = "EXPIRED"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(Enum(SignalDirection), nullable=False)
    confidence = Column(Integer, nullable=False)  # 0-100

    # Price levels
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=False)

    # Score breakdown
    oi_divergence_score = Column(Float, default=0)
    funding_rate_score = Column(Float, default=0)
    liquidation_score = Column(Float, default=0)
    momentum_score = Column(Float, default=0)
    volatility_score = Column(Float, default=0)

    # Context data at signal time
    entry_funding_rate = Column(Float, nullable=True)
    entry_oi = Column(Float, nullable=True)
    entry_volume_24h = Column(Float, nullable=True)

    # Reasons (list of strings)
    reasons = Column(JSON, default=list)

    # EOLAS link
    eolas_url = Column(String(500), nullable=True)

    # Outcome tracking
    status = Column(Enum(SignalStatus), default=SignalStatus.ACTIVE)
    exit_price = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    is_winner = Column(Boolean, nullable=True)

    # Telegram notification sent
    telegram_sent = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_signals_symbol_created", "symbol", "created_at"),
        Index("ix_signals_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "scores": {
                "oi_divergence": self.oi_divergence_score,
                "funding_rate": self.funding_rate_score,
                "liquidation": self.liquidation_score,
                "momentum": self.momentum_score,
                "volatility": self.volatility_score,
                "total": self.confidence,
            },
            "reasons": self.reasons,
            "eolas_url": self.eolas_url,
            "status": self.status.value,
            "pnl_pct": self.pnl_pct,
            "is_winner": self.is_winner,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
