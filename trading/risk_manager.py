from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import settings
from signals.crypto_engine import CryptoSignal

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    approved: bool
    reason: str
    event_type: str | None = None
    value: float | None = None
    threshold: float | None = None


class RiskManager:
    def __init__(self, initial_balance: float) -> None:
        self._initial = initial_balance

    def validate(
        self,
        signal: CryptoSignal,
        balance: float,
        realized_pnl_today: float,
        open_count: int,
    ) -> RiskCheck:
        # 1. Daily loss stop
        daily_pnl_pct = realized_pnl_today / self._initial
        if daily_pnl_pct <= settings.DAILY_LOSS_STOP:
            return RiskCheck(
                approved=False,
                reason=f"daily_loss_stop: {daily_pnl_pct:.2%} <= {settings.DAILY_LOSS_STOP:.2%}",
                event_type="DAILY_LOSS_STOP",
                value=daily_pnl_pct,
                threshold=settings.DAILY_LOSS_STOP,
            )

        # 2. Max open trades
        if open_count >= settings.MAX_OPEN_TRADES:
            return RiskCheck(
                approved=False,
                reason=f"max_open_trades: {open_count}/{settings.MAX_OPEN_TRADES}",
                event_type="MAX_OPEN_TRADES",
                value=float(open_count),
                threshold=float(settings.MAX_OPEN_TRADES),
            )

        # 3. Insufficient balance
        size = balance * settings.MAX_BET_PCT
        if size < 1.0:
            return RiskCheck(
                approved=False,
                reason=f"insufficient_balance: size=${size:.2f}",
                event_type="INSUFFICIENT_BALANCE",
                value=size,
                threshold=1.0,
            )

        return RiskCheck(approved=True, reason="ok")

    def compute_position_size(self, balance: float) -> float:
        return balance * settings.MAX_BET_PCT
