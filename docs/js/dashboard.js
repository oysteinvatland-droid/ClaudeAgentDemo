/**
 * Norwegian Energy Market Dashboard
 * Single-viewport layout — loads JSON and renders Chart.js charts.
 */

'use strict';

/* ── Chart.js dark theme defaults ──────────────────────────── */
Chart.defaults.color = '#8fa3bf';
Chart.defaults.borderColor = 'rgba(148, 163, 184, 0.06)';
Chart.defaults.font.family = "'Outfit', sans-serif";
Chart.defaults.font.size = 11;

const COLOR = {
  price:     '#60a5fa',
  priceFill: 'rgba(96, 165, 250, 0.15)',
  exchange:  '#34d399',
  exchFill:  'rgba(52, 211, 153, 0.15)',
  reservoir: '#a78bfa',
  resFill:   'rgba(167, 139, 250, 0.15)',
  median:    'rgba(167, 139, 250, 0.35)',
  fuel:      '#f4b860',
  fuelFill:  'rgba(244, 184, 96, 0.15)',
};

/* ── Shared chart options ──────────────────────────────────── */
function chartOpts(tooltipFmt) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400 },
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: '#1e2740',
        borderColor: 'rgba(148,163,184,0.12)',
        borderWidth: 1,
        titleColor: '#e2e8f5',
        bodyColor: '#94a3b8',
        padding: 8,
        cornerRadius: 6,
        titleFont: { size: 11 },
        bodyFont: { size: 11 },
        callbacks: tooltipFmt ? { label: tooltipFmt } : {},
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 6, color: '#475569', font: { size: 10 } },
      },
      y: {
        grid: { color: 'rgba(148,163,184,0.05)', drawBorder: false },
        ticks: { maxTicksLimit: 5, color: '#475569', font: { size: 10 } },
      },
    },
  };
}

/* ── Helpers ────────────────────────────────────────────────── */
function setStatus(id, state) {
  const el = document.getElementById('status-' + id);
  if (el) el.className = 'card-status ' + state;
}

function setChange(id, value, label) {
  const el = document.getElementById(id);
  if (!el) return;
  const cls = value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
  const sign = value >= 0 ? '+' : '';
  el.className = 'card-change ' + cls;
  el.textContent = `${sign}${label}`;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function stats(values) {
  const v = values.filter(x => x != null && isFinite(x));
  if (!v.length) return { min: 0, max: 0, avg: 0 };
  return {
    min: Math.min(...v),
    max: Math.max(...v),
    avg: v.reduce((a, b) => a + b, 0) / v.length,
  };
}

function makeGradient(ctx, color) {
  const g = ctx.createLinearGradient(0, 0, 0, ctx.canvas.clientHeight || 200);
  g.addColorStop(0, color);
  g.addColorStop(1, 'transparent');
  return g;
}

/* Format date labels: show month abbreviation */
function shortLabels(dates) {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let lastMonth = -1;
  return dates.map(d => {
    const m = new Date(d).getMonth();
    if (m !== lastMonth) { lastMonth = m; return months[m]; }
    return '';
  });
}

/* ── Load & render: Electricity Prices ─────────────────────── */
async function loadPrices() {
  const data = await fetch('data/prices.json').then(r => r.json());
  const history = data.history || [];
  const cur = data.current || {};

  setText('currentPrice', cur.value != null ? cur.value.toFixed(1) : '—');
  if (cur.change_ore != null) {
    setChange('priceChange', cur.change_ore,
      `${Math.abs(cur.change_ore).toFixed(1)} øre`);
  }
  setStatus('price', 'ok');

  const values = history.map(d => d.avg_ore_kwh);
  const s = stats(values);
  setText('priceHigh', s.max.toFixed(0));
  setText('priceLow', s.min.toFixed(0));
  setText('priceAvg', s.avg.toFixed(0));

  const ctx = document.getElementById('chartPrices')?.getContext('2d');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: shortLabels(history.map(d => d.date)),
      datasets: [{
        data: values,
        borderColor: COLOR.price,
        borderWidth: 1.5,
        backgroundColor: makeGradient(ctx, COLOR.priceFill),
        fill: true,
        pointRadius: 0,
        tension: 0.3,
      }],
    },
    options: chartOpts(c => `${c.parsed.y.toFixed(1)} øre/kWh`),
  });
}

/* ── Load & render: Exchange Rates ─────────────────────────── */
async function loadExchange() {
  const data = await fetch('data/exchange.json').then(r => r.json());
  const history = data.history || [];
  const cur = data.current || {};

  setText('currentExchange', cur.nok_per_usd != null ? cur.nok_per_usd.toFixed(2) : '—');
  if (cur.change_week != null) {
    setChange('exchangeChange', cur.change_week,
      `${Math.abs(cur.change_week).toFixed(3)}/w`);
  }
  setStatus('exchange', 'ok');

  const values = history.map(d => d.nok_per_usd);
  const s = stats(values);
  setText('fxHigh', s.max.toFixed(2));
  setText('fxLow', s.min.toFixed(2));
  setText('fxAvg', s.avg.toFixed(2));

  const ctx = document.getElementById('chartExchange')?.getContext('2d');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: shortLabels(history.map(d => d.date)),
      datasets: [{
        data: values,
        borderColor: COLOR.exchange,
        borderWidth: 1.5,
        backgroundColor: makeGradient(ctx, COLOR.exchFill),
        fill: true,
        pointRadius: 0,
        tension: 0.3,
      }],
    },
    options: chartOpts(c => `${c.parsed.y.toFixed(4)} NOK/USD`),
  });
}

