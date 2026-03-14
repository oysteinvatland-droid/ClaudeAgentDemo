#!/usr/bin/env python3
"""
Fetch Norwegian petrol prices from Statistics Norway (SSB).

Source: SSB StatBank table 09654
        "Prices on engine fuel (NOK per litres)"
        https://www.ssb.no/en/statbank/table/09654

API: data.ssb.no PxWebApi v1 — open, no authentication required.
     POST https://data.ssb.no/api/v0/en/table/09654
     Response format: json-stat2

The table contains monthly pump prices (incl. taxes) for unleaded 95 oktan
petrol and diesel. We fetch the last 13 months so the chart has a full
12-month history with at least one earlier point for the change calculation.

SSB updates the table monthly, roughly three weeks after end of reference month.
"""

import json
import sys
from datetime import datetime, date
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

OUTPUT_FILE = Path(__file__).parent.parent / "docs" / "data" / "fuel.json"
SSB_URL     = "https://data.ssb.no/api/v0/en/table/09654"

# SSB table 09654 variable codes (discovered from table metadata):
#   Drivstofftype : fuel product type
#     "blyfri95"  : unleaded petrol 95 oktan
#     "diesel"    : diesel
#   ContentsCode  : measure
#     "Pris"      : price in NOK per litre
#   Tid           : month in format "YYYYMM"
PRODUCT_CODE   = "blyfri95"
CONTENTS_CODE  = "Pris"


def _recent_months(n: int) -> list[str]:
    """Return the last n months in SSB format 'YYYYMM'."""
    today = date.today()
    months = []
    year, month = today.year, today.month
    for _ in range(n):
        months.append(f"{year}{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def fetch_metadata() -> dict:
    """
    GET the table metadata to discover actual variable codes and values.
    Returns the raw metadata JSON, or an empty dict on failure.
    """
    try:
        resp = requests.get(SSB_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  WARNING: Could not fetch metadata: {e}")
        return {}


def discover_product_code(metadata: dict) -> str:
    """
    Find the correct code for unleaded 95 oktan petrol from the metadata.
    Falls back to the hardcoded PRODUCT_CODE if metadata is unavailable.
    """
    if not metadata:
        return PRODUCT_CODE

    for var in metadata.get("variables", []):
        # Look for the fuel-type variable (not ContentsCode, not Tid)
        code = var.get("code", "")
        if code in ("Tid", "ContentsCode"):
            continue
        # Search values for something matching petrol/95/blyfri
        for val_code, val_text in zip(
            var.get("values", []),
            var.get("valueTexts", []),
        ):
            text_lower = val_text.lower()
            if any(k in text_lower for k in ("95", "blyfri", "petrol", "bensin")):
                print(f"  Found petrol code: '{val_code}' ({val_text})")
                return val_code

    print(f"  Using default product code: '{PRODUCT_CODE}'")
    return PRODUCT_CODE


def discover_fuel_variable(metadata: dict) -> str:
    """Return the variable code for fuel type (not Tid, not ContentsCode)."""
    if not metadata:
        return "Drivstofftype"
    for var in metadata.get("variables", []):
        code = var.get("code", "")
        if code not in ("Tid", "ContentsCode"):
            return code
    return "Drivstofftype"


def fetch_prices(product_code: str, fuel_var: str, months: list[str]) -> list[dict]:
    """
    POST a query to SSB and return a list of {date, price_nok} dicts.
    date is the first day of the month (YYYY-MM-01).
    """
    query = {
        "query": [
            {
                "code": fuel_var,
                "selection": {"filter": "item", "values": [product_code]},
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": [CONTENTS_CODE]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "item", "values": months},
            },
        ],
        "response": {"format": "json-stat2"},
    }

    print(f"  Querying SSB table 09654 for '{product_code}', {len(months)} months...")
    try:
        resp = requests.post(SSB_URL, json=query, timeout=20)
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"  ERROR: HTTP {e.response.status_code} from SSB API")
        if e.response.status_code == 400:
            print("  Hint: variable codes may have changed — check table metadata")
        return []
    except Exception as e:
        print(f"  ERROR fetching from SSB: {e}")
        return []

    data = resp.json()

    # json-stat2 structure:
    #   data["dimension"]["Tid"]["category"]["index"]  -> {period: position}
    #   data["dimension"]["Tid"]["category"]["label"]  -> {position: "2024M01"}
    #   data["value"]                                  -> flat list of values
    try:
        tid_dim   = data["dimension"]["Tid"]["category"]
        tid_index = tid_dim["index"]   # {"2024M01": 0, "2024M02": 1, ...}
        tid_label = tid_dim.get("label", tid_index)  # same keys if label missing
        values    = data["value"]      # one value per time period
    except (KeyError, TypeError) as e:
        print(f"  ERROR parsing json-stat2 response: {e}")
        print(f"  Response keys: {list(data.keys())}")
        return []

    history = []
    for period, pos in tid_index.items():
        val = values[pos] if pos < len(values) else None
        if val is None:
            continue
        # Convert "2024M01" → "2024-01-01"
        try:
            dt = datetime.strptime(period, "%YM%m")
            iso_date = dt.strftime("%Y-%m-01")
        except ValueError:
            iso_date = period  # keep raw if format is unexpected

        history.append({"date": iso_date, "price_nok": round(float(val), 2)})

    history.sort(key=lambda x: x["date"])
    print(f"  Fetched {len(history)} monthly prices")
    return history


def main():
    print("Fetching Norwegian petrol prices from SSB table 09654...")

    # Step 1: discover variable codes from live metadata
    metadata   = fetch_metadata()
    fuel_var   = discover_fuel_variable(metadata)
    prod_code  = discover_product_code(metadata)

    # Step 2: fetch last 13 months (12 for chart + 1 for change calculation)
    months  = _recent_months(13)
    history = fetch_prices(prod_code, fuel_var, months)

    if not history:
        print("ERROR: No fuel price data fetched.")
        sys.exit(1)

    # Step 3: build output
    current = history[-1]
    prev    = history[-2] if len(history) >= 2 else current
    change  = round(current["price_nok"] - prev["price_nok"], 2)

    # The chart uses the last 12 months (drop the oldest if we got 13)
    chart_history = history[-12:]

    output = {
        "meta": {
            "source":    "SSB StatBank table 09654 — Prices on engine fuel",
            "product":   "Unleaded petrol 95 oktan",
            "unit":      "NOK per litre (incl. taxes)",
            "frequency": "monthly",
            "updated":   datetime.utcnow().isoformat() + "Z",
            "months":    len(chart_history),
        },
        "current": {
            "price_nok":   current["price_nok"],
            "date":        current["date"],
            "change_week": change,   # month-over-month in this series
        },
        "history": chart_history,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Saved {len(chart_history)} months of fuel prices → {OUTPUT_FILE}")
    print(f"  Current: {current['price_nok']:.2f} NOK/L "
          f"({'+' if change >= 0 else ''}{change:.2f} vs prev month)")


if __name__ == "__main__":
    main()
