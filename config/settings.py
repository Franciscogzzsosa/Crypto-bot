from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MODE: Literal["DRY_RUN", "PAPER_TRADING"] = "DRY_RUN"
    PAPER_BALANCE: float = 10000.0
    TRADING_PAIRS: list[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # Binance fetch params
    KLINE_INTERVAL: str = "1h"
    KLINE_LIMIT: int = 100

    # Technical indicator params
    RSI_PERIOD: int = 14
    RSI_OVERSOLD: float = 30.0
    RSI_OVERBOUGHT: float = 70.0
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL_PERIOD: int = 9
    EMA_FAST: int = 9
    EMA_SLOW: int = 21
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    MIN_SIGNAL_SCORE: int = 2

    # Risk
    STOP_LOSS_PCT: float = 0.05
    TAKE_PROFIT_PCT: float = 0.15
    MAX_BET_PCT: float = 0.01
    MAX_OPEN_TRADES: int = 3
    DAILY_LOSS_STOP: float = -0.05
    SLIPPAGE_PCT: float = 0.001
    TAKER_FEE: float = 0.001

    # Scheduler
    CYCLE_INTERVAL_SECONDS: int = 60

    # DB
    DATABASE_URL: str = "sqlite+aiosqlite:///./crypto_bot.db"

    LOG_LEVEL: str = "INFO"

    @field_validator("TRADING_PAIRS", mode="before")
    @classmethod
    def parse_pairs(cls, v):
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v


settings = Settings()
