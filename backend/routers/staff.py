# Import the tool that groups things together
from collections import defaultdict
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the tool that counts numbers in the database
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from access import property_scope
from dependencies import get_db, get_current_user

# Make a group of endpoints that all start with /work
router = APIRouter(prefix="/work", tags=["Staff"])


# One unit, with only the details a caretaker needs (no rent, no deposit, no money)
class WorkUnit(BaseModel):
    # The unit's id
    unit_id: int
    # The unit number, like "A1"
    unit_number: str
    # The kind of unit
    unit_type: str | None
    # "vacant", "occupied", or "maintenance"
    status: str
    # The id of the lease running now (so the checklists can be opened)
    lease_id: int | None
    # The tenant living there (empty if nobody)
    tenant_name: str | None
    # The tenant's phone number
    tenant_phone: str | None
    # How many problems in this unit are not fixed yet
    open_repairs: int


# One property with its units
class WorkProperty(BaseModel):
    # The property's id
    property_id: int
    # The property's name
    name: str
    # The county
    county: str | None
    # The town or estate
    town: str | None
    # How many problems in this property are not fixed yet
    open_repairs: int
    # The units inside it
    units: list[WorkUnit]


# The data we ask for when changing a unit's status
class UnitStatusChange(BaseModel):
    # Only these two can be set by hand
    status: Literal["vacant", "maintenance"]


# What we send back after changing a unit's status
class UnitStatusResult(BaseModel):
    # The unit's id
    unit_id: int
    # Its new status
    status: str


# Get the properties this person works with, with their units and tenants
@router.get("/properties", response_model=list[WorkProperty])
def my_properties(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Which properties may this person work with?
    scope = property_scope(db, current_user)
    # Get those properties and all their units
    properties = (
        db.query(models.Property).filter(models.Property.id.in_(scope)).order_by(models.Property.name).all()
    )
    units = (
        db.query(models.Unit).filter(models.Unit.property_id.in_(scope)).order_by(models.Unit.unit_number).all()
    )
    unit_ids = [unit.id for unit in units]

    # Find who is living in each unit right now (and which lease it is)
    living_by_unit = {}
    if unit_ids:
        lease_rows = (
            db.query(models.Lease, models.Tenant)
            .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
            .filter(models.Lease.unit_id.in_(unit_ids), models.Lease.status == "active")
            .all()
        )
        for lease, tenant in lease_rows:
            living_by_unit[lease.unit_id] = (lease, tenant)

    # Count the problems that are not fixed yet, for each unit and each property
    repair_rows = (
        db.query(
            models.MaintenanceRequest.property_id,
            models.MaintenanceRequest.unit_id,
            func.count(models.MaintenanceRequest.id),
        )
        .filter(models.MaintenanceRequest.property_id.in_(scope), models.MaintenanceRequest.status != "fixed")
        .group_by(models.MaintenanceRequest.property_id, models.MaintenanceRequest.unit_id)
        .all()
    )
    repairs_by_property = defaultdict(int)
    repairs_by_unit = defaultdict(int)
    for property_id, unit_id, number in repair_rows:
        repairs_by_property[property_id] += number
        if unit_id is not None:
            repairs_by_unit[unit_id] += number

    # Put the units into their properties
    units_by_property = defaultdict(list)
    for unit in units:
        living = living_by_unit.get(unit.id)
        units_by_property[unit.property_id].append(WorkUnit(
            unit_id=unit.id,
            unit_number=unit.unit_number,
            unit_type=unit.unit_type,
            status=unit.status,
            lease_id=living[0].id if living else None,
            tenant_name=living[1].full_name if living else None,
            tenant_phone=living[1].phone if living else None,
            open_repairs=repairs_by_unit[unit.id],
        ))

    # Send everything back
    return [
        WorkProperty(
            property_id=prop.id,
            name=prop.name,
            county=prop.county,
            town=prop.town,
            open_repairs=repairs_by_property[prop.id],
            units=units_by_property[prop.id],
        )
        for prop in properties
    ]


# Mark an empty unit as vacant or under repair
@router.put("/units/{unit_id}/status", response_model=UnitStatusResult)
def change_unit_status(
    unit_id: int,
    data: UnitStatusChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Which properties may this person work with?
    scope = property_scope(db, current_user)
    # Find the unit, but only if it is inside one of those properties
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id, models.Unit.property_id.in_(scope)).first()
    # Say "not found" for missing and for someone else's, so nothing leaks
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    # An occupied unit's status is controlled by its lease
    if unit.status == "occupied":
        raise HTTPException(status_code=400, detail="This unit is occupied. Only the owner can end the lease")
    # Save the new status
    unit.status = data.status
    db.commit()
    # Tell the caller what happened
    return UnitStatusResult(unit_id=unit.id, status=unit.status)