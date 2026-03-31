"""Telegram alert bot for high-confidence signals."""
import asyncio
from typing import Optional
import structlog
from app.config import settings
from app.signals.engine import SignalOutput

logger = structlog.get_logger(__name__)

_telegram_app = None


async def _get_bot():
    """Lazy-init telegram bot."""
    global _telegram_app
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    if _telegram_app is None:
        try:
            from telegram import Bot
            _telegram_app = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        except Exception as e:
            logger.error("telegram_init_error", error=str(e))
            return None
    return _telegram_app


def _format_price(price: float, symbol: str) -> str:
    """Format price with appropriate decimal places."""
    if symbol in ("BTC",):
        return f"${price:,.2f}"
    elif price > 100:
        return f"${price:,.3f}"
    else:
        return f"${price:.4f}"


def _format_signal_message(signal: SignalOutput) -> str:
    """Format a signal into a Telegram message."""
    direction_emoji = "🟢 LONG" if signal.direction == "LONG" else "🔴 SHORT"
    confidence_bar = "▓" * (signal.confidence // 10) + "░" * (10 - signal.confidence // 10)

    entry = _format_price(signal.entry_price, signal.symbol)
    sl = _format_price(signal.stop_loss, signal.symbol)
    tp1 = _format_price(signal.take_profit_1, signal.symbol)
    tp2 = _format_price(signal.take_profit_2, signal.symbol)

    # Format reasons
    reasons_text = "\n".join(f"  • {r}" for r in signal.reasons[:4])  # max 4 reasons

    # Funding rate display
    fr_display = ""
    if signal.funding_rate is not None:
        fr_pct = signal.funding_rate * 100
        fr_display = f"\n💸 Funding: {fr_pct:+.4f}%"

    # OI display
    oi_display = ""
    if signal.open_interest:
        oi_m = signal.open_interest / 1e6
        oi_display = f"\n📊 OI: ${oi_m:.0f}M"

    msg = f"""⚡️ <b>EOLAS SIGNAL</b>

<b>{signal.symbol} — {direction_emoji}</b>
Confidence: <b>{signal.confidence}%</b> {confidence_bar}

💰 Entry:   {entry}
🛑 Stop Loss: {sl}
🎯 TP1:    {tp1}
🎯 TP2:    {tp2}
{fr_display}{oi_display}

📋 <b>Reasons:</b>
{reasons_text}

👉 <a href="{signal.eolas_url}">Trade on EOLAS DEX</a>

⏱ Signal valid for ~2h. Always use your own risk management.
<i>Not financial advice.</i>"""

    return msg


async def send_signal_alert(signal: SignalOutput) -> bool:
    """Send a signal alert to the configured Telegram channel."""
    if not signal.is_actionable():
        return False

    bot = await _get_bot()
    if not bot:
        logger.warning("telegram_not_configured")
        return False

    if not settings.TELEGRAM_CHANNEL_ID:
        logger.warning("telegram_channel_not_configured")
        return False

    try:
        message = _format_signal_message(signal)
        await bot.send_message(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
        logger.info("telegram_alert_sent", symbol=signal.symbol, direction=signal.direction)
        return True
    except Exception as e:
        logger.error("telegram_send_error", error=str(e))
        return False


async def send_custom_message(text: str) -> bool:
    """Send a custom message to the Telegram channel."""
    bot = await _get_bot()
    if not bot or not settings.TELEGRAM_CHANNEL_ID:
        return False
    try:
        await bot.send_message(
            chat_id=settings.TELEGRAM_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
        )
        return True
    except Exception as e:
        logger.error("telegram_custom_msg_error", error=str(e))
        return False
