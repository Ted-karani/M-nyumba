# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
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