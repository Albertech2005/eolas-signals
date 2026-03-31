"""
EOLAS Signal Engine — FastAPI Application Entry Point
"""
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
import orjson

from app.config import settings
from app.database import init_db, init_redis, close_connections, get_redis, redis_client
from app.api.routes import signals, markets, analytics
from app.tasks import scheduler
from app.ingestion import aggregator

logger = structlog.get_logger(__name__)

# Connected WebSocket clients
_ws_clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("starting_eolas_signal_engine", version=settings.APP_VERSION)

    # Init DB + Redis
    await init_db()
    await init_redis()

    # Wire Redis into scheduler
    from app.database import redis_client
    scheduler.set_redis(redis_client)

    # Initial data fetch (don't wait — let it run in background)
    asyncio.create_task(initial_fetch())

    # Start background loops
    asyncio.create_task(scheduler.data_refresh_loop())
    asyncio.create_task(scheduler.signal_eval_loop())
    asyncio.create_task(scheduler.performance_update_loop())
    asyncio.create_task(ws_broadcast_loop())

    logger.info("all_tasks_started")
    yield

    # Cleanup
    await close_connections()
    logger.info("shutdown_complete")


async def initial_fetch():
    """Run first data fetch on startup."""
    try:
        await aggregator.fetch_and_aggregate()
        logger.info("initial_fetch_complete")
    except Exception as e:
        logger.warning("initial_fetch_failed", error=str(e))


async def ws_broadcast_loop():
    """Broadcast live signal updates to WebSocket clients."""
    last_broadcast = 0
    while True:
        await asyncio.sleep(5)
        if not _ws_clients:
            continue

        try:
            market_data = aggregator.get_cached()
            from app.signals import engine
            signals_data = engine.evaluate_all(market_data)

            payload = {
                "type": "signals_update",
                "data": [
                    {
                        "symbol": s.symbol,
                        "direction": s.direction,
                        "confidence": s.confidence,
                        "entry_price": s.entry_price,
                        "eolas_url": s.eolas_url,
                        "is_actionable": s.is_actionable(),
                        "scores": s.scores,
                    }
                    for s in sorted(signals_data.values(), key=lambda x: x.confidence, reverse=True)
                ],
                "market": {
                    sym: {
                        "price": d.price,
                        "price_change_1h": d.price_change_1h,
                        "funding_rate": d.funding_rate,
                    }
                    for sym, d in market_data.items()
                },
            }

            message = orjson.dumps(payload).decode()
            dead = set()
            for ws in _ws_clients.copy():
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            _ws_clients -= dead

        except Exception as e:
            logger.error("ws_broadcast_error", error=str(e))


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(signals.router, prefix="/api")
app.include_router(markets.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")


@app.get("/api/health")
async def health():
    cache_age = aggregator.get_cache_age()
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "data_age_seconds": round(cache_age, 1),
        "markets_loaded": len(aggregator.get_cached()),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live signal streaming."""
    await websocket.accept()
    _ws_clients.add(websocket)
    logger.info("ws_client_connected", total=len(_ws_clients))

    try:
        # Send initial state immediately
        market_data = aggregator.get_cached()
        from app.signals import engine
        signals_data = engine.evaluate_all(market_data) if market_data else {}

        initial = {
            "type": "init",
            "data": [
                {
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "confidence": s.confidence,
                    "entry_price": s.entry_price,
                    "eolas_url": s.eolas_url,
                    "is_actionable": s.is_actionable(),
                    "scores": s.scores,
                }
                for s in signals_data.values()
            ],
        }
        await websocket.send_text(orjson.dumps(initial).decode())

        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')

    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(websocket)
        logger.info("ws_client_disconnected", total=len(_ws_clients))
