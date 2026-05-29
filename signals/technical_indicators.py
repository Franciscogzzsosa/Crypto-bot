from __future__ import annotations

import math


def ema(values: list[float], period: int) -> float:
    if len(values) < period:
        return sum(values) / len(values)
    k = 2.0 / (period + 1)
    result = sum(values[:period]) / period
    for v in values[period:]:
        result = v * k + result * (1 - k)
    return result


def rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """Returns (macd_line, signal_line, histogram)."""
    if len(closes) < slow + signal_period:
        return 0.0, 0.0, 0.0
    ema_fast = _ema_series(closes, fast)
    ema_slow = _ema_series(closes, slow)
    macd_series = [f - s for f, s in zip(ema_fast[-len(ema_slow):], ema_slow)]
    signal_line = ema(macd_series, signal_period)
    macd_line = macd_series[-1]
    return macd_line, signal_line, macd_line - signal_line


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[float, float, float]:
    """Returns (upper, mid, lower)."""
    if len(closes) < period:
        mid = sum(closes) / len(closes)
        return mid, mid, mid
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    return mid + num_std * std, mid, mid - num_std * std


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return [sum(values) / len(values)] * len(values)
    k = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result
