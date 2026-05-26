/* ============================================================
   FF Strategy Planner V2 — Frontend JS
   ============================================================ */

// --- DOM refs ---
const selProduct  = document.getElementById('selProduct');
const selTF       = document.getElementById('selTF');
const selStrategy = document.getElementById('selStrategy');
const inpRisk     = document.getElementById('inpRisk');
const statusBar   = document.getElementById('statusBar');

// --- Tab system ---
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');
tabs.forEach(t => t.addEventListener('click', () => {
  tabs.forEach(x => x.classList.remove('active'));
  tabContents.forEach(x => x.classList.add('hidden'));
  t.classList.add('active');
  document.getElementById('tab-' + t.dataset.tab).classList.remove('hidden');
}));

// --- Status helper ---
function setStatus(msg, isLoading = false) {
  statusBar.innerHTML = isLoading
    ? `<span class="spinner mr-2"></span>${msg}`
    : msg;
}

// =============================================================
// CHART
// =============================================================
let mainChart = null;
let candleSeries = null;
let vwapLine = null, ema9Line = null, ema21Line = null;
let bbUpper = null, bbLower = null, bbMid = null;
let sma20Line = null, sma50Line = null;
let rsiChart = null, rsiSeries = null;
let planLines = [];

function initChart() {
  const chartEl = document.getElementById('chart');
  if (mainChart) { mainChart.remove(); planLines = []; }

  mainChart = LightweightCharts.createChart(chartEl, {
    layout: { background: { color: '#161b22' }, textColor: '#8b949e' },
    grid:   { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    timeScale: { borderColor: '#30363d', timeVisible: true },
    rightPriceScale: { borderColor: '#30363d' },
    width: chartEl.clientWidth,
    height: 420,
  });

  candleSeries = mainChart.addCandlestickSeries({
    upColor: '#3fb950', downColor: '#f85149',
    borderUpColor: '#3fb950', borderDownColor: '#f85149',
    wickUpColor: '#3fb950', wickDownColor: '#f85149',
  });

  const rsiEl = document.getElementById('rsiChart');
  if (rsiChart) rsiChart.remove();
  rsiChart = LightweightCharts.createChart(rsiEl, {
    layout: { background: { color: '#161b22' }, textColor: '#8b949e' },
    grid:   { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
    timeScale: { borderColor: '#30363d', timeVisible: true, visible: false },
    rightPriceScale: { borderColor: '#30363d' },
    width: rsiEl.clientWidth,
    height: 100,
  });
  rsiSeries = rsiChart.addLineSeries({ color: '#d29922', lineWidth: 1 });

  mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
    if (range) rsiChart.timeScale().setVisibleLogicalRange(range);
  });

  window.addEventListener('resize', () => {
    mainChart.applyOptions({ width: chartEl.clientWidth });
    rsiChart.applyOptions({ width: rsiEl.clientWidth });
  });
}

function addIndicatorLines(indicators) {
  [vwapLine, ema9Line, ema21Line, bbUpper, bbLower, bbMid, sma20Line, sma50Line]
    .forEach(s => { if (s) try { mainChart.removeSeries(s); } catch(e){} });

  const make = (color, width=1, dash=false) => {
    const opts = { color, lineWidth: width };
    if (dash) opts.lineStyle = LightweightCharts.LineStyle.Dashed;
    return mainChart.addLineSeries(opts);
  };

  if (document.getElementById('togVwap').checked && indicators.vwap) {
    vwapLine = make('#d29922', 1, true);
    vwapLine.setData(indicators.vwap);
  }
  if (document.getElementById('togEma').checked) {
    if (indicators.ema9)  { ema9Line  = make('#a371f7', 1); ema9Line.setData(indicators.ema9); }
    if (indicators.ema21) { ema21Line = make('#79c0ff', 1); ema21Line.setData(indicators.ema21); }
  }
  if (document.getElementById('togBB').checked) {
    if (indicators.bb_upper) { bbUpper = make('#58a6ff', 1, true); bbUpper.setData(indicators.bb_upper); }
    if (indicators.bb_lower) { bbLower = make('#58a6ff', 1, true); bbLower.setData(indicators.bb_lower); }
    if (indicators.bb_mid)   { bbMid   = make('#58a6ff', 1);       bbMid.setData(indicators.bb_mid); }
  }
  if (document.getElementById('togSMA').checked) {
    if (indicators.sma20) { sma20Line = make('#f0883e', 1); sma20Line.setData(indicators.sma20); }
    if (indicators.sma50) { sma50Line = make('#ff7b72', 1); sma50Line.setData(indicators.sma50); }
  }
  if (indicators.rsi14) rsiSeries.setData(indicators.rsi14);
}

