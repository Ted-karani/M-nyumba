# Import the tools we need
import io
import json
from collections import defaultdict
from datetime import date

# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query, Response
# Import the tool for writing Excel files
from openpyxl import Workbook
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import taxrules
from dependencies import get_db, get_current_user
from ownership import chunks
from routers.dataexport import safe_cell
from routers.properties import require_owner
from tax_models import TaxFiling, TaxSettings

# Make a group of endpoints that all start with /tax
router = APIRouter(prefix="/tax", tags=["Rental income tax"])

# How a whole building can be treated
TREATMENTS = ("auto", "residential", "commercial")


# A month the landlord has filed
class FilingOut(BaseModel):
    period: str
    tax_due: int
    amount_paid: int
    paid_on: date
    reference: str | None
    note: str | None


# What we ask for when marking a month as filed
class FilingIn(BaseModel):
    amount_paid: int = Field(ge=0, le=100_000_000)
    paid_on: date
    reference: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=200)


# The landlord's tax settings
class SettingsOut(BaseModel):
    resident: bool
    rate_percent: float
    default_rate: float
    threshold_low: int
    threshold_high: int


# What we ask for when the settings change
class SettingsIn(BaseModel):
    resident: bool
    rate_percent: float = Field(gt=0, le=30)
    # How each building is treated: {"12": "commercial"}
    treatments: dict[str, str] = Field(default_factory=dict)


# One building in a month
class PropertyLine(BaseModel):
    property_id: int
    name: str
    # What the landlord chose for this building: "auto", "residential" or "commercial"
    setting: str
    residential_units: int
    commercial_units: int
    # Rent received that counts for the tax
    gross_rent: int
    # Money received that is left out, and why
    commercial_excluded: int
    other_excluded: int


# One month in full
class MonthSummary(BaseModel):
    period: str
    due_date: date
    # Days until it is due (negative once it is overdue)
    days_left: int
    # "filed", "due", "overdue", "upcoming" (the month is not over), "nil" (nothing received) or "not_applicable"
    state: str
    rate_percent: float
    resident: bool
    # The rent received that counts, and the tax on it
    gross_rent: int
    tax_due: int
    # What the gross rent is made of
    rent: int
    arrears: int
    advance: int
    # What was left out
    deposits: int
    bills: int
    commercial: int
    # For comparison: the rent that was billed that month
    rent_billed: int
    properties: list[PropertyLine]
    filing: FilingOut | None


# One month in the year strip
class YearMonth(BaseModel):
    period: str
    gross_rent: int
    tax_due: int
    state: str


# The last 12 months
class YearSummary(BaseModel):
    total: int
    status: str
    months: list[YearMonth]


# Everything the page needs
class TaxOverview(BaseModel):
    month: MonthSummary
    year: YearSummary
    settings: SettingsOut


# Read a landlord's settings (a landlord who never changed anything gets the usual ones)
def read_settings(db: Session, owner_id: int):
    row = db.query(TaxSettings).filter(TaxSettings.owner_id == owner_id).first()
    if row is None:
        return True, taxrules.DEFAULT_RATE, {}
    try:
        treatments = json.loads(row.property_treatments or "{}")
    except ValueError:
        treatments = {}
    return row.resident, row.rate_percent, treatments


# Go through every payment the landlord ever received, and split each one over what it paid for
def build_ledger(db: Session, owner_id: int, treatments: dict):
    found = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == owner_id)
        .all()
    )
    leases = {lease.id: (lease, unit, prop, tenant) for lease, unit, prop, tenant in found}
    charges = defaultdict(list)
    payments = defaultdict(list)
    for piece in chunks(list(leases)):
        for charge in db.query(models.Charge).filter(models.Charge.lease_id.in_(piece)).all():
            charges[charge.lease_id].append({
                "id": charge.id,
                "due_date": charge.due_date,
                "amount": charge.amount,
                "category": taxrules.charge_category(charge.charge_type, charge.description),
                "period": charge.period or taxrules.period_of(charge.due_date),
            })
        for payment in db.query(models.Payment).filter(models.Payment.lease_id.in_(piece)).all():
            payments[payment.lease_id].append({"id": payment.id, "paid_on": payment.paid_on, "amount": payment.amount})
    rows = []
    billed = defaultdict(int)
    for lease_id, (lease, unit, prop, tenant) in leases.items():
        treatment = taxrules.treatment_of(treatments, prop.id, unit.unit_type)
        split = taxrules.allocate(charges[lease_id], payments[lease_id])
        for payment in payments[lease_id]:
            rows.append({
                "property_id": prop.id,
                "unit_number": unit.unit_number,
                "tenant": tenant.full_name,
                "treatment": treatment,
                "paid_on": payment["paid_on"],
                "period": taxrules.period_of(payment["paid_on"]),
                "amount": payment["amount"],
                **split[payment["id"]],
            })
        if treatment == "residential":
            for charge in charges[lease_id]:
                if charge["category"] == "rent":
                    billed[charge["period"]] += charge["amount"]
    return rows, billed


