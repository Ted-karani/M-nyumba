# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the database session type
from sqlalchemy.orm import Session
# Import the tool that lets us list allowed values
from typing import Literal

# Import our own files
import models
import schemas
from dependencies import get_db, get_current_user
# Reuse the two safety helpers we wrote for properties
from routers.properties import require_owner, get_owned_property

# Make a group of endpoints for units
router = APIRouter(tags=["Units"])

# Fields that must always have a value (they cannot be emptied out)
REQUIRED_FIELDS = {"unit_number", "rent_amount", "deposit_amount", "status"}


# Find a unit, but only if its property belongs to this user
def get_owned_unit(db: Session, unit_id: int, user: models.User):
    # Join units to properties and check the owner
    unit = (
        db.query(models.Unit)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Unit.id == unit_id, models.Property.owner_id == user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    # Hand back the unit
    return unit


# Check that a unit number is not already used inside the same property
def check_unit_number_free(db: Session, property_id: int, unit_number: str, ignore_unit_id: int | None = None):
    # Look for another unit with the same number in the same property
    query = db.query(models.Unit).filter(
        models.Unit.property_id == property_id,
        models.Unit.unit_number == unit_number,
    )
    # When editing, do not count the unit we are editing
    if ignore_unit_id is not None:
        query = query.filter(models.Unit.id != ignore_unit_id)
    # If one exists, refuse with a clear message
    if query.first():
        raise HTTPException(status_code=400, detail="This unit number already exists in this property")


# Add a unit inside a property
@router.post("/properties/{property_id}/units", response_model=schemas.UnitOut, status_code=201)
def create_unit(
    property_id: int,
    data: schemas.UnitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add units
    require_owner(current_user)
    # Make sure the property is theirs
    prop = get_owned_property(db, property_id, current_user)
    # Clean up spaces around the unit number
    unit_number = data.unit_number.strip()
    # Make sure the number is not already taken in this property
    check_unit_number_free(db, prop.id, unit_number)
    # Build the unit and attach it to the property
    values = data.model_dump()
    values["unit_number"] = unit_number
    unit = models.Unit(property_id=prop.id, **values)
    # Save it to the database
    db.add(unit)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(unit)
    # Send it back
    return unit


# List the units inside a property (optionally only vacant, occupied, or maintenance ones)
@router.get("/properties/{property_id}/units", response_model=list[schemas.UnitOut])
def list_units(
    property_id: int,
    status: Literal["vacant", "occupied", "maintenance"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Make sure the property is theirs
    prop = get_owned_property(db, property_id, current_user)
    # Start with all units in this property
    query = db.query(models.Unit).filter(models.Unit.property_id == prop.id)
    # If a status filter was given, apply it
    if status:
        query = query.filter(models.Unit.status == status)
    # Return them ordered by unit number
    return query.order_by(models.Unit.unit_number).all()


# Get one unit by its id
@router.get("/units/{unit_id}", response_model=schemas.UnitOut)
def get_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if it is theirs
    return get_owned_unit(db, unit_id, current_user)


# Edit a unit (send only the fields that changed)
@router.put("/units/{unit_id}", response_model=schemas.UnitOut)
def update_unit(
    unit_id: int,
    data: schemas.UnitUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit units
    require_owner(current_user)
    # Find it, but only if it is theirs
    unit = get_owned_unit(db, unit_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # An occupied unit's status is controlled by its lease, not by hand
    if "status" in changes and unit.status == "occupied":
        raise HTTPException(status_code=400, detail="This unit is occupied. End the lease to change its status")
    # If the unit number is changing, check it is free and clean it up
    if "unit_number" in changes and changes["unit_number"] is not None:
        changes["unit_number"] = changes["unit_number"].strip()
        check_unit_number_free(db, unit.property_id, changes["unit_number"], ignore_unit_id=unit.id)
    # Apply each change
    for field, value in changes.items():
        # Required fields cannot be emptied out
        if field in REQUIRED_FIELDS and value is None:
            continue
        # Save the new value on the unit
        setattr(unit, field, value)
    # Save the changes
    db.commit()
    # Reload it with the changes
    db.refresh(unit)
    # Send it back
    return unit


# Delete a unit (only if it has never had a lease)
@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete units
    require_owner(current_user)
    # Find it, but only if it is theirs
    unit = get_owned_unit(db, unit_id, current_user)
    # Refuse if it has lease history, so we never lose rent records by accident
    if unit.leases:
        raise HTTPException(status_code=400, detail="This unit has lease history and cannot be deleted")
    # Delete it
    db.delete(unit)
    db.commit()