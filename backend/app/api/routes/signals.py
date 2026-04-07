from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime, timezone
import orjson

from app.database import get_db, get_redis
from app.models.signal import Signal, SignalStatus, SignalDirection
from app.ingestion import aggregator
from app.signals import engine
from app.config import settings

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
async def list_signals(
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """List signals with optional filters."""
    # Try cache for active signals (fast path)
    if not symbol and not direction and status == "ACTIVE" and offset == 0 and redis:
        cached = await redis.get("signals:active")
        if cached:
            data = orjson.loads(cached)
            return {"signals": data[:limit], "total": len(data), "cached": True}

    query = select(Signal).order_by(desc(Signal.created_at))

    if symbol:
        query = query.where(Signal.symbol == symbol.upper())
    if direction:
        query = query.where(Signal.direction == direction.upper())
    if status:
        query = query.where(Signal.status == status.upper())

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    signals = result.scalars().all()

    return {
        "signals": [s.to_dict() for s in signals],
        "total": len(signals),
        "offset": offset,
        "limit": limit,
    }


@router.get("/active")
async def active_signals(redis=Depends(get_redis), db: AsyncSession = Depends(get_db)):
    """Return all currently active (non-expired) signals."""
    now = datetime.now(timezone.utc)

    if redis:
        cached = await redis.get("signals:active")
        if cached:
            data = orjson.loads(cached)
            # Filter out expired signals from cache
            fresh = [
                s for s in data
                if s.get("status") != "EXPIRED"
                and (not s.get("expires_at") or s["expires_at"] > now.isoformat())
            ]
            return {"signals": fresh, "cached": True}

    result = await db.execute(
        select(Signal)
        .where(Signal.status == SignalStatus.ACTIVE)
        .where((Signal.expires_at == None) | (Signal.expires_at > now))
        .order_by(desc(Signal.created_at))
        .limit(20)
    )
    signals = result.scalars().all()
    return {"signals": [s.to_dict() for s in signals], "cached": False}


@router.get("/latest")
async def latest_signals(
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Latest signals (excluding NO_TRADE and EXPIRED) sorted by time."""
    result = await db.execute(
        select(Signal)
        .where(Signal.direction != SignalDirection.NO_TRADE)
        .where(Signal.status != SignalStatus.EXPIRED)
        .order_by(desc(Signal.created_at))
        .limit(limit)
    )
    signals = result.scalars().all()
    return {"signals": [s.to_dict() for s in signals]}


@router.get("/live")
async def live_evaluation(redis=Depends(get_redis)):
    """
    Run signal engine on latest market data right now.
    This is the real-time evaluation endpoint — returns current signal state.
    """
    market_data = aggregator.get_cached()
    cache_age = aggregator.get_cache_age()

    if not market_data:
        raise HTTPException(503, "Market data not yet available — please retry in a moment")

    signals = engine.evaluate_all(market_data)

    output = []
    for symbol, sig in signals.items():
        output.append({
            "symbol": symbol,
            "direction": sig.direction,
            "confidence": sig.confidence,
            "entry_price": sig.entry_price,
            "stop_loss": sig.stop_loss,
            "take_profit_1": sig.take_profit_1,
            "take_profit_2": sig.take_profit_2,
            "reasons": sig.reasons,
            "scores": sig.scores,
            "eolas_url": sig.eolas_url,
            "is_actionable": sig.is_actionable(),
        })

    return {
        "signals": sorted(output, key=lambda x: x["confidence"], reverse=True),
        "data_age_seconds": round(cache_age, 1),
        "evaluated_at": aggregator._last_fetch_time,
    }


@router.post("/admin/reset")
async def reset_all_data(
    request: dict,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis)
):
    """Reset all signals and analytics. Pass {"secret": "..."} in body."""
    from app.config import settings
    secret = request.get("secret", "")
    expected = getattr(settings, "ADMIN_SECRET", None)
    if not expected or secret != expected:
        raise HTTPException(403, "Invalid secret")

    from sqlalchemy import text
    from app.models.market import MarketData, SignalPerformanceCache
    await db.execute(text("TRUNCATE TABLE signals RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE market_data RESTART IDENTITY CASCADE"))
    await db.execute(text("TRUNCATE TABLE signal_performance RESTART IDENTITY CASCADE"))
    await db.commit()

    if redis:
        await redis.flushdb()

    return {"status": "reset complete", "message": "All signals and analytics cleared"}


@router.get("/{signal_id}")
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific signal by ID."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")
    return signal.to_dict()