# The rent that counts for the tax in one payment row
def counted(row) -> int:
    return 0 if row["treatment"] == "commercial" else row["rent"] + row["arrears"] + row["advance"]


# Where one month stands
def month_state(period: str, gross: int, filed: bool, today: date, resident: bool) -> str:
    if not resident:
        return "not_applicable"
    if filed:
        return "filed"
    if period >= taxrules.period_of(today):
        return "upcoming"
    if gross == 0:
        return "nil"
    return "overdue" if today > taxrules.due_date_for(period) else "due"


# Work out everything the page needs for one month
def make_overview(db: Session, owner_id: int, period: str) -> TaxOverview:
    resident, rate, treatments = read_settings(db, owner_id)
    rows, billed = build_ledger(db, owner_id, treatments)
    today = date.today()
    filings = {row.period: row for row in db.query(TaxFiling).filter(TaxFiling.owner_id == owner_id).all()}

    # This month's totals, by kind of money and by building
    totals = {"rent": 0, "arrears": 0, "advance": 0, "deposits": 0, "bills": 0, "commercial": 0}
    per_property = defaultdict(lambda: {"gross": 0, "commercial": 0, "other": 0})
    for row in rows:
        if row["period"] != period:
            continue
        line = per_property[row["property_id"]]
        if row["treatment"] == "commercial":
            totals["commercial"] += row["amount"]
            line["commercial"] += row["amount"]
            continue
        totals["rent"] += row["rent"]
        totals["arrears"] += row["arrears"]
        totals["advance"] += row["advance"]
        totals["deposits"] += row["deposit"]
        totals["bills"] += row["bills"]
        line["gross"] += row["rent"] + row["arrears"] + row["advance"]
        line["other"] += row["deposit"] + row["bills"]
    gross = totals["rent"] + totals["arrears"] + totals["advance"]
    tax = taxrules.tax_for(gross, rate) if resident else 0

    # The buildings
    properties = db.query(models.Property).filter(models.Property.owner_id == owner_id).order_by(models.Property.name).all()
    units = db.query(models.Unit).filter(models.Unit.property_id.in_([prop.id for prop in properties])).all() if properties else []
    lines = []
    for prop in properties:
        mine = [unit for unit in units if unit.property_id == prop.id]
        commercial_units = sum(1 for unit in mine if taxrules.treatment_of(treatments, prop.id, unit.unit_type) == "commercial")
        figures = per_property[prop.id]
        lines.append(PropertyLine(
            property_id=prop.id,
            name=prop.name,
            setting=treatments.get(str(prop.id), "auto"),
            residential_units=len(mine) - commercial_units,
            commercial_units=commercial_units,
            gross_rent=figures["gross"],
            commercial_excluded=figures["commercial"],
            other_excluded=figures["other"],
        ))

    filing = filings.get(period)
    due = taxrules.due_date_for(period)
    month = MonthSummary(
        period=period,
        due_date=due,
        days_left=(due - today).days,
        state=month_state(period, gross, filing is not None, today, resident),
        rate_percent=rate,
        resident=resident,
        gross_rent=gross,
        tax_due=tax,
        rent=totals["rent"],
        arrears=totals["arrears"],
        advance=totals["advance"],
        deposits=totals["deposits"],
        bills=totals["bills"],
        commercial=totals["commercial"],
        rent_billed=billed.get(period, 0),
        properties=lines,
        filing=FilingOut(period=filing.period, tax_due=filing.tax_due, amount_paid=filing.amount_paid, paid_on=filing.paid_on, reference=filing.reference, note=filing.note) if filing else None,
    )

    # The last 12 months, ending with this one
    months = []
    total = 0
    for step in range(11, -1, -1):
        label = taxrules.shift_period(period, -step)
        value = sum(counted(row) for row in rows if row["period"] == label)
        total += value
        months.append(YearMonth(
            period=label,
            gross_rent=value,
            tax_due=taxrules.tax_for(value, rate) if resident else 0,
            state=month_state(label, value, label in filings, today, resident),
        ))
    return TaxOverview(
        month=month,
        year=YearSummary(total=total, status=taxrules.annual_status(total), months=months),
        settings=SettingsOut(resident=resident, rate_percent=rate, default_rate=taxrules.DEFAULT_RATE, threshold_low=taxrules.ANNUAL_MIN, threshold_high=taxrules.ANNUAL_MAX),
    )


# The month to show when none is asked for: the last month that is over
def last_completed() -> str:
    return taxrules.shift_period(taxrules.period_of(date.today()), -1)


# Check a month typed in an address
def check_period(period: str) -> str:
    if not taxrules.valid_period(period):
        raise HTTPException(status_code=422, detail="Write the month like 2026-10")
    return period


