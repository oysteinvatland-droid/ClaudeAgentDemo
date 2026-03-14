/**
 * Norwegian Energy Market Dashboard
 * Loads JSON data files and renders charts with Chart.js 4.x.
 *
 * Architecture decision (Developer Agent):
 * - Pure vanilla JS — no framework overhead, instant load on GitHub Pages
 * - Parallel data fetching via Promise.allSettled for resilience
 * - Chart defaults set once via Chart.defaults for consistent dark theme
 * - Sparklines reuse the same config factory as full charts
 */

'use strict';

/* ── Chart.js global dark theme defaults ───────────────────── */
Chart.defaults.color = '#8fa3bf';
Chart.defaults.borderColor = 'rgba(148, 163, 184, 0.08)';
Chart.defaults.font.family = "'Outfit', sans-serif";
Chart.defaults.font.size = 12;

/* ── CSS variable helpers ───────────────────────────────────── */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const COLOR = {
  price:     '#60a5fa',
  priceFill: 'rgba(96, 165, 250, 0.12)',
  exchange:  '#34d399',
  exchFill:  'rgba(52, 211, 153, 0.12)',
  reservoir: '#a78bfa',
  resFill:   'rgba(167, 139, 250, 0.12)',
  median:    'rgba(167, 139, 250, 0.35)',
};

/* ── Shared chart option factory ────────────────────────────── */
function lineOptions({ yLabel = '', tooltipFormatter = null, miniMode = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: miniMode ? 0 : 600 },
    interaction: {
      intersect: false,
      mode: 'index',
    },
    plugins: {
      legend: {
        display: !miniMode,
        position: 'top',
        align: 'end',
        labels: {
          boxWidth: 12,
          boxHeight: 2,
          usePointStyle: true,
          pointStyle: 'line',
          padding: 16,
          color: '#8fa3bf',
          font: { size: 11, weight: '500' },
        },
      },
      tooltip: {
        enabled: !miniMode,
        backgroundColor: '#1e2740',
        borderColor: 'rgba(148,163,184,0.15)',
        borderWidth: 1,
        titleColor: '#e2e8f5',
        bodyColor: '#94a3b8',
        padding: 12,
        cornerRadius: 8,
        callbacks: tooltipFormatter ? { label: tooltipFormatter } : {},
      },
    },
    scales: miniMode
      ? {
          x: { display: false },
          y: { display: false },
        }
      : {
          x: {
            grid: { color: 'rgba(148,163,184,0.06)', drawBorder: false },
            ticks: {
              maxTicksLimit: 8,
              color: '#576880',
              font: { size: 11 },
            },
          },
          y: {
            position: 'left',
            grid: { color: 'rgba(148,163,184,0.06)', drawBorder: false },
            ticks: {
              color: '#576880',
              font: { size: 11 },
              callback: (v) => yLabel ? `${v} ${yLabel}` : v,
            },
          },
        },
  };
}

/* ── Sparkline helper ───────────────────────────────────────── */
function createSparkline(canvasId, data, color, fillColor) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return;

  const gradient = ctx.createLinearGradient(0, 0, 0, 48);
  gradient.addColorStop(0, fillColor.replace('0.12', '0.25'));
  gradient.addColorStop(1, 'transparent');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map((_, i) => i),
      datasets: [{
        data,
        borderColor: color,
        borderWidth: 1.5,
        backgroundColor: gradient,
        fill: true,
        pointRadius: 0,
        tension: 0.35,
      }],
    },
    options: lineOptions({ miniMode: true }),
  });
}

/* ── Status indicator helper ─────────────────────────────────── */
function setStatus(id, state) {
  const el = document.getElementById('status-' + id);
  if (!el) return;
  el.className = 'card-status ' + state;
  el.title = state === 'ok' ? 'Data loaded' : state === 'error' ? 'Failed to load' : 'Loading…';
}

