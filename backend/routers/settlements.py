# Import the tools we need
import json
from datetime import date, datetime
from typing import Literal

# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, field_validator
# Import the tool that catches "this already exists" errors
from sqlalchemy.exc import IntegrityError
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import settlement_rules as rules
from dependencies import get_db, get_current_user
from routers.properties import require_owner
from settlement_models import DepositSettlement

# Make a group of endpoints that all start with /settlements
router = APIRouter(prefix="/settlements", tags=["Move-out settlements"])
# The biggest amount we accept
MAX_AMOUNT = 100_000_000


# One deduction, like "Repainting: 1500"
class Deduction(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    amount: int = Field(gt=0, le=MAX_AMOUNT)

    # Take away spaces around the label, and refuse one that is only spaces
    @field_validator("label")
    @classmethod
    def label_is_clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Write what the deduction is for")
        return value


# What we ask for when a settlement is saved or finalised
class SettlementIn(BaseModel):
    deposit_held: int = Field(ge=0, le=MAX_AMOUNT)
    deductions: list[Deduction] = Field(default_factory=list, max_length=rules.MAX_DEDUCTIONS)
    notes: str | None = Field(default=None, max_length=300)


# What we ask for when the refund is paid
class RefundIn(BaseModel):
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    paid_on: date
    method: Literal["mpesa", "cash", "bank"]
    reference: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=200)


# The refund that was paid
class RefundOut(BaseModel):
    amount: int
    method: str
    reference: str | None
    paid_on: date
    note: str | None


# A settlement
class SettlementOut(BaseModel):
    status: str
    deposit_held: int
    unpaid_charges: int
    credit: int
    deductions: list[Deduction]
    total_deductions: int
    refund_due: int
    tenant_owes: int
    notes: str | None
    refund: RefundOut | None
    finalized_at: datetime | None


# The tenancy, for the top of the page
class LeaseInfo(BaseModel):
    lease_id: int
    tenant_name: str
    unit_number: str
    property_name: str
    start_date: date
    end_date: date | None
    rent_amount: int
    agreed_deposit: int


# What the ledger says today (the starting point for a settlement)
class Suggested(BaseModel):
    deposit_held: int
    found_from: str
    deposit_charged: int
    unpaid_charges: int
    credit: int


# Everything the settlement page needs
class Detail(BaseModel):
    lease: LeaseInfo
    suggested: Suggested
    settlement: SettlementOut | None
    state: str


# One line of the list of tenants who moved out
class ListRow(BaseModel):
    lease_id: int
    tenant_name: str
    unit_number: str
    property_name: str
    ended_on: date | None
    agreed_deposit: int
    state: str
    refund_due: int
    tenant_owes: int


# Find a tenancy, but only if it belongs to this landlord
def find_lease(db: Session, owner_id: int, lease_id: int):
    found = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Lease.id == lease_id, models.Property.owner_id == owner_id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if found is None:
        raise HTTPException(status_code=404, detail="Tenancy not found")
    return found


# A settlement is made when the tenant has moved out
def ensure_ended(lease: models.Lease):
    if lease.status != "ended":
        raise HTTPException(status_code=400, detail="End the tenancy first. A settlement is made when the tenant has moved out")


# What the ledger says for this tenancy
def ledger_figures(db: Session, lease: models.Lease) -> dict:
    charges = [
        {"id": row.id, "due_date": row.due_date, "amount": row.amount, "charge_type": row.charge_type, "description": row.description}
        for row in db.query(models.Charge).filter(models.Charge.lease_id == lease.id).all()
    ]
    payments = [{"id": row.id, "paid_on": row.paid_on, "amount": row.amount} for row in db.query(models.Payment).filter(models.Payment.lease_id == lease.id).all()]
    return rules.figures(charges, payments, lease.deposit_amount)


