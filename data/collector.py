from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from config.settings import settings
from data.binance_client import BinanceClient, Candle, OrderBook, TickerData

logger = logging.getLogger(__name__)

# Max concurrent requests to avoid hitting rate limits
_SEMAPHORE_SIZE = 10


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
        pairs = settings.TRADING_PAIRS

        # Dynamic discovery when user sets TRADING_PAIRS=["ALL"]
        if pairs == ["ALL"]:
            pairs = await self._client.get_all_usdt_pairs(
                min_volume_usd=settings.MIN_VOLUME_USD
            )

        sem = asyncio.Semaphore(_SEMAPHORE_SIZE)
        tasks = [self._fetch_pair(sym, sem) for sym in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        enriched = []
        for sym, result in zip(pairs, results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch %s: %s", sym, result)
            else:
                enriched.append(result)

        logger.info("Collected %d/%d pairs", len(enriched), len(pairs))
        return enriched

    async def _fetch_pair(self, symbol: str, sem: asyncio.Semaphore) -> EnrichedPair:
        async with sem:
            candles, ticker, order_book = await asyncio.gather(
                self._client.get_klines(symbol, settings.KLINE_INTERVAL, settings.KLINE_LIMIT),
                self._client.get_ticker(symbol),
                self._client.get_order_book(symbol),
            )
            return EnrichedPair(symbol=symbol, candles=candles, ticker=ticker, order_book=order_book)