/* ── Load & render: Reservoir Levels ───────────────────────── */
async function loadReservoirs() {
  const data = await fetch('data/reservoirs.json').then(r => r.json());
  const history = data.history || [];
  const cur = data.current || {};

  setText('currentReservoir', cur.filling_pct != null ? cur.filling_pct.toFixed(1) : '—');
  if (cur.change_week != null) {
    setChange('reservoirChange', cur.change_week,
      `${Math.abs(cur.change_week).toFixed(1)}%/w`);
  }
  setStatus('reservoir', 'ok');

  if (cur.filling_pct != null) setText('resCurrentStat', cur.filling_pct.toFixed(1) + '%');
  if (cur.vs_median_pct != null) {
    const sign = cur.vs_median_pct >= 0 ? '+' : '';
    setText('resVsMedian', sign + cur.vs_median_pct.toFixed(1) + '%');
  }

  const filling = history.map(d => d.filling_pct);
  const medians = history.map(d => d.median_pct ?? null);
  const labels = history.map(d => `W${d.week}`);

  const ctx = document.getElementById('chartReservoir')?.getContext('2d');
  if (!ctx) return;

  const datasets = [{
    data: filling,
    borderColor: COLOR.reservoir,
    borderWidth: 1.5,
    backgroundColor: makeGradient(ctx, COLOR.resFill),
    fill: true,
    pointRadius: 0,
    tension: 0.3,
  }];

  if (medians.some(v => v != null)) {
    datasets.push({
      data: medians,
      borderColor: COLOR.median,
      borderWidth: 1,
      borderDash: [3, 3],
      backgroundColor: 'transparent',
      fill: false,
      pointRadius: 0,
      tension: 0.3,
    });
  }

  const opts = chartOpts(c => `${c.parsed.y?.toFixed(1)}%`);
  // Show legend when we have median line
  if (datasets.length > 1) {
    opts.plugins.legend = {
      display: true,
      position: 'top',
      align: 'end',
      labels: {
        boxWidth: 10, boxHeight: 2, usePointStyle: true, pointStyle: 'line',
        padding: 8, color: '#8fa3bf', font: { size: 10 },
        generateLabels: () => [
          { text: 'Filling', strokeStyle: COLOR.reservoir, lineWidth: 2, hidden: false },
          { text: 'Median', strokeStyle: COLOR.median, lineWidth: 1, lineDash: [3,3], hidden: false },
        ],
      },
    };
  }

  new Chart(ctx, { type: 'line', data: { labels, datasets }, options: opts });
}

/* ── Load & render: Fuel Prices ────────────────────────────── */
async function loadFuel() {
  const data = await fetch('data/fuel.json').then(r => r.json());
  const history = data.history || [];
  const cur = data.current || {};

  setText('currentFuel', cur.price_nok != null ? cur.price_nok.toFixed(2) : '—');
  if (cur.change_week != null) {
    setChange('fuelChange', cur.change_week,
      `${Math.abs(cur.change_week).toFixed(2)}/w`);
  }
  setStatus('fuel', 'ok');

  const values = history.map(d => d.price_nok);
  const s = stats(values);
  setText('fuelHigh', s.max.toFixed(2));
  setText('fuelLow', s.min.toFixed(2));
  setText('fuelAvg', s.avg.toFixed(2));

  const ctx = document.getElementById('chartFuel')?.getContext('2d');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: shortLabels(history.map(d => d.date)),
      datasets: [{
        data: values,
        borderColor: COLOR.fuel,
        borderWidth: 1.5,
        backgroundColor: makeGradient(ctx, COLOR.fuelFill),
        fill: true,
        pointRadius: 0,
        tension: 0.3,
      }],
    },
    options: chartOpts(c => `${c.parsed.y.toFixed(2)} NOK/L`),
  });
}

/* ── Timestamp ─────────────────────────────────────────────── */
function setTimestamp(iso) {
  const el = document.getElementById('updatedTime');
  if (!el) return;
  try {
    el.textContent = new Date(iso).toLocaleString('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
    });
  } catch { el.textContent = iso; }
}

/* ── Init ──────────────────────────────────────────────────── */
async function init() {
  await Promise.allSettled([
    loadPrices().catch(() => setStatus('price', 'error')),
    loadExchange().catch(() => setStatus('exchange', 'error')),
    loadReservoirs().catch(() => setStatus('reservoir', 'error')),
    loadFuel().catch(() => setStatus('fuel', 'error')),
  ]);

  try {
    const d = await fetch('data/prices.json').then(r => r.json());
    if (d?.meta?.updated) setTimestamp(d.meta.updated);
  } catch {}
}

document.addEventListener('DOMContentLoaded', init);
