from __future__ import annotations

import asyncio
import logging

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text

from config.settings import settings
from db.database import AsyncSessionLocal, init_db
from db.models import PaperTrade, PortfolioSnapshot, Signal, StrategyRun
from sqlalchemy import desc, select

logger = logging.getLogger(__name__)
console = Console()


def _pnl_color(val: float | None) -> str:
    if val is None:
        return "white"
    return "green" if val >= 0 else "red"


async def _build_layout() -> Layout:
    async with AsyncSessionLocal() as db:
        snap_result = await db.execute(
            select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.created_at)).limit(1)
        )
        snap = snap_result.scalar_one_or_none()

        trades_result = await db.execute(
            select(PaperTrade).order_by(desc(PaperTrade.opened_at)).limit(10)
        )
        trades = trades_result.scalars().all()

        signals_result = await db.execute(
            select(Signal).where(Signal.rejected == False)  # noqa: E712
            .order_by(desc(Signal.detected_at)).limit(5)
        )
        signals = signals_result.scalars().all()

        runs_result = await db.execute(
            select(StrategyRun).order_by(desc(StrategyRun.started_at)).limit(3)
        )
        runs = runs_result.scalars().all()

    # Portfolio panel
    portfolio_table = Table(show_header=False, box=None, padding=(0, 1))
    portfolio_table.add_column("Key", style="dim")
    portfolio_table.add_column("Value")

    if snap:
        pnl_color = _pnl_color(snap.total_pnl)
        portfolio_table.add_row("Balance", f"[bold]${snap.balance:,.2f}[/bold] / ${snap.initial_balance:,.2f}")
        portfolio_table.add_row("Total P&L", f"[{pnl_color}]{snap.total_pnl:+.2f} ({snap.total_pnl_pct*100:+.2f}%)[/{pnl_color}]")
        portfolio_table.add_row("Open positions", str(snap.open_positions_count))
        portfolio_table.add_row("Exposure", f"${snap.total_exposure:,.2f}")
    else:
        portfolio_table.add_row("Status", "No data yet — run a cycle first")

    # Trades table
    trades_table = Table(title="Recent Trades", show_lines=False)
    trades_table.add_column("Symbol", style="cyan")
    trades_table.add_column("Side")
    trades_table.add_column("Entry", justify="right")
    trades_table.add_column("Exit", justify="right")
    trades_table.add_column("P&L", justify="right")
    trades_table.add_column("Status")
    trades_table.add_column("Reason")

    for t in trades:
        pnl_str = f"{t.realized_pnl:+.4f}" if t.realized_pnl is not None else "-"
        pnl_color = _pnl_color(t.realized_pnl)
        trades_table.add_row(
            t.symbol,
            f"[{'green' if t.side == 'BUY' else 'red'}]{t.side}[/]",
            f"${t.entry_price:.4f}",
            f"${t.exit_price:.4f}" if t.exit_price else "-",
            f"[{pnl_color}]{pnl_str}[/{pnl_color}]",
            t.status,
            t.exit_reason or "-",
        )

    # Signals table
    signals_table = Table(title="Recent Signals", show_lines=False)
    signals_table.add_column("Symbol", style="cyan")
    signals_table.add_column("Side")
    signals_table.add_column("Price", justify="right")
    signals_table.add_column("Conf", justify="right")
    signals_table.add_column("Reason")

    for s in signals:
        signals_table.add_row(
            s.symbol,
            f"[{'green' if s.side == 'BUY' else 'red'}]{s.side or '-'}[/]",
            f"${s.current_price:.4f}" if s.current_price else "-",
            f"{s.confidence*100:.0f}%" if s.confidence else "-",
            s.reason or "-",
        )

    # Cycles
    runs_table = Table(title="Last Cycles", show_lines=False)
    runs_table.add_column("Mode")
    runs_table.add_column("Pairs", justify="right")
    runs_table.add_column("Signals", justify="right")
    runs_table.add_column("Trades", justify="right")
    runs_table.add_column("ms", justify="right")
    runs_table.add_column("Error")

    for r in runs:
        runs_table.add_row(
            r.mode, str(r.pairs_analyzed), str(r.signals_detected),
            str(r.trades_executed), str(r.cycle_duration_ms or "-"),
            f"[red]{r.error[:40]}[/red]" if r.error else "",
        )

    layout = Layout()
    layout.split_column(
        Layout(portfolio_table, name="portfolio", size=8),
        Layout(trades_table, name="trades"),
        Layout(signals_table, name="signals", size=10),
        Layout(runs_table, name="runs", size=8),
    )
    return layout


async def run_dashboard() -> None:
    await init_db()
    console.print("[bold cyan]Crypto Paper Bot — Live Dashboard[/bold cyan]")
    console.print(f"[dim]Pairs: {settings.TRADING_PAIRS} | Mode: {settings.MODE}[/dim]\n")

    with Live(console=console, refresh_per_second=0.1) as live:
        while True:
            try:
                layout = await _build_layout()
                live.update(layout)
            except Exception as e:
                logger.error("Dashboard error: %s", e)
            await asyncio.sleep(5)
