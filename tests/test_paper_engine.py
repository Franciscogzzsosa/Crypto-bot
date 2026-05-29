import pytest
from signals.crypto_engine import CryptoSignal
from trading.crypto_paper_engine import CryptoPaperEngine


def _signal(price=50000.0) -> CryptoSignal:
    return CryptoSignal(
        symbol="BTCUSDT", side="BUY", reason="RSI_OVERSOLD",
        confidence=0.5, current_price=price, indicators=None,
    )


def test_simulate_buy_reduces_balance():
    engine = CryptoPaperEngine(10000.0)
    size = 100.0
    trade = engine.simulate_buy(_signal(), size)
    assert trade is not None
    assert engine.state.balance < 10000.0
    assert len(engine.state.open_trades) == 1


def test_simulate_buy_sets_stop_take():
    engine = CryptoPaperEngine(10000.0)
    trade = engine.simulate_buy(_signal(50000.0), 100.0)
    assert trade.stop_loss_price < trade.entry_price
    assert trade.take_profit_price > trade.entry_price


def test_take_profit_exit():
    engine = CryptoPaperEngine(10000.0)
    trade = engine.simulate_buy(_signal(50000.0), 100.0)
    tp_price = trade.take_profit_price * 1.01
    closed = engine.check_exits({"BTCUSDT": tp_price})
    assert len(closed) == 1
    assert closed[0].exit_reason == "TAKE_PROFIT"
    assert closed[0].realized_pnl > 0


def test_stop_loss_exit():
    engine = CryptoPaperEngine(10000.0)
    trade = engine.simulate_buy(_signal(50000.0), 100.0)
    sl_price = trade.stop_loss_price * 0.99
    closed = engine.check_exits({"BTCUSDT": sl_price})
    assert len(closed) == 1
    assert closed[0].exit_reason == "STOP_LOSS"
    assert closed[0].realized_pnl < 0


def test_no_exit_when_price_in_range():
    engine = CryptoPaperEngine(10000.0)
    engine.simulate_buy(_signal(50000.0), 100.0)
    closed = engine.check_exits({"BTCUSDT": 50000.0})
    assert len(closed) == 0
    assert len(engine.state.open_trades) == 1


def test_insufficient_balance_returns_none():
    engine = CryptoPaperEngine(0.5)
    trade = engine.simulate_buy(_signal(), 100.0)
    assert trade is None
