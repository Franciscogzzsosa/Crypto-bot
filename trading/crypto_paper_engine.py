from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from config.settings import settings
from signals.crypto_engine import CryptoSignal

logger = logging.getLogger(__name__)


@dataclass
class CryptoPaperTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float | None
    size_usd: float
    shares: float
    fee_paid: float
    slippage_cost: float
    stop_loss_price: float
    take_profit_price: float
    realized_pnl: float | None
    status: str  # OPEN / CLOSED
    exit_reason: str | None
    signal_id: int | None
    confidence: float
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None


@dataclass
class PaperEngineState:
    balance: float
    initial_balance: float
    open_trades: list[CryptoPaperTrade] = field(default_factory=list)
    closed_trades: list[CryptoPaperTrade] = field(default_factory=list)

    @property
    def open_symbols(self) -> set[str]:
        return {t.symbol for t in self.open_trades}

    @property
    def total_exposure(self) -> float:
        return sum(t.size_usd for t in self.open_trades)

    @property
    def realized_pnl_today(self) -> float:
        today = datetime.utcnow().date()
        return sum(
            t.realized_pnl or 0.0
            for t in self.closed_trades
            if t.closed_at and t.closed_at.date() == today
        )


class CryptoPaperEngine:
    def __init__(self, initial_balance: float) -> None:
        self.state = PaperEngineState(
            balance=initial_balance,
            initial_balance=initial_balance,
        )

    def simulate_buy(self, signal: CryptoSignal, size_usd: float, signal_id: int | None = None) -> CryptoPaperTrade | None:
        ask = signal.current_price  # use current price as proxy for ask

        slippage_cost = size_usd * settings.SLIPPAGE_PCT
        exec_price = ask * (1 + settings.SLIPPAGE_PCT)
        fee = size_usd * settings.TAKER_FEE
        net_size = size_usd - fee - slippage_cost
        if net_size <= 0 or self.state.balance < size_usd:
            return None

        shares = net_size / exec_price
        stop_loss = exec_price * (1 - settings.STOP_LOSS_PCT)
        take_profit = exec_price * (1 + settings.TAKE_PROFIT_PCT)

        self.state.balance -= size_usd

        trade = CryptoPaperTrade(
            symbol=signal.symbol,
            side="BUY",
            entry_price=exec_price,
            exit_price=None,
            size_usd=size_usd,
            shares=shares,
            fee_paid=fee,
            slippage_cost=slippage_cost,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            realized_pnl=None,
            status="OPEN",
            exit_reason=None,
            signal_id=signal_id,
            confidence=signal.confidence,
        )
        self.state.open_trades.append(trade)
        logger.info(
            "BUY %s @ %.4f | size=$%.2f | sl=%.4f | tp=%.4f",
            signal.symbol, exec_price, size_usd, stop_loss, take_profit,
        )
        return trade

    def check_exits(self, current_prices: dict[str, float]) -> list[CryptoPaperTrade]:
        closed: list[CryptoPaperTrade] = []
        still_open: list[CryptoPaperTrade] = []

        for trade in self.state.open_trades:
            price = current_prices.get(trade.symbol)
            if price is None:
                still_open.append(trade)
                continue

            exit_reason: str | None = None
            if price >= trade.take_profit_price:
                exit_reason = "TAKE_PROFIT"
            elif price <= trade.stop_loss_price:
                exit_reason = "STOP_LOSS"

            if exit_reason:
                exit_price = price * (1 - settings.SLIPPAGE_PCT)
                exit_fee = trade.shares * exit_price * settings.TAKER_FEE
                proceeds = trade.shares * exit_price - exit_fee
                trade.exit_price = exit_price
                trade.realized_pnl = proceeds - trade.size_usd
                trade.status = "CLOSED"
                trade.exit_reason = exit_reason
                trade.closed_at = datetime.utcnow()
                self.state.balance += proceeds
                self.state.closed_trades.append(trade)
                closed.append(trade)
                logger.info(
                    "EXIT %s %s @ %.4f | pnl=$%.2f",
                    exit_reason, trade.symbol, exit_price, trade.realized_pnl,
                )
            else:
                still_open.append(trade)

        self.state.open_trades = still_open
        return closed
