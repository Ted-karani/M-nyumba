# Import the date tool
from datetime import date
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, field_validator
# Import the tool that adds up and counts numbers in the database
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session
from datetime import datetime

# Import our own files
import models
from dependencies import get_db, get_current_user
# Reuse the safety helpers and the phone cleaner we wrote earlier
from routers.properties import require_owner, get_owned_property
from schemas import clean_phone

# Make a group of endpoints that all start with /maintenance
router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

# The order we show things in: open problems first, and urgent ones first
STATUS_RANK = {"open": 0, "in_progress": 1, "fixed": 2}
PRIORITY_RANK = {"urgent": 0, "normal": 1, "low": 2}


# Clean a contractor's phone number (empty stays empty)
def tidy_phone(value: str | None):
    # Nothing was typed
    if value is None or value.strip() == "":
        return None
    # Turn it into the 254... format, or raise an error if it is not valid
    return clean_phone(value)


# The data we ask for when reporting a problem
class RepairCreate(BaseModel):
    # The property the problem is in
    property_id: int
    # The unit it is in (leave empty for the whole property)
    unit_id: int | None = None
    # A short title
    title: str = Field(min_length=3, max_length=120)
    # A longer explanation (optional)
    description: str | None = None
    # How urgent it is
    priority: Literal["low", "normal", "urgent"] = "normal"
    # Who is fixing it (optional)
    contractor_name: str | None = None
    # Their phone number (optional)
    contractor_phone: str | None = None

    # Clean the phone number before saving
    @field_validator("contractor_phone")
    @classmethod
    def check_phone(cls, value):
        return tidy_phone(value)


# The data we accept when editing a problem (every field is optional, send only what changed)
class RepairUpdate(BaseModel):
    # New title
    title: str | None = Field(default=None, min_length=3, max_length=120)
    # New explanation
    description: str | None = None
    # New priority
    priority: Literal["low", "normal", "urgent"] | None = None
    # New status
    status: Literal["open", "in_progress", "fixed"] | None = None
    # The cost in shillings
    cost: int | None = Field(default=None, ge=0)
    # Who is fixing it
    contractor_name: str | None = None
    # Their phone number
    contractor_phone: str | None = None
    # Extra notes
    notes: str | None = None

    # Clean the phone number before saving
    @field_validator("contractor_phone")
    @classmethod
    def check_phone(cls, value):
        return tidy_phone(value)


# The data we send back about a problem
class RepairOut(BaseModel):
    # The request's id
    id: int
    # The property it is in
    property_id: int
    # The property's name
    property_name: str
    # The unit it is in (empty for the whole property)
    unit_id: int | None
    # The unit's number
    unit_number: str | None
    # The title
    title: str
    # The explanation
    description: str | None
    # How urgent it is
    priority: str
    # How far along it is
    status: str
    # What it cost
    cost: int | None
    # Who is fixing it
    contractor_name: str | None
    # Their phone number
    contractor_phone: str | None
    # Extra notes
    notes: str | None
    # The name of the person who reported it
    reported_by_name: str | None
    # When it was reported
    created_at: datetime
    # The date it was fixed
    resolved_on: date | None


# Everything the repairs page needs
class RepairReport(BaseModel):
    # How many are open
    open_count: int
    # How many are in progress
    in_progress_count: int
    # How many are fixed
    fixed_count: int
    # What was spent on repairs fixed this month
    cost_this_month: int
    # The problems themselves
    items: list[RepairOut]


# Turn a request and its related rows into the shape we send back
def to_out(repair, prop, unit, creator) -> RepairOut:
    return RepairOut(
        id=repair.id,
        property_id=prop.id,
        property_name=prop.name,
        unit_id=repair.unit_id,
        unit_number=unit.unit_number if unit else None,
        title=repair.title,
        description=repair.description,
        priority=repair.priority,
        status=repair.status,
        cost=repair.cost,
        contractor_name=repair.contractor_name,
        contractor_phone=repair.contractor_phone,
        notes=repair.notes,
        reported_by_name=creator.full_name if creator else None,
        created_at=repair.created_at,
        resolved_on=repair.resolved_on,
    )


