"""
Background task scheduler.
- Refreshes market data every N seconds
- Evaluates signals every N seconds
- Tracks signal outcomes (TP/SL hit)
- Updates performance cache
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import structlog
from sqlalchemy import select, update

from app.ingestion import aggregator
from app.ingestion.base import AggregatedMarketData
from app.signals import engine
from app.signals.engine import SignalOutput
from app.telegram import bot as telegram
from app.database import AsyncSessionLocal
from app.models.signal import Signal, SignalDirection, SignalStatus
from app.models.market import MarketData, SignalPerformanceCache
from app.config import settings
import redis.asyncio as redis_lib

logger = structlog.get_logger(__name__)

# Track last signal time per symbol to enforce cooldown
_last_signal_time: Dict[str, float] = {}

# Global redis ref (set from main.py)
_redis: Optional[redis_lib.Redis] = None


def set_redis(r: redis_lib.Redis):
    global _redis
    _redis = r


async def _cache_market_data(market_data: Dict[str, AggregatedMarketData]):
    """Persist market data to DB and Redis cache."""
    async with AsyncSessionLocal() as db:
        for symbol, data in market_data.items():
            # Upsert market data
            existing = await db.execute(
                select(MarketData).where(MarketData.symbol == symbol)
            )
            row = existing.scalar_one_or_none()

            md_dict = {
                "price": data.price,
                "price_change_1h": data.price_change_1h,
                "price_change_4h": data.price_change_4h,
                "price_change_24h": data.price_change_24h,
                "volume_24h": data.volume_24h,
                "volume_1h": data.volume_1h,
                "open_interest": data.open_interest,
                "oi_change_1h": data.oi_change_1h,
                "oi_change_4h": data.oi_change_4h,
                "funding_rate": data.funding_rate,
                "long_liquidations_1h": data.long_liquidations_1h,
                "short_liquidations_1h": data.short_liquidations_1h,
                "long_short_ratio": data.long_short_ratio,
            }

            if row:
                for k, v in md_dict.items():
                    setattr(row, k, v)
            else:
                db.add(MarketData(symbol=symbol, **md_dict))

        await db.commit()

    # Cache in Redis for fast API access
    if _redis:
        import orjson
        market_snapshot = {
            sym: {
                "symbol": data.symbol,
                "price": data.price,
                "price_change_1h": data.price_change_1h,
                "price_change_24h": data.price_change_24h,
                "volume_24h": data.volume_24h,
                "open_interest": data.open_interest,
                "oi_change_1h": data.oi_change_1h,
                "funding_rate": data.funding_rate,
                "long_liquidations_1h": data.long_liquidations_1h,
                "short_liquidations_1h": data.short_liquidations_1h,
                "long_short_ratio": data.long_short_ratio,
                "sources": data.sources,
                "fetched_at": data.fetched_at,
            }
            for sym, data in market_data.items()
        }
        await _redis.setex(
            "market:snapshot",
            settings.CACHE_TTL,
            orjson.dumps(market_snapshot),
        )


async def _persist_signal(signal: SignalOutput) -> Optional[Signal]:
    """Save a new signal to the database."""
    from datetime import datetime, timezone, timedelta
    async with AsyncSessionLocal() as db:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        db_signal = Signal(
            symbol=signal.symbol,
            direction=SignalDirection(signal.direction),
            confidence=signal.confidence,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            oi_divergence_score=signal.oi_divergence_score,
            funding_rate_score=signal.funding_rate_score,
            liquidation_score=signal.liquidation_score,
            momentum_score=signal.momentum_score,
            volatility_score=signal.volatility_score,
            entry_funding_rate=signal.funding_rate,
            entry_oi=signal.open_interest,
            entry_volume_24h=signal.volume_24h,
            reasons=signal.reasons,
            eolas_url=signal.eolas_url,
            expires_at=expires_at,
        )
        db.add(db_signal)
        await db.commit()
        await db.refresh(db_signal)
        return db_signal


async def _cache_active_signals(signals: list[Signal]):
    """Cache active signals in Redis."""
    if not _redis:
        return
    import orjson
    data = [s.to_dict() for s in signals]
    await _redis.setex("signals:active", 120, orjson.dumps(data))


_MIN_OUTCOME_CHECK_AGE_SECONDS = 10 * 60  # 10-minute grace period before outcome checks


async def _check_signal_outcomes(market_data: Dict[str, AggregatedMarketData]):
    """Check if any active signals have hit TP or SL."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Signal).where(Signal.status == SignalStatus.ACTIVE)
        )
        active_signals = result.scalars().all()

        now = datetime.now(timezone.utc)
        updated = []

        for sig in active_signals:
            # Check expiry
            if sig.expires_at and sig.expires_at < now:
                sig.status = SignalStatus.EXPIRED
                updated.append(sig)
                continue

            # Grace period: ignore very new signals to avoid premature SL hits from
            # price wicks / transient volatility right after signal creation.
            if sig.created_at:
                created_at = sig.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_seconds = (now - created_at).total_seconds()
                if age_seconds < _MIN_OUTCOME_CHECK_AGE_SECONDS:
                    continue

            current_data = market_data.get(sig.symbol)
            if not current_data:
                continue

            current_price = current_data.price
            if not current_price:
                continue

            if sig.direction == SignalDirection.LONG:
                if current_price >= sig.take_profit_2:
                    sig.status = SignalStatus.HIT_TP2
                    sig.exit_price = current_price
                    sig.pnl_pct = ((current_price - sig.entry_price) / sig.entry_price) * 100
                    sig.is_winner = True
                elif current_price >= sig.take_profit_1:
                    sig.status = SignalStatus.HIT_TP1
                    sig.exit_price = current_price
                    sig.pnl_pct = ((current_price - sig.entry_price) / sig.entry_price) * 100
                    sig.is_winner = True
                elif current_price <= sig.stop_loss:
                    sig.status = SignalStatus.HIT_SL
                    sig.exit_price = current_price
                    sig.pnl_pct = ((current_price - sig.entry_price) / sig.entry_price) * 100
                    sig.is_winner = False
            else:  # SHORT
                if current_price <= sig.take_profit_2:
                    sig.status = SignalStatus.HIT_TP2
                    sig.exit_price = current_price
                    sig.pnl_pct = ((sig.entry_price - current_price) / sig.entry_price) * 100
                    sig.is_winner = True
                elif current_price <= sig.take_profit_1:
                    sig.status = SignalStatus.HIT_TP1
                    sig.exit_price = current_price
                    sig.pnl_pct = ((sig.entry_price - current_price) / sig.entry_price) * 100
                    sig.is_winner = True
                elif current_price >= sig.stop_loss:
                    sig.status = SignalStatus.HIT_SL
                    sig.exit_price = current_price
                    sig.pnl_pct = ((sig.entry_price - current_price) / sig.entry_price) * 100
                    sig.is_winner = False

            if sig.status != SignalStatus.ACTIVE:
                updated.append(sig)

        if updated:
            await db.commit()
            logger.info("signal_outcomes_updated", count=len(updated))


