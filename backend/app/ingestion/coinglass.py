"""
Coinglass ingestion — DEPRECATED.

Coinglass removed their free API tier. All data previously sourced from
Coinglass is now fetched directly from exchange APIs:

  - Liquidation data  → liquidation_tracker.py (Binance WebSocket, free)
  - Long/Short ratio  → binance.py + bybit.py (public REST, free)
  - Open Interest     → binance.py + bybit.py (public REST, free)
  - Funding rate      → binance.py + bybit.py + okx.py (public REST, free)

This file is kept as a no-op stub so any old imports don't break.
"""
from typing import Dict
from app.ingestion.base import RawMarketData
import structlog

logger = structlog.get_logger(__name__)


async def enrich_with_coinglass(data_map: Dict[str, RawMarketData]) -> None:
    """No-op. Coinglass replaced by direct exchange APIs."""
    logger.debug("coinglass_skipped", reason="deprecated — using exchange APIs directly")
    return