async function loadChart() {
  const product = selProduct.value;
  const timeframe = selTF.value;

  tabs.forEach(t => t.classList.remove('active'));
  tabContents.forEach(x => x.classList.add('hidden'));
  document.querySelector('[data-tab="chart"]').classList.add('active');
  document.getElementById('tab-chart').classList.remove('hidden');

  setStatus(`Loading chart for ${product}…`, true);
  initChart();

  try {
    const res = await fetch(`/api/chart-data?product=${product}&timeframe=${timeframe}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    window._lastChartData = data;

    candleSeries.setData(data.ohlcv);
    addIndicatorLines(data.indicators);
    mainChart.timeScale().fitContent();
    rsiChart.timeScale().fitContent();
    setStatus(`Chart loaded — ${data.ohlcv.length} bars`);
  } catch (e) {
    setStatus(`Chart error: ${e.message}`);
  }
}

['togVwap','togEma','togBB','togSMA'].forEach(id => {
  document.getElementById(id).addEventListener('change', () => {
    if (window._lastChartData) addIndicatorLines(window._lastChartData.indicators);
  });
});

// =============================================================
// PLAN (V2)
// =============================================================

function renderPlanBanner(plan) {
  const banner = document.getElementById('planBanner');
  banner.classList.remove('hidden');

  // Badges
  document.getElementById('planTradeType').textContent = plan.trade_type || 'outright';
  const strat = plan.strategy || {};
  document.getElementById('planStrategy').textContent = strat.name || plan.strategy || '—';

  const dir = plan.ladder?.direction || strat.direction || '—';
  const dirEl = document.getElementById('planDirection');
  dirEl.textContent = dir;
  dirEl.className = `badge ${dir === 'LONG' ? 'badge-green' : 'badge-red'}`;

  // Thesis
  const thesis = plan.execution_notes?.thesis || strat.thesis || plan.thesis || '—';
  document.getElementById('planThesis').textContent = thesis;

  // Meta
  document.getElementById('planProduct').textContent = plan.product;
  document.getElementById('planTF').textContent = plan.timeframe;
  const execState = plan.contract_context?.execution_state?.state || '—';
  document.getElementById('planExecState').textContent = execState;

  // Execution quality
  const quality = plan.execution_quality || 0;
  const qEl = document.getElementById('planQuality');
  qEl.textContent = Math.round(quality);
  const qColor = quality >= 70 ? '#3fb950' : quality >= 40 ? '#d29922' : '#f85149';
  qEl.style.color = qColor;
  const qBar = document.getElementById('planQualityBar');
  qBar.style.width = `${quality}%`;
  qBar.style.background = qColor;
}

function renderEntryLadder(plan) {
  const el = document.getElementById('entryLadder');
  const ladder = plan.ladder;
  if (!ladder || !ladder.entries) {
    el.innerHTML = '<div class="text-xs text-[#8b949e] px-2">No entries</div>';
    return;
  }

  let html = '';
  ladder.entries.forEach((e, i) => {
    html += `<div class="ladder-row entry-row">
      <span>${e.level?.toFixed(5) || '—'}</span>
      <span>${e.size} lot${e.size > 1 ? 's' : ''}</span>
      <span style="color:#3fb950">${e.confidence || '—'}%</span>
      <span class="text-[#8b949e]">${e.reason || ''}</span>
    </div>`;
  });

  // Stop
  html += `<div class="ladder-row stop-row">
    <span>${ladder.stop?.toFixed(5) || '—'}</span>
    <span>${ladder.total_lots || '—'} lots</span>
    <span></span>
    <span class="text-[#f85149]">STOP</span>
  </div>`;

  el.innerHTML = html;
}

function renderExitLadder(plan) {
  const el = document.getElementById('exitLadder');
  const ladder = plan.ladder;
  if (!ladder || !ladder.exits) {
    el.innerHTML = '<div class="text-xs text-[#8b949e] px-2">No exits</div>';
    return;
  }

  let html = '';
  ladder.exits.forEach((e, i) => {
    html += `<div class="ladder-row exit-row">
      <span>${e.level?.toFixed(5) || '—'}</span>
      <span>${e.size} lot${e.size > 1 ? 's' : ''}</span>
      <span></span>
      <span class="text-[#8b949e]">${e.reason || ''}</span>
    </div>`;
  });

  el.innerHTML = html;
}

function renderRiskPanel(plan) {
  const el = document.getElementById('riskPanel');
  const risk = plan.ladder?.risk || {};

  el.innerHTML = `
    <div class="flex justify-between"><span class="text-[#8b949e]">Max Loss</span><span class="text-red-400">$${risk.max_loss_usd || '—'}</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Tick Exposure</span><span>${risk.tick_exposure || '—'}</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Risk/Reward</span><span class="text-green-400">${risk.risk_reward || '—'}x</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Capital</span><span>$${plan.risk_usd || '—'}</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Total Lots</span><span>${plan.ladder?.total_lots || '—'}</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Avg Entry</span><span class="font-mono">${plan.ladder?.weighted_avg_entry?.toFixed(5) || '—'}</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Stop Ticks</span><span>${plan.ladder?.stop_ticks || '—'}</span></div>
    <div class="flex justify-between"><span class="text-[#8b949e]">Hold Est.</span><span>${risk.expected_hold_bars || '—'} bars</span></div>
  `;
}

function renderCrossContract(plan) {
  const el = document.getElementById('crossPanel');
  const cross = plan.cross_contract;
  if (!cross) {
    el.innerHTML = '<div class="text-[#8b949e]">N/A</div>';
    return;
  }

  const scoreColor = cross.score >= 60 ? '#3fb950' : cross.score >= 40 ? '#d29922' : '#f85149';
  let html = `
    <div class="flex items-center gap-2">
      <span class="text-[#8b949e]">Score:</span>
      <span class="font-bold" style="color:${scoreColor}">${cross.score}/100</span>
    </div>
    <div class="text-[#8b949e]">${cross.reasoning || '—'}</div>
  `;

  if (cross.details && cross.details.length) {
    html += '<div class="mt-2 space-y-1">';
    cross.details.forEach(d => {
      const icon = d.aligned ? '<span class="text-green-400">+</span>' : '<span class="text-red-400">-</span>';
      html += `<div class="flex gap-2">${icon}<span>${d.contract}: ${d.pct_5bar > 0 ? '+' : ''}${d.pct_5bar?.toFixed(4)}% | vol ratio ${d.vol_ratio}</span></div>`;
    });
    html += '</div>';
  }

  el.innerHTML = html;
}

function renderExecNotes(plan) {
  const el = document.getElementById('execNotes');
  const notes = plan.execution_notes || plan;
  const inv = notes.invalidation || plan.invalidation || '—';
  const conf = notes.confirmation || plan.confirmation || '—';

  el.innerHTML = `
    <div>
      <div class="text-red-400 font-medium mb-1">Invalidates</div>
      <div class="text-[#8b949e]">${inv}</div>
    </div>
    <div>
      <div class="text-green-400 font-medium mb-1">Confirms</div>
      <div class="text-[#8b949e]">${conf}</div>
    </div>
  `;
}

function renderConfidenceFactors(plan) {
  const el = document.getElementById('confFactors');
  const factors = plan.strategy?.confidence_factors || {};
  const keys = Object.keys(factors);

  if (!keys.length) {
    el.innerHTML = '<div class="text-xs text-[#8b949e]">No confidence factors</div>';
    return;
  }

  let html = '';
  keys.forEach(k => {
    const val = factors[k];
    const color = val >= 70 ? '#3fb950' : val >= 40 ? '#d29922' : '#f85149';
    const label = k.replace(/_/g, ' ');
    html += `
      <div>
        <div class="flex justify-between text-xs mb-1">
          <span class="text-[#8b949e]">${label}</span>
          <span style="color:${color}">${val.toFixed(0)}</span>
        </div>
        <div class="comp-bar"><div class="comp-fill" style="width:${Math.min(100,val)}%;background:${color}"></div></div>
      </div>
    `;
  });

  el.innerHTML = html;
}

async function generatePlan() {
  setStatus('Generating plan…', true);

  tabs.forEach(t => t.classList.remove('active'));
  tabContents.forEach(x => x.classList.add('hidden'));
  document.querySelector('[data-tab="plan"]').classList.add('active');
  document.getElementById('tab-plan').classList.remove('hidden');

  const payload = {
    product:   selProduct.value,
    timeframe: selTF.value,
    strategy:  selStrategy.value,
    risk_usd:  parseFloat(inpRisk.value),
  };

  try {
    const res = await fetch('/api/generate-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    const plan = await res.json();
    window._lastPlan = plan;

    renderPlanBanner(plan);
    renderEntryLadder(plan);
    renderExitLadder(plan);
    renderRiskPanel(plan);
    renderCrossContract(plan);
    renderExecNotes(plan);
    renderConfidenceFactors(plan);

    const dir = plan.ladder?.direction || plan.strategy?.direction || '—';
    setStatus(`Plan generated — ${plan.strategy?.name || ''} ${dir} @ ${plan.contract_context?.last_price?.toFixed(5) || '—'}`);
  } catch (e) {
    setStatus(`Plan error: ${e.message}`);
    console.error(e);
  }
}

// =============================================================
// BACKTEST (V2)
// =============================================================

function drawCurve(canvasId, data, key, color, fillAlpha = 0.1) {
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;

  if (!data || !data.length) return;

  const vals = data.map(d => d[key]);
  const min = Math.min(...vals, 0);
  const max = Math.max(...vals, 0);
  const range = max - min || 1;
  const w = canvas.width, h = canvas.height;
  const pad = 20;

  ctx.clearRect(0, 0, w, h);

  // Grid
  ctx.strokeStyle = '#21262d';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad + (h - 2*pad) * (1 - i/4);
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w-pad, y); ctx.stroke();
  }

  // Zero line
  const zeroY = pad + (h - 2*pad) * (1 - (0 - min) / range);
  ctx.strokeStyle = '#30363d'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, zeroY); ctx.lineTo(w-pad, zeroY); ctx.stroke();

  // Curve
  ctx.beginPath();
  vals.forEach((v, i) => {
    const x = pad + (w - 2*pad) * (i / Math.max(1, vals.length - 1));
    const y = pad + (h - 2*pad) * (1 - (v - min) / range);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Fill
  const lastX = pad + (w - 2*pad);
  ctx.lineTo(lastX, zeroY);
  ctx.lineTo(pad, zeroY);
  ctx.closePath();
  ctx.fillStyle = color.replace(')', `,${fillAlpha})`).replace('rgb', 'rgba');
  ctx.fill();
}

async function runBacktest() {
  setStatus('Running backtest…', true);

  tabs.forEach(t => t.classList.remove('active'));
  tabContents.forEach(x => x.classList.add('hidden'));
  document.querySelector('[data-tab="backtest"]').classList.add('active');
  document.getElementById('tab-backtest').classList.remove('hidden');

  const payload = {
    product:   selProduct.value,
    timeframe: selTF.value,
    strategy:  selStrategy.value,
    risk_usd:  parseFloat(inpRisk.value),
    lookback:  150,
  };

  try {
    const res = await fetch('/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const s = data.summary;

    // Row 1
    document.getElementById('btTotal').textContent = s.total;
    document.getElementById('btWinRate').textContent = `${s.win_rate}%`;
    document.getElementById('btPF').textContent = s.profit_factor >= 999 ? '∞' : s.profit_factor;
    document.getElementById('btSharpe').textContent = s.sharpe;
    document.getElementById('btDD').textContent = `$${Math.abs(s.max_drawdown_usd).toFixed(0)}`;

    // Row 2
    document.getElementById('btExpectancy').textContent = `$${s.expectancy_usd}`;
    document.getElementById('btAvgHold').textContent = s.avg_hold_bars;
    document.getElementById('btRiskEff').textContent = `${s.risk_efficiency_pct}%`;
    document.getElementById('btLadderEff').textContent = `${s.ladder_efficiency_pct}%`;
    document.getElementById('btExecQual').textContent = `${s.execution_quality}`;

    // MAE/MFE + Total PnL
    document.getElementById('btMAE').textContent = s.avg_mae_ticks;
    document.getElementById('btMFE').textContent = s.avg_mfe_ticks;
    const pnlColor = s.total_pnl_usd >= 0 ? 'text-green-400' : 'text-red-400';
    document.getElementById('btTotalPnl').className = `${pnlColor} font-bold`;
    document.getElementById('btTotalPnl').textContent = `$${s.total_pnl_usd.toFixed(2)}`;

    // Equity curve
    drawCurve('eqCanvas', data.equity_curve, 'equity', 'rgb(63, 185, 80)');

    // Drawdown curve
    if (data.drawdown_curve) {
      drawCurve('ddCanvas', data.drawdown_curve, 'drawdown', 'rgb(248, 81, 73)');
    }

    // Trade log
    const tbody = document.getElementById('btTradeLog');
    tbody.innerHTML = '';
    (data.trades || []).slice(0, 50).forEach(t => {
      const color = t.result === 'WIN' ? '#3fb950' : (t.result === 'LOSS' ? '#f85149' : '#d29922');
      tbody.innerHTML += `<tr class="border-b border-[#21262d]">
        <td class="py-1 pr-3">${t.signal_bar}</td>
        <td class="py-1 pr-3" style="color:${t.direction==='LONG'?'#3fb950':'#f85149'}">${t.direction}</td>
        <td class="py-1 pr-3 text-[#8b949e]">${t.strategy || '—'}</td>
        <td class="text-right py-1 pr-3 font-mono">${t.weighted_entry?.toFixed(5) || '—'}</td>
        <td class="text-right py-1 pr-3 font-mono" style="color:${color}">$${t.pnl_usd?.toFixed(2) || '0'}</td>
        <td class="text-right py-1 pr-3 font-mono">${t.pnl_ticks || '0'}</td>
        <td class="text-right py-1 pr-3 text-red-400">${t.mae_ticks || '0'}</td>
        <td class="text-right py-1 pr-3 text-green-400">${t.mfe_ticks || '0'}</td>
        <td class="text-right py-1 pr-3">${t.ladder_efficiency || '0'}%</td>
        <td class="text-right py-1" style="color:${color}">${t.result}</td>
      </tr>`;
    });

    setStatus(`Backtest complete — ${s.total} trades, ${s.win_rate}% win, PF ${s.profit_factor}`);
  } catch (e) {
    setStatus(`Backtest error: ${e.message}`);
    console.error(e);
  }
}

// =============================================================
// BUTTON WIRING
// =============================================================
document.getElementById('btnGenerate').addEventListener('click', generatePlan);
document.getElementById('btnChart').addEventListener('click', loadChart);
document.getElementById('btnBacktest').addEventListener('click', runBacktest);

// =============================================================
// INIT
// =============================================================
initChart();
setStatus('Ready — select contract and generate plan');
