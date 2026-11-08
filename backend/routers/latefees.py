# Import the tools we need
import calendar
from collections import defaultdict
from datetime import date, datetime
from typing import Literal

# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, model_validator
# Import the tool that catches "this already exists" errors
from sqlalchemy.exc import IntegrityError
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import latefee_rules as rules
import models
from dependencies import get_db, get_current_user
from latefee_models import LateFeeLog, LateFeeSettings
from ownership import chunks
from routers.properties import require_owner

# Make a group of endpoints that all start with /late-fees
router = APIRouter(prefix="/late-fees", tags=["Late fees"])
# The most fees one request may add
MAX_ITEMS = 300


# The late fee rule
class SettingsOut(BaseModel):
    enabled: bool
    grace_days: int
    kind: str
    amount: float
    start_period: str | None


# What we ask for when the rule changes
class SettingsIn(BaseModel):
    enabled: bool
    grace_days: int = Field(ge=0, le=30)
    kind: Literal["flat", "percent"]
    amount: float = Field(gt=0, le=1_000_000)
    start_period: str | None = None

    # Check the amount makes sense for the kind, and that the month is written correctly
    @model_validator(mode="after")
    def check(self):
        if self.kind == "percent" and self.amount > 50:
            raise ValueError("A percentage fee cannot be more than 50%")
        if self.kind == "flat" and self.amount < 1:
            raise ValueError("A flat fee must be at least 1 shilling")
        if self.start_period is not None and not rules.valid_period(self.start_period):
            raise ValueError("Write the month like 2026-11")
        return self


# A tenant who is late, and the fee that would be added
class Candidate(BaseModel):
    lease_id: int
    period: str
    tenant_name: str
    unit_number: str
    property_name: str
    rent_amount: int
    due_date: date
    deadline: date
    # What was still unpaid on the deadline day
    unpaid_at_deadline: int
    # What is still unpaid on this rent today (0 means it was paid, but late)
    still_owing: int
    fee: int


# The page: the rule, and who is late right now
class PreviewOut(BaseModel):
    settings: SettingsOut
    candidates: list[Candidate]
    total_fee: int


# One tenant's month, as named in a request
class ItemRef(BaseModel):
    lease_id: int
    period: str

    @model_validator(mode="after")
    def check(self):
        if not rules.valid_period(self.period):
            raise ValueError("Write the month like 2026-11")
        return self


# What we ask for when applying fees
class ApplyIn(BaseModel):
    items: list[ItemRef] = Field(min_length=1, max_length=MAX_ITEMS)


# What we send back after applying
class ApplyResult(BaseModel):
    applied: int
    skipped: int
    total: int


# What we send back after waiving
class WaiveResult(BaseModel):
    waived: bool
    fee: int


# One line of the history
class HistoryRow(BaseModel):
    lease_id: int
    period: str
    action: str
    amount: int
    created_at: datetime
    tenant_name: str
    unit_number: str
    property_name: str
    # True if a fee was added and can still be taken back
    can_waive: bool


# "October 2026"
def month_label(period: str) -> str:
    return f"{calendar.month_name[int(period[5:7])]} {period[:4]}"


# Read a landlord's rule (a landlord who never set one gets the usual values, switched off)
def read_settings(db: Session, owner_id: int) -> SettingsOut:
    row = db.query(LateFeeSettings).filter(LateFeeSettings.owner_id == owner_id).first()
    if row is None:
        return SettingsOut(enabled=False, grace_days=5, kind="flat", amount=500, start_period=None)
    return SettingsOut(enabled=row.enabled, grace_days=row.grace_days, kind=row.kind, amount=row.amount, start_period=row.start_period)


# Find every tenant who is late and has not been decided on yet (nothing is saved here)
def find_candidates(db: Session, owner_id: int, settings: SettingsOut, today: date) -> list[Candidate]:
    if not settings.enabled:
        return []
    found = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == owner_id, models.Lease.status == "active")
        .all()
    )
    charges = defaultdict(list)
    payments = defaultdict(list)
    for piece in chunks([lease.id for lease, _, _, _ in found]):
        for charge in db.query(models.Charge).filter(models.Charge.lease_id.in_(piece)).all():
            charges[charge.lease_id].append({"id": charge.id, "due_date": charge.due_date, "amount": charge.amount, "type": charge.charge_type, "period": charge.period})
        for payment in db.query(models.Payment).filter(models.Payment.lease_id.in_(piece)).all():
            payments[payment.lease_id].append({"amount": payment.amount, "paid_on": payment.paid_on})
    decided = {(lease_id, period) for lease_id, period in db.query(LateFeeLog.lease_id, LateFeeLog.period).filter(LateFeeLog.owner_id == owner_id).all()}
    result = []
    for lease, unit, prop, tenant in found:
        seen = set()
        for charge in sorted(charges[lease.id], key=lambda item: (item["due_date"], item["id"])):
            if charge["type"] != "rent":
                continue
            period = charge["period"] or rules.period_of(charge["due_date"])
            # Skip months before the start month, months already decided, and a second rent charge for the same month
            if (settings.start_period and period < settings.start_period) or (lease.id, period) in decided or period in seen:
                continue
            deadline = rules.deadline_for(charge["due_date"], settings.grace_days)
            if today <= deadline:
                continue
            unpaid = rules.unpaid_at(charges[lease.id], payments[lease.id], charge["id"], deadline)
            if unpaid <= 0:
                continue
            fee = rules.fee_for(settings.kind, settings.amount, charge["amount"])
            if fee <= 0:
                continue
            seen.add(period)
            result.append(Candidate(
                lease_id=lease.id,
                period=period,
                tenant_name=tenant.full_name,
                unit_number=unit.unit_number,
                property_name=prop.name,
                rent_amount=charge["amount"],
                due_date=charge["due_date"],
                deadline=deadline,
                unpaid_at_deadline=unpaid,
                still_owing=rules.unpaid_at(charges[lease.id], payments[lease.id], charge["id"], date.max),
                fee=fee,
            ))
    result.sort(key=lambda item: (item.property_name.lower(), item.unit_number.lower(), item.period))
    return result


