# Import the date tool so we can use today's date
from datetime import date
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tool that adds up numbers in the database
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import schemas
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.properties import require_owner
from routers.units import get_owned_unit
from routers.tenants import get_owned_tenant

# Make a group of endpoints that all start with /leases
router = APIRouter(prefix="/leases", tags=["Leases"])


# Turn a lease from the database into the shape we send back (with the money totals)
def build_lease_out(db: Session, lease: models.Lease) -> schemas.LeaseOut:
    # Add up everything this lease has been charged (0 if nothing yet)
    total_charged = (
        db.query(func.coalesce(func.sum(models.Charge.amount), 0))
        .filter(models.Charge.lease_id == lease.id)
        .scalar()
    )
    # Add up everything this lease has paid (0 if nothing yet)
    total_paid = (
        db.query(func.coalesce(func.sum(models.Payment.amount), 0))
        .filter(models.Payment.lease_id == lease.id)
        .scalar()
    )
    # Put it all together, with the balance calculated, never typed in
    return schemas.LeaseOut(
        id=lease.id,
        unit_id=lease.unit_id,
        unit_number=lease.unit.unit_number,
        tenant_id=lease.tenant_id,
        tenant_name=lease.tenant.full_name,
        start_date=lease.start_date,
        end_date=lease.end_date,
        rent_amount=lease.rent_amount,
        deposit_amount=lease.deposit_amount,
        status=lease.status,
        notes=lease.notes,
        created_at=lease.created_at,
        total_charged=total_charged,
        total_paid=total_paid,
        balance=total_charged - total_paid,
    )


# Find a lease, but only if its unit's property belongs to this user
def get_owned_lease(db: Session, lease_id: int, user: models.User):
    # Join leases to units to properties and check the owner
    lease = (
        db.query(models.Lease)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Lease.id == lease_id, models.Property.owner_id == user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if lease is None:
        raise HTTPException(status_code=404, detail="Lease not found")
    # Hand back the lease
    return lease


# Move a tenant into a unit
@router.post("", response_model=schemas.LeaseOut, status_code=201)
def create_lease(
    data: schemas.LeaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can create leases
    require_owner(current_user)
    # Make sure the unit is theirs
    unit = get_owned_unit(db, data.unit_id, current_user)
    # Make sure the tenant is theirs
    tenant = get_owned_tenant(db, data.tenant_id, current_user)
    # Only a vacant unit can be rented out
    if unit.status == "occupied":
        raise HTTPException(status_code=400, detail="This unit is already occupied")
    if unit.status == "maintenance":
        raise HTTPException(status_code=400, detail="This unit is under maintenance. Set it to vacant first")
    # Use the unit's rent and deposit unless different amounts were given
    rent = data.rent_amount if data.rent_amount is not None else unit.rent_amount
    deposit = data.deposit_amount if data.deposit_amount is not None else unit.deposit_amount
    # Build the lease
    lease = models.Lease(
        unit_id=unit.id,
        tenant_id=tenant.id,
        start_date=data.start_date,
        end_date=data.end_date,
        rent_amount=rent,
        deposit_amount=deposit,
        status="active",
        notes=data.notes,
    )
    # Add it to the database session and get its id (nothing is permanent yet)
    db.add(lease)
    db.flush()
    # Create the deposit charge, due on the move-in date
    if deposit > 0:
        db.add(models.Charge(
            lease_id=lease.id,
            charge_type="deposit",
            amount=deposit,
            period=None,
            due_date=data.start_date,
            description="Deposit",
        ))
    # Create the first month's rent charge, due on the move-in date
    if rent > 0:
        period = f"{data.start_date.year}-{data.start_date.month:02d}"
        db.add(models.Charge(
            lease_id=lease.id,
            charge_type="rent",
            amount=rent,
            period=period,
            due_date=data.start_date,
            description=f"Rent for {period}",
        ))
    # Mark the unit as occupied
    unit.status = "occupied"
    # Save everything together: the lease, the charges, and the unit status
    db.commit()
    # Reload the lease so it includes everything
    db.refresh(lease)
    # Send it back with the money totals
    return build_lease_out(db, lease)


# List this owner's leases (optionally filter by status, property, unit, or tenant)
@router.get("", response_model=list[schemas.LeaseOut])
def list_leases(
    status: Literal["active", "ended"] | None = Query(default=None),
    property_id: int | None = Query(default=None),
    unit_id: int | None = Query(default=None),
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Start with only this owner's leases
    query = (
        db.query(models.Lease)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == current_user.id)
    )
    # Apply each filter that was given
    if status:
        query = query.filter(models.Lease.status == status)
    if property_id:
        query = query.filter(models.Unit.property_id == property_id)
    if unit_id:
        query = query.filter(models.Lease.unit_id == unit_id)
    if tenant_id:
        query = query.filter(models.Lease.tenant_id == tenant_id)
    # Newest first
    leases = query.order_by(models.Lease.created_at.desc(), models.Lease.id.desc()).all()
    # Turn each one into the shape we send back
    return [build_lease_out(db, lease) for lease in leases]


# Get one lease by its id
@router.get("/{lease_id}", response_model=schemas.LeaseOut)
def get_lease(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if it is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # Send it back with the money totals
    return build_lease_out(db, lease)


# Edit an active lease (send only the fields that changed)
@router.put("/{lease_id}", response_model=schemas.LeaseOut)
def update_lease(
    lease_id: int,
    data: schemas.LeaseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit leases
    require_owner(current_user)
    # Find it, but only if it is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # An ended lease is history and cannot be changed
    if lease.status != "active":
        raise HTTPException(status_code=400, detail="This lease has ended and cannot be edited")
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # If the leaving date is changing, make sure it is not before the move-in date
    if changes.get("end_date") is not None and changes["end_date"] < lease.start_date:
        raise HTTPException(status_code=400, detail="The leaving date cannot be before the move-in date")
    # Apply each change
    for field, value in changes.items():
        # The rent cannot be emptied out
        if field == "rent_amount" and value is None:
            continue
        # Save the new value on the lease
        setattr(lease, field, value)
    # Save the changes
    db.commit()
    # Reload it with the changes
    db.refresh(lease)
    # Send it back with the money totals
    return build_lease_out(db, lease)


# End a lease: the tenant leaves and the unit becomes vacant again
@router.post("/{lease_id}/end", response_model=schemas.LeaseOut)
def end_lease(
    lease_id: int,
    data: schemas.LeaseEnd = schemas.LeaseEnd(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can end leases
    require_owner(current_user)
    # Find it, but only if it is theirs
    lease = get_owned_lease(db, lease_id, current_user)
    # A lease can only be ended once
    if lease.status != "active":
        raise HTTPException(status_code=400, detail="This lease has already ended")
    # Use the date given, or today
    end_date = data.end_date or date.today()
    # The leaving date cannot be before the move-in date
    if end_date < lease.start_date:
        raise HTTPException(status_code=400, detail="The leaving date cannot be before the move-in date")
    # Mark the lease as ended and record the leaving date
    lease.status = "ended"
    lease.end_date = end_date
    # Make the unit vacant again
    lease.unit.status = "vacant"
    # Save both changes together
    db.commit()
    # Reload it with the changes
    db.refresh(lease)
    # Send it back (check the balance in case the tenant still owes money)
    return build_lease_out(db, lease)