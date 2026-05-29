from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import desc, func, select

from db.database import AsyncSessionLocal, init_db
from db.models import PaperTrade, PortfolioSnapshot, RiskEvent, Signal, StrategyRun


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Crypto Paper Bot", lifespan=lifespan)

_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Crypto Paper Bot</title>
  <style>
    body { font-family: monospace; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
    h1 { color: #58a6ff; }
    h2 { color: #8b949e; border-bottom: 1px solid #21262d; padding-bottom: 6px; }
    .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
    .card { background: #161b22; border: 1px solid #21262d; border-radius: 6px; padding: 16px; }
    .card .label { color: #8b949e; font-size: 12px; margin-bottom: 4px; }
    .card .value { font-size: 22px; font-weight: bold; }
    .pos { color: #3fb950; } .neg { color: #f85149; } .neu { color: #c9d1d9; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
    th { text-align: left; padding: 8px; background: #161b22; color: #8b949e; font-size: 12px; border-bottom: 1px solid #21262d; }
    td { padding: 8px; border-bottom: 1px solid #161b22; font-size: 13px; }
    tr:hover td { background: #161b22; }
    .badge { padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    .OPEN { background: #1f6feb; } .CLOSED { background: #21262d; }
    .BUY { background: #1a4731; color: #3fb950; }
    .SELL { background: #3b1f24; color: #f85149; }
  </style>
</head>
<body>
  <h1>Crypto Paper Bot</h1>
  <div id="portfolio" class="grid"></div>
  <h2>Recent Trades</h2>
  <table id="trades-table">
    <thead><tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>Size</th><th>P&L</th><th>Status</th><th>Reason</th><th>Opened</th></tr></thead>
    <tbody id="trades-body"></tbody>
  </table>
  <h2>Recent Signals</h2>
  <table id="signals-table">
    <thead><tr><th>Symbol</th><th>Side</th><th>Price</th><th>Confidence</th><th>Reason</th><th>Time</th></tr></thead>
    <tbody id="signals-body"></tbody>
  </table>
  <h2>Cycle Log</h2>
  <table id="runs-table">
    <thead><tr><th>Mode</th><th>Pairs</th><th>Signals</th><th>Trades</th><th>Rejected</th><th>ms</th><th>Error</th><th>Started</th></tr></thead>
    <tbody id="runs-body"></tbody>
  </table>
<script>
async function load() {
  const [port, trades, sigs, runs, stats] = await Promise.all([
    fetch('/api/portfolio').then(r=>r.json()),
    fetch('/api/trades?limit=20').then(r=>r.json()),
    fetch('/api/signals?limit=20').then(r=>r.json()),
    fetch('/api/runs?limit=10').then(r=>r.json()),
    fetch('/api/stats').then(r=>r.json()),
  ]);

  const p = port.data || {};
  const s = stats.data || {};
  const pnlClass = (p.total_pnl||0) >= 0 ? 'pos' : 'neg';
  document.getElementById('portfolio').innerHTML = `
    <div class="card"><div class="label">Balance</div><div class="value neu">$${fmt(p.balance)}</div></div>
    <div class="card"><div class="label">Total P&L</div><div class="value ${pnlClass}">$${fmt(p.total_pnl)} (${pct(p.total_pnl_pct)})</div></div>
    <div class="card"><div class="label">Open Positions</div><div class="value neu">${p.open_positions||0}</div></div>
    <div class="card"><div class="label">Win Rate</div><div class="value neu">${s.win_rate != null ? pct(s.win_rate) : 'N/A'} (${s.winning_trades||0}/${s.closed_trades||0})</div></div>
  `;

  document.getElementById('trades-body').innerHTML = (trades.data||[]).map(t => {
    const pnl = t.realized_pnl;
    const cls = pnl > 0 ? 'pos' : pnl < 0 ? 'neg' : 'neu';
    return `<tr>
      <td>${t.symbol}</td>
      <td><span class="badge ${t.side}">${t.side}</span></td>
      <td>$${t.entry_price?.toFixed(4)}</td>
      <td>${t.exit_price ? '$'+t.exit_price.toFixed(4) : '-'}</td>
      <td>$${fmt(t.size_usd)}</td>
      <td class="${cls}">${pnl != null ? '$'+pnl.toFixed(4) : '-'}</td>
      <td><span class="badge ${t.status}">${t.status}</span></td>
      <td>${t.exit_reason||'-'}</td>
      <td>${t.opened_at ? t.opened_at.slice(0,19).replace('T',' ') : '-'}</td>
    </tr>`;
  }).join('');

  document.getElementById('signals-body').innerHTML = (sigs.data||[]).map(s => `<tr>
    <td>${s.symbol}</td>
    <td>${s.side ? '<span class="badge '+s.side+'">'+s.side+'</span>' : '-'}</td>
    <td>$${s.current_price?.toFixed(4)||'-'}</td>
    <td>${s.confidence != null ? (s.confidence*100).toFixed(0)+'%' : '-'}</td>
    <td>${s.reason||'-'}</td>
    <td>${s.detected_at ? s.detected_at.slice(0,19).replace('T',' ') : '-'}</td>
  </tr>`).join('');

  document.getElementById('runs-body').innerHTML = (runs.data||[]).map(r => `<tr>
    <td>${r.mode}</td>
    <td>${r.pairs_analyzed}</td>
    <td>${r.signals_detected}</td>
    <td>${r.trades_executed}</td>
    <td>${r.trades_rejected}</td>
    <td>${r.cycle_duration_ms||'-'}</td>
    <td style="color:#f85149">${r.error||''}</td>
    <td>${r.started_at ? r.started_at.slice(0,19).replace('T',' ') : '-'}</td>
  </tr>`).join('');
}
function fmt(v) { return v != null ? v.toFixed(2) : '-'; }
function pct(v) { return v != null ? (v*100).toFixed(2)+'%' : '-'; }
load();
setInterval(load, 10000);
</script>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return _HTML


@app.get("/api/portfolio")
async def get_portfolio():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.created_at)).limit(1)
        )
        snap = result.scalar_one_or_none()
        if not snap:
            return {"data": None}
        return {"data": {
            "balance": snap.balance,
            "initial_balance": snap.initial_balance,
            "total_equity": snap.total_equity,
            "unrealized_pnl": snap.unrealized_pnl,
            "realized_pnl": snap.realized_pnl,
            "total_pnl": snap.total_pnl,
            "total_pnl_pct": snap.total_pnl_pct,
            "open_positions": snap.open_positions_count,
            "total_exposure": snap.total_exposure,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
        }}


@app.get("/api/trades")
async def get_trades(limit: int = 20):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PaperTrade).order_by(desc(PaperTrade.opened_at)).limit(limit)
        )
        trades = result.scalars().all()
        return {"data": [{
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "size_usd": t.size_usd,
            "shares": t.shares,
            "fee_paid": t.fee_paid,
            "realized_pnl": t.realized_pnl,
            "status": t.status,
            "confidence": t.confidence,
            "exit_reason": t.exit_reason,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        } for t in trades]}


@app.get("/api/signals")
async def get_signals(limit: int = 30, rejected: bool = False):
    async with AsyncSessionLocal() as db:
        query = select(Signal).order_by(desc(Signal.detected_at)).limit(limit)
        if not rejected:
            query = query.where(Signal.rejected == False)  # noqa: E712
        result = await db.execute(query)
        signals = result.scalars().all()
        return {"data": [{
            "id": s.id,
            "symbol": s.symbol,
            "side": s.side,
            "reason": s.reason,
            "confidence": s.confidence,
            "current_price": s.current_price,
            "rejected": s.rejected,
            "rejection_reason": s.rejection_reason,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        } for s in signals]}


@app.get("/api/runs")
async def get_runs(limit: int = 10):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StrategyRun).order_by(desc(StrategyRun.started_at)).limit(limit)
        )
        runs = result.scalars().all()
        return {"data": [{
            "id": r.id,
            "mode": r.mode,
            "pairs_analyzed": r.pairs_analyzed,
            "signals_detected": r.signals_detected,
            "trades_executed": r.trades_executed,
            "trades_rejected": r.trades_rejected,
            "cycle_duration_ms": r.cycle_duration_ms,
            "error": r.error,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        } for r in runs]}


@app.get("/api/risk-events")
async def get_risk_events(limit: int = 20):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RiskEvent).order_by(desc(RiskEvent.created_at)).limit(limit)
        )
        events = result.scalars().all()
        return {"data": [{
            "id": e.id,
            "event_type": e.event_type,
            "symbol": e.symbol,
            "description": e.description,
            "value": e.value,
            "threshold": e.threshold,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in events]}


@app.get("/api/stats")
async def get_stats():
    async with AsyncSessionLocal() as db:
        total_trades = await db.scalar(select(func.count(PaperTrade.id)))
        open_trades = await db.scalar(
            select(func.count(PaperTrade.id)).where(PaperTrade.status == "OPEN")
        )
        wins = await db.scalar(
            select(func.count(PaperTrade.id))
            .where(PaperTrade.status == "CLOSED", PaperTrade.realized_pnl > 0)
        )
        total_closed = await db.scalar(
            select(func.count(PaperTrade.id)).where(PaperTrade.status == "CLOSED")
        )
        total_signals = await db.scalar(select(func.count(Signal.id)))
        rejected_signals = await db.scalar(
            select(func.count(Signal.id)).where(Signal.rejected == True)  # noqa: E712
        )
        total_runs = await db.scalar(select(func.count(StrategyRun.id)))
        win_rate = wins / total_closed if total_closed else None

        return {"data": {
            "total_trades": total_trades or 0,
            "open_trades": open_trades or 0,
            "closed_trades": total_closed or 0,
            "winning_trades": wins or 0,
            "win_rate": win_rate,
            "total_signals": total_signals or 0,
            "rejected_signals": rejected_signals or 0,
            "total_cycles": total_runs or 0,
        }}
