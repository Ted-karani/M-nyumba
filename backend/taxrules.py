# taxrules.py - the rules for the monthly rental income tax (no database in here, so it is easy to test)

# Import the tools we need
import calendar
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

# The rate KRA publishes for residential rent (a landlord can change it on the page if KRA changes it)
DEFAULT_RATE = 7.5
# The yearly rent between which this simple tax applies
ANNUAL_MIN = 288_000
ANNUAL_MAX = 15_000_000
# The day of the following month when the return and payment are due
DUE_DAY = 20
# The description our import gives to a balance carried over from a notebook
BROUGHT_FORWARD = "Balance brought forward"
# Words in a unit's type that tell us it is a commercial unit
COMMERCIAL_WORDS = ("shop", "office", "store", "stall", "warehouse", "godown", "kiosk", "commercial", "showroom", "hall")
# The kinds of money a payment can be split into
CATEGORIES = ("rent", "arrears", "deposit", "bills", "advance")
# What a month looks like: 2026-10
PERIOD = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


# Is this text a month like 2026-10?
def valid_period(text) -> bool:
    return bool(PERIOD.match(text or ""))


# The month a date falls in, like "2026-10"
def period_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


# Move a month forwards or backwards: shift_period("2026-01", -1) is "2025-12"
def shift_period(period: str, months: int) -> str:
    index = int(period[:4]) * 12 + (int(period[5:7]) - 1) + months
    return f"{index // 12}-{index % 12 + 1:02d}"


# The first and last day of a month
def month_bounds(period: str):
    year, month = int(period[:4]), int(period[5:7])
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


# The day the tax for a month is due: the 20th of the next month
def due_date_for(period: str) -> date:
    following = shift_period(period, 1)
    return date(int(following[:4]), int(following[5:7]), DUE_DAY)


# Which kind of money a charge is: rent, arrears (an old balance), deposit, or bills (water, wifi, electricity and so on)
def charge_category(charge_type: str, description) -> str:
    if charge_type == "rent":
        return "rent"
    if charge_type == "other" and (description or "").strip() == BROUGHT_FORWARD:
        return "arrears"
    if charge_type == "deposit":
        return "deposit"
    return "bills"


# Does the unit's type say it is a shop, an office or something else commercial?
def unit_is_commercial(unit_type) -> bool:
    text = (unit_type or "").lower()
    return any(word in text for word in COMMERCIAL_WORDS)


# Is a unit taxed as residential rent or left out as commercial? (the landlord can force a whole building either way)
def treatment_of(treatments: dict, property_id: int, unit_type) -> str:
    setting = (treatments or {}).get(str(property_id), "auto")
    if setting in ("residential", "commercial"):
        return setting
    return "commercial" if unit_is_commercial(unit_type) else "residential"


# Split every payment of ONE lease over what it paid for, oldest charge first.
# charges: [{id, due_date, amount, category}]   payments: [{id, paid_on, amount}]
# Gives back {payment id: {"rent": .., "arrears": .., "deposit": .., "bills": .., "advance": ..}}
def allocate(charges, payments) -> dict:
    ordered = sorted((charge for charge in charges if charge["amount"] > 0), key=lambda charge: (charge["due_date"], charge["id"]))
    remaining = [charge["amount"] for charge in ordered]
    position = 0
    result = {}
    for payment in sorted(payments, key=lambda item: (item["paid_on"], item["id"])):
        split = {name: 0 for name in CATEGORIES}
        left = payment["amount"]
        while left > 0 and position < len(ordered):
            take = min(left, remaining[position])
            split[ordered[position]["category"]] += take
            remaining[position] -= take
            left -= take
            if remaining[position] == 0:
                position += 1
        # Whatever is left paid nothing that was owed yet: it is money paid in advance
        split["advance"] += left
        result[payment["id"]] = split
    return result


# The tax on an amount, rounded to the nearest shilling
def tax_for(gross: int, rate_percent: float) -> int:
    amount = Decimal(gross) * Decimal(str(rate_percent)) / Decimal(100)
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# Where a year's rent puts a landlord: "below" the line, "in_band" (this tax applies), or "above" the line
def annual_status(total: int) -> str:
    if total < ANNUAL_MIN:
        return "below"
    if total > ANNUAL_MAX:
        return "above"
    return "in_band"