# Where a settlement stands
def state_of(row) -> str:
    if row is None:
        return "to_settle"
    if row.status == "draft":
        return "draft"
    if row.tenant_owes > 0:
        return "tenant_owes"
    if row.refund_due == 0:
        return "nothing_to_refund"
    if row.refund_amount is None:
        return "refund_pending"
    return "refunded" if row.refund_amount >= row.refund_due else "part_refunded"


# Turn a row into the shape we send back
def to_out(row: DepositSettlement) -> SettlementOut:
    try:
        deductions = [Deduction(**item) for item in json.loads(row.deductions or "[]")]
    except (ValueError, TypeError):
        deductions = []
    refund = None
    if row.refund_amount is not None:
        refund = RefundOut(amount=row.refund_amount, method=row.refund_method or "cash", reference=row.refund_reference, paid_on=row.refunded_on, note=row.refund_note)
    return SettlementOut(
        status=row.status,
        deposit_held=row.deposit_held,
        unpaid_charges=row.unpaid_charges,
        credit=row.credit,
        deductions=deductions,
        total_deductions=row.total_deductions,
        refund_due=row.refund_due,
        tenant_owes=row.tenant_owes,
        notes=row.notes,
        refund=refund,
        finalized_at=row.finalized_at,
    )


# Build everything the page needs for one tenancy
def build_detail(db: Session, owner_id: int, lease_id: int) -> Detail:
    lease, unit, prop, tenant = find_lease(db, owner_id, lease_id)
    ensure_ended(lease)
    row = db.query(DepositSettlement).filter(DepositSettlement.lease_id == lease.id).first()
    found = ledger_figures(db, lease)
    return Detail(
        lease=LeaseInfo(lease_id=lease.id, tenant_name=tenant.full_name, unit_number=unit.unit_number, property_name=prop.name, start_date=lease.start_date, end_date=lease.end_date, rent_amount=lease.rent_amount, agreed_deposit=lease.deposit_amount),
        suggested=Suggested(deposit_held=found["deposit_held"], found_from=found["deposit_found_from"], deposit_charged=found["deposit_charged"], unpaid_charges=found["unpaid_charges"], credit=found["credit"]),
        settlement=to_out(row) if row else None,
        state=state_of(row),
    )


# Write the figures into a settlement (the unpaid charges and credit are read fresh from the ledger)
def fill(db: Session, row: DepositSettlement, lease: models.Lease, data: SettlementIn):
    found = ledger_figures(db, lease)
    deductions = [{"label": item.label, "amount": item.amount} for item in data.deductions]
    result = rules.outcome(data.deposit_held, found["credit"], found["unpaid_charges"], deductions)
    row.deposit_held = data.deposit_held
    row.unpaid_charges = found["unpaid_charges"]
    row.credit = found["credit"]
    row.deductions = json.dumps(deductions)
    row.total_deductions = result["total_deductions"]
    row.refund_due = result["refund_due"]
    row.tenant_owes = result["tenant_owes"]
    row.notes = (data.notes or "").strip() or None


# Save (or change) a settlement, as a draft or as final
def save(db: Session, owner: models.User, lease_id: int, data: SettlementIn, final: bool) -> Detail:
    lease, unit, prop, tenant = find_lease(db, owner.id, lease_id)
    ensure_ended(lease)
    row = db.query(DepositSettlement).filter(DepositSettlement.lease_id == lease.id).first()
    if row is not None and row.status == "final":
        raise HTTPException(status_code=400, detail="This settlement is final. Reopen it to change it")
    if row is None:
        row = DepositSettlement(owner_id=owner.id, lease_id=lease.id)
        db.add(row)
    fill(db, row, lease, data)
    row.status = "final" if final else "draft"
    row.finalized_at = datetime.utcnow() if final else None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This settlement was just saved somewhere else. Please reload the page")
    return build_detail(db, owner.id, lease_id)


