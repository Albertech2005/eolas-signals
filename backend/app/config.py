from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "EOLAS Signal Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://eolas:eolas@localhost:5432/eolasdb"
    DATABASE_POOL_SIZE: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 30  # seconds

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://eolas-signals.vercel.app",
        "https://signal.eolas.fun",
    ]

    # Signal Engine
    MIN_CONFIDENCE_SCORE: int = 45  # signals fire at ≥ this score
    MIN_STRONG_SIGNALS: int = 2
    SIGNAL_COOLDOWN_MINUTES: int = 30  # don't re-signal same asset within this window
    LOOKBACK_PERIODS: int = 24  # hours for historical context

    # Trade parameters — ATR-based sizing preferred (see engine._compute_tp_sl)
    # These are fallback defaults when ATR is unavailable
    DEFAULT_SL_PCT: float = 0.06   # 6% stop loss — wider buffer, harder to stop out
    DEFAULT_TP1_PCT: float = 0.03  # 3% take profit 1 — tighter target, faster wins
    DEFAULT_TP2_PCT: float = 0.055 # 5.5% take profit 2 — tighter extended target

    # EOLAS DEX
    EOLAS_BASE_URL: str = "https://perps.eolas.fun"
    EOLAS_TRADE_PATH: str = "/trade"

    # Supported markets (must exist on EOLAS)
    SUPPORTED_SYMBOLS: List[str] = ["BTC", "ETH", "SOL", "BNB", "ARB", "OP"]

    # Data ingestion
    BINANCE_WS_URL: str = "wss://fstream.binance.com"
    BINANCE_REST_URL: str = "https://fapi.binance.com"

    BYBIT_WS_URL: str = "wss://stream.bybit.com/v5/public/linear"
    BYBIT_REST_URL: str = "https://api.bybit.com"

    OKX_WS_URL: str = "wss://ws.okx.com:8443/ws/v5/public"
    OKX_REST_URL: str = "https://www.okx.com"

    # Admin
    ADMIN_SECRET: str = ""  # set this in Railway env vars — required for /admin/reset

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHANNEL_ID: str = ""  # e.g. @your_channel or -1001234567890

    # API Keys (optional, raises rate limits)
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""

    # Refresh intervals
    SIGNAL_EVAL_INTERVAL_SECONDS: int = 60   # how often to evaluate signals
    DATA_REFRESH_INTERVAL_SECONDS: int = 30  # how often to refresh market data

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# EOLAS market mapping: external symbol -> EOLAS market id
EOLAS_MARKET_MAP = {
    "BTC":  {"market_id": "PERP_BTC_USDC",  "display": "Bitcoin"},
    "ETH":  {"market_id": "PERP_ETH_USDC",  "display": "Ethereum"},
    "SOL":  {"market_id": "PERP_SOL_USDC",  "display": "Solana"},
    "BNB":  {"market_id": "PERP_BNB_USDC",  "display": "BNB"},
    "ARB":  {"market_id": "PERP_ARB_USDC",  "display": "Arbitrum"},
    "OP":   {"market_id": "PERP_OP_USDC",   "display": "Optimism"},
}


def get_eolas_trade_url(
    symbol: str,
    side: str,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> str:
    """
    Generate an EOLAS DEX trade URL that pre-fills the exact signal trade.

    With price levels supplied the URL becomes a deep-link that opens the
    perp market with side, entry, SL, and TP already populated.
    Without price levels it falls back to a plain market page link.
    """
    from urllib.parse import urlencode

    market = EOLAS_MARKET_MAP.get(symbol, {})
    market_id = market.get("market_id", f"PERP_{symbol}_USDC")
    base = f"{settings.EOLAS_BASE_URL}/perp/{market_id}"

    params: dict = {"side": side.lower()}

    if entry_price and entry_price > 0:
        params["entry"] = round(entry_price, 6)
    if stop_loss and stop_loss > 0:
        params["sl"] = round(stop_loss, 6)
    if take_profit and take_profit > 0:
        params["tp"] = round(take_profit, 6)

    return f"{base}?{urlencode(params)}"