# The whole page for one month
@router.get("/overview", response_model=TaxOverview)
def tax_overview(
    period: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    return make_overview(db, current_user.id, check_period(period or last_completed()))


# Change the settings (resident or not, the rate, and how each building is treated)
@router.put("/settings", response_model=SettingsOut)
def save_settings(
    data: SettingsIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    mine = {str(prop_id) for (prop_id,) in db.query(models.Property.id).filter(models.Property.owner_id == current_user.id).all()}
    clean = {}
    for key, value in data.treatments.items():
        if key not in mine:
            raise HTTPException(status_code=400, detail="One of the buildings was not found")
        if value not in TREATMENTS:
            raise HTTPException(status_code=400, detail="A building can be treated as auto, residential or commercial")
        if value != "auto":
            clean[key] = value
    row = db.query(TaxSettings).filter(TaxSettings.owner_id == current_user.id).first()
    if row is None:
        row = TaxSettings(owner_id=current_user.id)
        db.add(row)
    row.resident = data.resident
    row.rate_percent = data.rate_percent
    row.property_treatments = json.dumps(clean)
    db.commit()
    return SettingsOut(resident=row.resident, rate_percent=row.rate_percent, default_rate=taxrules.DEFAULT_RATE, threshold_low=taxrules.ANNUAL_MIN, threshold_high=taxrules.ANNUAL_MAX)


# Mark a month as filed and paid (or change the record)
@router.put("/filings/{period}", response_model=FilingOut)
def save_filing(
    period: str,
    data: FilingIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    check_period(period)
    today = date.today()
    # A month can only be filed once it is over
    if period >= taxrules.period_of(today):
        raise HTTPException(status_code=400, detail="That month is not over yet")
    if data.paid_on > today:
        raise HTTPException(status_code=400, detail="The payment date cannot be in the future")
    calculated = make_overview(db, current_user.id, period).month.tax_due
    row = db.query(TaxFiling).filter(TaxFiling.owner_id == current_user.id, TaxFiling.period == period).first()
    if row is None:
        row = TaxFiling(owner_id=current_user.id, period=period)
        db.add(row)
    row.tax_due = calculated
    row.amount_paid = data.amount_paid
    row.paid_on = data.paid_on
    row.reference = (data.reference or "").strip() or None
    row.note = (data.note or "").strip() or None
    db.commit()
    return FilingOut(period=row.period, tax_due=row.tax_due, amount_paid=row.amount_paid, paid_on=row.paid_on, reference=row.reference, note=row.note)


# Take back a "filed" mark
@router.delete("/filings/{period}", status_code=204)
def delete_filing(
    period: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    check_period(period)
    row = db.query(TaxFiling).filter(TaxFiling.owner_id == current_user.id, TaxFiling.period == period).first()
    if row is None:
        raise HTTPException(status_code=404, detail="That month was not marked as filed")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


# An Excel file for the landlord or their accountant: the summary, and the rent received unit by unit
@router.get("/export")
def export_schedule(
    period: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    period = check_period(period or last_completed())
    overview = make_overview(db, current_user.id, period)
    month = overview.month
    resident, rate, treatments = read_settings(db, current_user.id)
    rows, _ = build_ledger(db, current_user.id, treatments)
    names = {prop.id: prop.name for prop in db.query(models.Property).filter(models.Property.owner_id == current_user.id).all()}

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    first, _last = taxrules.month_bounds(period)
    for line in [
        ("EstateLoom: rental income tax schedule",),
        ("Month", first.strftime("%B %Y")),
        ("Rent received that counts (residential)", month.gross_rent),
        ("Tax rate (%)", rate),
        ("Tax", month.tax_due),
        ("Due date", month.due_date.isoformat()),
        ("Left out: deposits", month.deposits),
        ("Left out: bills", month.bills),
        ("Left out: commercial units", month.commercial),
        ("",),
        ("This is an estimate for convenience, not tax advice. Please confirm the rate and your figures with KRA or an accountant.",),
    ]:
        summary.append([safe_cell(item) if isinstance(item, str) else item for item in line])

    sheet = workbook.create_sheet("By unit")
    sheet.append(["Building", "Unit", "Tenant", "Treated as", "Rent received", "Old balances received", "Paid in advance", "Deposits (left out)", "Bills (left out)", "Commercial (left out)"])
    grouped = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for row in rows:
        if row["period"] != period:
            continue
        key = (names.get(row["property_id"], ""), row["unit_number"], row["tenant"], row["treatment"])
        figures = grouped[key]
        if row["treatment"] == "commercial":
            figures[5] += row["amount"]
        else:
            figures[0] += row["rent"]
            figures[1] += row["arrears"]
            figures[2] += row["advance"]
            figures[3] += row["deposit"]
            figures[4] += row["bills"]
    for (building, unit, tenant, treatment), figures in sorted(grouped.items()):
        sheet.append([safe_cell(building), safe_cell(unit), safe_cell(tenant), treatment, *figures])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="estateloom-rent-tax-{period}.xlsx"'},
    )