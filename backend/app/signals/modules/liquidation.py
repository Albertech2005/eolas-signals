"""
Liquidation Pressure Detection Module (max score: 25)

Logic:
- Heavy long liquidations → price drops → more short opportunities (SHORT)
- Heavy short liquidations → short squeeze → LONG
- Balanced liquidations → no edge
- Asymmetric liq ratios indicate overleveraged side about to get wiped

This predicts WHERE the cascade will head, not where it just came from.
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


MAX_SCORE = 25.0

# Minimum liquidation size to be meaningful (USDT)
MIN_LIQ_USD = 100_000  # $100k min


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    long_liq = data.long_liquidations_1h
    short_liq = data.short_liquidations_1h

    if long_liq is None or short_liq is None:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "Liquidation data unavailable", False)

    total_liq = long_liq + short_liq

    # Not enough liquidation volume to matter
    if total_liq < MIN_LIQ_USD:
        return ModuleResult(
            0, MAX_SCORE, "NEUTRAL",
            f"Low liquidation volume (${total_liq/1e6:.1f}M) — no pressure detected",
            False
        )

    if total_liq == 0:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "No liquidations data", False)

    long_ratio = long_liq / total_liq
    short_ratio = short_liq / total_liq

    # --- SHORTS GETTING LIQUIDATED (short squeeze → LONG) ---
    # When shorts are wiped out, price tends to keep rising
    if short_ratio >= 0.70:
        intensity = (short_ratio - 0.60) / 0.40  # 0 to 1
        score = min(MAX_SCORE, intensity * MAX_SCORE * 1.2)
        short_liq_m = short_liq / 1e6
        strong = score >= 15
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Short squeeze in progress — ${short_liq_m:.1f}M shorts liquidated (ratio {short_ratio:.0%})",
            strong=strong,
        )

    # --- LONGS GETTING LIQUIDATED (long cascade → SHORT) ---
    # Longs getting wiped forces more selling → downward cascade
    if long_ratio >= 0.70:
        intensity = (long_ratio - 0.60) / 0.40
        score = min(MAX_SCORE, intensity * MAX_SCORE * 1.2)
        long_liq_m = long_liq / 1e6
        strong = score >= 15
        return ModuleResult(
            score=round(score, 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Long liquidation cascade — ${long_liq_m:.1f}M longs wiped (ratio {long_ratio:.0%})",
            strong=strong,
        )

    # Moderate imbalance
    if short_ratio >= 0.60:
        score = (short_ratio - 0.50) * MAX_SCORE * 2
        return ModuleResult(
            score=round(min(score, 12.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Moderate short liquidations dominant ({short_ratio:.0%})",
            strong=False,
        )

    if long_ratio >= 0.60:
        score = (long_ratio - 0.50) * MAX_SCORE * 2
        return ModuleResult(
            score=round(min(score, 12.0), 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Moderate long liquidations dominant ({long_ratio:.0%})",
            strong=False,
        )

    # Balanced — overleveraged on both sides (choppy)
    total_m = total_liq / 1e6
    return ModuleResult(
        0, MAX_SCORE, "NEUTRAL",
        f"Balanced liquidations (${total_m:.1f}M total, {long_ratio:.0%}L/{short_ratio:.0%}S)",
        False
    )