# Find a request, but only if its property belongs to this user
def load_item(db: Session, repair_id: int, owner: models.User):
    # Join the request to its property, unit, and the person who reported it
    row = (
        db.query(models.MaintenanceRequest, models.Property, models.Unit, models.User)
        .join(models.Property, models.MaintenanceRequest.property_id == models.Property.id)
        .outerjoin(models.Unit, models.MaintenanceRequest.unit_id == models.Unit.id)
        .outerjoin(models.User, models.MaintenanceRequest.created_by_id == models.User.id)
        .filter(models.MaintenanceRequest.id == repair_id, models.Property.owner_id == owner.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if row is None:
        raise HTTPException(status_code=404, detail="Repair not found")
    # Hand back the request and its related rows
    return row


# List this owner's repairs (optionally only one status or one property)
@router.get("", response_model=RepairReport)
def list_repairs(
    status: Literal["open", "in_progress", "fixed"] | None = Query(default=None),
    property_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Always start with only this owner's repairs
    conditions = [models.Property.owner_id == current_user.id]
    # Only one property
    if property_id:
        conditions.append(models.MaintenanceRequest.property_id == property_id)

    # Count the repairs in each status (ignoring the status filter, so the buttons can show their numbers)
    count_rows = (
        db.query(models.MaintenanceRequest.status, func.count(models.MaintenanceRequest.id))
        .join(models.Property, models.MaintenanceRequest.property_id == models.Property.id)
        .filter(*conditions)
        .group_by(models.MaintenanceRequest.status)
        .all()
    )
    counts = {"open": 0, "in_progress": 0, "fixed": 0}
    for row_status, number in count_rows:
        counts[row_status] = number

    # Add up what was spent on repairs fixed this month
    month_start = date.today().replace(day=1)
    cost_this_month = (
        db.query(func.coalesce(func.sum(models.MaintenanceRequest.cost), 0))
        .join(models.Property, models.MaintenanceRequest.property_id == models.Property.id)
        .filter(
            *conditions,
            models.MaintenanceRequest.status == "fixed",
            models.MaintenanceRequest.resolved_on >= month_start,
        )
        .scalar()
    )

    # Get the repairs themselves, newest first
    query = (
        db.query(models.MaintenanceRequest, models.Property, models.Unit, models.User)
        .join(models.Property, models.MaintenanceRequest.property_id == models.Property.id)
        .outerjoin(models.Unit, models.MaintenanceRequest.unit_id == models.Unit.id)
        .outerjoin(models.User, models.MaintenanceRequest.created_by_id == models.User.id)
        .filter(*conditions)
    )
    if status:
        query = query.filter(models.MaintenanceRequest.status == status)
    rows = query.order_by(models.MaintenanceRequest.created_at.desc(), models.MaintenanceRequest.id.desc()).all()
    # Put open and urgent problems first (the sort keeps "newest first" inside each group)
    rows.sort(key=lambda row: (STATUS_RANK[row[0].status], PRIORITY_RANK[row[0].priority]))

    # Send everything back
    return RepairReport(
        open_count=counts["open"],
        in_progress_count=counts["in_progress"],
        fixed_count=counts["fixed"],
        cost_this_month=int(cost_this_month),
        items=[to_out(repair, prop, unit, creator) for repair, prop, unit, creator in rows],
    )


# Report a new problem
@router.post("", response_model=RepairOut, status_code=201)
def create_repair(
    data: RepairCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can report problems for now (caretakers come in the next step)
    require_owner(current_user)
    # Make sure the property is theirs
    prop = get_owned_property(db, data.property_id, current_user)
    # If a unit was given, make sure it is inside this property
    unit = None
    if data.unit_id is not None:
        unit = (
            db.query(models.Unit)
            .filter(models.Unit.id == data.unit_id, models.Unit.property_id == prop.id)
            .first()
        )
        if unit is None:
            raise HTTPException(status_code=400, detail="That unit is not in this property")
    # Clean up spaces around the title
    title = data.title.strip()
    if len(title) < 3:
        raise HTTPException(status_code=400, detail="The title must be at least 3 characters")
    # Build the request
    repair = models.MaintenanceRequest(
        property_id=prop.id,
        unit_id=unit.id if unit else None,
        title=title,
        description=(data.description or "").strip() or None,
        priority=data.priority,
        status="open",
        contractor_name=(data.contractor_name or "").strip() or None,
        contractor_phone=data.contractor_phone,
        created_by_id=current_user.id,
    )
    # Save it to the database
    db.add(repair)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(repair)
    # Send it back
    return to_out(repair, prop, unit, current_user)


# Get one repair by its id
@router.get("/{repair_id}", response_model=RepairOut)
def get_repair(
    repair_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if it is theirs
    repair, prop, unit, creator = load_item(db, repair_id, current_user)
    # Send it back
    return to_out(repair, prop, unit, creator)


# Edit a repair (send only the fields that changed)
@router.put("/{repair_id}", response_model=RepairOut)
def update_repair(
    repair_id: int,
    data: RepairUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit repairs for now
    require_owner(current_user)
    # Find it, but only if it is theirs
    repair, prop, unit, creator = load_item(db, repair_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # Change the status first, and keep the "fixed on" date in step with it
    new_status = changes.pop("status", None)
    if new_status and new_status != repair.status:
        # Fixed today, or no longer fixed
        repair.resolved_on = date.today() if new_status == "fixed" else None
        repair.status = new_status
    # Apply the other changes
    for field, value in changes.items():
        # These fields cannot be emptied out
        if field in ("title", "priority") and value is None:
            continue
        # Tidy up text (empty text becomes "nothing")
        if isinstance(value, str):
            value = value.strip() or None
            if field == "title" and (value is None or len(value) < 3):
                raise HTTPException(status_code=400, detail="The title must be at least 3 characters")
        # Save the new value on the repair
        setattr(repair, field, value)
    # Save the changes
    db.commit()
    # Reload it with the changes
    db.refresh(repair)
    # Send it back
    return to_out(repair, prop, unit, creator)


# Delete a repair (for fixing a mistake)
@router.delete("/{repair_id}", status_code=204)
def delete_repair(
    repair_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete repairs
    require_owner(current_user)
    # Find it, but only if it is theirs
    repair, prop, unit, creator = load_item(db, repair_id, current_user)
    # Delete it
    db.delete(repair)
    db.commit()