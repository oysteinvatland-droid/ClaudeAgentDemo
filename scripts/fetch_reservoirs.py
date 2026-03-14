#!/usr/bin/env python3
"""
Fetch Norwegian hydroelectric reservoir filling levels from NVE (Norwegian
Water Resources and Energy Directorate).

API: biapi.nve.no/magasinstatistikk — Provides weekly reservoir statistics
for all Norwegian hydro regions. The aggregate filling percentage for the
entire country is a key indicator for electricity price forecasting.

Agent decision: NVE was chosen as it is the official Norwegian government
agency responsible for hydro data. The reservoir filling percentage is
critical for Norwegian energy markets because ~90% of Norwegian electricity
comes from hydropower, so low reservoirs typically mean higher prices.
The API returns weekly aggregates (ISO weeks), which is the standard
publication frequency for this data.
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


OUTPUT_FILE = Path(__file__).parent.parent / "docs" / "data" / "reservoirs.json"
NVE_API = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk"


def fetch_nve_data() -> list[dict]:
    """
    Fetch reservoir statistics from NVE for all Norway (UtvalgtOmr=Norge).
    Returns list of weekly records with actual and median filling percentages.
    """
    print("Fetching reservoir data from NVE...")
    try:
        resp = requests.get(
            NVE_API,
            params={"UtvalgtOmr": "Norge"},
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ERROR fetching from NVE: {e}")
        return []


def parse_records(raw: list[dict]) -> list[dict]:
    """
    Parse NVE response into a consistent format.
    NVE returns records with: Uke (week), År (year), Fyllingsgrad (filling%),
    Median (median filling%), and similar fields.
    """
    records = []
    seen = set()

    for item in raw:
        try:
            week = item.get("uke") or item.get("Uke")
            year = item.get("år") or item.get("År")
            filling = item.get("fyllingsgrad") or item.get("Fyllingsgrad")
            median = item.get("medianFyllingsgrad") or item.get("median") or item.get("Median")

            if week is None or year is None or filling is None:
                continue

            key = (int(year), int(week))
            if key in seen:
                continue
            seen.add(key)

            # Compute approximate ISO date for the start of the week
            week_date = datetime.strptime(f"{int(year)}-W{int(week):02d}-1", "%Y-W%W-%w").date()

            records.append({
                "year": int(year),
                "week": int(week),
                "date": week_date.isoformat(),
                "filling_pct": round(float(filling), 2),
                "median_pct": round(float(median), 2) if median is not None else None,
            })
        except (ValueError, TypeError):
            continue

    # Sort by date and keep the most recent 54 weeks (just over 1 year)
    records.sort(key=lambda x: x["date"])
    return records[-54:]


def main():
    raw = fetch_nve_data()

    if not raw:
        print("  WARNING: NVE API returned no data. Using fallback empty dataset.")
        history = []
    else:
        history = parse_records(raw)
        print(f"  Parsed {len(history)} weekly records")

    if not history:
        print("ERROR: No reservoir data available.")
        sys.exit(1)

    current = history[-1]
    prev = history[-2] if len(history) > 1 else current
    change = round(current["filling_pct"] - prev["filling_pct"], 2)

    # Deviation from median (positive = above median = good supply)
    vs_median = None
    if current.get("median_pct") is not None:
        vs_median = round(current["filling_pct"] - current["median_pct"], 2)

    output = {
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
            "source": "NVE (biapi.nve.no/magasinstatistikk)",
            "region": "Norway (national aggregate)",
            "updated": datetime.utcnow().isoformat() + "Z",
            "weeks": len(history),
        }
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved {len(history)} weeks of reservoir data → {OUTPUT_FILE}")
    print(f"  Current filling: {current['filling_pct']:.1f}%"
          f"{f' ({vs_median:+.1f}% vs median)' if vs_median is not None else ''}")


if __name__ == "__main__":
    main()
