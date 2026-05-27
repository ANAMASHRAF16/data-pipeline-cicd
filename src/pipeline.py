"""Order enrichment pipeline.

Reads orders.csv -> validates each row -> enriches valid rows with
fx-converted USD amount + region tag -> writes enriched.json.

Designed to be small enough that the focus of this project stays on the
CI/CD automation around it, but real enough that there's something
meaningful for tests to validate.

Run locally:
    python -m src.pipeline data/orders.csv data/output/enriched.json
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.validators import validate_order

# Static FX rates — in production this would be a service call; for this
# pipeline a constant table keeps the code deterministic for tests.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012}

COUNTRY_TO_REGION = {
    "US": "AMER", "MX": "AMER", "BR": "AMER",
    "GB": "EMEA", "DE": "EMEA", "FR": "EMEA", "IN": "APAC",
    "JP": "APAC", "AU": "APAC",
}


def parse_row(row: dict) -> dict:
    """Normalise a CSV row into the order dict the validator expects."""
    try:
        amount = float(row["amount"]) if row.get("amount") not in (None, "") else None
    except ValueError:
        amount = row.get("amount")  # leave as-is so validator catches it
    return {
        "order_id": row.get("order_id", "").strip(),
        "user_id": row.get("user_id", "").strip(),
        "amount": amount,
        "currency": (row.get("currency") or "").strip().upper(),
        "country": (row.get("country") or "").strip().upper(),
    }


def enrich(order: dict) -> dict:
    """Add usd_amount and region. Returns a new dict (no mutation)."""
    usd_amount = round(order["amount"] * FX_TO_USD[order["currency"]], 2)
    region = COUNTRY_TO_REGION.get(order["country"], "UNKNOWN")
    return {**order, "usd_amount": usd_amount, "region": region}


def process(rows: Iterable[dict]) -> dict:
    """Drive the pipeline over an iterable of raw rows."""
    enriched = []
    failures = []

    for raw in rows:
        order = parse_row(raw)
        ok, error_code = validate_order(order)
        if not ok:
            failures.append({"order_id": order.get("order_id") or "?", "error_code": error_code})
            continue
        enriched.append(enrich(order))

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total": len(enriched) + len(failures),
        "enriched_count": len(enriched),
        "failed_count": len(failures),
        "enriched": enriched,
        "failures": failures,
    }


def main(input_path: str, output_path: str) -> dict:
    """Read CSV, run pipeline, write JSON. Returns the result dict."""
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        result = process(reader)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    Path(output_path).write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        f"Pipeline complete: enriched={result['enriched_count']}, "
        f"failed={result['failed_count']}, total={result['total']}"
    )
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m src.pipeline <input.csv> <output.json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
