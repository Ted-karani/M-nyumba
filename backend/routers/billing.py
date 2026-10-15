# Import the date tool so we can work out the start and end of a month
from datetime import date
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import tools to add up numbers and to search with "or"
from sqlalchemy import func, or_
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import schemas
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.properties import require_owner
from routers.leases import get_owned_lease, build_lease_out

# Make a group of endpoints for charges and payments
router = APIRouter()

# The most payment rows we send back in one request
MAX_ROWS = 300


# One payment in the big list, with the names filled in
class PaymentListItem(BaseModel):
    # The payment's id
    id: int
    # The lease it belongs to
    lease_id: int
    # The tenant who paid
    tenant_id: int
    # The tenant's name
    tenant_name: str
    # The unit number, like "A1"
    unit_number: str
    # The name of the property
    property_name: str
    # The amount paid
    amount: int
    # The date the money was received
    paid_on: date
    # How it was paid: "mpesa", "cash", or "bank"
    method: str
    # The M-Pesa code or other reference
    reference: str | None
    # The name of the person who recorded it
    recorded_by_name: str | None


# The money received, split by how it was paid
class MethodTotals(BaseModel):
    # Total received by M-Pesa
    mpesa: int = 0
    # Total received in cash
    cash: int = 0
    # Total received by bank
    bank: int = 0


# Everything the payments page needs
class PaymentsReport(BaseModel):
    # The total of ALL matching payments
    total: int
    # How many payments match
    count: int
    # The total split by payment method
    by_method: MethodTotals
    # The matching payments, newest first (up to MAX_ROWS)
    items: list[PaymentListItem]


# Start a database query that joins a payment to its lease, unit, property, tenant, and the person who recorded it
def payments_joined(db: Session, *entities):
    return (
        db.query(*entities)
        .select_from(models.Payment)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .outerjoin(models.User, models.Payment.recorded_by_id == models.User.id)
    )


