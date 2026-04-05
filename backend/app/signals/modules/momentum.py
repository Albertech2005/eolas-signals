"""
Momentum Confirmation Module (max score: 20)

Logic:
- Strong directional move (1h price change) with elevated volume = real momentum
- Volume ratio: current 1h volume vs. 24h average
- RSI proxy from klines to filter overbought/oversold
"""
from dataclasses import dataclass
from typing import Optional, List
import numpy as np
from app.ingestion.base import AggregatedMarketData


@dataclass
class ModuleResult:
    score: float
    max_score: float
    direction: str
    reason: str
    strong: bool


MAX_SCORE = 20.0

# Minimum volume ratio to consider meaningful
MIN_VOLUME_RATIO = 1.0     # TEST MODE: lowered
# Minimum price move for momentum
MIN_PRICE_MOVE_PCT = 0.1   # TEST MODE: lowered


def compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Compute RSI from a list of closing prices."""
    if len(closes) < period + 1:
        return None
    closes_arr = np.array(closes)
    deltas = np.diff(closes_arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        return 100.0

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    return 100 - (100 / (1 + rs))


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    price_change_1h = data.price_change_1h
    price_change_4h = data.price_change_4h
    volume_1h = data.volume_1h
    volume_24h = data.volume_24h
    klines = data.klines_1h

    if price_change_1h is None:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "Momentum data unavailable", False)

    # Compute volume ratio
    volume_ratio = None
    if volume_1h and volume_24h and volume_24h > 0:
        avg_1h_volume = volume_24h / 24
        volume_ratio = volume_1h / avg_1h_volume if avg_1h_volume > 0 else None

    # Compute RSI
    rsi = None
    if klines and len(klines) >= 15:
        closes = [k["close"] for k in klines]
        rsi = compute_rsi(closes)

    abs_price_1h = abs(price_change_1h)
    direction = "LONG" if price_change_1h > 0 else "SHORT"

    # Minimum move required
    if abs_price_1h < MIN_PRICE_MOVE_PCT:
        return ModuleResult(
            0, MAX_SCORE, "NEUTRAL",
            f"Price move too small ({price_change_1h:.2f}%) — no momentum",
            False
        )

    # Volume confirmation required for strong signal
    has_volume = volume_ratio is not None and volume_ratio >= MIN_VOLUME_RATIO

    # RSI filter: don't chase an already overbought/oversold move
    if rsi is not None:
        if direction == "LONG" and rsi > 75:
            return ModuleResult(
                3, MAX_SCORE, "NEUTRAL",
                f"Price up {price_change_1h:.2f}% but RSI={rsi:.0f} — overbought, skip",
                False
            )
        if direction == "SHORT" and rsi < 25:
            return ModuleResult(
                3, MAX_SCORE, "NEUTRAL",
                f"Price down {abs_price_1h:.2f}% but RSI={rsi:.0f} — oversold, skip",
                False
            )

    # 4h trend alignment bonus
    trend_aligned = False
    if price_change_4h is not None:
        trend_aligned = (direction == "LONG" and price_change_4h > 0) or \
                        (direction == "SHORT" and price_change_4h < 0)

    # Score calculation
    base_score = min(12.0, abs_price_1h * 6)  # up to 12 from price move (was 4x → 6x)

    volume_bonus = 0.0
    if has_volume and volume_ratio:
        volume_bonus = min(5.0, (volume_ratio - 1.0) * 4.0)

    trend_bonus = 3.0 if trend_aligned else 0.0
    rsi_bonus = 2.0 if rsi is not None and (
        (direction == "LONG" and 40 <= rsi <= 65) or
        (direction == "SHORT" and 35 <= rsi <= 60)
    ) else 0.0

    total_score = min(MAX_SCORE, base_score + volume_bonus + trend_bonus + rsi_bonus)
    strong = total_score >= 12  # lowered from 14 → 12

    vol_str = f"Vol ratio {volume_ratio:.1f}x" if volume_ratio else "vol unknown"
    rsi_str = f"RSI {rsi:.0f}" if rsi else ""
    reason_parts = [
        f"Strong {"up" if direction == "LONG" else "down"} move: {price_change_1h:.2f}% (1h)",
        vol_str,
    ]
    if rsi_str:
        reason_parts.append(rsi_str)
    if trend_aligned:
        reason_parts.append("4h trend aligned")

    return ModuleResult(
        score=round(total_score, 2),
        max_score=MAX_SCORE,
        direction=direction,
        reason=" | ".join(reason_parts),
        strong=strong,
    )
