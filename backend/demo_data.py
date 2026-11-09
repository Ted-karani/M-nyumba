# demo_data.py - builds (and removes) a believable demo landlord, for showing EstateLoom to other landlords
# Everything is made up, and every date is worked out from today, so the demo never looks stale.

# Import the tools we need
import calendar
import json
import secrets
import typing
from datetime import date, datetime, timedelta

# Import the tools for deleting and counting rows
from sqlalchemy import delete, func

# Import our own files
import legal_models
import models
import security
import taxrules
from admin_models import AdminEvent, OwnerAccount
from latefee_models import LateFeeSettings
from ownership import collect, erase, member_user_ids, stored_files
from portal_models import Notice
from routers import documents
from routers.expenses import Expense
from routers.listings import Listing
from routers.tasks import Task
from security_models import LoginAttempt
from settlement_models import DepositSettlement
from tax_models import TaxFiling

# The demo landlord signs in with this email (nobody else is ever touched)
DEMO_EMAIL = "demo.landlord@example.com"
# This note on the account marks it as a demo
DEMO_NOTE = "DEMO ACCOUNT: made-up data for presentations"

# Names to build tenants from
FIRST = [
    "Grace", "John", "Mercy", "Peter", "Faith", "Samuel", "Lucy", "James", "Esther", "David",
    "Ann", "Joseph", "Rose", "Daniel", "Mary", "Brian", "Purity", "Kevin", "Janet", "Moses",
    "Winnie", "Dennis", "Lilian", "Collins", "Beatrice", "Martin", "Caroline", "Felix", "Naomi", "Victor",
    "Joyce", "Eric", "Susan", "Paul", "Margaret", "Isaac", "Agnes", "Antony", "Eunice", "Stephen",
]
LAST = [
    "Mwangi", "Kamau", "Njeri", "Otieno", "Wanjiru", "Kiprop", "Mutua", "Muriuki", "Achieng", "Kariuki",
    "Wafula", "Chebet", "Maina", "Nyambura", "Mbugua", "Kimani", "Atieno", "Gitonga", "Kinyua", "Mutwiri",
    "Kiplagat", "Omondi", "Wambui", "Karanja", "Mugambi", "Kithinji", "Murithi", "Nduta", "Cheruiyot", "Wekesa",
]
# How tenants behave: most pay on time, some pay late, one in ten falls behind
PROFILES = ["on_time"] * 7 + ["late", "late", "problem"]


# Units of the three buildings: (unit number, kind, monthly rent)
def kinoru_units():
    units = [(f"A{n}", "Bedsitter", 6000) for n in range(1, 17)]
    units += [(f"B{n}", "1 Bedroom", 12000) for n in range(1, 9)]
    return units


def mwalimu_units():
    units = []
    for floor in (1, 2, 3):
        for letter in "ABCDEFGH":
            small = letter in "ABCD"
            units.append((f"{floor}{letter}", "1 Bedroom" if small else "2 Bedroom", 15000 if small else 25000))
    return units


def githongo_units():
    units = [(f"G{n}", "Single room", 5500) for n in range(1, 9)]
    units += [(f"S{n}", "Shop", 18000) for n in range(1, 5)]
    return units


BUILDINGS = [
    {"name": "Kinoru Court", "county": "Meru", "town": "Makutano", "address": "Behind the main stage, Makutano", "units": kinoru_units(), "vacant": {"A15", "A16", "B8"}, "maintenance": set()},
    {"name": "Mwalimu Heights", "county": "Nairobi", "town": "Kahawa Sukari", "address": "Off Kamiti Road, Kahawa Sukari", "units": mwalimu_units(), "vacant": {"2H", "3G"}, "maintenance": {"3H"}},
    {"name": "Githongo Plaza", "county": "Meru", "town": "Githongo", "address": "Next to the market, Githongo", "units": githongo_units(), "vacant": {"G8", "S4"}, "maintenance": set()},
]


# A made-up name and a made-up phone number for tenant number "index"
def person(index: int) -> str:
    return f"{FIRST[index % len(FIRST)]} {LAST[(index * 7 + index // len(FIRST)) % len(LAST)]}"


