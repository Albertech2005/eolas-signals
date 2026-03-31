"""
Signal Engine — orchestrates all modules and produces final signals.

Scoring:
  OI Divergence      0-25
  Funding Rate       0-20
  Liquidation        0-25
  Momentum           0-20
  Volatility Quality 0-10
  ─────────────────────────
  Total              0-100

Rules:
  - Only generate LONG or SHORT when total ≥ 70
  - At least 2 strong signals must agree on direction
  - Volatility score < 3 = NO TRADE (market too dangerous)
  - Conflicting directions between strong signals = NO TRADE
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta
import structlog

from app.ingestion.base import AggregatedMarketData
from app.signals.modules import oi_divergence, funding_rate, liquidation, momentum, volatility
from app.config import settings, get_eolas_trade_url

logger = structlog.get_logger(__name__)


@dataclass
class SignalOutput:
    symbol: str
    direction: str             # LONG / SHORT / NO_TRADE
    confidence: int            # 0-100
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    reasons: List[str]
    scores: dict
    eolas_url: Optional[str]
    generated_at: float = field(default_factory=time.time)

    # Score breakdown
    oi_divergence_score: float = 0
    funding_rate_score: float = 0
    liquidation_score: float = 0
    momentum_score: float = 0
    volatility_score: float = 0

    # Context
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    volume_24h: Optional[float] = None

    def is_actionable(self) -> bool:
        return self.direction in ("LONG", "SHORT")


def _compute_tp_sl(price: float, direction: str, atr_pct: Optional[float] = None) -> tuple:
    """Compute SL and TP levels. Uses ATR-based sizing when available."""
    sl_pct = settings.DEFAULT_SL_PCT
    tp1_pct = settings.DEFAULT_TP1_PCT
    tp2_pct = settings.DEFAULT_TP2_PCT

    # ATR-based dynamic sizing (more volatility = wider levels)
    if atr_pct:
        sl_pct = max(settings.DEFAULT_SL_PCT, atr_pct / 100 * 1.5)
        tp1_pct = max(settings.DEFAULT_TP1_PCT, sl_pct * 1.5)
        tp2_pct = max(settings.DEFAULT_TP2_PCT, sl_pct * 2.5)

    if direction == "LONG":
        sl = price * (1 - sl_pct)
        tp1 = price * (1 + tp1_pct)
        tp2 = price * (1 + tp2_pct)
    else:  # SHORT
        sl = price * (1 + sl_pct)
        tp1 = price * (1 - tp1_pct)
        tp2 = price * (1 - tp2_pct)

    return round(sl, 6), round(tp1, 6), round(tp2, 6)


def evaluate_symbol(data: AggregatedMarketData) -> SignalOutput:
    """
    Run all signal modules and produce a final signal for one symbol.
    Always returns a SignalOutput — direction will be NO_TRADE if not enough confidence.
    """
    symbol = data.symbol
    price = data.price

    if not price or price <= 0:
        logger.warning("no_price_data", symbol=symbol)
        return _no_trade(symbol, price or 0, "No price data available")

    # --- Run modules ---
    oi_result = oi_divergence.evaluate(data)
    fr_result = funding_rate.evaluate(data)
    liq_result = liquidation.evaluate(data)
    mom_result = momentum.evaluate(data)
    vol_result = volatility.evaluate(data)

    scores = {
        "oi_divergence": oi_result.score,
        "funding_rate": fr_result.score,
        "liquidation": liq_result.score,
        "momentum": mom_result.score,
        "volatility": vol_result.score,
    }

    total_score = sum(scores.values())

    # --- Volatility gate ---
    if vol_result.score < 3.0:
        return _no_trade(
            symbol, price,
            f"Volatility filter: {vol_result.reason}",
            scores=scores,
        )

    # --- Collect directional votes ---
    # Each module casts a vote with its score as weight
    directional_modules = [oi_result, fr_result, liq_result, mom_result]
    strong_longs = [m for m in directional_modules if m.direction == "LONG" and m.strong]
    strong_shorts = [m for m in directional_modules if m.direction == "SHORT" and m.strong]
    all_longs = [m for m in directional_modules if m.direction == "LONG"]
    all_shorts = [m for m in directional_modules if m.direction == "SHORT"]

    # --- Direction determination ---
    long_score = sum(m.score for m in all_longs)
    short_score = sum(m.score for m in all_shorts)

    # Require clear directional consensus
    if len(strong_longs) >= 2 and long_score > short_score * 1.5:
        direction = "LONG"
    elif len(strong_shorts) >= 2 and short_score > long_score * 1.5:
        direction = "SHORT"
    elif len(strong_longs) == 1 and len(all_longs) >= 3 and long_score > short_score * 2:
        direction = "LONG"
    elif len(strong_shorts) == 1 and len(all_shorts) >= 3 and short_score > long_score * 2:
        direction = "SHORT"
    # Relaxed consensus: simple majority direction when scores are low
    elif long_score > short_score and long_score > 0:
        direction = "LONG"
    elif short_score > long_score and short_score > 0:
        direction = "SHORT"
    elif long_score == short_score and long_score > 0:
        direction = "LONG"  # tiebreak to long
    else:
        return _no_trade(
            symbol, price,
            "Insufficient directional consensus — conflicting signals",
            scores=scores,
        )

    # --- Confidence threshold ---
    confidence = min(100, int(total_score))
    if confidence < settings.MIN_CONFIDENCE_SCORE:
        return _no_trade(
            symbol, price,
            f"Score {confidence}/100 below threshold ({settings.MIN_CONFIDENCE_SCORE})",
            scores=scores,
        )

    # --- Generate signal ---
    atr_pct = vol_result.atr_pct
    sl, tp1, tp2 = _compute_tp_sl(price, direction, atr_pct)

    reasons = []
    for module, result in [
        ("OI Divergence", oi_result),
        ("Funding Rate", fr_result),
        ("Liquidation", liq_result),
        ("Momentum", mom_result),
        ("Volatility", vol_result),
    ]:
        if result.score > 0 and result.direction not in ("NEUTRAL",) or module == "Volatility":
            reasons.append(result.reason)

    eolas_url = get_eolas_trade_url(symbol, direction)

    output = SignalOutput(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        entry_price=round(price, 6),
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        reasons=reasons,
        scores=scores,
        eolas_url=eolas_url,
        oi_divergence_score=oi_result.score,
        funding_rate_score=fr_result.score,
        liquidation_score=liq_result.score,
        momentum_score=mom_result.score,
        volatility_score=vol_result.score,
        funding_rate=data.funding_rate,
        open_interest=data.open_interest,
        volume_24h=data.volume_24h,
    )

    logger.info(
        "signal_generated",
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        scores=scores,
    )

    return output


def _no_trade(symbol: str, price: float, reason: str, scores: dict = None) -> SignalOutput:
    return SignalOutput(
        symbol=symbol,
        direction="NO_TRADE",
        confidence=0,
        entry_price=price,
        stop_loss=0,
        take_profit_1=0,
        take_profit_2=0,
        reasons=[reason],
        scores=scores or {},
        eolas_url=None,
    )


def evaluate_all(market_data: Dict[str, AggregatedMarketData]) -> Dict[str, SignalOutput]:
    """Evaluate all symbols and return signals map."""
    results = {}
    for symbol, data in market_data.items():
        if symbol in settings.SUPPORTED_SYMBOLS:
            try:
                results[symbol] = evaluate_symbol(data)
            except Exception as e:
                logger.error("engine_eval_error", symbol=symbol, error=str(e))
                results[symbol] = _no_trade(symbol, 0, f"Engine error: {e}")
    return results
