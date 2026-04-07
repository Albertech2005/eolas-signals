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
#
# Asymmetric design (intentional):
#   LONG side: normal market has +0.01%/8h positive funding — only fire on genuinely elevated rates
#   SHORT side: ANY negative funding is unusual and a real bullish signal → lower threshold
#
THRESHOLD_EXTREME_LONG  =  0.0007   # +0.07%/8h → truly extreme → SHORT bias (strong)
THRESHOLD_HIGH_LONG     =  0.0002   # +0.02%/8h → elevated above neutral → SHORT bias (weak)
THRESHOLD_HIGH_SHORT    = -0.00005  # -0.005%/8h → any notable negative funding → LONG bias (weak)
THRESHOLD_EXTREME_SHORT = -0.0004   # -0.04%/8h → extreme negative → LONG bias (strong)


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    fr = data.funding_rate
    if fr is None:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "Funding rate unavailable", False)

    fr_pct = fr * 100  # Convert to percentage for display

    # --- EXTREME SHORT BIAS (longs paying a lot → contrarian short) ---
    if fr >= THRESHOLD_EXTREME_LONG:
        intensity = (fr - THRESHOLD_HIGH_LONG) / (THRESHOLD_EXTREME_LONG - THRESHOLD_HIGH_LONG)
        score = min(MAX_SCORE, 14.0 + intensity * 6.0)
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Extreme positive funding ({fr_pct:.3f}%) — longs overcrowded, reversal likely",
            strong=True,
        )

    if fr >= THRESHOLD_HIGH_LONG:
        intensity = (fr - THRESHOLD_HIGH_LONG) / (THRESHOLD_EXTREME_LONG - THRESHOLD_HIGH_LONG)
        score = min(MAX_SCORE * 0.7, 8.0 + intensity * 8.0)
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Elevated positive funding ({fr_pct:.3f}%) — long squeeze risk",
            strong=False,
        )

    # --- EXTREME LONG BIAS (shorts paying a lot → contrarian long) ---
    if fr <= THRESHOLD_EXTREME_SHORT:
        intensity = (abs(fr) - abs(THRESHOLD_HIGH_SHORT)) / (abs(THRESHOLD_EXTREME_SHORT) - abs(THRESHOLD_HIGH_SHORT))
        score = min(MAX_SCORE, 14.0 + intensity * 6.0)
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Extreme negative funding ({fr_pct:.3f}%) — shorts overcrowded, squeeze likely",
            strong=True,
        )

    if fr <= THRESHOLD_HIGH_SHORT:
        intensity = (abs(fr) - abs(THRESHOLD_HIGH_SHORT)) / (abs(THRESHOLD_EXTREME_SHORT) - abs(THRESHOLD_HIGH_SHORT))
        score = min(MAX_SCORE * 0.7, 8.0 + intensity * 8.0)
        return ModuleResult(
            score=round(score, 2),
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