def phone(index: int) -> str:
    return f"254700{index:06d}"


# A day of a month like "2026-10", kept inside that month
def day_in(period: str, day: int) -> date:
    year, month = int(period[:4]), int(period[5:7])
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


# "October rent"
def rent_text(period: str) -> str:
    return f"{calendar.month_name[int(period[5:7])]} rent"


# A moment on a day, as a date and time
def at(day: date, hour: int = 9) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)


# Work out one tenant's charges and payments over the last four months
def plan_for(index: int, rent: int, today: date, periods: list, is_new: bool):
    profile = "advance" if index == 3 else PROFILES[index % 10]
    charges = []
    payments = []
    if is_new:
        # A new tenant: moved in 1 to 3 months ago, with a deposit
        first = 3 - (1 + index % 3)
        start_date = day_in(periods[first], 1 + (index * 5) % 27)
        charges.append({"type": "deposit", "amount": rent, "period": None, "due": start_date, "description": "Deposit"})
        payments.append({"amount": rent, "paid_on": start_date})
        months = periods[first:]
    else:
        # An existing tenant, brought in from a notebook, with no deposit charge on record
        start_date = date(today.year, today.month, 1) - timedelta(days=30 * (4 + index % 20))
        months = periods
    for period in months:
        first_month = is_new and period == months[0]
        due = start_date if first_month else day_in(period, 5)
        charges.append({"type": "rent", "amount": rent, "period": period, "due": due, "description": rent_text(period)})
        amount = rent
        if first_month:
            planned = start_date
        elif profile == "late":
            planned = day_in(period, 12 + index % 5)
        elif profile == "problem" and period == periods[2]:
            planned = day_in(period, 9)
            amount = rent // 2
        elif profile == "problem" and period == periods[3]:
            planned = None
        else:
            planned = day_in(period, max(1, 5 - index % 4))
        if profile == "advance" and period == periods[3]:
            planned = day_in(period, 2)
            amount = rent * 2
        # Nothing is paid in the future, or before the tenant moved in
        if planned is None or planned > today or planned < start_date:
            continue
        payments.append({"amount": amount, "paid_on": planned})
    return start_date, charges, payments


# The categories the expenses page allows (read from the app itself, so we never invent one)
def expense_categories() -> list:
    try:
        from routers import expenses

        for value in vars(expenses).values():
            fields = getattr(value, "model_fields", None)
            if fields and "category" in fields and "spent_on" in fields:
                options = typing.get_args(fields["category"].annotation)
                if options and all(isinstance(item, str) for item in options):
                    return list(options)
    except Exception:
        pass
    return []


CATEGORY_WORDS = {
    "caretaker": ("caretaker", "salar", "wage", "staff"),
    "security": ("security", "guard"),
    "repairs": ("repair", "maint"),
    "cleaning": ("clean", "suppl"),
    "taxes": ("tax", "rate", "levy", "permit"),
}


# Choose the allowed category that fits best
def pick_category(available: list, kind: str) -> str:
    for word in CATEGORY_WORDS.get(kind, ()):
        for name in available:
            if word in name.lower():
                return name
    for name in available:
        if "other" in name.lower():
            return name
    return available[0] if available else "other"


# Find the demo landlord, and whether it really is a demo account
def find_demo(db):
    owner = db.query(models.User).filter(models.User.email == DEMO_EMAIL).first()
    if owner is None:
        return None, False
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner.id).first()
    return owner, owner.role == "owner" and account is not None and (account.notes or "").startswith("DEMO ACCOUNT")


