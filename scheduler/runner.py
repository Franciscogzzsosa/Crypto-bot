from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from data.binance_client import BinanceClient
from data.collector import CryptoCollector, EnrichedPair
from db.database import AsyncSessionLocal, init_db
from db.models import (
    CryptoPair, MarketSnapshot, PortfolioSnapshot,
    RiskEvent, Signal as SignalModel,
    PaperTrade as PaperTradeModel, StrategyRun,
)
from portfolio.manager import PortfolioManager
from signals.crypto_engine import CryptoSignalEngine
from trading.crypto_paper_engine import CryptoPaperEngine, CryptoPaperTrade
from trading.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class BotRunner:
    def __init__(self) -> None:
        self.engine = CryptoPaperEngine(settings.PAPER_BALANCE)
        self.risk = RiskManager(settings.PAPER_BALANCE)
        self.signal_engine = CryptoSignalEngine()
        self.portfolio = PortfolioManager()
        self._cycle_count = 0

    async def run_cycle(self) -> None:
        cycle_start = time.monotonic()
        self._cycle_count += 1
        logger.info("=== Cycle %d started | mode=%s ===", self._cycle_count, settings.MODE)

        run = StrategyRun(mode=settings.MODE, started_at=datetime.utcnow())
        pairs_analyzed = 0
        signals_detected = 0
        trades_executed = 0
        trades_rejected = 0
        error_msg = None

        try:
            async with BinanceClient() as client:
                collector = CryptoCollector(client)
                enriched_list: list[EnrichedPair] = await collector.collect()

            pairs_analyzed = len(enriched_list)
            current_prices = {e.symbol: e.ticker.price for e in enriched_list}

            async with AsyncSessionLocal() as db:
                for enriched in enriched_list:
                    await self._upsert_pair(db, enriched.symbol)
                    await self._save_snapshot(db, enriched)
                await db.commit()

            # Check exits on open positions
            if settings.MODE == "PAPER_TRADING":
                closed = self.engine.check_exits(current_prices)
                if closed:
                    async with AsyncSessionLocal() as db:
                        for trade in closed:
                            await self._update_trade_in_db(db, trade)
                        await db.commit()

            open_symbols = self.engine.state.open_symbols

            for enriched in enriched_list:
                signal = self.signal_engine.analyze(enriched, open_symbols)

                async with AsyncSessionLocal() as db:
                    signal_model = await self._save_signal(db, signal)
                    await db.commit()

                if signal.rejected:
                    continue

                signals_detected += 1

                if settings.MODE == "DRY_RUN":
                    trades_rejected += 1
                    continue

                risk_check = self.risk.validate(
                    signal,
                    balance=self.engine.state.balance,
                    realized_pnl_today=self.engine.state.realized_pnl_today,
                    open_count=len(self.engine.state.open_trades),
                )

                if not risk_check.approved:
                    trades_rejected += 1
                    logger.debug("Risk rejected %s: %s", signal.symbol, risk_check.reason)
                    if risk_check.event_type:
                        async with AsyncSessionLocal() as db:
                            await self._save_risk_event(db, signal.symbol, risk_check)
                            await db.commit()
                    continue

                size_usd = self.risk.compute_position_size(self.engine.state.balance)
                trade = self.engine.simulate_buy(signal, size_usd, signal_model.id if signal_model else None)

                if trade:
                    trades_executed += 1
                    open_symbols = self.engine.state.open_symbols
                    async with AsyncSessionLocal() as db:
                        await self._save_trade(db, trade)
                        await db.commit()

            stats = self.portfolio.compute_stats(self.engine.state, current_prices)
            self.portfolio.log_summary(stats)

            async with AsyncSessionLocal() as db:
                await self._save_portfolio_snapshot(db, stats)
                await db.commit()

        except Exception as e:
            error_msg = str(e)
            logger.exception("Cycle %d error: %s", self._cycle_count, e)

        finally:
            duration_ms = int((time.monotonic() - cycle_start) * 1000)
            async with AsyncSessionLocal() as db:
                run.pairs_analyzed = pairs_analyzed
                run.signals_detected = signals_detected
                run.trades_executed = trades_executed
                run.trades_rejected = trades_rejected
                run.cycle_duration_ms = duration_ms
                run.error = error_msg
                run.finished_at = datetime.utcnow()
                db.add(run)
                await db.commit()

            logger.info(
                "=== Cycle %d done | %dms | pairs=%d signals=%d trades=%d rejected=%d ===",
                self._cycle_count, duration_ms, pairs_analyzed,
                signals_detected, trades_executed, trades_rejected,
            )

    # ── DB helpers ──────────────────────────────────────────────────────────

    async def _upsert_pair(self, db, symbol: str) -> None:
        from sqlalchemy import select
        result = await db.execute(select(CryptoPair).where(CryptoPair.symbol == symbol))
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(CryptoPair(symbol=symbol, active=True))

    async def _save_snapshot(self, db, enriched: EnrichedPair) -> None:
        ind = None
        from signals.technical_indicators import bollinger_bands, ema, macd, rsi
        closes = [c.close for c in enriched.candles]
        if len(closes) >= settings.MACD_SLOW + settings.MACD_SIGNAL_PERIOD:
            from signals.crypto_engine import IndicatorSnapshot
            macd_line, macd_sig, macd_hist = macd(closes, settings.MACD_FAST, settings.MACD_SLOW, settings.MACD_SIGNAL_PERIOD)
            bb_upper, bb_mid, bb_lower = bollinger_bands(closes, settings.BB_PERIOD, settings.BB_STD)
            ind = {
                "rsi": rsi(closes, settings.RSI_PERIOD),
                "macd": macd_line, "macd_signal": macd_sig, "macd_hist": macd_hist,
                "ema_fast": ema(closes, settings.EMA_FAST), "ema_slow": ema(closes, settings.EMA_SLOW),
                "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
            }

        ob = enriched.order_book
        db.add(MarketSnapshot(
            symbol=enriched.symbol,
            price=enriched.ticker.price,
            volume_24h=enriched.ticker.volume_24h,
            price_change_pct=enriched.ticker.price_change_pct,
            best_bid=ob.best_bid,
            best_ask=ob.best_ask,
            spread=ob.spread,
            **(ind or {}),
        ))

    async def _save_signal(self, db, signal) -> SignalModel:
        model = SignalModel(
            symbol=signal.symbol,
            side=signal.side,
            reason=signal.reason,
            confidence=signal.confidence,
            current_price=signal.current_price,
            rejected=signal.rejected,
            rejection_reason=signal.rejection_reason,
            detected_at=signal.detected_at,
        )
        db.add(model)
        await db.flush()
        return model

    async def _save_trade(self, db, trade: CryptoPaperTrade) -> None:
        db.add(PaperTradeModel(
            symbol=trade.symbol,
            side=trade.side,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            size_usd=trade.size_usd,
            shares=trade.shares,
            fee_paid=trade.fee_paid,
            slippage_cost=trade.slippage_cost,
            stop_loss_price=trade.stop_loss_price,
            take_profit_price=trade.take_profit_price,
            realized_pnl=trade.realized_pnl,
            status=trade.status,
            exit_reason=trade.exit_reason,
            signal_id=trade.signal_id,
            confidence=trade.confidence,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
        ))

    async def _update_trade_in_db(self, db, trade: CryptoPaperTrade) -> None:
        from sqlalchemy import select
        result = await db.execute(
            select(PaperTradeModel)
            .where(PaperTradeModel.symbol == trade.symbol, PaperTradeModel.status == "OPEN")
            .order_by(PaperTradeModel.opened_at.desc())
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.exit_price = trade.exit_price
            existing.realized_pnl = trade.realized_pnl
            existing.status = trade.status
            existing.exit_reason = trade.exit_reason
            existing.closed_at = trade.closed_at

    async def _save_portfolio_snapshot(self, db, stats) -> None:
        db.add(PortfolioSnapshot(
            balance=stats.balance,
            initial_balance=stats.initial_balance,
            total_equity=stats.total_equity,
            unrealized_pnl=stats.unrealized_pnl,
            realized_pnl=stats.realized_pnl,
            total_pnl=stats.total_pnl,
            total_pnl_pct=stats.total_pnl_pct,
            open_positions_count=stats.open_positions,
            total_exposure=stats.total_exposure,
        ))

    async def _save_risk_event(self, db, symbol: str, risk_check) -> None:
        db.add(RiskEvent(
            event_type=risk_check.event_type,
            symbol=symbol,
            description=risk_check.reason,
            value=risk_check.value,
            threshold=risk_check.threshold,
        ))


async def run_bot() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    await init_db()
    runner = BotRunner()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        runner.run_cycle,
        "interval",
        seconds=settings.CYCLE_INTERVAL_SECONDS,
        max_instances=1,
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()
    logger.info(
        "Crypto Bot started | mode=%s | interval=%ds | balance=%.2f | pairs=%s",
        settings.MODE,
        settings.CYCLE_INTERVAL_SECONDS,
        settings.PAPER_BALANCE,
        settings.TRADING_PAIRS,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Bot stopped.")