/* ── Change badge helper ─────────────────────────────────────── */
function renderChange(el, value, label) {
  if (!el) return;
  const sign = value >= 0 ? '+' : '';
  const cls = value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
  el.className = 'card-change ' + cls;
  el.textContent = `${sign}${label}`;
}

/* ── Stat helpers ────────────────────────────────────────────── */
function setStat(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function statsFor(values) {
  const valid = values.filter((v) => v != null && isFinite(v));
  if (!valid.length) return { min: 0, max: 0, avg: 0 };
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  const avg = valid.reduce((a, b) => a + b, 0) / valid.length;
  return { min, max, avg };
}

/* ── Electricity prices ──────────────────────────────────────── */
async function loadPrices() {
  const data = await fetch('data/prices.json').then((r) => r.json());

  const history = data.history || [];
  const current = data.current || {};

  // Summary card
  document.getElementById('currentPrice').textContent =
    current.value != null ? current.value.toFixed(1) : '—';

  const chEl = document.getElementById('priceChange');
  if (current.change_ore != null) {
    renderChange(chEl, current.change_ore,
      `${Math.abs(current.change_ore).toFixed(1)} øre/kWh vs yesterday`);
  }
  setStatus('price', 'ok');

  // Sparkline (last 30 days)
  const spark = history.slice(-30).map((d) => d.avg_ore_kwh);
  createSparkline('sparkPrice', spark, COLOR.price, COLOR.priceFill);

  // Full chart
  const labels = history.map((d) => d.date);
  const values = history.map((d) => d.avg_ore_kwh);
  const s = statsFor(values);

  setStat('priceHigh', s.max.toFixed(1) + ' øre');
  setStat('priceLow',  s.min.toFixed(1) + ' øre');
  setStat('priceAvg',  s.avg.toFixed(1) + ' øre');

  const ctx = document.getElementById('chartPrices')?.getContext('2d');
  if (!ctx) return;

  const gradient = ctx.createLinearGradient(0, 0, 0, 220);
  gradient.addColorStop(0, 'rgba(96,165,250,0.20)');
  gradient.addColorStop(1, 'rgba(96,165,250,0.00)');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Avg daily price (øre/kWh)',
        data: values,
        borderColor: COLOR.price,
        borderWidth: 2,
        backgroundColor: gradient,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.3,
      }],
    },
    options: lineOptions({
      yLabel: 'øre',
      tooltipFormatter: (ctx) =>
        `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} øre/kWh`,
    }),
  });
}

/* ── Exchange rates ──────────────────────────────────────────── */
async function loadExchange() {
  const data = await fetch('data/exchange.json').then((r) => r.json());

  const history = data.history || [];
  const current = data.current || {};

  document.getElementById('currentExchange').textContent =
    current.nok_per_usd != null ? current.nok_per_usd.toFixed(2) : '—';

  const chEl = document.getElementById('exchangeChange');
  if (current.change_week != null) {
    renderChange(chEl, current.change_week,
      `${Math.abs(current.change_week).toFixed(4)} vs last week`);
  }
  setStatus('exchange', 'ok');

  // Sparkline (last 30 days)
  const spark = history.slice(-30).map((d) => d.nok_per_usd);
  createSparkline('sparkExchange', spark, COLOR.exchange, COLOR.exchFill);

  // Full chart
  const labels = history.map((d) => d.date);
  const values = history.map((d) => d.nok_per_usd);
  const s = statsFor(values);

  setStat('fxHigh', s.max.toFixed(4));
  setStat('fxLow',  s.min.toFixed(4));
  setStat('fxAvg',  s.avg.toFixed(4));

  const ctx = document.getElementById('chartExchange')?.getContext('2d');
  if (!ctx) return;

  const gradient = ctx.createLinearGradient(0, 0, 0, 220);
  gradient.addColorStop(0, 'rgba(52,211,153,0.20)');
  gradient.addColorStop(1, 'rgba(52,211,153,0.00)');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'NOK per USD',
        data: values,
        borderColor: COLOR.exchange,
        borderWidth: 2,
        backgroundColor: gradient,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.3,
      }],
    },
    options: lineOptions({
      tooltipFormatter: (ctx) =>
        `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(4)}`,
    }),
  });
}

