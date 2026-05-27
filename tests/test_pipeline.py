"""End-to-end tests for the orders pipeline.

These tests are the contract that CI enforces on every PR. If they pass
locally and pass in GitHub Actions, the deploy job is allowed to run.
"""

import json
from pathlib import Path

import pytest

from src.pipeline import enrich, main
from src.validators import validate_order

FIXTURES = Path(__file__).parent / "fixtures"


# ---------- validator unit tests ----------------------------------------------

def test_valid_order_passes():
    order = {"order_id": "X", "user_id": "U", "amount": 10.0, "currency": "USD"}
    ok, err = validate_order(order)
    assert ok and err == ""


@pytest.mark.parametrize("field", ["order_id", "user_id", "amount", "currency"])
def test_missing_required_field_fails(field):
    order = {"order_id": "X", "user_id": "U", "amount": 10.0, "currency": "USD"}
    order[field] = None
    ok, err = validate_order(order)
    assert not ok and err == f"missing_{field}"


def test_non_numeric_amount_fails():
    ok, err = validate_order({"order_id": "X", "user_id": "U", "amount": "abc", "currency": "USD"})
    assert not ok and err == "invalid_amount_type"


def test_negative_amount_fails():
    ok, err = validate_order({"order_id": "X", "user_id": "U", "amount": -1, "currency": "USD"})
    assert not ok and err == "non_positive_amount"


def test_unknown_currency_fails():
    ok, err = validate_order({"order_id": "X", "user_id": "U", "amount": 10, "currency": "JPY"})
    assert not ok and err == "unknown_currency"


# ---------- enrichment ---------------------------------------------------------

def test_enrich_adds_usd_amount_and_region():
    order = {"order_id": "X", "user_id": "U", "amount": 100.0, "currency": "EUR", "country": "DE"}
    out = enrich(order)
    assert out["usd_amount"] == 108.00
    assert out["region"] == "EMEA"


def test_enrich_unknown_country_yields_unknown_region():
    order = {"order_id": "X", "user_id": "U", "amount": 50.0, "currency": "USD", "country": "ZZ"}
    out = enrich(order)
    assert out["region"] == "UNKNOWN"


# ---------- end-to-end ---------------------------------------------------------

def test_full_pipeline_on_fixture_csv(tmp_path):
    out_path = tmp_path / "enriched.json"
    result = main(str(FIXTURES / "orders.csv"), str(out_path))

    # 10 input rows: ORD-001..ORD-005 + ORD-010 = 6 enriched; rest fail
    assert result["enriched_count"] == 6
    assert result["failed_count"] == 4

    # output file matches return value
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk["enriched_count"] == 6
    assert on_disk["failed_count"] == 4

    # every enriched row has all required derived fields
    for o in on_disk["enriched"]:
        assert "usd_amount" in o and "region" in o

    # failure error codes are from the fixed enum
    error_codes = {f["error_code"] for f in on_disk["failures"]}
    assert error_codes <= {"missing_user_id", "non_positive_amount", "invalid_amount_type", "unknown_currency"}
