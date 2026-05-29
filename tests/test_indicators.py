import pytest
from signals.technical_indicators import bollinger_bands, ema, macd, rsi


def test_rsi_oversold():
    # Falling prices → RSI should be low
    closes = [100 - i for i in range(20)]
    val = rsi(closes)
    assert val < 40


def test_rsi_overbought():
    # Rising prices → RSI should be high
    closes = [100 + i for i in range(20)]
    val = rsi(closes)
    assert val > 60


def test_rsi_neutral():
    # Alternating up/down → equal gains and losses → RSI near 50
    closes = [50.0 + (1 if i % 2 == 0 else -1) for i in range(20)]
    val = rsi(closes)
    assert 40 <= val <= 60


def test_ema_converges():
    # EMA of constant series = constant
    val = ema([50.0] * 50, period=14)
    assert abs(val - 50.0) < 0.01


def test_macd_returns_tuple():
    closes = [float(100 + i % 5) for i in range(50)]
    m, s, h = macd(closes)
    assert isinstance(m, float)
    assert isinstance(s, float)
    assert abs(h - (m - s)) < 1e-9


def test_bollinger_bands_width():
    # Volatile series should have wide bands
    closes = [100.0 if i % 2 == 0 else 110.0 for i in range(30)]
    upper, mid, lower = bollinger_bands(closes)
    assert upper > mid > lower
    assert upper - lower > 5


def test_bollinger_flat():
    closes = [100.0] * 30
    upper, mid, lower = bollinger_bands(closes)
    assert abs(upper - 100.0) < 0.001
    assert abs(lower - 100.0) < 0.001
