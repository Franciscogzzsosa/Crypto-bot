from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from config.settings import settings
from data.binance_client import BinanceClient, Candle, OrderBook, TickerData

logger = logging.getLogger(__name__)


@dataclass
class EnrichedPair:
    symbol: str
    candles: list[Candle]
    ticker: TickerData
    order_book: OrderBook


class CryptoCollector:
    def __init__(self, client: BinanceClient) -> None:
        self._client = client

    async def collect(self) -> list[EnrichedPair]:
        tasks = [self._fetch_pair(sym) for sym in settings.TRADING_PAIRS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        enriched = []
        for sym, result in zip(settings.TRADING_PAIRS, results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch %s: %s", sym, result)
            else:
                enriched.append(result)
        return enriched

    async def _fetch_pair(self, symbol: str) -> EnrichedPair:
        candles, ticker, order_book = await asyncio.gather(
            self._client.get_klines(symbol, settings.KLINE_INTERVAL, settings.KLINE_LIMIT),
            self._client.get_ticker(symbol),
            self._client.get_order_book(symbol),
        )
        return EnrichedPair(symbol=symbol, candles=candles, ticker=ticker, order_book=order_book)