async def _update_performance_cache():
    """Refresh the performance stats table."""
    from sqlalchemy import func as sqlfunc
    async with AsyncSessionLocal() as db:
        symbols = settings.SUPPORTED_SYMBOLS
        for symbol in symbols:
            result = await db.execute(
                select(Signal).where(
                    Signal.symbol == symbol,
                    Signal.status != SignalStatus.ACTIVE,
                    Signal.status != SignalStatus.EXPIRED,   # exclude inconclusive
                    Signal.direction != SignalDirection.NO_TRADE,
                )
            )
            sigs = result.scalars().all()

            # Also fetch expired count separately (for display only)
            expired_result = await db.execute(
                select(Signal).where(
                    Signal.symbol == symbol,
                    Signal.status == SignalStatus.EXPIRED,
                    Signal.direction != SignalDirection.NO_TRADE,
                )
            )
            expired_count = len(expired_result.scalars().all())

            if not sigs:
                continue

            # Only count signals that actually resolved (TP1, TP2, or SL)
            total = len(sigs)
            winners = [s for s in sigs if s.is_winner is True]
            losers  = [s for s in sigs if s.is_winner is False]
            pnl_values = [s.pnl_pct for s in sigs if s.pnl_pct is not None]

            perf = await db.get(SignalPerformanceCache, symbol)
            if not perf:
                perf = SignalPerformanceCache(symbol=symbol)
                db.add(perf)

            perf.total_signals = total
            perf.winning_signals = len(winners)
            perf.losing_signals = len(losers)
            perf.win_rate = (len(winners) / total * 100) if total > 0 else 0
            perf.avg_confidence = sum(s.confidence for s in sigs) / total if total else 0
            perf.avg_pnl_pct = sum(pnl_values) / len(pnl_values) if pnl_values else 0
            perf.best_pnl_pct = max(pnl_values) if pnl_values else 0
            perf.worst_pnl_pct = min(pnl_values) if pnl_values else 0

        await db.commit()


async def data_refresh_loop():
    """Continuous market data refresh loop."""
    logger.info("data_refresh_loop_started")
    while True:
        try:
            market_data = await aggregator.fetch_and_aggregate()
            await _cache_market_data(market_data)
        except Exception as e:
            logger.error("data_refresh_error", error=str(e))
        await asyncio.sleep(settings.DATA_REFRESH_INTERVAL_SECONDS)


async def signal_eval_loop():
    """Continuous signal evaluation loop."""
    logger.info("signal_eval_loop_started")
    while True:
        try:
            market_data = aggregator.get_cached()
            if not market_data:
                await asyncio.sleep(5)
                continue

            # Check outcomes of existing signals
            await _check_signal_outcomes(market_data)

            # Evaluate new signals
            signals = engine.evaluate_all(market_data)
            new_signals = []

            for symbol, signal in signals.items():
                if not signal.is_actionable():
                    continue

                # Enforce cooldown
                last_time = _last_signal_time.get(symbol, 0)
                cooldown_secs = settings.SIGNAL_COOLDOWN_MINUTES * 60
                if time.time() - last_time < cooldown_secs:
                    logger.debug("signal_cooldown", symbol=symbol)
                    continue

                # Persist to DB
                db_signal = await _persist_signal(signal)
                if db_signal:
                    new_signals.append(db_signal)
                    _last_signal_time[symbol] = time.time()

                    # Send Telegram alert
                    sent = await telegram.send_signal_alert(signal)
                    if sent and db_signal:
                        async with AsyncSessionLocal() as db:
                            db_signal.telegram_sent = True
                            db.add(db_signal)
                            await db.commit()

            # Update active signals cache
            if new_signals or True:  # always refresh cache
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Signal)
                        .where(Signal.status == SignalStatus.ACTIVE)
                        .order_by(Signal.created_at.desc())
                        .limit(50)
                    )
                    active = result.scalars().all()
                await _cache_active_signals(active)

        except Exception as e:
            logger.error("signal_eval_error", error=str(e))

        await asyncio.sleep(settings.SIGNAL_EVAL_INTERVAL_SECONDS)


async def performance_update_loop():
    """Update performance stats every 5 minutes."""
    while True:
        try:
            await _update_performance_cache()
        except Exception as e:
            logger.error("perf_update_error", error=str(e))
        await asyncio.sleep(300)  # every 5 mins
