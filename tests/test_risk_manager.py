import pytest
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from config.settings import settings
from signals.crypto_engine import CryptoSignal
from trading.risk_manager import RiskManager


def _signal(symbol="BTCUSDT") -> CryptoSignal:
    return CryptoSignal(
        symbol=symbol, side="BUY", reason="RSI_OVERSOLD",
        confidence=0.5, current_price=50000.0, indicators=None,
    )


def test_approved():
    rm = RiskManager(10000.0)
    check = rm.validate(_signal(), balance=10000.0, realized_pnl_today=0.0, open_count=0)
    assert check.approved


def test_daily_loss_stop():
    rm = RiskManager(10000.0)
    check = rm.validate(_signal(), balance=9400.0, realized_pnl_today=-600.0, open_count=0)
    assert not check.approved
    assert check.event_type == "DAILY_LOSS_STOP"


def test_max_open_trades():
    rm = RiskManager(10000.0)
    check = rm.validate(_signal(), balance=10000.0, realized_pnl_today=0.0, open_count=3)
    assert not check.approved
    assert check.event_type == "MAX_OPEN_TRADES"


def test_insufficient_balance():
    rm = RiskManager(10000.0)
    check = rm.validate(_signal(), balance=0.5, realized_pnl_today=0.0, open_count=0)
    assert not check.approved
    assert check.event_type == "INSUFFICIENT_BALANCE"


def test_position_size():
    rm = RiskManager(10000.0)
    size = rm.compute_position_size(10000.0)
    assert abs(size - 10000.0 * settings.MAX_BET_PCT) < 0.01