# Show the rule, and who is late now
@router.get("/preview", response_model=PreviewOut)
def preview_fees(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    settings = read_settings(db, current_user.id)
    candidates = find_candidates(db, current_user.id, settings, date.today())
    return PreviewOut(settings=settings, candidates=candidates, total_fee=sum(item.fee for item in candidates))


# Change the rule
@router.put("/settings", response_model=SettingsOut)
def save_settings(
    data: SettingsIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    row = db.query(LateFeeSettings).filter(LateFeeSettings.owner_id == current_user.id).first()
    if row is None:
        row = LateFeeSettings(owner_id=current_user.id)
        db.add(row)
    # Switching on without a start month means "from this month on"
    start = data.start_period or row.start_period
    if data.enabled and start is None:
        start = rules.period_of(date.today())
    row.enabled = data.enabled
    row.grace_days = data.grace_days
    row.kind = data.kind
    row.amount = data.amount
    row.start_period = start
    db.commit()
    return read_settings(db, current_user.id)


# Add the fees the landlord ticked (the server works out again who is late and how much)
@router.post("/apply", response_model=ApplyResult)
def apply_fees(
    data: ApplyIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    settings = read_settings(db, current_user.id)
    if not settings.enabled:
        raise HTTPException(status_code=400, detail="Late fees are switched off")
    today = date.today()
    candidates = {(item.lease_id, item.period): item for item in find_candidates(db, current_user.id, settings, today)}
    applied = skipped = total = 0
    for key in sorted({(item.lease_id, item.period) for item in data.items}):
        candidate = candidates.get(key)
        # Someone who is not late (any more), or was already decided on, is skipped
        if candidate is None:
            skipped += 1
            continue
        charge = models.Charge(
            lease_id=candidate.lease_id,
            charge_type="other",
            amount=candidate.fee,
            period=candidate.period,
            due_date=today,
            description=f"Late fee: {month_label(candidate.period)} rent",
        )
        db.add(charge)
        db.flush()
        db.add(LateFeeLog(owner_id=current_user.id, lease_id=candidate.lease_id, period=candidate.period, action="applied", amount=candidate.fee, charge_id=charge.id))
        applied += 1
        total += candidate.fee
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Some of these fees were just handled. Please reload the page")
    return ApplyResult(applied=applied, skipped=skipped, total=total)


# Waive a fee: either before it was added (so it never will be), or take back one that was added
@router.post("/waive", response_model=WaiveResult)
def waive_fee(
    data: ItemRef,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    log = db.query(LateFeeLog).filter(LateFeeLog.owner_id == current_user.id, LateFeeLog.lease_id == data.lease_id, LateFeeLog.period == data.period).first()
    if log is not None:
        if log.action == "waived":
            raise HTTPException(status_code=400, detail="This fee was already waived")
        charge = db.get(models.Charge, log.charge_id) if log.charge_id else None
        log.action = "waived"
        log.charge_id = None
        db.flush()
        if charge is not None and charge.lease_id == log.lease_id:
            db.delete(charge)
        db.commit()
        return WaiveResult(waived=True, fee=log.amount)
    settings = read_settings(db, current_user.id)
    candidate = next((item for item in find_candidates(db, current_user.id, settings, date.today()) if item.lease_id == data.lease_id and item.period == data.period), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="That late fee was not found")
    db.add(LateFeeLog(owner_id=current_user.id, lease_id=candidate.lease_id, period=candidate.period, action="waived", amount=candidate.fee, charge_id=None))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This fee was just handled. Please reload the page")
    return WaiveResult(waived=True, fee=candidate.fee)


# The latest fees that were added or waived
@router.get("/history", response_model=list[HistoryRow])
def fee_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    rows = (
        db.query(LateFeeLog, models.Unit, models.Property, models.Tenant)
        .join(models.Lease, LateFeeLog.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(LateFeeLog.owner_id == current_user.id)
        .order_by(LateFeeLog.created_at.desc(), LateFeeLog.id.desc())
        .limit(50)
        .all()
    )
    charge_ids = {log.charge_id for log, _, _, _ in rows if log.charge_id}
    existing = {charge_id for (charge_id,) in db.query(models.Charge.id).filter(models.Charge.id.in_(charge_ids)).all()} if charge_ids else set()
    return [
        HistoryRow(
            lease_id=log.lease_id,
            period=log.period,
            action=log.action,
            amount=log.amount,
            created_at=log.created_at,
            tenant_name=tenant.full_name,
            unit_number=unit.unit_number,
            property_name=prop.name,
            can_waive=log.action == "applied" and log.charge_id in existing,
        )
        for log, unit, prop, tenant in rows
    ]