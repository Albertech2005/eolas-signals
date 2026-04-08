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
MIN_LIQ_USD = 25_000  # $25k min (lowered from $100k — alts have smaller liq events)


def _ls_ratio_fallback(data: AggregatedMarketData) -> ModuleResult:
    """
    When liquidation data is sparse, fall back to long/short ratio sentiment.
    Extreme LS ratios indicate crowded positioning that can unwind fast.
    Max score from this path: 10 (partial contribution only).
    """
    ls = data.long_short_ratio
    if ls is None:
        return ModuleResult(0, MAX_SCORE, "NEUTRAL", "Liquidation & L/S ratio data unavailable", False)

    if ls >= 1.6:
        # Very crowded longs → long squeeze risk → SHORT bias
        score = min(10.0, (ls - 1.4) * 15)
        return ModuleResult(
            score=round(score, 2), max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Crowded long positioning (L/S ratio {ls:.2f}) — squeeze risk",
            strong=False,
        )
    if ls <= 0.65:
        # Very crowded shorts → short squeeze risk → LONG bias
        score = min(10.0, (0.75 - ls) * 25)
        return ModuleResult(
            score=round(score, 2), max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Crowded short positioning (L/S ratio {ls:.2f}) — squeeze likely",
            strong=False,
        )

    return ModuleResult(0, MAX_SCORE, "NEUTRAL", f"L/S ratio neutral ({ls:.2f}) — no positioning edge", False)


def evaluate(data: AggregatedMarketData) -> ModuleResult:
    long_liq = data.long_liquidations_1h
    short_liq = data.short_liquidations_1h

    if long_liq is None or short_liq is None:
        return _ls_ratio_fallback(data)

    total_liq = long_liq + short_liq

    # Not enough liquidation volume — fall back to L/S ratio
    if total_liq < MIN_LIQ_USD:
        return _ls_ratio_fallback(data)

    if total_liq == 0:
        return _ls_ratio_fallback(data)

    long_ratio = long_liq / total_liq
    short_ratio = short_liq / total_liq

    # Scale factor by absolute USD amount — small liquidations shouldn't max out the score.
    # $500k+ = full weight, $100k = 45%, $25k (minimum) ≈ 22%
    amount_factor = min(1.0, (total_liq / 500_000) ** 0.5)

    # --- SHORTS GETTING LIQUIDATED (short squeeze → LONG) ---
    if short_ratio >= 0.65:
        intensity = (short_ratio - 0.55) / 0.45  # 0 to 1
        score = min(MAX_SCORE, intensity * MAX_SCORE * 1.2 * amount_factor)
        short_liq_m = short_liq / 1e6
        strong = score >= 15
        return ModuleResult(
            score=round(max(score, 3.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Short squeeze in progress — ${short_liq_m:.1f}M shorts liquidated (ratio {short_ratio:.0%})",
            strong=strong,
        )

    # --- LONGS GETTING LIQUIDATED (long cascade → SHORT) ---
    if long_ratio >= 0.65:
        intensity = (long_ratio - 0.55) / 0.45
        score = min(MAX_SCORE, intensity * MAX_SCORE * 1.2 * amount_factor)
        long_liq_m = long_liq / 1e6
        strong = score >= 15
        return ModuleResult(
            score=round(max(score, 3.0), 2),
            max_score=MAX_SCORE,
            direction="SHORT",
            reason=f"Long liquidation cascade — ${long_liq_m:.1f}M longs wiped (ratio {long_ratio:.0%})",
            strong=strong,
        )

    # Moderate imbalance
    if short_ratio >= 0.55:
        score = (short_ratio - 0.50) * MAX_SCORE * 2 * amount_factor
        return ModuleResult(
            score=round(min(score, 12.0), 2),
            max_score=MAX_SCORE,
            direction="LONG",
            reason=f"Moderate short liquidations dominant ({short_ratio:.0%})",
            strong=False,
        )

    if long_ratio >= 0.55:
        score = (long_ratio - 0.50) * MAX_SCORE * 2 * amount_factor
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