# How much is in the demo
def demo_counts(db, owner_id: int) -> dict:
    units = db.query(models.Unit).join(models.Property, models.Unit.property_id == models.Property.id).filter(models.Property.owner_id == owner_id)
    payments = (
        db.query(func.count(models.Payment.id))
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == owner_id)
        .scalar()
    )
    return {
        "properties": db.query(func.count(models.Property.id)).filter(models.Property.owner_id == owner_id).scalar(),
        "units": units.count(),
        "occupied_units": units.filter(models.Unit.status == "occupied").count(),
        "tenants": db.query(func.count(models.Tenant.id)).filter(models.Tenant.owner_id == owner_id).scalar(),
        "payments": payments,
        "repairs": db.query(func.count(models.MaintenanceRequest.id)).join(models.Property, models.MaintenanceRequest.property_id == models.Property.id).filter(models.Property.owner_id == owner_id).scalar(),
        "listings": db.query(func.count(Listing.id)).filter(Listing.owner_id == owner_id).scalar(),
    }


# Build the demo landlord and everything in it (nothing is saved until the very end)
def build_demo(db, today=None) -> dict:
    today = today or date.today()
    periods = [taxrules.shift_period(taxrules.period_of(today), step) for step in (-3, -2, -1, 0)]
    password = f"Demo-{secrets.token_hex(3)}-{secrets.token_hex(3)}"

    # The landlord, their plan (paid for a year, so it never turns read-only), and their acceptance of the terms
    owner = models.User(full_name="Demo Landlord", email=DEMO_EMAIL, phone=None, password_hash=security.hash_password(password), role="owner", is_active=True)
    db.add(owner)
    db.flush()
    db.add(OwnerAccount(owner_id=owner.id, plan="paid", status="active", paid_until=today + timedelta(days=365), unit_limit=None, notes=DEMO_NOTE, must_change_password=False))
    db.add(legal_models.TermsAcceptance(user_id=owner.id, terms_version=legal_models.TERMS_VERSION, privacy_version=legal_models.PRIVACY_VERSION))

    # The buildings and their units
    properties = []
    records = []
    for b, spec in enumerate(BUILDINGS):
        prop = models.Property(owner_id=owner.id, name=spec["name"], county=spec["county"], town=spec["town"], address=spec["address"])
        db.add(prop)
        db.flush()
        properties.append(prop)
        for number, kind, rent in spec["units"]:
            status = "maintenance" if number in spec["maintenance"] else "vacant" if number in spec["vacant"] else "occupied"
            unit = models.Unit(property_id=prop.id, unit_number=number, unit_type=kind, rent_amount=rent, deposit_amount=rent, status=status)
            db.add(unit)
            records.append((b, unit, rent, status))
    db.flush()
    unit_by_key = {(b, unit.unit_number): unit for b, unit, _, _ in records}

    # The tenants who live there, with four months of rent history
    counter = 0
    index = 0
    for b, unit, rent, status in records:
        if status != "occupied":
            continue
        tenant = models.Tenant(owner_id=owner.id, full_name=person(index), phone=phone(index))
        db.add(tenant)
        db.flush()
        start_date, charges, payments = plan_for(index, rent, today, periods, is_new=index % 7 == 3)
        lease = models.Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=start_date, rent_amount=rent, deposit_amount=rent, status="active")
        db.add(lease)
        db.flush()
        for item in charges:
            db.add(models.Charge(lease_id=lease.id, charge_type=item["type"], amount=item["amount"], period=item["period"], due_date=item["due"], description=item["description"]))
        for item in payments:
            counter += 1
            choice = (index + counter) % 20
            method = "mpesa" if choice < 16 else "cash" if choice < 19 else "bank"
            db.add(models.Payment(lease_id=lease.id, amount=item["amount"], paid_on=item["paid_on"], method=method, reference=f"DEMO-{counter:06d}" if method == "mpesa" else None, recorded_by_id=owner.id))
        index += 1

    # A tenant who moved out of A16 in the middle of last month, with a draft deposit settlement
    gone = models.Tenant(owner_id=owner.id, full_name=person(index), phone=phone(index))
    db.add(gone)
    db.flush()
    lease = models.Lease(unit_id=unit_by_key[(0, "A16")].id, tenant_id=gone.id, start_date=today - timedelta(days=240), end_date=day_in(periods[2], 15), rent_amount=6000, deposit_amount=6000, status="ended")
    db.add(lease)
    db.flush()
    for period in periods[:3]:
        db.add(models.Charge(lease_id=lease.id, charge_type="rent", amount=6000, period=period, due_date=day_in(period, 5), description=rent_text(period)))
        counter += 1
        db.add(models.Payment(lease_id=lease.id, amount=6000, paid_on=day_in(period, 3), method="mpesa", reference=f"DEMO-{counter:06d}", recorded_by_id=owner.id))
    db.add(DepositSettlement(
        owner_id=owner.id, lease_id=lease.id, status="draft", deposit_held=6000, unpaid_charges=0, credit=0,
        deductions=json.dumps([{"label": "Repainting", "amount": 1500}]), total_deductions=1500, refund_due=4500, tenant_owes=0, notes="Keys returned",
    ))

    # Repairs: (building, unit or None for the whole building, title, description, priority, status, cost, contractor, days since reported, days since fixed)
    repairs = [
        (0, "A3", "Leaking kitchen tap", "Drips all day and night", "normal", "fixed", 800, "Mutua Plumbers", 40, 36),
        (0, "B2", "Broken window latch", None, "low", "open", None, None, 6, None),
        (0, None, "Gate padlock keeps jamming", "Tenants wait outside in the evening", "normal", "in_progress", None, "Kinyua Welding", 9, None),
        (1, None, "Gate motor does not close fully", "It stops halfway", "urgent", "open", None, None, 2, None),
        (1, "2C", "No hot water in the shower", None, "normal", "in_progress", None, "Kamau Electricals", 5, None),
        (1, "1B", "Cracked bathroom tile", None, "low", "fixed", 3500, "Otieno Tiles", 55, 50),
        (2, "G4", "Door lock replaced", "Old lock was broken in", "normal", "fixed", 1200, "Mwenda Locks", 25, 24),
        (2, "S2", "Roof leaks above the shop", "Water drips on the shelves when it rains", "urgent", "open", None, None, 3, None),
    ]
    for b, number, title, description, priority, status, cost, contractor, created, fixed in repairs:
        db.add(models.MaintenanceRequest(
            property_id=properties[b].id, unit_id=unit_by_key[(b, number)].id if number else None, title=title, description=description, priority=priority,
            status=status, cost=cost, contractor_name=contractor, created_by_id=owner.id, created_at=at(today - timedelta(days=created)),
            resolved_on=today - timedelta(days=fixed) if fixed is not None else None,
        ))

    # Expenses: monthly pay for caretakers, security, the repairs above, supplies and yearly land rates
    available = expense_categories()
    spent = []
    for period in periods:
        day = day_in(period, 28)
        for b, (who, pay) in enumerate([("Peter Mwenda", 8000), ("Anne Wairimu", 9000), ("Joseph Kiprop", 7000)]):
            spent.append(("caretaker", b, pay, day, who, f"Caretaker pay for {rent_text(period)[:-5]}"))
        spent.append(("security", 1, 15000, day, "Mlinzi Security", "Night guards"))
    for b, number, title, _d, _p, status, cost, contractor, _c, fixed in repairs:
        if status == "fixed":
            spent.append(("repairs", b, cost, today - timedelta(days=fixed), contractor, title))
    for period, amount in zip(periods[:3], (1800, 2200, 1500)):
        spent.append(("cleaning", None, amount, day_in(period, 12), "Shop-Rite Supplies", "Cleaning supplies"))
    spent.append(("taxes", None, 24000, day_in(periods[0], 15), "Meru County", "Land rates for the year"))
    for kind, b, amount, day, who, note in spent:
        if day <= today:
            db.add(Expense(owner_id=owner.id, property_id=properties[b].id if b is not None else None, category=pick_category(available, kind), amount=amount, spent_on=day, description=note, paid_to=who, created_by_id=owner.id))

    # Notices
    db.add(Notice(owner_id=owner.id, property_id=None, title="Rent is due on the 5th", body="Please pay your rent by the 5th of every month. Thank you.", pinned=True, expires_on=None))
    db.add(Notice(owner_id=owner.id, property_id=properties[0].id, title="Water off on Tuesday", body="The water will be off from 9am to 2pm while the tank is cleaned.", pinned=False, expires_on=today + timedelta(days=7)))
    db.add(Notice(owner_id=owner.id, property_id=properties[1].id, title="New gate motor coming", body="We are replacing the gate motor this week. Use the side entrance meanwhile.", pinned=False, expires_on=today + timedelta(days=10)))

    # Tasks: the monthly tax return (next 20th), a yearly permit, a quarterly job, and one that is overdue
    next_twentieth = date(today.year, today.month, 20) if today.day <= 20 else day_in(taxrules.shift_period(taxrules.period_of(today), 1), 20)
    db.add(Task(owner_id=owner.id, property_id=None, title="File the monthly rental income tax", notes="Due by the 20th", due_date=next_twentieth, repeat="monthly", last_done_on=day_in(taxrules.shift_period(taxrules.period_of(next_twentieth), -1), 20) if day_in(taxrules.shift_period(taxrules.period_of(next_twentieth), -1), 20) <= today else None, is_done=False))
    db.add(Task(owner_id=owner.id, property_id=None, title="Renew the business permit", notes=None, due_date=today + timedelta(days=45), repeat="yearly", last_done_on=None, is_done=False))
    db.add(Task(owner_id=owner.id, property_id=properties[1].id, title="Service the water pump", notes=None, due_date=today + timedelta(days=12), repeat="quarterly", last_done_on=None, is_done=False))
    db.add(Task(owner_id=owner.id, property_id=properties[0].id, title="Check the fire extinguishers", notes=None, due_date=today - timedelta(days=3), repeat="yearly", last_done_on=None, is_done=False))

    # Listings for four empty units (the public link works, but there are no photos)
    for b, number, views in [(0, "A15", 12), (0, "B8", 7), (1, "2H", 31), (2, "G8", 4)]:
        unit = unit_by_key[(b, number)]
        spec = BUILDINGS[b]
        db.add(Listing(
            owner_id=owner.id, unit_id=unit.id, token=secrets.token_urlsafe(16), title=f"{unit.unit_type} for rent in {spec['town']}",
            description=f"A clean, quiet {unit.unit_type.lower()} in {spec['name']}, close to the road and the shops. Water is always available.",
            available_from=today + timedelta(days=5), contact_name="Demo Landlord", contact_phone="0700 000 000", show_exact_address=False, is_active=True, views=views,
        ))

    # Late fees are switched on from last month, so the page has people to show
    db.add(LateFeeSettings(owner_id=owner.id, enabled=True, grace_days=5, kind="flat", amount=500, start_period=periods[2]))
    db.flush()

    # The tax for two months ago is already filed (so the year chart has a green bar)
    from routers.tax import make_overview

    filed = periods[1]
    tax = make_overview(db, owner.id, filed).month.tax_due
    db.add(TaxFiling(owner_id=owner.id, period=filed, tax_due=tax, amount_paid=tax, paid_on=min(taxrules.due_date_for(filed), today), reference=f"DEMO-KRA-{filed}", note="Demo"))

    db.commit()
    return {"owner": owner, "password": password, "counts": demo_counts(db, owner.id)}


# Remove the demo landlord and everything of theirs (the caller has already checked that it is a demo)
def wipe_demo(db, owner) -> None:
    owner_id = owner.id
    marked = collect(db, owner_id)
    files = stored_files(db, marked)
    members = member_user_ids(db, owner_id)
    emails = [owner.email]
    if members:
        emails += [email for (email,) in db.query(models.User.email).filter(models.User.id.in_(members)).all()]
    try:
        erase(db, marked)
        db.execute(delete(LoginAttempt).where(LoginAttempt.email.in_(emails)))
        # Keep the admin's log, but without the link to a landlord who no longer exists
        db.query(AdminEvent).filter(AdminEvent.owner_id == owner_id).update({"owner_id": None})
        db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).delete()
        db.flush()
        db.execute(delete(models.User).where(models.User.id == owner_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    for _table, _row_id, stored, _original in files:
        (documents.UPLOAD_DIR / stored).unlink(missing_ok=True)