# The tenants who moved out, with where each settlement stands
@router.get("", response_model=list[ListRow])
def list_settlements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    found = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == current_user.id, models.Lease.status == "ended")
        .order_by(models.Lease.id.desc())
        .limit(300)
        .all()
    )
    settled = {row.lease_id: row for row in db.query(DepositSettlement).filter(DepositSettlement.owner_id == current_user.id).all()}
    rows = []
    for lease, unit, prop, tenant in found:
        row = settled.get(lease.id)
        rows.append(ListRow(
            lease_id=lease.id,
            tenant_name=tenant.full_name,
            unit_number=unit.unit_number,
            property_name=prop.name,
            ended_on=lease.end_date,
            agreed_deposit=lease.deposit_amount,
            state=state_of(row),
            refund_due=row.refund_due if row else 0,
            tenant_owes=row.tenant_owes if row else 0,
        ))
    # The ones that need something done come first
    order = {"refund_pending": 0, "to_settle": 1, "draft": 2, "tenant_owes": 3, "part_refunded": 4, "refunded": 5, "nothing_to_refund": 6}
    rows.sort(key=lambda item: order[item.state])
    return rows


# One tenancy: the ledger figures, and the settlement if there is one
@router.get("/lease/{lease_id}", response_model=Detail)
def settlement_detail(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    return build_detail(db, current_user.id, lease_id)


# Save a draft
@router.put("/lease/{lease_id}", response_model=Detail)
def save_draft(
    lease_id: int,
    data: SettlementIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    return save(db, current_user, lease_id, data, final=False)


# Finalise: the numbers are frozen
@router.post("/lease/{lease_id}/finalize", response_model=Detail)
def finalize(
    lease_id: int,
    data: SettlementIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    return save(db, current_user, lease_id, data, final=True)


# Open a final settlement again (only while no refund has been recorded)
@router.post("/lease/{lease_id}/reopen", response_model=Detail)
def reopen(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    lease, unit, prop, tenant = find_lease(db, current_user.id, lease_id)
    row = db.query(DepositSettlement).filter(DepositSettlement.lease_id == lease.id).first()
    if row is None or row.status != "final":
        raise HTTPException(status_code=400, detail="This settlement is not final")
    if row.refund_amount is not None:
        raise HTTPException(status_code=400, detail="A refund was recorded. Remove the refund record first")
    row.status = "draft"
    row.finalized_at = None
    db.commit()
    return build_detail(db, current_user.id, lease_id)


# Record that the refund was paid
@router.post("/lease/{lease_id}/refund", response_model=Detail)
def record_refund(
    lease_id: int,
    data: RefundIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    lease, unit, prop, tenant = find_lease(db, current_user.id, lease_id)
    row = db.query(DepositSettlement).filter(DepositSettlement.lease_id == lease.id).first()
    if row is None or row.status != "final":
        raise HTTPException(status_code=400, detail="Finalise the settlement first")
    if row.refund_due <= 0:
        raise HTTPException(status_code=400, detail="There is nothing to refund on this settlement")
    if row.refund_amount is not None:
        raise HTTPException(status_code=400, detail="A refund was already recorded. Remove it first to change it")
    if data.amount > row.refund_due:
        raise HTTPException(status_code=400, detail=f"The refund cannot be more than KSh {row.refund_due:,}")
    if data.paid_on > date.today():
        raise HTTPException(status_code=400, detail="The payment date cannot be in the future")
    row.refund_amount = data.amount
    row.refund_method = data.method
    row.refund_reference = (data.reference or "").strip() or None
    row.refunded_on = data.paid_on
    row.refund_note = (data.note or "").strip() or None
    db.commit()
    return build_detail(db, current_user.id, lease_id)


# Take back the refund record
@router.delete("/lease/{lease_id}/refund", response_model=Detail)
def remove_refund(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    lease, unit, prop, tenant = find_lease(db, current_user.id, lease_id)
    row = db.query(DepositSettlement).filter(DepositSettlement.lease_id == lease.id).first()
    if row is None or row.refund_amount is None:
        raise HTTPException(status_code=404, detail="No refund was recorded")
    row.refund_amount = None
    row.refund_method = None
    row.refund_reference = None
    row.refunded_on = None
    row.refund_note = None
    db.commit()
    return build_detail(db, current_user.id, lease_id)