/* ── Reservoir levels ────────────────────────────────────────── */
async function loadReservoirs() {
  const data = await fetch('data/reservoirs.json').then((r) => r.json());

  const history = data.history || [];
  const current = data.current || {};

  document.getElementById('currentReservoir').textContent =
    current.filling_pct != null ? current.filling_pct.toFixed(1) : '—';

  const chEl = document.getElementById('reservoirChange');
  if (current.change_week != null) {
    renderChange(chEl, current.change_week,
      `${Math.abs(current.change_week).toFixed(1)}% vs last week`);
  }
  setStatus('reservoir', 'ok');

  // Sparkline (last 20 weeks)
  const spark = history.slice(-20).map((d) => d.filling_pct);
  createSparkline('sparkReservoir', spark, COLOR.reservoir, COLOR.resFill);

  // Full chart with actual + median
  const labels   = history.map((d) => d.date || `W${d.week}`);
  const filling  = history.map((d) => d.filling_pct);
  const medians  = history.map((d) => d.median_pct ?? null);

  const hasMedian = medians.some((v) => v != null);

  if (current.filling_pct != null) {
    setStat('resCurrentStat', current.filling_pct.toFixed(1) + '%');
  }
  if (current.vs_median_pct != null) {
    const sign = current.vs_median_pct >= 0 ? '+' : '';
    setStat('resVsMedian', sign + current.vs_median_pct.toFixed(1) + '%');
  }

  const ctx = document.getElementById('chartReservoir')?.getContext('2d');
  if (!ctx) return;

  const gradient = ctx.createLinearGradient(0, 0, 0, 220);
  gradient.addColorStop(0, 'rgba(167,139,250,0.20)');
  gradient.addColorStop(1, 'rgba(167,139,250,0.00)');

  const datasets = [
    {
      label: 'Filling %',
      data: filling,
      borderColor: COLOR.reservoir,
      borderWidth: 2,
      backgroundColor: gradient,
      fill: true,
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.3,
    },
  ];

  if (hasMedian) {
    datasets.push({
      label: 'Historical median %',
      data: medians,
      borderColor: COLOR.median,
      borderWidth: 1.5,
      borderDash: [4, 4],
      backgroundColor: 'transparent',
      fill: false,
      pointRadius: 0,
      pointHoverRadius: 3,
      tension: 0.3,
    });
  }

  new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: lineOptions({
      yLabel: '%',
      tooltipFormatter: (ctx) =>
        `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(1)}%`,
    }),
  });
}

/* ── Last-updated timestamp ──────────────────────────────────── */
function updateTimestamp(isoString) {
  const el = document.getElementById('updatedTime');
  if (!el) return;
  try {
    const d = new Date(isoString);
    el.textContent = d.toLocaleString('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
      timeZoneName: 'short',
    });
  } catch {
    el.textContent = isoString;
  }
}

/* ── Bootstrap ───────────────────────────────────────────────── */
async function init() {
  const results = await Promise.allSettled([
    loadPrices().catch((e) => {
      console.error('Prices failed:', e);
      setStatus('price', 'error');
    }),
    loadExchange().catch((e) => {
      console.error('Exchange failed:', e);
      setStatus('exchange', 'error');
    }),
    loadReservoirs().catch((e) => {
      console.error('Reservoirs failed:', e);
      setStatus('reservoir', 'error');
    }),
  ]);

  // Show the most recent updated timestamp across all datasets
  try {
    const [pricesData] = await Promise.all([
      fetch('data/prices.json').then((r) => r.json()),
    ]);
    if (pricesData?.meta?.updated) {
      updateTimestamp(pricesData.meta.updated);
    }
  } catch {
    // Non-critical — timestamp is cosmetic
  }
}

document.addEventListener('DOMContentLoaded', init);
