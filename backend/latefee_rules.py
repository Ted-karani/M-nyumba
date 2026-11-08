# latefee_rules.py - the rules for late fees (no database in here, so it is easy to test)

# Import the tools we need
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# What a month looks like: 2026-10
PERIOD = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


# Is this text a month like 2026-10?
def valid_period(text) -> bool:
    return bool(PERIOD.match(text or ""))


# The month a date falls in, like "2026-10"
def period_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


# The last day the rent may be paid without a fee
def deadline_for(due_date: date, grace_days: int) -> date:
    return due_date + timedelta(days=grace_days)


# How much of one charge was still unpaid on a day.
# Payments are applied to the oldest charge first, and only payments made on or before that day count.
# charges: [{id, due_date, amount}]   payments: [{amount, paid_on}]
def unpaid_at(charges, payments, charge_id: int, as_of: date) -> int:
    ordered = sorted((charge for charge in charges if charge["amount"] > 0), key=lambda charge: (charge["due_date"], charge["id"]))
    money = sum(payment["amount"] for payment in payments if payment["paid_on"] <= as_of)
    for charge in ordered:
        take = min(money, charge["amount"])
        money -= take
        if charge["id"] == charge_id:
            return charge["amount"] - take
    return 0


# The fee: a flat amount, or a percentage of the month's rent (rounded to the nearest shilling)
def fee_for(kind: str, amount: float, rent: int) -> int:
    if kind == "percent":
        value = Decimal(rent) * Decimal(str(amount)) / Decimal(100)
    else:
        value = Decimal(str(amount))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))