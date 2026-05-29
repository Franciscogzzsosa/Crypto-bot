from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com"
_CIRCUIT_BREAK_THRESHOLD = 3
_CIRCUIT_BREAK_PAUSE = 60.0


@dataclass
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TickerData:
    symbol: str
    price: float
    volume_24h: float
    price_change_pct: float
    bid: float
    ask: float


@dataclass
class OrderBook:
    symbol: str
    bids: list[tuple[float, float]]  # (price, qty)
    asks: list[tuple[float, float]]

    @property
    def best_bid(self) -> float | None:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> float | None:
        return self.asks[0][0] if self.asks else None

    @property
    def spread(self) -> float | None:
        if self.best_bid and self.best_ask and self.best_ask > 0:
            return (self.best_ask - self.best_bid) / self.best_ask
        return None


class BinanceClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._errors = 0
        self._paused_until: float = 0.0

    async def __aenter__(self) -> BinanceClient:
        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict) -> dict | list:
        import time

        if time.monotonic() < self._paused_until:
            remaining = self._paused_until - time.monotonic()
            logger.warning("BinanceClient circuit open — waiting %.0fs", remaining)
            await asyncio.sleep(remaining)

        assert self._client is not None
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            self._errors = 0
            return resp.json()
        except Exception as exc:
            self._errors += 1
            logger.error("Binance API error (%d/%d): %s", self._errors, _CIRCUIT_BREAK_THRESHOLD, exc)
            if self._errors >= _CIRCUIT_BREAK_THRESHOLD:
                import time as _time
                self._paused_until = _time.monotonic() + _CIRCUIT_BREAK_PAUSE
                logger.warning("Circuit breaker open for %.0fs", _CIRCUIT_BREAK_PAUSE)
                self._errors = 0
            raise

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[Candle]:
        data = await self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        candles = []
        for row in data:
            candles.append(Candle(
                open_time=datetime.fromtimestamp(row[0] / 1000),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            ))
        return candles

    async def get_ticker(self, symbol: str) -> TickerData:
        data = await self._get("/api/v3/ticker/24hr", {"symbol": symbol})
        return TickerData(
            symbol=symbol,
            price=float(data["lastPrice"]),
            volume_24h=float(data["quoteVolume"]),
            price_change_pct=float(data["priceChangePercent"]),
            bid=float(data["bidPrice"]),
            ask=float(data["askPrice"]),
        )

    async def get_order_book(self, symbol: str, limit: int = 10) -> OrderBook:
        data = await self._get("/api/v3/depth", {"symbol": symbol, "limit": limit})
        return OrderBook(
            symbol=symbol,
            bids=[(float(p), float(q)) for p, q in data["bids"]],
            asks=[(float(p), float(q)) for p, q in data["asks"]],
        )
