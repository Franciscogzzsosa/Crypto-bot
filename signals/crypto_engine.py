from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from config.settings import settings
from data.collector import EnrichedPair
from signals.technical_indicators import bollinger_bands, ema, macd, rsi

logger = logging.getLogger(__name__)


@dataclass
class IndicatorSnapshot:
    rsi: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    macd_prev_hist: float
    ema_fast: float
    ema_slow: float
    bb_upper: float
    bb_mid: float
    bb_lower: float


@dataclass
class CryptoSignal:
    symbol: str
    side: Literal["BUY", "SELL"] | None
    reason: str
    confidence: float
    current_price: float
    indicators: IndicatorSnapshot | None
    rejected: bool = False
    rejection_reason: str | None = None
    detected_at: datetime = field(default_factory=datetime.utcnow)


class CryptoSignalEngine:
    def analyze(self, pair: EnrichedPair, open_symbols: set[str]) -> CryptoSignal:
        closes = [c.close for c in pair.candles]
        price = pair.ticker.price

        if len(closes) < settings.MACD_SLOW + settings.MACD_SIGNAL_PERIOD:
            return CryptoSignal(
                symbol=pair.symbol,
                side=None,
                reason="",
                confidence=0.0,
                current_price=price,
                indicators=None,
                rejected=True,
                rejection_reason="insufficient_candles",
            )

        rsi_val = rsi(closes, settings.RSI_PERIOD)
        macd_line, macd_sig, macd_hist = macd(closes, settings.MACD_FAST, settings.MACD_SLOW, settings.MACD_SIGNAL_PERIOD)
        ema_fast_val = ema(closes, settings.EMA_FAST)
        ema_slow_val = ema(closes, settings.EMA_SLOW)
        bb_upper, bb_mid, bb_lower = bollinger_bands(closes, settings.BB_PERIOD, settings.BB_STD)

        # Previous MACD histogram for crossover detection
        closes_prev = closes[:-1]
        _, _, macd_prev_hist = macd(closes_prev, settings.MACD_FAST, settings.MACD_SLOW, settings.MACD_SIGNAL_PERIOD)

        indicators = IndicatorSnapshot(
            rsi=rsi_val,
            macd_line=macd_line,
            macd_signal=macd_sig,
            macd_hist=macd_hist,
            macd_prev_hist=macd_prev_hist,
            ema_fast=ema_fast_val,
            ema_slow=ema_slow_val,
            bb_upper=bb_upper,
            bb_mid=bb_mid,
            bb_lower=bb_lower,
        )

        # Score BUY conditions
        buy_reasons: list[str] = []
        if rsi_val < settings.RSI_OVERSOLD:
            buy_reasons.append("RSI_OVERSOLD")
        if macd_prev_hist < 0 < macd_hist:
            buy_reasons.append("MACD_BULL_CROSS")
        if ema_fast_val > ema_slow_val:
            buy_reasons.append("EMA_BULL")
        if price <= bb_lower:
            buy_reasons.append("BB_LOWER")

        # Score SELL conditions (short signal — price overbought)
        sell_reasons: list[str] = []
        if rsi_val > settings.RSI_OVERBOUGHT:
            sell_reasons.append("RSI_OVERBOUGHT")
        if macd_prev_hist > 0 > macd_hist:
            sell_reasons.append("MACD_BEAR_CROSS")
        if ema_fast_val < ema_slow_val:
            sell_reasons.append("EMA_BEAR")
        if price >= bb_upper:
            sell_reasons.append("BB_UPPER")

        if len(buy_reasons) >= settings.MIN_SIGNAL_SCORE:
            side: Literal["BUY", "SELL"] = "BUY"
            reasons = buy_reasons
        elif len(sell_reasons) >= settings.MIN_SIGNAL_SCORE:
            side = "SELL"
            reasons = sell_reasons
        else:
            return CryptoSignal(
                symbol=pair.symbol,
                side=None,
                reason=f"score_insufficient buy={len(buy_reasons)} sell={len(sell_reasons)}",
                confidence=0.0,
                current_price=price,
                indicators=indicators,
                rejected=True,
                rejection_reason="no_signal",
            )

        confidence = len(reasons) / 4.0

        # Only open new BUY if not already in this symbol
        if side == "BUY" and pair.symbol in open_symbols:
            return CryptoSignal(
                symbol=pair.symbol,
                side=side,
                reason="+".join(reasons),
                confidence=confidence,
                current_price=price,
                indicators=indicators,
                rejected=True,
                rejection_reason="already_open",
            )

        signal = CryptoSignal(
            symbol=pair.symbol,
            side=side,
            reason="+".join(reasons),
            confidence=confidence,
            current_price=price,
            indicators=indicators,
        )
        logger.info("Signal %s %s conf=%.2f reason=%s", side, pair.symbol, confidence, signal.reason)
        return signal
