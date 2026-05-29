from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func, select, text

from db.database import AsyncSessionLocal, init_db
from db.models import MarketSnapshot, PaperTrade, PortfolioSnapshot, RiskEvent, Signal, StrategyRun


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Crypto Paper Bot", lifespan=lifespan)

_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Crypto Paper Bot</title>
  <style>
    :root {
      --bg: #0a0e1a; --bg2: #111827; --bg3: #1a2236; --border: #1f2d45;
      --text: #e2e8f0; --muted: #64748b; --accent: #3b82f6;
      --green: #10b981; --red: #ef4444; --yellow: #f59e0b; --purple: #8b5cf6;
      --cyan: #06b6d4;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:var(--bg); color:var(--text); font-family:'SF Mono',Monaco,monospace; font-size:13px; }

    /* HEADER */
    .header { display:flex; align-items:center; justify-content:space-between; padding:14px 24px;
      background:var(--bg2); border-bottom:1px solid var(--border); position:sticky; top:0; z-index:100; }
    .header-left { display:flex; align-items:center; gap:16px; }
    .logo { font-size:18px; font-weight:700; color:var(--accent); letter-spacing:1px; }
    .badge { padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }
    .badge-live { background:#10b98120; color:var(--green); border:1px solid #10b98140; }
    .badge-mode { background:#3b82f620; color:var(--accent); border:1px solid #3b82f640; }
    .header-right { display:flex; align-items:center; gap:16px; color:var(--muted); font-size:11px; }
    .dot { width:8px; height:8px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

    /* LAYOUT */
    .main { padding:20px 24px; display:flex; flex-direction:column; gap:20px; }

    /* CARDS */
    .cards-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
    .card { background:var(--bg2); border:1px solid var(--border); border-radius:10px; padding:18px; }
    .card-label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.8px; margin-bottom:8px; }
    .card-value { font-size:26px; font-weight:700; line-height:1; }
    .card-sub { color:var(--muted); font-size:11px; margin-top:6px; }
    .pos { color:var(--green); } .neg { color:var(--red); } .neu { color:var(--text); }
    .acc { color:var(--accent); }

    /* SECTION */
    .section { background:var(--bg2); border:1px solid var(--border); border-radius:10px; overflow:hidden; }
    .section-header { display:flex; align-items:center; justify-content:space-between;
      padding:14px 18px; border-bottom:1px solid var(--border); background:var(--bg3); }
    .section-title { font-size:13px; font-weight:600; color:var(--text); letter-spacing:.5px; }
    .section-body { padding:18px; }

    /* PAIRS GRID */
    .pairs-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
    .pair-card { background:var(--bg3); border:1px solid var(--border); border-radius:8px; padding:16px; }
    .pair-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }
    .pair-name { font-size:15px; font-weight:700; color:var(--text); }
    .pair-price { font-size:15px; font-weight:600; }
    .pair-change { font-size:11px; padding:2px 6px; border-radius:4px; }
    .change-pos { background:#10b98115; color:var(--green); }
    .change-neg { background:#ef444415; color:var(--red); }

    /* INDICATORS */
    .indicators { display:flex; flex-direction:column; gap:10px; }
    .ind-row { display:flex; align-items:center; gap:10px; }
    .ind-name { color:var(--muted); font-size:11px; width:52px; flex-shrink:0; }
    .ind-bar-wrap { flex:1; height:6px; background:#1e293b; border-radius:3px; overflow:hidden; }
    .ind-bar { height:100%; border-radius:3px; transition:width .5s; }
    .ind-val { font-size:11px; width:64px; text-align:right; flex-shrink:0; }
    .ind-signal { font-size:10px; padding:1px 5px; border-radius:3px; flex-shrink:0; }
    .sig-bull { background:#10b98120; color:var(--green); }
    .sig-bear { background:#ef444420; color:var(--red); }
    .sig-neu { background:#1e293b; color:var(--muted); }

    /* SCORE */
    .score-row { display:flex; align-items:center; justify-content:space-between; margin-top:14px;
      padding-top:12px; border-top:1px solid var(--border); }
    .score-dots { display:flex; gap:5px; }
    .score-dot { width:12px; height:12px; border-radius:50%; }
    .dot-filled-bull { background:var(--green); box-shadow:0 0 6px var(--green); }
    .dot-filled-bear { background:var(--red); box-shadow:0 0 6px var(--red); }
    .dot-empty { background:#1e293b; border:1px solid var(--border); }
    .score-label { font-size:11px; }
    .signal-pill { padding:4px 12px; border-radius:20px; font-size:11px; font-weight:700; }
    .pill-buy { background:#10b98120; color:var(--green); border:1px solid #10b98140; }
    .pill-sell { background:#ef444420; color:var(--red); border:1px solid #ef444440; }
    .pill-watch { background:#1e293b; color:var(--muted); border:1px solid var(--border); }

    /* TWO-COL */
    .two-col { display:grid; grid-template-columns:1fr 1fr; gap:14px; }

    /* TABLE */
    table { width:100%; border-collapse:collapse; }
    th { text-align:left; padding:9px 12px; color:var(--muted); font-size:11px; text-transform:uppercase;
      letter-spacing:.6px; border-bottom:1px solid var(--border); font-weight:500; }
    td { padding:9px 12px; border-bottom:1px solid #0f172a; font-size:12px; }
    tr:last-child td { border-bottom:none; }
    tr:hover td { background:#ffffff05; }
    .tbl-empty { text-align:center; color:var(--muted); padding:24px; }

    /* BADGES */
    .b { padding:2px 7px; border-radius:4px; font-size:10px; font-weight:600; }
    .b-open { background:#3b82f620; color:var(--accent); }
    .b-closed { background:#1e293b; color:var(--muted); }
    .b-buy { background:#10b98120; color:var(--green); }
    .b-sell { background:#ef444420; color:var(--red); }
    .b-tp { background:#10b98120; color:var(--green); }
    .b-sl { background:#ef444420; color:var(--red); }

    /* EQUITY CHART */
    .chart-wrap { position:relative; height:120px; }
    canvas { width:100%!important; }

    /* MINI STAT */
    .mini-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--border); }
    .mini-stat { background:var(--bg3); padding:12px 16px; }
    .mini-stat .label { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.6px; }
    .mini-stat .val { font-size:15px; font-weight:700; margin-top:3px; }

    /* BB visualization */
    .bb-bar { position:relative; height:8px; background:#1e293b; border-radius:4px; margin:4px 0; }
    .bb-range { position:absolute; top:0; height:100%; background:#3b82f615; border-radius:4px; }
    .bb-price { position:absolute; top:-2px; width:12px; height:12px; background:var(--accent);
      border-radius:50%; transform:translateX(-50%); border:2px solid var(--bg); }

    /* SCROLLBAR */
    ::-webkit-scrollbar { width:4px; } ::-webkit-scrollbar-track { background:var(--bg); }
    ::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }

    /* RESPONSIVE */
    @media(max-width:1100px) { .pairs-grid{grid-template-columns:1fr 1fr;} .cards-grid{grid-template-columns:repeat(2,1fr);} }
    @media(max-width:700px) { .pairs-grid,.two-col,.cards-grid{grid-template-columns:1fr;} }
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="logo">CRYPTO PAPER BOT</div>
    <span class="badge badge-live">● LIVE</span>
    <span class="badge badge-mode" id="hdr-mode">PAPER_TRADING</span>
  </div>
  <div class="header-right">
    <div class="dot"></div>
    <span id="hdr-pairs">BTC · ETH · SOL</span>
    <span>|</span>
    <span id="hdr-cycle">Ciclo #–</span>
    <span>|</span>
    <span id="hdr-time">–</span>
  </div>
</div>

<div class="main">

  <!-- PORTFOLIO CARDS -->
  <div class="cards-grid">
    <div class="card">
      <div class="card-label">Balance</div>
      <div class="card-value neu" id="c-balance">$–</div>
      <div class="card-sub" id="c-initial">Initial: $–</div>
    </div>
    <div class="card">
      <div class="card-label">Total P&L</div>
      <div class="card-value" id="c-pnl">$–</div>
      <div class="card-sub" id="c-pnlpct">–</div>
    </div>
    <div class="card">
      <div class="card-label">Equity Total</div>
      <div class="card-value neu" id="c-equity">$–</div>
      <div class="card-sub" id="c-exposure">Exposición: $–</div>
    </div>
    <div class="card">
      <div class="card-label">Win Rate</div>
      <div class="card-value neu" id="c-winrate">–</div>
      <div class="card-sub" id="c-winsub">– trades cerrados</div>
    </div>
  </div>

  <!-- MINI STATS -->
  <div class="section">
    <div class="mini-stats">
      <div class="mini-stat"><div class="label">Ciclos</div><div class="val acc" id="ms-cycles">–</div></div>
      <div class="mini-stat"><div class="label">Señales hoy</div><div class="val" id="ms-signals">–</div></div>
      <div class="mini-stat"><div class="label">Trades abiertos</div><div class="val acc" id="ms-open">–</div></div>
      <div class="mini-stat"><div class="label">Trades cerrados</div><div class="val" id="ms-closed">–</div></div>
    </div>
  </div>

  <!-- PAIRS ANALYSIS -->
  <div class="section">
    <div class="section-header">
      <span class="section-title">ANÁLISIS EN TIEMPO REAL — INDICADORES POR PAR</span>
      <span style="color:var(--muted);font-size:11px" id="last-update">actualizado hace –s</span>
    </div>
    <div class="section-body">
      <div class="pairs-grid" id="pairs-grid">
        <div style="color:var(--muted);padding:40px;text-align:center;grid-column:1/-1">Cargando datos...</div>
      </div>
    </div>
  </div>

  <!-- EQUITY + OPEN POSITIONS -->
  <div class="two-col">
    <div class="section">
      <div class="section-header"><span class="section-title">EQUITY HISTÓRICO</span></div>
      <div class="section-body">
        <div class="chart-wrap"><canvas id="equity-chart"></canvas></div>
      </div>
    </div>
    <div class="section">
      <div class="section-header"><span class="section-title">POSICIONES ABIERTAS</span></div>
      <div class="section-body" style="padding:0">
        <table>
          <thead><tr><th>Par</th><th>Entrada</th><th>Precio actual</th><th>P&L</th><th>SL</th><th>TP</th></tr></thead>
          <tbody id="open-positions"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- RECENT SIGNALS -->
  <div class="section">
    <div class="section-header">
      <span class="section-title">SEÑALES DETECTADAS (con razón)</span>
      <label style="color:var(--muted);font-size:11px;cursor:pointer">
        <input type="checkbox" id="show-rejected" style="margin-right:4px">Mostrar rechazadas
      </label>
    </div>
    <div class="section-body" style="padding:0">
      <table>
        <thead><tr><th>Par</th><th>Side</th><th>Precio</th><th>Conf.</th><th>Razón / Indicadores</th><th>Estado</th><th>Hora</th></tr></thead>
        <tbody id="signals-body"></tbody>
      </table>
    </div>
  </div>

  <!-- RECENT TRADES -->
  <div class="section">
    <div class="section-header"><span class="section-title">HISTORIAL DE TRADES</span></div>
    <div class="section-body" style="padding:0">
      <table>
        <thead><tr><th>Par</th><th>Side</th><th>Entrada</th><th>Salida</th><th>Size</th><th>Fee</th><th>P&L</th><th>Estado</th><th>Razón salida</th><th>Duración</th></tr></thead>
        <tbody id="trades-body"></tbody>
      </table>
    </div>
  </div>

  <!-- CYCLE LOG -->
  <div class="section">
    <div class="section-header"><span class="section-title">LOG DE CICLOS</span></div>
    <div class="section-body" style="padding:0">
      <table>
        <thead><tr><th>Inicio</th><th>Modo</th><th>Pares</th><th>Señales</th><th>Trades</th><th>Rechazados</th><th>ms</th><th>Error</th></tr></thead>
        <tbody id="runs-body"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
// ── helpers ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const fmt = (v, d=2) => v != null ? Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}) : '–';
const pct = v => v != null ? (v*100).toFixed(2)+'%' : '–';
const pctRaw = v => v != null ? (Number(v)).toFixed(2)+'%' : '–';
const cls = v => v > 0 ? 'pos' : v < 0 ? 'neg' : 'neu';
const ago = ts => { if(!ts) return '–'; const s=Math.round((Date.now()-new Date(ts+'Z'))/1000); return s<60?s+'s ago':Math.round(s/60)+'m ago'; };
const dur = (a,b) => { if(!a||!b) return '–'; const s=Math.round((new Date(b+'Z')-new Date(a+'Z'))/1000); return s<60?s+'s':Math.round(s/60)+'m'; };

// ── equity chart ─────────────────────────────────────────────────────────────
let equityPoints = [];
function drawEquity() {
  const canvas = $('equity-chart');
  if (!canvas || !equityPoints.length) return;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.parentElement.offsetWidth;
  const h = 120;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w+'px'; canvas.style.height = h+'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  const vals = equityPoints.map(p => p.equity);
  const min = Math.min(...vals); const max = Math.max(...vals);
  const range = max - min || 1;
  const pad = 10;

  const x = i => pad + (i / (vals.length-1||1)) * (w - pad*2);
  const y = v => h - pad - ((v - min) / range) * (h - pad*2);

  // gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, '#3b82f630'); grad.addColorStop(1, '#3b82f605');
  ctx.beginPath();
  ctx.moveTo(x(0), y(vals[0]));
  vals.forEach((v,i) => i && ctx.lineTo(x(i), y(v)));
  ctx.lineTo(x(vals.length-1), h); ctx.lineTo(x(0), h); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  // line
  ctx.beginPath();
  ctx.moveTo(x(0), y(vals[0]));
  vals.forEach((v,i) => i && ctx.lineTo(x(i), y(v)));
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2; ctx.stroke();

  // last dot
  const lx = x(vals.length-1), ly = y(vals[vals.length-1]);
  ctx.beginPath(); ctx.arc(lx, ly, 4, 0, Math.PI*2);
  ctx.fillStyle = '#3b82f6'; ctx.fill();

  // baseline label
  ctx.fillStyle = '#64748b'; ctx.font = '10px monospace';
  ctx.fillText('$'+fmt(min), pad, h-2);
  ctx.fillText('$'+fmt(max), pad, 14);
}

// ── RSI gauge ────────────────────────────────────────────────────────────────
function rsiColor(v) {
  if (v < 30) return 'var(--green)';
  if (v > 70) return 'var(--red)';
  if (v < 45) return 'var(--cyan)';
  if (v > 55) return 'var(--yellow)';
  return 'var(--accent)';
}

function macdLabel(hist, prevHist) {
  if (prevHist < 0 && hist > 0) return ['BULL CROSS', 'sig-bull'];
  if (prevHist > 0 && hist < 0) return ['BEAR CROSS', 'sig-bear'];
  if (hist > 0) return ['BULL', 'sig-bull'];
  if (hist < 0) return ['BEAR', 'sig-bear'];
  return ['NEUTRAL', 'sig-neu'];
}

function bbPosition(price, upper, mid, lower) {
  if (!upper || !lower) return { pos: 0.5, label: '–', cls: 'sig-neu' };
  const range = upper - lower;
  const pos = Math.max(0, Math.min(1, (price - lower) / (range || 1)));
  let label, c;
  if (price <= lower) { label='LOWER'; c='sig-bull'; }
  else if (price >= upper) { label='UPPER'; c='sig-bear'; }
  else if (pos < 0.35) { label='CERCA LOWER'; c='sig-bull'; }
  else if (pos > 0.65) { label='CERCA UPPER'; c='sig-bear'; }
  else { label='MEDIO'; c='sig-neu'; }
  return { pos, label, cls: c };
}

function renderPair(sym, snap, latestSig) {
  if (!snap) return `<div class="pair-card"><div class="pair-name">${sym}</div><div style="color:var(--muted);margin-top:20px">Sin datos</div></div>`;

  const rsi = snap.rsi;
  const hist = snap.macd_hist;
  const prevHist = snap.macd_prev_hist ?? 0;
  const emaFast = snap.ema_fast, emaSlow = snap.ema_slow;
  const price = snap.price;
  const chg = snap.price_change_pct;
  const bb = bbPosition(price, snap.bb_upper, snap.bb_mid, snap.bb_lower);
  const [macdLbl, macdCls] = macdLabel(hist, prevHist);
  const emaTrend = (emaFast && emaSlow) ? (emaFast > emaSlow ? ['BULL','sig-bull'] : ['BEAR','sig-bear']) : ['–','sig-neu'];
  const rsiLbl = rsi < 30 ? 'SOBREVENTA' : rsi > 70 ? 'SOBRECOMPRA' : 'NEUTRAL';
  const rsiCls = rsi < 30 ? 'sig-bull' : rsi > 70 ? 'sig-bear' : 'sig-neu';

  // score
  let bullScore = 0, bearScore = 0;
  const conditions = [
    { bull: rsi < 30, bear: rsi > 70, label: 'RSI' },
    { bull: prevHist < 0 && hist > 0, bear: prevHist > 0 && hist < 0, label: 'MACD' },
    { bull: emaFast > emaSlow, bear: emaFast < emaSlow, label: 'EMA' },
    { bull: price <= snap.bb_lower, bear: price >= snap.bb_upper, label: 'BB' },
  ];
  conditions.forEach(c => { if(c.bull) bullScore++; if(c.bear) bearScore++; });
  const score = Math.max(bullScore, bearScore);
  const side = bullScore >= 2 ? 'BUY' : bearScore >= 2 ? 'SELL' : null;

  const dots = conditions.map(c => {
    if (side === 'BUY') return `<div class="score-dot ${c.bull?'dot-filled-bull':'dot-empty'}" title="${c.label}"></div>`;
    if (side === 'SELL') return `<div class="score-dot ${c.bear?'dot-filled-bear':'dot-empty'}" title="${c.label}"></div>`;
    return `<div class="score-dot dot-empty" title="${c.label}"></div>`;
  }).join('');

  const pill = side === 'BUY' ? '<span class="signal-pill pill-buy">▲ BUY</span>'
    : side === 'SELL' ? '<span class="signal-pill pill-sell">▼ SELL</span>'
    : '<span class="signal-pill pill-watch">● WATCHING</span>';

  const chgCls = chg >= 0 ? 'change-pos' : 'change-neg';
  const chgSign = chg >= 0 ? '+' : '';
  const bbLeft = Math.max(0, Math.min(96, bb.pos * 100));

  // BB bar
  const bbHtml = (snap.bb_upper && snap.bb_lower) ? `
    <div class="bb-bar">
      <div class="bb-range" style="left:0;right:0"></div>
      <div class="bb-price" style="left:${bbLeft}%"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--muted)">
      <span>$${fmt(snap.bb_lower,0)}</span><span>$${fmt(snap.bb_mid,0)}</span><span>$${fmt(snap.bb_upper,0)}</span>
    </div>` : '';

  return `<div class="pair-card">
    <div class="pair-header">
      <div>
        <div class="pair-name">${sym.replace('USDT','')}<span style="color:var(--muted);font-weight:400">/USDT</span></div>
        <div style="color:var(--muted);font-size:10px;margin-top:2px">Spread: ${snap.spread ? (snap.spread*100).toFixed(3)+'%' : '–'}</div>
      </div>
      <div style="text-align:right">
        <div class="pair-price ${cls(chg)}">$${fmt(price, price > 100 ? 2 : 4)}</div>
        <div class="pair-change ${chgCls}">${chgSign}${pctRaw(chg)}</div>
      </div>
    </div>

    <div class="indicators">
      <div class="ind-row">
        <span class="ind-name">RSI(14)</span>
        <div class="ind-bar-wrap">
          <div class="ind-bar" style="width:${Math.min(100,rsi||50)}%;background:${rsiColor(rsi||50)}"></div>
        </div>
        <span class="ind-val ${rsi<30?'pos':rsi>70?'neg':'neu'}">${rsi!=null?rsi.toFixed(1):'–'}</span>
        <span class="ind-signal ${rsiCls}">${rsiLbl}</span>
      </div>
      <div class="ind-row">
        <span class="ind-name">MACD</span>
        <div class="ind-bar-wrap">
          <div class="ind-bar" style="width:${hist!=null?Math.min(100,Math.abs(hist/0.001)*50+50)+'%':'50%'};background:${hist>0?'var(--green)':'var(--red)'}"></div>
        </div>
        <span class="ind-val ${hist>0?'pos':'neg'}">${hist!=null?hist.toFixed(4):'–'}</span>
        <span class="ind-signal ${macdCls}">${macdLbl}</span>
      </div>
      <div class="ind-row">
        <span class="ind-name">EMA 9/21</span>
        <div class="ind-bar-wrap">
          <div class="ind-bar" style="width:${emaFast&&emaSlow?Math.min(100,((emaFast/emaSlow)-0.995)*200*100)+'%':'50%'};background:${emaFast>emaSlow?'var(--green)':'var(--red)'}"></div>
        </div>
        <span class="ind-val ${emaTrend[1]==='sig-bull'?'pos':'neg'}">${emaFast?'$'+fmt(emaFast, emaFast>100?0:2):'–'}</span>
        <span class="ind-signal ${emaTrend[1]}">${emaTrend[0]}</span>
      </div>
      <div class="ind-row">
        <span class="ind-name">BB</span>
        <div style="flex:1">${bbHtml}</div>
        <span class="ind-signal ${bb.cls}" style="margin-left:8px">${bb.label}</span>
      </div>
    </div>

    <div class="score-row">
      <div style="display:flex;align-items:center;gap:8px">
        <div class="score-dots">${dots}</div>
        <span class="score-label" style="color:var(--muted)">Score ${score}/4</span>
      </div>
      ${pill}
    </div>
  </div>`;
}

// ── FETCH & RENDER ────────────────────────────────────────────────────────────
let lastUpdate = null;

async function fetchAll() {
  const showRej = $('show-rejected').checked;
  const [port, stats, mkt, sigs, trades, runs, hist] = await Promise.all([
    fetch('/api/portfolio').then(r=>r.json()).catch(()=>({data:null})),
    fetch('/api/stats').then(r=>r.json()).catch(()=>({data:{}})),
    fetch('/api/market-data').then(r=>r.json()).catch(()=>({data:{}})),
    fetch(`/api/signals?limit=30${showRej?'&rejected=true':''}`).then(r=>r.json()).catch(()=>({data:[]})),
    fetch('/api/trades?limit=20').then(r=>r.json()).catch(()=>({data:[]})),
    fetch('/api/runs?limit=15').then(r=>r.json()).catch(()=>({data:[]})),
    fetch('/api/portfolio-history?limit=200').then(r=>r.json()).catch(()=>({data:[]})),
  ]);

  lastUpdate = new Date();

  // header
  const run = (runs.data||[])[0];
  if (run) {
    $('hdr-cycle').textContent = 'Ciclo #'+(stats.data?.total_cycles||'–');
    $('hdr-mode').textContent = run.mode;
  }
  $('hdr-time').textContent = lastUpdate.toLocaleTimeString();

  // portfolio cards
  const p = port.data || {};
  const s = stats.data || {};
  const pnl = p.total_pnl ?? 0;
  $('c-balance').textContent = '$'+fmt(p.balance);
  $('c-initial').textContent = 'Initial: $'+fmt(p.initial_balance);
  $('c-pnl').className = 'card-value '+(pnl>=0?'pos':'neg');
  $('c-pnl').textContent = (pnl>=0?'+':'')+' $'+fmt(pnl);
  $('c-pnlpct').textContent = pct(p.total_pnl_pct);
  $('c-equity').textContent = '$'+fmt(p.total_equity);
  $('c-exposure').textContent = 'Exposición: $'+fmt(p.total_exposure)+' ('+pct(p.exposure_pct)+')';
  const wr = s.win_rate;
  $('c-winrate').textContent = wr!=null ? (wr*100).toFixed(1)+'%' : 'N/A';
  $('c-winsub').textContent = (s.winning_trades||0)+'W / '+(s.closed_trades||0)+' cerrados';

  // mini stats
  $('ms-cycles').textContent = s.total_cycles||0;
  $('ms-signals').textContent = s.total_signals||0;
  $('ms-open').textContent = s.open_trades||0;
  $('ms-closed').textContent = s.closed_trades||0;

  // pairs
  const mkd = mkt.data || {};
  const pairs = Object.keys(mkd);
  if (pairs.length) {
    $('pairs-grid').innerHTML = pairs.map(sym => renderPair(sym, mkd[sym]?.snapshot, mkd[sym]?.signal)).join('');
  }

  // equity chart
  equityPoints = (hist.data||[]);
  if (!equityPoints.length && p.total_equity) equityPoints = [{equity: p.total_equity}];
  drawEquity();

  // open positions
  const openTrades = (trades.data||[]).filter(t=>t.status==='OPEN');
  const curPrices = {};
  pairs.forEach(sym => { if(mkd[sym]?.snapshot) curPrices[sym] = mkd[sym].snapshot.price; });
  $('open-positions').innerHTML = openTrades.length ? openTrades.map(t => {
    const cur = curPrices[t.symbol] || t.entry_price;
    const unr = (cur - t.entry_price) * t.shares;
    return `<tr>
      <td><strong>${t.symbol}</strong></td>
      <td>$${fmt(t.entry_price,4)}</td>
      <td>$${fmt(cur,4)}</td>
      <td class="${cls(unr)}">${unr>=0?'+':''}$${fmt(unr)}</td>
      <td class="neg">$${fmt(t.stop_loss_price||0,4)}</td>
      <td class="pos">$${fmt(t.take_profit_price||0,4)}</td>
    </tr>`;
  }).join('') : `<tr><td colspan="6" class="tbl-empty">Sin posiciones abiertas</td></tr>`;

  // signals
  $('signals-body').innerHTML = (sigs.data||[]).length ? (sigs.data||[]).map(s => {
    const sideCls = s.side==='BUY'?'b-buy':s.side==='SELL'?'b-sell':'';
    const reasons = (s.reason||'').split('+').map(r=>`<span class="b" style="background:#1e293b;color:var(--accent);margin-right:3px">${r}</span>`).join('');
    return `<tr style="${s.rejected?'opacity:.5':''}">
      <td><strong>${s.symbol||'–'}</strong></td>
      <td>${s.side?`<span class="b ${sideCls}">${s.side}</span>`:'<span class="b b-closed">–</span>'}</td>
      <td>${s.current_price?'$'+fmt(s.current_price,4):'–'}</td>
      <td>${s.confidence!=null?(s.confidence*100).toFixed(0)+'%':'–'}</td>
      <td>${s.rejected?`<span style="color:var(--red);font-size:11px">✗ ${s.rejection_reason||''}</span>`:reasons}</td>
      <td>${s.rejected?'<span class="b b-closed">RECHAZADA</span>':'<span class="b b-buy">VÁLIDA</span>'}</td>
      <td style="color:var(--muted)">${ago(s.detected_at)}</td>
    </tr>`;
  }).join('') : `<tr><td colspan="7" class="tbl-empty">Sin señales aún — el bot analiza cada 60s</td></tr>`;

  // trades
  $('trades-body').innerHTML = (trades.data||[]).length ? (trades.data||[]).map(t => {
    const pnl = t.realized_pnl;
    const exitCls = t.exit_reason==='TAKE_PROFIT'?'b-tp':t.exit_reason==='STOP_LOSS'?'b-sl':'';
    return `<tr>
      <td><strong>${t.symbol}</strong></td>
      <td><span class="b b-buy">${t.side}</span></td>
      <td>$${fmt(t.entry_price,4)}</td>
      <td>${t.exit_price?'$'+fmt(t.exit_price,4):'–'}</td>
      <td>$${fmt(t.size_usd)}</td>
      <td style="color:var(--muted)">$${fmt(t.fee_paid)}</td>
      <td class="${cls(pnl)}">${pnl!=null?(pnl>=0?'+':'')+' $'+fmt(pnl):'–'}</td>
      <td><span class="b ${t.status==='OPEN'?'b-open':'b-closed'}">${t.status}</span></td>
      <td>${t.exit_reason?`<span class="b ${exitCls}">${t.exit_reason}</span>`:'–'}</td>
      <td style="color:var(--muted)">${dur(t.opened_at,t.closed_at)}</td>
    </tr>`;
  }).join('') : `<tr><td colspan="10" class="tbl-empty">Sin trades aún</td></tr>`;

  // runs
  $('runs-body').innerHTML = (runs.data||[]).map(r => `<tr>
    <td style="color:var(--muted)">${r.started_at?r.started_at.replace('T',' ').slice(0,19):'–'}</td>
    <td><span class="b badge-mode">${r.mode}</span></td>
    <td>${r.pairs_analyzed}</td>
    <td class="${r.signals_detected>0?'acc':''}">${r.signals_detected}</td>
    <td class="${r.trades_executed>0?'pos':''}">${r.trades_executed}</td>
    <td style="color:var(--muted)">${r.trades_rejected}</td>
    <td style="color:var(--muted)">${r.cycle_duration_ms||'–'}</td>
    <td style="color:var(--red);font-size:11px">${r.error?r.error.slice(0,60):''}</td>
  </tr>`).join('');

  // last update label
  $('last-update').textContent = 'actualizado hace 0s';
}

// update "ago" counter
setInterval(() => {
  if (!lastUpdate) return;
  const s = Math.round((Date.now()-lastUpdate)/1000);
  $('last-update').textContent = `actualizado hace ${s}s`;
}, 1000);

$('show-rejected').addEventListener('change', fetchAll);
window.addEventListener('resize', drawEquity);

fetchAll();
setInterval(fetchAll, 10000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return _HTML


@app.get("/api/market-data")
async def get_market_data():
    """Latest snapshot + signal per symbol with all indicator values."""
    async with AsyncSessionLocal() as db:
        # Latest snapshot per symbol
        subq = (
            select(MarketSnapshot.symbol, func.max(MarketSnapshot.id).label("max_id"))
            .group_by(MarketSnapshot.symbol)
            .subquery()
        )
        result = await db.execute(
            select(MarketSnapshot).join(subq, MarketSnapshot.id == subq.c.max_id)
        )
        snapshots = {s.symbol: s for s in result.scalars().all()}

        # Latest signal per symbol (including rejected)
        sig_subq = (
            select(Signal.symbol, func.max(Signal.id).label("max_id"))
            .group_by(Signal.symbol)
            .subquery()
        )
        sig_result = await db.execute(
            select(Signal).join(sig_subq, Signal.id == sig_subq.c.max_id)
        )
        signals = {s.symbol: s for s in sig_result.scalars().all()}

        # Previous MACD hist for crossover detection (second-to-last snapshot)
        prev_subq = (
            select(MarketSnapshot.symbol, func.max(MarketSnapshot.id).label("max_id"))
            .where(MarketSnapshot.id.notin_([s.id for s in snapshots.values()]))
            .group_by(MarketSnapshot.symbol)
            .subquery()
        )
        prev_result = await db.execute(
            select(MarketSnapshot).join(prev_subq, MarketSnapshot.id == prev_subq.c.max_id)
        )
        prev_snaps = {s.symbol: s for s in prev_result.scalars().all()}

    data = {}
    all_symbols = set(snapshots.keys()) | set(signals.keys())
    for sym in all_symbols:
        snap = snapshots.get(sym)
        prev = prev_snaps.get(sym)
        sig = signals.get(sym)
        snap_dict = None
        if snap:
            snap_dict = {
                "symbol": snap.symbol,
                "price": snap.price,
                "volume_24h": snap.volume_24h,
                "price_change_pct": snap.price_change_pct,
                "best_bid": snap.best_bid,
                "best_ask": snap.best_ask,
                "spread": snap.spread,
                "rsi": snap.rsi,
                "macd": snap.macd,
                "macd_signal": snap.macd_signal,
                "macd_hist": snap.macd_hist,
                "macd_prev_hist": prev.macd_hist if prev else None,
                "ema_fast": snap.ema_fast,
                "ema_slow": snap.ema_slow,
                "bb_upper": snap.bb_upper,
                "bb_mid": snap.bb_mid,
                "bb_lower": snap.bb_lower,
                "created_at": snap.created_at.isoformat() if snap.created_at else None,
            }
        data[sym] = {
            "snapshot": snap_dict,
            "signal": {
                "side": sig.side,
                "reason": sig.reason,
                "confidence": sig.confidence,
                "rejected": sig.rejected,
                "rejection_reason": sig.rejection_reason,
            } if sig else None,
        }

    return {"data": data}


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
            "exposure_pct": snap.exposure_pct if hasattr(snap, 'exposure_pct') else 0,
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
            "id": t.id, "symbol": t.symbol, "side": t.side,
            "entry_price": t.entry_price, "exit_price": t.exit_price,
            "size_usd": t.size_usd, "shares": t.shares,
            "fee_paid": t.fee_paid, "slippage_cost": t.slippage_cost,
            "stop_loss_price": t.stop_loss_price, "take_profit_price": t.take_profit_price,
            "realized_pnl": t.realized_pnl, "status": t.status,
            "confidence": t.confidence, "exit_reason": t.exit_reason,
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
            "id": s.id, "symbol": s.symbol, "side": s.side, "reason": s.reason,
            "confidence": s.confidence, "current_price": s.current_price,
            "rejected": s.rejected, "rejection_reason": s.rejection_reason,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None,
        } for s in signals]}


@app.get("/api/runs")
async def get_runs(limit: int = 15):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StrategyRun).order_by(desc(StrategyRun.started_at)).limit(limit)
        )
        runs = result.scalars().all()
        return {"data": [{
            "id": r.id, "mode": r.mode,
            "pairs_analyzed": r.pairs_analyzed, "signals_detected": r.signals_detected,
            "trades_executed": r.trades_executed, "trades_rejected": r.trades_rejected,
            "cycle_duration_ms": r.cycle_duration_ms, "error": r.error,
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
            "id": e.id, "event_type": e.event_type, "symbol": e.symbol,
            "description": e.description, "value": e.value, "threshold": e.threshold,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        } for e in events]}


@app.get("/api/portfolio-history")
async def get_portfolio_history(limit: int = 200):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.created_at.asc())
            .limit(limit)
        )
        snaps = result.scalars().all()
        return {"data": [{
            "equity": s.total_equity,
            "balance": s.balance,
            "total_pnl_pct": s.total_pnl_pct,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        } for s in snaps]}


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
            "total_trades": total_trades or 0, "open_trades": open_trades or 0,
            "closed_trades": total_closed or 0, "winning_trades": wins or 0,
            "win_rate": win_rate, "total_signals": total_signals or 0,
            "rejected_signals": rejected_signals or 0, "total_cycles": total_runs or 0,
        }}
