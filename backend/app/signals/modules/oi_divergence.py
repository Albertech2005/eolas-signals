"""
OI + Price Divergence Module (max score: 25)

Logic:
- OI rising while price is flat/falling → smart money building longs → LONG signal
- OI rising while price is rising → confirmation → adds to momentum (long)
- OI falling while price is rising → distribution → SHORT signal
- OI and price both falling → panic exit, potential reversal (mild long)
"""
from dataclasses import dataclass
from typing import Optional
from app.ingestion.base import AggregatedMarketData


@dataclass
class ModuleResult:
    score: float       # 0 to max
    max_score: float
    direction: str     # "LONG", "SHORT", "NEUTRAL"
    reason: str
    strong: bool       # qualifies as a "strong" signal


MAX_SCORE = 25.0


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    oi_change = data.oi_change_1h
    price_change = data.price_change_1h

    if oi_change is None or price_change is None:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "OI data unavailable", False)

    # Normalize inputs
    oi_pct = oi_change     # already in %
    price_pct = price_change  # already in %

    # --- LONG SIGNAL ---
    # OI rising while price is stalling or dipping = accumulation
    # 0.08% threshold: filters pure noise while catching real 1h OI moves
    if oi_pct >= 0.08 and price_pct <= 1.0:
        divergence_strength = oi_pct - price_pct + 0.5  # base boost so small divergence still scores
        score = min(MAX_SCORE, divergence_strength * 6.0)
        strong = score >= 14
        return ModuleResult(
            score=round(max(score, 5.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"OI up {oi_pct:.2f}% while price flat ({price_pct:.2f}%) — accumulation detected",
            strong=strong,
        )

    # OI rising with moderate price rise = trend confirmation (partial)
    if oi_pct >= 0.2 and 0.3 < price_pct <= 2.5:
        score = min(MAX_SCORE * 0.6, oi_pct * 3.5)
        return ModuleResult(
            score=round(max(score, 5.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"OI rising {oi_pct:.2f}% with price +{price_pct:.2f}% — trend confirmed",
            strong=False,
        )

    # --- SHORT SIGNAL ---
    # OI rising while price is pumping strongly = potential top / overleveraged longs
    if oi_pct >= 1.5 and price_pct >= 2.0:
        score = min(MAX_SCORE, (oi_pct + price_pct) * 2.5)
        strong = score >= 14
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"OI +{oi_pct:.2f}% with price +{price_pct:.2f}% — overleveraged longs, reversal risk",
            strong=strong,
        )

    # OI falling while price rising = divergence (distribution / smart money exiting)
    if oi_pct <= -0.5 and price_pct >= 0.5:
        divergence_strength = abs(oi_pct) + price_pct
        score = min(MAX_SCORE, divergence_strength * 4.0)
        strong = score >= 14
        return ModuleResult(
            score=round(max(score, 5.0), 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"OI falling {oi_pct:.2f}% while price rising — distribution signal",
            strong=strong,
        )

    # Mild long: both OI and price falling (panic selling, potential reversal)
    if oi_pct <= -1.0 and price_pct <= -0.8:
        score = min(12.0, abs(oi_pct + price_pct) * 2.5)
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Mass deleveraging — OI -{abs(oi_pct):.2f}%, price -{abs(price_pct):.2f}%",
            strong=False,
        )

    return ModuleResult(0, MAX_SCORE, "NEUTRAL", "No significant OI/price divergence", False)
