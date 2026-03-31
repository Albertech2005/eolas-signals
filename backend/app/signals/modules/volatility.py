"""
Volatility Quality Filter Module (max score: 10)

This module acts as a gating filter — it penalizes signals in choppy or
extremely volatile markets and rewards clean trending conditions.

Also computes ATR (Average True Range) as % of price.
"""
from dataclasses import dataclass
from typing import Optional, List
import numpy as np
from app.ingestion.base import AggregatedMarketData


@dataclass
class ModuleResult:
    score: float
    max_score: float
    direction: str    # always NEUTRAL — this module doesn't pick direction
    reason: str
    strong: bool
    atr_pct: Optional[float]


MAX_SCORE = 10.0

# ATR quality windows (% of price)
ATR_TOO_LOW = 0.20    # < 0.2% per candle → market dead / ranging
ATR_IDEAL_LOW = 0.30  # good trending starts
ATR_IDEAL_HIGH = 2.0  # good trending top
ATR_TOO_HIGH = 3.5    # > 3.5% → extremely choppy/volatile → high risk


def compute_atr(klines: List[dict], period: int = 14) -> Optional[float]:
    """Compute Average True Range from klines list."""
    if len(klines) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(klines)):
        high = klines[i]["high"]
        low = klines[i]["low"]
        prev_close = klines[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    return float(np.mean(true_ranges[-period:]))


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    klines = data.klines_1h
    price = data.price

    if not klines or len(klines) < 15 or not price or price == 0:
        return ModuleResult(
            score=5.0,  # neutral score when data unavailable
            max_score=MAX_SCORE,
            direction="NEUTRAL",
            reason="Insufficient kline data for ATR — using neutral score",
            strong=False,
            atr_pct=None,
        )

    atr = compute_atr(klines)
    if atr is None:
        return ModuleResult(5.0, MAX_SCORE, "NEUTRAL", "ATR calculation failed", False, None)

    atr_pct = (atr / price) * 100

    # Dead market — too quiet
    if atr_pct < ATR_TOO_LOW:
        return ModuleResult(
            score=0.0,
            max_score=MAX_SCORE,
            direction="NEUTRAL",
            reason=f"Market too quiet — ATR {atr_pct:.2f}% (below {ATR_TOO_LOW}%)",
            strong=False,
            atr_pct=atr_pct,
        )

    # Good range — ideal for trending signals
    if ATR_IDEAL_LOW <= atr_pct <= ATR_IDEAL_HIGH:
        # Scale: 10 at midpoint, slightly less at edges
        midpoint = (ATR_IDEAL_LOW + ATR_IDEAL_HIGH) / 2
        distance_from_mid = abs(atr_pct - midpoint) / (ATR_IDEAL_HIGH - ATR_IDEAL_LOW)
        score = MAX_SCORE * (1.0 - distance_from_mid * 0.3)
        return ModuleResult(
            score=round(min(MAX_SCORE, score), 2),
            max_score=MAX_SCORE,
            direction="NEUTRAL",
            reason=f"Ideal volatility — ATR {atr_pct:.2f}% (trending conditions)",
            strong=False,
            atr_pct=atr_pct,
        )

    # Slightly below ideal
    if ATR_TOO_LOW <= atr_pct < ATR_IDEAL_LOW:
        score = (atr_pct / ATR_IDEAL_LOW) * MAX_SCORE * 0.5
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="NEUTRAL",
            reason=f"Low volatility — ATR {atr_pct:.2f}% (choppy conditions, reduced confidence)",
            strong=False,
            atr_pct=atr_pct,
        )

    # Too volatile — high risk, reduce confidence
    if atr_pct > ATR_TOO_HIGH:
        return ModuleResult(
            score=2.0,
            max_score=MAX_SCORE,
            direction="NEUTRAL",
            reason=f"Extreme volatility — ATR {atr_pct:.2f}% — high risk environment",
            strong=False,
            atr_pct=atr_pct,
        )

    # Elevated but within trading range
    score = MAX_SCORE * (1.0 - (atr_pct - ATR_IDEAL_HIGH) / (ATR_TOO_HIGH - ATR_IDEAL_HIGH) * 0.7)
    return ModuleResult(
        score=round(max(3.0, score), 2),
        max_score=MAX_SCORE,
        direction="NEUTRAL",
        reason=f"Elevated volatility — ATR {atr_pct:.2f}% (acceptable, use tight SL)",
        strong=False,
        atr_pct=atr_pct,
    )
