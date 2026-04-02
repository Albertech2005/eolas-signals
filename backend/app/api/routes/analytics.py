from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.database import get_db
from app.models.signal import Signal, SignalStatus, SignalDirection
from app.models.market import SignalPerformanceCache
from app.config import settings

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/performance")
async def overall_performance(db: AsyncSession = Depends(get_db)):
    """Overall signal performance stats."""
    result = await db.execute(select(SignalPerformanceCache))
    rows = result.scalars().all()

    total_signals = sum(r.total_signals for r in rows)
    total_winning = sum(r.winning_signals for r in rows)
    total_losing = sum(r.losing_signals for r in rows)

    return {
        "overall": {
            "total_signals": total_signals,
            "winning": total_winning,
            "losing": total_losing,
            "win_rate": round((total_winning / total_signals * 100) if total_signals > 0 else 0, 1),
        },
        "by_symbol": [
            {
                "symbol": r.symbol,
                "total": r.total_signals,
                "wins": r.winning_signals,
                "losses": r.losing_signals,
                "win_rate": round(r.win_rate, 1),
                "avg_confidence": round(r.avg_confidence, 1),
                "avg_pnl_pct": round(r.avg_pnl_pct, 2),
                "best_pnl_pct": round(r.best_pnl_pct, 2),
                "worst_pnl_pct": round(r.worst_pnl_pct, 2),
            }
            for r in rows
        ],
    }


@router.get("/history")
async def signal_history(
    symbol: Optional[str] = None,
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Historical signals (resolved only)."""
    from datetime import datetime, timezone, timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        select(Signal)
        .where(
            Signal.created_at >= since,
            Signal.direction != SignalDirection.NO_TRADE,
            Signal.status != SignalStatus.ACTIVE,
        )
        .order_by(desc(Signal.created_at))
        .limit(200)
    )
    if symbol:
        query = query.where(Signal.symbol == symbol.upper())

    result = await db.execute(query)
    signals = result.scalars().all()

    return {
        "signals": [s.to_dict() for s in signals],
        "count": len(signals),
        "days": days,
    }


@router.get("/streaks")
async def win_streaks(db: AsyncSession = Depends(get_db)):
    """Current consecutive win/loss streak per symbol."""
    result = await db.execute(
        select(Signal)
        .where(
            Signal.direction != SignalDirection.NO_TRADE,
            Signal.is_winner != None,  # noqa: E711
        )
        .order_by(Signal.symbol, desc(Signal.created_at))
    )
    all_sigs = result.scalars().all()

    # Group by symbol (already ordered by created_at desc per symbol)
    by_symbol: dict = {}
    for s in all_sigs:
        by_symbol.setdefault(s.symbol, []).append(s)

    streaks = []
    for symbol, sigs in by_symbol.items():
        if not sigs:
            continue
        streak_type = "win" if sigs[0].is_winner else "loss"
        count = 0
        for s in sigs:
            if (s.is_winner and streak_type == "win") or (not s.is_winner and streak_type == "loss"):
                count += 1
            else:
                break
        streaks.append({"symbol": symbol, "streak_type": streak_type, "count": count})

    return {"streaks": sorted(streaks, key=lambda x: x["count"], reverse=True)}


@router.get("/leaderboard")
async def leaderboard(db: AsyncSession = Depends(get_db)):
    """Symbol leaderboard by win rate."""
    result = await db.execute(
        select(SignalPerformanceCache)
        .where(SignalPerformanceCache.total_signals > 0)
        .order_by(desc(SignalPerformanceCache.win_rate))
    )
    rows = result.scalars().all()
    return {
        "leaderboard": [
            {
                "rank": i + 1,
                "symbol": r.symbol,
                "win_rate": round(r.win_rate, 1),
                "total_signals": r.total_signals,
                "avg_pnl_pct": round(r.avg_pnl_pct, 2),
            }
            for i, r in enumerate(rows)
        ]
    }


@router.get("/stats/summary")
async def stats_summary(db: AsyncSession = Depends(get_db)):
    """Quick stats for dashboard header."""
    # Total resolved signals
    total_result = await db.execute(
        select(func.count(Signal.id)).where(
            Signal.direction != SignalDirection.NO_TRADE,
            Signal.status != SignalStatus.ACTIVE,
        )
    )
    total = total_result.scalar() or 0

    winning_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.is_winner == True)
    )
    winning = winning_result.scalar() or 0

    active_result = await db.execute(
        select(func.count(Signal.id)).where(Signal.status == SignalStatus.ACTIVE)
    )
    active = active_result.scalar() or 0

    win_rate = (winning / total * 100) if total > 0 else 0

    return {
        "total_signals": total,
        "winning_signals": winning,
        "active_signals": active,
        "win_rate": round(win_rate, 1),
        "supported_markets": len(settings.SUPPORTED_SYMBOLS),
    }
