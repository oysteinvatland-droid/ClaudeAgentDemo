#!/usr/bin/env python3
"""
Generate realistic seed data for the dashboard.
Run this once to populate docs/data/ so GitHub Pages has data to show
before the first GitHub Actions run.

The data is synthetic but follows realistic Norwegian energy market patterns:
- Electricity prices: seasonal (high winter, low summer), 30-150 øre/kWh
- NOK/USD: gradual drift with noise, ~10.0-11.5 range (2024 levels)
- Reservoir levels: seasonal pattern (fills spring/summer, drains winter)
"""

import json
import math
import random
from datetime import date, timedelta, datetime
from pathlib import Path

random.seed(42)  # Reproducible

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sine_wave(day_of_year: int, period: float, phase: float,
              amplitude: float, baseline: float) -> float:
    return baseline + amplitude * math.sin(2 * math.pi * (day_of_year / period - phase))


def noisy(value: float, noise: float) -> float:
    return value + random.gauss(0, noise)


# ── Electricity prices ────────────────────────────────────────────────────────

def generate_prices():
    today = date.today()
    history = []
    prev_avg = 85.0

    for i in range(364, -1, -1):
        d = today - timedelta(days=i)
        doy = d.timetuple().tm_yday

        # Seasonal: high Jan-Mar, low Jul-Aug
        seasonal = sine_wave(doy, 365, 0.55, 35, 80)
        # Add some week-to-week volatility
        trend = noisy(seasonal, 12)
        # Mean-revert toward seasonal
        avg = 0.7 * trend + 0.3 * prev_avg
        avg = max(10, min(220, avg))
        prev_avg = avg

        spread = avg * 0.25
        history.append({
            "date": d.isoformat(),
            "avg_ore_kwh": round(avg, 2),
            "min_ore_kwh": round(max(5, avg - spread * random.uniform(0.5, 1.0)), 2),
            "max_ore_kwh": round(avg + spread * random.uniform(0.5, 1.2), 2),
            "hours": 24,
        })

    current = history[-1]
    prev    = history[-2]
    change  = round(current["avg_ore_kwh"] - prev["avg_ore_kwh"], 2)

    return {
        "current": {
            "value": current["avg_ore_kwh"],
            "unit": "øre/kWh",
            "zone": "NO1",
            "date": current["date"],
            "change_ore": change,
            "change_pct": round(change / prev["avg_ore_kwh"] * 100, 1),
        },
        "today_hourly": [],
        "history": history,
        "meta": {
            "source": "hvakosterstrommen.no (seed data — replace with real fetch)",
            "zone": "NO1",
            "zone_name": "NO1 — Oslo / Østlandet",
            "updated": datetime.utcnow().isoformat() + "Z",
            "days": len(history),
            "note": "SEED DATA — run scripts/fetch_all.py to fetch real data",
        }
    }


# ── Exchange rates ─────────────────────────────────────────────────────────

def generate_exchange():
    today = date.today()
    history = []

    rate = 10.55  # Jan 2024 starting rate

    for i in range(364, -1, -1):
        d = today - timedelta(days=i)
        # Slow trend + noise
        rate += random.gauss(0, 0.035)
        rate = 0.99 * rate + 0.01 * 10.65  # Mean-revert toward 10.65
        rate = max(9.5, min(12.0, rate))

        history.append({
            "date": d.isoformat(),
            "nok_per_usd": round(rate, 4),
        })

    current = history[-1]
    prev_week = history[-8]
    change = round(current["nok_per_usd"] - prev_week["nok_per_usd"], 4)

    return {
        "current": {
            "nok_per_usd": current["nok_per_usd"],
            "usd_per_nok": round(1 / current["nok_per_usd"], 6),
            "date": current["date"],
            "change_week": change,
            "change_week_pct": round(change / prev_week["nok_per_usd"] * 100, 2),
        },
        "history": history,
        "meta": {
            "source": "Norges Bank (seed data — replace with real fetch)",
            "pair": "USD/NOK",
            "updated": datetime.utcnow().isoformat() + "Z",
            "days": len(history),
            "trading_days": len(history),
            "note": "SEED DATA — run scripts/fetch_all.py to fetch real data",
        }
    }


# ── Reservoir levels ──────────────────────────────────────────────────────

def generate_reservoirs():
    today = date.today()
    history = []
    filling = 72.0

    for week_offset in range(52, -1, -1):
        week_start = today - timedelta(weeks=week_offset)
        iso_year, iso_week, _ = week_start.isocalendar()
        doy = week_start.timetuple().tm_yday

        # Seasonal pattern: drains winter, fills spring/summer
        # Min ~35% in Feb/Mar, max ~90% in Oct
        seasonal = sine_wave(doy, 365, 0.72, 28, 68)
        median   = sine_wave(doy, 365, 0.72, 25, 70)

        # Noisy walk around seasonal
        filling = 0.85 * filling + 0.15 * seasonal + random.gauss(0, 2)
        filling = max(20, min(97, filling))

        history.append({
            "year": int(iso_year),
            "week": int(iso_week),
            "date": week_start.isoformat(),
            "filling_pct": round(filling, 2),
            "median_pct": round(median + random.gauss(0, 1), 2),
        })

    current = history[-1]
    prev    = history[-2]
    change  = round(current["filling_pct"] - prev["filling_pct"], 2)
    vs_median = round(current["filling_pct"] - current["median_pct"], 2) if current.get("median_pct") else None

    return {
        "current": {
            "filling_pct": current["filling_pct"],
            "median_pct": current.get("median_pct"),
            "vs_median_pct": vs_median,
            "week": current["week"],
            "year": current["year"],
            "date": current["date"],
            "change_week": change,
        },
        "history": history,
        "meta": {
            "source": "NVE Magasinstatistikk (seed data — replace with real fetch)",
            "region": "Norway (national aggregate)",
            "updated": datetime.utcnow().isoformat() + "Z",
            "weeks": len(history),
            "note": "SEED DATA — run scripts/fetch_all.py to fetch real data",
        }
    }


def main():
    print("Generating seed data for Norwegian Energy Market Dashboard...")

    prices = generate_prices()
    with open(OUTPUT_DIR / "prices.json", "w") as f:
        json.dump(prices, f, indent=2, ensure_ascii=False)
    print(f"  ✓ prices.json — {len(prices['history'])} days, "
          f"current: {prices['current']['value']:.1f} øre/kWh")

    exchange = generate_exchange()
    with open(OUTPUT_DIR / "exchange.json", "w") as f:
        json.dump(exchange, f, indent=2)
    print(f"  ✓ exchange.json — {len(exchange['history'])} days, "
          f"current: {exchange['current']['nok_per_usd']:.4f} NOK/USD")

    reservoirs = generate_reservoirs()
    with open(OUTPUT_DIR / "reservoirs.json", "w") as f:
        json.dump(reservoirs, f, indent=2, ensure_ascii=False)
    print(f"  ✓ reservoirs.json — {len(reservoirs['history'])} weeks, "
          f"current: {reservoirs['current']['filling_pct']:.1f}%")

    print(f"\nSeed data written to {OUTPUT_DIR}")
    print("NOTE: This is synthetic data. Run `python scripts/fetch_all.py` to fetch real data.")


if __name__ == "__main__":
    main()
