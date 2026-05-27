"""Input validation for the orders pipeline.

Each validator returns (is_valid, error_code). The pipeline uses the error
code as the failure reason in logs and metrics — keeping it as a fixed enum
means downstream consumers (dashboards, alerts) can group failures by class
instead of by free-text exception message.
"""

from typing import Tuple

REQUIRED_FIELDS = ("order_id", "user_id", "amount", "currency")
ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "INR"}


def validate_order(order: dict) -> Tuple[bool, str]:
    """Return (True, "") if valid, else (False, error_code)."""
    for field in REQUIRED_FIELDS:
        if field not in order or order[field] in (None, ""):
            return False, f"missing_{field}"

    amount = order.get("amount")
    if not isinstance(amount, (int, float)):
        return False, "invalid_amount_type"
    if amount <= 0:
        return False, "non_positive_amount"

    if order["currency"] not in ALLOWED_CURRENCIES:
        return False, "unknown_currency"

    return True, ""
