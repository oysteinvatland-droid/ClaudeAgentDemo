#!/usr/bin/env python3
"""
Fetch Norwegian electricity prices from Strømpris API (hvakosterstrommen.no).

Zone: NO1 (Oslo/Østlandet) — the largest consumption zone.
API returns hourly prices in øre/kWh (including VAT when applicable).
365 days of daily averages are fetched and stored in docs/data/prices.json.

Agent decision: We chose NO1 as the default zone because it covers the Oslo
region and represents the largest share of Norwegian consumption. The API is
free, requires no authentication, and returns real-time market prices.
"""

import json
import os
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


ZONE = "NO1"
BASE_URL = "https://www.hvakosterstrommen.no/api/v1/prices"
OUTPUT_FILE = Path(__file__).parent.parent / "docs" / "data" / "prices.json"


def fetch_day_prices(target_date: date) -> list[dict] | None:
    """Fetch hourly prices for a single day. Returns None on failure."""
    url = f"{BASE_URL}/{target_date.year}/{target_date.strftime('%m-%d')}_{ZONE}.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  WARNING: Could not fetch {target_date}: {e}")
        return None


def average_price(hourly: list[dict]) -> float:
    """Return daily average NOK_per_kWh (in øre/kWh = * 100)."""
    prices = [h.get("NOK_per_kWh", 0) for h in hourly if h.get("NOK_per_kWh") is not None]
    if not prices:
        return 0.0
    return round(sum(prices) / len(prices) * 100, 2)  # Convert to øre/kWh


def build_history(days: int = 365) -> list[dict]:
    """Fetch daily average prices for the past `days` days."""
    today = date.today()
    history = []
    print(f"Fetching electricity prices for the past {days} days (zone {ZONE})...")
    for i in range(days - 1, -1, -1):
        target = today - timedelta(days=i)
        hourly = fetch_day_prices(target)
        if hourly:
            avg = average_price(hourly)
            raw_prices = [h.get("NOK_per_kWh", 0) * 100 for h in hourly if h.get("NOK_per_kWh") is not None]
            history.append({
                "date": target.isoformat(),
                "avg_ore_kwh": avg,
                "min_ore_kwh": round(min(raw_prices), 2) if raw_prices else avg,
                "max_ore_kwh": round(max(raw_prices), 2) if raw_prices else avg,
                "hours": len(hourly),
            })
            if i % 30 == 0:
                print(f"  ...fetched up to {target} ({avg:.1f} øre/kWh)")
        else:
            # Carry forward last known value if fetch fails
            if history:
                prev = history[-1].copy()
                prev["date"] = target.isoformat()
                prev["note"] = "estimated"
                history.append(prev)
    return history


def main():
    history = build_history(365)
    if not history:
        print("ERROR: No price data fetched.")
        sys.exit(1)

    # Current value = latest available day's average
    current = history[-1]
    prev_day = history[-2] if len(history) > 1 else current
    change = round(current["avg_ore_kwh"] - prev_day["avg_ore_kwh"], 2)
    change_pct = round((change / prev_day["avg_ore_kwh"]) * 100, 1) if prev_day["avg_ore_kwh"] else 0

    # Also get today's hourly breakdown for the current-day card
    today_hourly_raw = fetch_day_prices(date.today())
    today_hourly = []
    if today_hourly_raw:
        today_hourly = [
            {"hour": h.get("time_start", "")[:13], "ore_kwh": round(h.get("NOK_per_kWh", 0) * 100, 2)}
            for h in today_hourly_raw
        ]

    output = {
        "current": {
            "value": current["avg_ore_kwh"],
            "unit": "øre/kWh",
            "zone": ZONE,
            "date": current["date"],
            "change_ore": change,
            "change_pct": change_pct,
        },
        "today_hourly": today_hourly,
        "history": history,
        "meta": {
            "source": "hvakosterstrommen.no",
            "zone": ZONE,
            "zone_name": "NO1 — Oslo / Østlandet",
            "updated": datetime.utcnow().isoformat() + "Z",
            "days": len(history),
        }
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved {len(history)} days of price data → {OUTPUT_FILE}")
    print(f"  Current: {current['avg_ore_kwh']:.1f} øre/kWh ({'+' if change >= 0 else ''}{change:.1f} vs yesterday)")


if __name__ == "__main__":
    main()
