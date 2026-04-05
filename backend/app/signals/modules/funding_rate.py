"""
Funding Rate Extremes Module (max score: 20)

Logic:
- Extremely positive funding → longs paying too much → SHORT bias (mean reversion)
- Extremely negative funding → shorts paying too much → LONG bias (mean reversion)
- Near-zero funding → no signal

Funding rate thresholds (annualized):
- Binance 8h rate: normal ~0.01%, extreme >0.05% or <-0.03%
"""
from dataclasses import dataclass
from typing import Optional
from app.ingestion.base import AggregatedMarketData


@dataclass
class ModuleResult:
    score: float
    max_score: float
    direction: str
    reason: str
    strong: bool


MAX_SCORE = 20.0

# Funding rate thresholds (per 8h period, as decimal)
# Typical BTC funding: 0.01%/8h (neutral), extreme: >0.05%/8h
THRESHOLD_EXTREME_LONG  =  0.0003   # +0.03%/8h → longs very crowded → SHORT bias (strong)
THRESHOLD_HIGH_LONG     =  0.00005  # +0.005%/8h → mild long crowding → SHORT bias (weak)
THRESHOLD_HIGH_SHORT    = -0.00005  # -0.005%/8h → mild short crowding → LONG bias (weak)
THRESHOLD_EXTREME_SHORT = -0.0003   # -0.03%/8h → shorts very crowded → LONG bias (strong)


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    fr = data.funding_rate
    if fr is None:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "Funding rate unavailable", False)

    fr_pct = fr * 100  # Convert to percentage for display

    # --- EXTREME SHORT BIAS (longs paying a lot → contrarian short) ---
    if fr >= THRESHOLD_EXTREME_LONG:
        score = min(MAX_SCORE, (fr - THRESHOLD_HIGH_LONG) / THRESHOLD_HIGH_LONG * MAX_SCORE * 1.5)
        return ModuleResult(
            score=round(max(score, 14.0), 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Extreme positive funding ({fr_pct:.3f}%) — longs overcrowded, reversal likely",
            strong=True,
        )

    if fr >= THRESHOLD_HIGH_LONG:
        score = min(MAX_SCORE * 0.75, (fr - THRESHOLD_HIGH_LONG) / THRESHOLD_HIGH_LONG * 30)
        return ModuleResult(
            score=round(max(score, 8.0), 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Elevated positive funding ({fr_pct:.3f}%) — long squeeze risk",
            strong=False,
        )

    # --- EXTREME LONG BIAS (shorts paying a lot → contrarian long) ---
    if fr <= THRESHOLD_EXTREME_SHORT:
        score = min(MAX_SCORE, abs(fr - THRESHOLD_HIGH_SHORT) / abs(THRESHOLD_HIGH_SHORT) * MAX_SCORE * 1.5)
        return ModuleResult(
            score=round(max(score, 14.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Extreme negative funding ({fr_pct:.3f}%) — shorts overcrowded, squeeze likely",
            strong=True,
        )

    if fr <= THRESHOLD_HIGH_SHORT:
        score = min(MAX_SCORE * 0.75, abs(fr - THRESHOLD_HIGH_SHORT) / abs(THRESHOLD_HIGH_SHORT) * 30)
        return ModuleResult(
            score=round(max(score, 8.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Negative funding ({fr_pct:.3f}%) — short squeeze building",
            strong=False,
        )

    return ModuleResult(
        0, MAX_SCORE, "NEUTRAL",
        f"Funding rate neutral ({fr_pct:.3f}%) — no directional bias",
        False
    )
