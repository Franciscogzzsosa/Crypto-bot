from __future__ import annotations

import logging
from dataclasses import dataclass

from trading.crypto_paper_engine import PaperEngineState

logger = logging.getLogger(__name__)


@dataclass
class PortfolioStats:
    balance: float
    initial_balance: float
    total_equity: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_pnl_pct: float
    open_positions: int
    total_exposure: float
    exposure_pct: float


class PortfolioManager:
    def compute_stats(self, state: PaperEngineState, current_prices: dict[str, float] | None = None) -> PortfolioStats:
        current_prices = current_prices or {}

        unrealized = 0.0
        for trade in state.open_trades:
            price = current_prices.get(trade.symbol, trade.entry_price)
            unrealized += (price - trade.entry_price) * trade.shares

        realized = sum(t.realized_pnl or 0.0 for t in state.closed_trades)
        total_pnl = unrealized + realized
        total_equity = state.balance + state.total_exposure + unrealized
        total_pnl_pct = total_pnl / state.initial_balance if state.initial_balance else 0.0
        exposure_pct = state.total_exposure / state.initial_balance if state.initial_balance else 0.0

        return PortfolioStats(
            balance=state.balance,
            initial_balance=state.initial_balance,
            total_equity=total_equity,
            unrealized_pnl=unrealized,
            realized_pnl=realized,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            open_positions=len(state.open_trades),
            total_exposure=state.total_exposure,
            exposure_pct=exposure_pct,
        )

    def log_summary(self, stats: PortfolioStats) -> None:
        logger.info(
            "Portfolio | balance=$%.2f equity=$%.2f pnl=$%.2f (%.2f%%) open=%d exposure=$%.2f",
            stats.balance,
            stats.total_equity,
            stats.total_pnl,
            stats.total_pnl_pct * 100,
            stats.open_positions,
            stats.total_exposure,
        )
