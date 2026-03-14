#!/usr/bin/env python3
"""
Fetch NOK/USD exchange rates from Norges Bank's public API.

API: data.norges-bank.no — The official Norwegian central bank data portal.
Free, no authentication required. Returns daily spot exchange rates.

Agent decision: Norges Bank was chosen as the authoritative source for NOK
exchange rates as it is Norway's central bank and publishes official daily
rates. The API is REST-based, returns SDMX-JSON, and covers the full year.
"""

import json
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


OUTPUT_FILE = Path(__file__).parent.parent / "docs" / "data" / "exchange.json"
NB_API = "https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP"


def fetch_rates(start: str, end: str) -> list[dict]:
    """
    Fetch USD/NOK daily rates from Norges Bank for a date range.
    The rate returned is NOK per 1 USD.
    """
    params = {
        "format": "sdmx-json",
        "startPeriod": start,
        "endPeriod": end,
        "locale": "en",
    }
    print(f"Fetching NOK/USD rates {start} → {end} from Norges Bank...")
    try:
        resp = requests.get(NB_API, params=params, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching from Norges Bank: {e}")
        return []

    data = resp.json()
    try:
        # SDMX-JSON structure: dataSets[0].series["0:0:0:0"].observations
        observations = data["dataSets"][0]["series"]["0:0:0:0"]["observations"]
        time_periods = data["structure"]["dimensions"]["observation"][0]["values"]
    except (KeyError, IndexError) as e:
        print(f"  ERROR parsing SDMX-JSON response: {e}")
        return []

    history = []
    for i, period in enumerate(time_periods):
        obs = observations.get(str(i))
        if obs and obs[0] is not None:
            history.append({
                "date": period["id"],
                "nok_per_usd": round(float(obs[0]), 4),
            })

    print(f"  Fetched {len(history)} trading days")
    return history


def fill_weekends(history: list[dict]) -> list[dict]:
    """
    Norges Bank only publishes rates on trading days. Fill weekends/holidays
    by carrying the last known rate forward, so charts show continuous data.
    """
    if not history:
        return []

    filled = []
    rate_map = {h["date"]: h["nok_per_usd"] for h in history}

    start = date.fromisoformat(history[0]["date"])
    end = date.fromisoformat(history[-1]["date"])
    current = start
    last_rate = history[0]["nok_per_usd"]

    while current <= end:
        d = current.isoformat()
        if d in rate_map:
            last_rate = rate_map[d]
            filled.append({"date": d, "nok_per_usd": last_rate})
        else:
            filled.append({"date": d, "nok_per_usd": last_rate, "estimated": True})
        current += timedelta(days=1)

    return filled


def main():
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    history_raw = fetch_rates(one_year_ago.isoformat(), today.isoformat())

    if not history_raw:
        print("ERROR: No exchange rate data fetched.")
        sys.exit(1)

    history = fill_weekends(history_raw)

    current = history[-1]
    prev = history[-8] if len(history) > 7 else history[0]  # Compare to 1 week ago
    change = round(current["nok_per_usd"] - prev["nok_per_usd"], 4)
    change_pct = round((change / prev["nok_per_usd"]) * 100, 2) if prev["nok_per_usd"] else 0

    output = {
        "current": {
            "nok_per_usd": current["nok_per_usd"],
            "usd_per_nok": round(1 / current["nok_per_usd"], 6) if current["nok_per_usd"] else 0,
            "date": current["date"],
            "change_week": change,
            "change_week_pct": change_pct,
        },
        "history": history,
        "meta": {
            "source": "Norges Bank (data.norges-bank.no)",
            "pair": "USD/NOK",
            "updated": datetime.utcnow().isoformat() + "Z",
            "days": len(history),
            "trading_days": len(history_raw),
        }
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ Saved {len(history)} days of exchange data → {OUTPUT_FILE}")
    print(f"  Current: {current['nok_per_usd']:.4f} NOK/USD "
          f"({'+' if change >= 0 else ''}{change:.4f} vs last week)")


if __name__ == "__main__":
    main()
