"""
Real-time Liquidation Tracker — Binance public WebSocket stream.

Connects to wss://fstream.binance.com/ws/!forceOrder@arr (no API key needed).
Accumulates per-symbol long/short liquidations in a rolling 1-hour window.

Side mapping:
  order side "SELL" = long position was liquidated (forced sell)
  order side "BUY"  = short position was liquidated (forced buy-to-close)
"""
import asyncio
import json
import time
from collections import defaultdict, deque
from typing import Dict, Tuple
import aiohttp
import structlog

logger = structlog.get_logger(__name__)

WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"
WINDOW_SECONDS = 3600  # 1-hour rolling window
RECONNECT_DELAY = 5    # seconds before reconnect attempt

# Internal symbol map: Binance perp symbol → our short symbol
_SYMBOL_MAP: Dict[str, str] = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
    "BNBUSDT": "BNB",
    "ARBUSDT": "ARB",
    "OPUSDT":  "OP",
}

# Rolling event store: symbol → deque of (timestamp, long_usd, short_usd)
_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50_000))

_running: bool = False
_connected: bool = False
_total_received: int = 0


def _record(symbol: str, side: str, usd_value: float) -> None:
    """Append a liquidation event to the rolling window."""
    now = time.time()
    if side == "SELL":          # long position liquidated
        _events[symbol].append((now, usd_value, 0.0))
    else:                       # short position liquidated (BUY order)
        _events[symbol].append((now, 0.0, usd_value))


def get_liquidations_1h(symbol: str) -> Tuple[float, float]:
    """
    Return (long_liq_usd, short_liq_usd) accumulated in the last 1 hour.
    Returns (0.0, 0.0) if no data yet.
    """
    cutoff = time.time() - WINDOW_SECONDS
    long_total = 0.0
    short_total = 0.0
    for ts, long_usd, short_usd in _events.get(symbol, deque()):
        if ts >= cutoff:
            long_total += long_usd
            short_total += short_usd
    return long_total, short_total


def is_connected() -> bool:
    return _connected


def get_stats() -> dict:
    """Debug stats for health endpoint."""
    return {
        "connected": _connected,
        "total_received": _total_received,
        "symbols_with_data": [s for s in _SYMBOL_MAP.values() if _events.get(s)],
        "window_seconds": WINDOW_SECONDS,
    }


async def run() -> None:
    """
    Run the liquidation WebSocket listener forever.
    Auto-reconnects on any disconnect or error.
    Call this as an asyncio task from app startup.
    """
    global _running, _connected, _total_received
    _running = True

    while _running:
        try:
            timeout = aiohttp.ClientTimeout(total=None, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.ws_connect(WS_URL, heartbeat=20) as ws:
                    _connected = True
                    logger.info("liquidation_tracker_connected", url=WS_URL)

                    async for msg in ws:
                        if not _running:
                            break

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                order = data.get("o", {})
                                binance_sym = order.get("s", "")
                                symbol = _SYMBOL_MAP.get(binance_sym)
                                if not symbol:
                                    continue

                                side      = order.get("S", "")
                                avg_price = float(order.get("ap", 0) or 0)
                                filled    = float(order.get("z",  0) or 0)
                                usd_value = avg_price * filled

                                if usd_value > 0 and side in ("BUY", "SELL"):
                                    _record(symbol, side, usd_value)
                                    _total_received += 1

                            except Exception as parse_err:
                                logger.debug("liq_parse_error", error=str(parse_err))

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            logger.warning("liq_ws_closed", msg_type=str(msg.type))
                            break

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("liq_tracker_error", error=str(exc))
        finally:
            _connected = False

        if _running:
            logger.info("liq_tracker_reconnecting", delay=RECONNECT_DELAY)
            await asyncio.sleep(RECONNECT_DELAY)


def stop() -> None:
    global _running
    _running = False
