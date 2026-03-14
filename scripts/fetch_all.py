#!/usr/bin/env python3
"""
Master data fetch script — runs all three data sources in sequence.
Called daily by the GitHub Actions workflow.

Exit codes:
  0 — all sources succeeded
  1 — one or more sources failed (partial data may have been updated)
"""

import subprocess
import sys
import os
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

FETCHERS = [
    ("Electricity Prices",   SCRIPTS_DIR / "fetch_prices.py"),
    ("NOK/USD Exchange Rate", SCRIPTS_DIR / "fetch_exchange.py"),
    ("Reservoir Levels",     SCRIPTS_DIR / "fetch_reservoirs.py"),
    ("Petrol Prices (SSB)",  SCRIPTS_DIR / "fetch_fuel.py"),
]


def run(name: str, script: Path) -> bool:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, str(script)], capture_output=False)
    success = result.returncode == 0
    if not success:
        print(f"\n  ✗ {name} FAILED (exit code {result.returncode})")
    return success


def main():
    print("Norwegian Energy Market — Data Refresh")
    print(f"Running {len(FETCHERS)} data fetchers...\n")

    results = {}
    for name, script in FETCHERS:
        results[name] = run(name, script)

    print("\n" + "="*60)
    print("Summary:")
    all_ok = True
    for name, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {name}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\nAll data sources updated successfully.")
        sys.exit(0)
    else:
        print("\nWARNING: Some data sources failed. Check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
