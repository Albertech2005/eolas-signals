from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import orjson

from app.database import get_db, get_redis
from app.models.market import MarketData
from app.ingestion import aggregator
from app.config import settings, EOLAS_MARKET_MAP, get_eolas_trade_url

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
async def list_markets(redis=Depends(get_redis), db: AsyncSession = Depends(get_db)):
    """Return all supported markets with latest data."""
    # Try Redis cache first
    if redis:
        cached = await redis.get("market:snapshot")
        if cached:
            snapshot = orjson.loads(cached)
            # Enrich with EOLAS links
            for sym, data in snapshot.items():
                data["eolas_long_url"] = get_eolas_trade_url(sym, "LONG")
                data["eolas_short_url"] = get_eolas_trade_url(sym, "SHORT")
                data["eolas_info"] = EOLAS_MARKET_MAP.get(sym, {})
            return {"markets": list(snapshot.values()), "cached": True}

    # Fallback to DB
    result = await db.execute(select(MarketData))
    rows = result.scalars().all()
    markets = []
    for row in rows:
        d = row.to_dict()
        d["eolas_long_url"] = get_eolas_trade_url(row.symbol, "LONG")
        d["eolas_short_url"] = get_eolas_trade_url(row.symbol, "SHORT")
        d["eolas_info"] = EOLAS_MARKET_MAP.get(row.symbol, {})
        markets.append(d)
    return {"markets": markets, "cached": False}


@router.get("/{symbol}")
async def get_market(symbol: str, redis=Depends(get_redis), db: AsyncSession = Depends(get_db)):
    """Get market data for a single symbol."""
    symbol = symbol.upper()
    if symbol not in settings.SUPPORTED_SYMBOLS:
        raise HTTPException(404, f"Symbol {symbol} not supported")

    # Try live cache
    if redis:
        cached = await redis.get("market:snapshot")
        if cached:
            snapshot = orjson.loads(cached)
            if symbol in snapshot:
                data = snapshot[symbol]
                data["eolas_long_url"] = get_eolas_trade_url(symbol, "LONG")
                data["eolas_short_url"] = get_eolas_trade_url(symbol, "SHORT")
                return data

    # DB fallback
    result = await db.execute(select(MarketData).where(MarketData.symbol == symbol))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"No data for {symbol} yet")

    data = row.to_dict()
    data["eolas_long_url"] = get_eolas_trade_url(symbol, "LONG")
    data["eolas_short_url"] = get_eolas_trade_url(symbol, "SHORT")
    return data


@router.get("/supported/list")
async def supported_markets():
    """Return list of supported market symbols."""
    return {
        "symbols": settings.SUPPORTED_SYMBOLS,
        "markets": [
            {
                "symbol": sym,
                **EOLAS_MARKET_MAP.get(sym, {}),
                "eolas_long_url": get_eolas_trade_url(sym, "LONG"),
                "eolas_short_url": get_eolas_trade_url(sym, "SHORT"),
            }
            for sym in settings.SUPPORTED_SYMBOLS
        ],
    }