# Find a charge, but only if its lease's property belongs to this user
def get_owned_charge(db: Session, charge_id: int, user: models.User):
    # Join charges to leases to units to properties and check the owner
    charge = (
        db.query(models.Charge)
        .join(models.Lease, models.Charge.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Charge.id == charge_id, models.Property.owner_id == user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    # Hand back the charge
    return charge


# Find a payment, but only if its lease's property belongs to this user
def get_owned_payment(db: Session, payment_id: int, user: models.User):
    # Join payments to leases to units to properties and check the owner
    payment = (
        db.query(models.Payment)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Payment.id == payment_id, models.Property.owner_id == user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    # Hand back the payment
    return payment


# Add a charge to a lease (next month's rent, water, wifi, electricity, other)
@router.post("/leases/{lease_id}/charges", response_model=schemas.ChargeCreatedOut, status_code=201, tags=["Charges"])
def create_charge(
    lease_id: int,
    data: schemas.ChargeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add charges
    require_owner(current_user)
    # Make sure the lease is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # Never create rent twice for the same month
    if data.charge_type == "rent":
        existing = (
            db.query(models.Charge)
            .filter(
                models.Charge.lease_id == lease.id,
                models.Charge.charge_type == "rent",
                models.Charge.period == data.period,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Rent for this month has already been charged on this lease")
    # Build the charge and attach it to the lease
    charge = models.Charge(lease_id=lease.id, **data.model_dump())
    # Save it to the database
    db.add(charge)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(charge)
    # Work out the tenant's new balance
    balance = build_lease_out(db, lease).balance
    # Send the charge back with the new balance
    out = schemas.ChargeOut.model_validate(charge).model_dump()
    return schemas.ChargeCreatedOut(**out, lease_balance=balance)


# List the charges on a lease, oldest due date first
@router.get("/leases/{lease_id}/charges", response_model=list[schemas.ChargeOut], tags=["Charges"])
def list_charges(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Make sure the lease is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # Return its charges in order
    return (
        db.query(models.Charge)
        .filter(models.Charge.lease_id == lease.id)
        .order_by(models.Charge.due_date, models.Charge.id)
        .all()
    )


# Delete a charge (for fixing a mistake)
@router.delete("/charges/{charge_id}", status_code=204, tags=["Charges"])
def delete_charge(
    charge_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete charges
    require_owner(current_user)
    # Find it, but only if it is theirs
    charge = get_owned_charge(db, charge_id, current_user)
    # Delete it
    db.delete(charge)
    db.commit()


# Record a payment on a lease
@router.post("/leases/{lease_id}/payments", response_model=schemas.PaymentCreatedOut, status_code=201, tags=["Payments"])
def create_payment(
    lease_id: int,
    data: schemas.PaymentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can record payments for now (caretakers come later)
    require_owner(current_user)
    # Make sure the lease is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # Never record the same code twice
    if data.reference:
        existing = db.query(models.Payment).filter(models.Payment.reference == data.reference).first()
        if existing:
            raise HTTPException(status_code=400, detail="A payment with this code has already been recorded")
    # Build the payment, and note who entered it
    payment = models.Payment(lease_id=lease.id, recorded_by_id=current_user.id, **data.model_dump())
    # Save it to the database
    db.add(payment)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(payment)
    # Work out the tenant's new balance
    balance = build_lease_out(db, lease).balance
    # Send the payment back with the new balance
    out = schemas.PaymentOut.model_validate(payment).model_dump()
    return schemas.PaymentCreatedOut(**out, lease_balance=balance)


# List the payments on a lease, newest first
@router.get("/leases/{lease_id}/payments", response_model=list[schemas.PaymentOut], tags=["Payments"])
def list_payments(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Make sure the lease is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # Return its payments, newest first
    return (
        db.query(models.Payment)
        .filter(models.Payment.lease_id == lease.id)
        .order_by(models.Payment.paid_on.desc(), models.Payment.id.desc())
        .all()
    )


# List ALL of this owner's payments, with filters (month, property, method, and a search word)
@router.get("/payments", response_model=PaymentsReport, tags=["Payments"])
def list_all_payments(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    property_id: int | None = Query(default=None),
    method: Literal["mpesa", "cash", "bank"] | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Always start with only this owner's payments
    conditions = [models.Property.owner_id == current_user.id]
    # Only one month, like "2026-10"
    if month:
        year, month_number = int(month[:4]), int(month[5:7])
        # The first day of that month, and the first day of the next month
        start = date(year, month_number, 1)
        end = date(year + 1, 1, 1) if month_number == 12 else date(year, month_number + 1, 1)
        conditions.append(models.Payment.paid_on >= start)
        conditions.append(models.Payment.paid_on < end)
    # Only one property
    if property_id:
        conditions.append(models.Unit.property_id == property_id)
    # Only one way of paying
    if method:
        conditions.append(models.Payment.method == method)
    # Only payments that match a search word (tenant name, unit number, or M-Pesa code)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                models.Tenant.full_name.ilike(pattern),
                models.Unit.unit_number.ilike(pattern),
                models.Payment.reference.ilike(pattern),
            )
        )

    # Add up the matching payments for each way of paying
    total_rows = (
        payments_joined(db, models.Payment.method, func.sum(models.Payment.amount), func.count(models.Payment.id))
        .filter(*conditions)
        .group_by(models.Payment.method)
        .all()
    )
    # Work out the totals from those rows
    by_method = {"mpesa": 0, "cash": 0, "bank": 0}
    total = 0
    count = 0
    for pay_method, amount, number in total_rows:
        by_method[pay_method] = int(amount)
        total += int(amount)
        count += number

    # Get the matching payments themselves, newest first
    rows = (
        payments_joined(db, models.Payment, models.Lease, models.Unit, models.Property, models.Tenant, models.User)
        .filter(*conditions)
        .order_by(models.Payment.paid_on.desc(), models.Payment.id.desc())
        .limit(MAX_ROWS)
        .all()
    )
    # Turn each row into the shape we send back
    items = [
        PaymentListItem(
            id=payment.id,
            lease_id=payment.lease_id,
            tenant_id=tenant.id,
            tenant_name=tenant.full_name,
            unit_number=unit.unit_number,
            property_name=prop.name,
            amount=payment.amount,
            paid_on=payment.paid_on,
            method=payment.method,
            reference=payment.reference,
            recorded_by_name=user.full_name if user else None,
        )
        for payment, lease, unit, prop, tenant, user in rows
    ]

    # Send everything back
    return PaymentsReport(total=total, count=count, by_method=MethodTotals(**by_method), items=items)


# Delete a payment (for fixing a mistake)
@router.delete("/payments/{payment_id}", status_code=204, tags=["Payments"])
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete payments
    require_owner(current_user)
    # Find it, but only if it is theirs
    payment = get_owned_payment(db, payment_id, current_user)
    # Delete it
    db.delete(payment)
    db.commit()