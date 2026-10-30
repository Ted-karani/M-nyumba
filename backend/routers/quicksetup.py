# quicksetup.py - add a whole building and its units in one go

# Import the tool that checks text patterns
import re
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, model_validator
# Import the tool that counts rows
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from admin_models import OwnerAccount
from dependencies import get_db, get_current_user
from routers.properties import require_owner

# Make a group of endpoints that all start with /quick-setup
router = APIRouter(prefix="/quick-setup", tags=["Quick setup"])

# The most units one request may add, and the longest unit number
MAX_UNITS = 300
MAX_LABEL_LENGTH = 20
# A range like A1-A12, A1-12, 1-12, or "Shop 1 to 4" (the second prefix is optional)
RANGE = re.compile(r"^(?P<prefix>\D*?)(?P<first>\d+)\s*(?:-|–|—|\bto\b)\s*(?P=prefix)?(?P<last>\d+)$", re.IGNORECASE)
# Something that looks like a range but could not be read, like A1-B12
BAD_RANGE = re.compile(r"\d\s*[-–—]\s*\D*\d")
# The characters a unit number may contain
GOOD_LABEL = re.compile(r"^[\w .#/-]+$")


# One kind of unit in the building
class UnitGroup(BaseModel):
    # The unit numbers, typed freely: "A1-A12, B1, B2"
    labels: str = Field(min_length=1, max_length=2000)
    # The kind of unit, like "Bedsitter"
    unit_type: str | None = Field(default=None, max_length=40)
    # The monthly rent and the deposit
    rent_amount: int = Field(default=0, ge=0, le=10_000_000)
    deposit_amount: int = Field(default=0, ge=0, le=10_000_000)


# The details of a new building
class NewProperty(BaseModel):
    # The building's name
    name: str = Field(min_length=2, max_length=80)
    # Where it is
    county: str | None = Field(default=None, max_length=60)
    town: str | None = Field(default=None, max_length=60)
    address: str | None = Field(default=None, max_length=200)


# What we ask for: a building (new or existing) and its groups of units
class BuildingRequest(BaseModel):
    # An existing building of this owner
    property_id: int | None = None
    # Or the details of a new one
    new_property: NewProperty | None = None
    # The groups of units to add
    groups: list[UnitGroup] = Field(min_length=1, max_length=10)
    # When adding to an existing building: skip unit numbers that already exist (otherwise they count as problems)
    skip_existing: bool = True

    # Exactly one of the two buildings must be given
    @model_validator(mode="after")
    def one_building(self):
        if (self.property_id is None) == (self.new_property is None):
            raise ValueError("Choose an existing building, or give the details of a new one")
        return self


# What will be (or was) done for one group
class GroupPreview(BaseModel):
    # The unit numbers that will be made
    labels: list[str]
    # The unit numbers skipped because they already exist
    skipped: list[str]
    # The settings for this group
    unit_type: str | None
    rent_amount: int
    deposit_amount: int


# What we send back
class BuildingResult(BaseModel):
    # True if there is nothing wrong
    ok: bool
    # The building (empty for a new building until it is saved)
    property_id: int | None
    property_name: str
    new_property: bool
    # How many units will be added, how many were saved, and how many were skipped
    will_add: int
    created: int
    skipped: int
    # What the monthly rent would be if every new unit were let
    potential_rent: int
    # What happens for each group
    groups: list[GroupPreview]
    # Everything that is wrong, in plain words
    problems: list[str]


# Turn what was typed into a list of unit numbers (and a list of problems)
def expand_labels(text: str):
    labels = []
    problems = []
    # Unit numbers are separated by commas, semicolons, or new lines
    for token in re.split(r"[,;\n]+", text):
        token = token.strip()
        if not token:
            continue
        match = RANGE.match(token)
        if match:
            prefix = match.group("prefix")
            first = match.group("first")
            last = match.group("last")
            low, high = int(first), int(last)
            if high < low:
                problems.append(f"“{token}” goes backwards. Write the smaller number first")
                continue
            if high - low + 1 > MAX_UNITS:
                problems.append(f"“{token}” is more than {MAX_UNITS} units")
                continue
            # Keep leading zeros, so A01-A03 gives A01, A02, A03
            width = len(first) if first.startswith("0") and len(first) > 1 else 0
            for number in range(low, high + 1):
                labels.append(f"{prefix}{str(number).zfill(width) if width else number}")
        else:
            # Something like A1-B12 is almost certainly a mistake
            if BAD_RANGE.search(token):
                problems.append(f"I could not read “{token}” as a range. Write it like A1-A12")
                continue
            labels.append(token)
    # Check every unit number
    clean = []
    for label in labels:
        if len(label) > MAX_LABEL_LENGTH:
            problems.append(f"“{label}” is too long. Unit numbers can have at most {MAX_LABEL_LENGTH} characters")
        elif not GOOD_LABEL.match(label):
            problems.append(f"“{label}” has a character that is not allowed. Use letters, numbers, spaces, dots, # / or -")
        else:
            clean.append(label)
    return clean, problems


# Tidy a piece of text (empty becomes nothing)
def clean_text(value):
    return (value or "").strip() or None


# How many units an owner has in all their buildings
def count_units(db: Session, owner_id: int) -> int:
    return (
        db.query(func.count(models.Unit.id))
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == owner_id)
        .scalar()
    )


# Work out what would be done, and what is wrong (nothing is saved here)
def plan_building(db: Session, owner: models.User, data: BuildingRequest):
    problems = []
    existing_labels = set()
    # Which building is it?
    if data.property_id is not None:
        prop = (
            db.query(models.Property)
            .filter(models.Property.id == data.property_id, models.Property.owner_id == owner.id)
            .first()
        )
        # Say "not found" for missing and for someone else's, so nothing leaks
        if prop is None:
            raise HTTPException(status_code=404, detail="Property not found")
        property_name = prop.name
        rows = db.query(models.Unit.unit_number).filter(models.Unit.property_id == prop.id).all()
        existing_labels = {label.lower() for (label,) in rows}
    else:
        property_name = data.new_property.name.strip()
        clash = (
            db.query(models.Property)
            .filter(models.Property.owner_id == owner.id, func.lower(models.Property.name) == property_name.lower())
            .first()
        )
        if clash is not None:
            problems.append(f"You already have a building called “{property_name}”. Choose it from the list to add units to it")

    groups = []
    plan = []
    seen = set()
    for number, group in enumerate(data.groups, start=1):
        labels, group_problems = expand_labels(group.labels)
        problems.extend(f"Group {number}: {text}" for text in group_problems)
        if not labels and not group_problems:
            problems.append(f"Group {number} has no unit numbers")
        fresh = []
        skipped = []
        for label in labels:
            key = label.lower()
            # The same unit number cannot be used twice in one request
            if key in seen:
                problems.append(f"{label} appears more than once")
                continue
            seen.add(key)
            if key in existing_labels:
                if data.skip_existing:
                    skipped.append(label)
                else:
                    problems.append(f"Unit {label} already exists in {property_name}")
                continue
            fresh.append(label)
            plan.append({"label": label, "unit_type": clean_text(group.unit_type), "rent": group.rent_amount, "deposit": group.deposit_amount})
        groups.append(GroupPreview(
            labels=fresh,
            skipped=skipped,
            unit_type=clean_text(group.unit_type),
            rent_amount=group.rent_amount,
            deposit_amount=group.deposit_amount,
        ))

    # The limits
    if len(plan) > MAX_UNITS:
        problems.append(f"You can add at most {MAX_UNITS} units at a time")
    if not plan and not problems:
        problems.append("There is nothing new to add. Every unit number already exists")
    # The unit limit the admin set for this account
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner.id).first()
    if account is not None and account.unit_limit is not None:
        current = count_units(db, owner.id)
        if current + len(plan) > account.unit_limit:
            problems.append(
                f"Your plan allows {account.unit_limit} units and you have {current}. This would add {len(plan)}. Please contact support to add more"
            )

    result = BuildingResult(
        ok=not problems,
        property_id=data.property_id,
        property_name=property_name,
        new_property=data.property_id is None,
        will_add=len(plan),
        created=0,
        skipped=sum(len(group.skipped) for group in groups),
        potential_rent=sum(item["rent"] for item in plan),
        groups=groups,
        problems=problems,
    )
    return result, plan


# Save the building (if it is new) and all its units
def save_building(db: Session, owner: models.User, data: BuildingRequest, plan) -> int:
    if data.property_id is not None:
        property_id = data.property_id
    else:
        details = data.new_property
        prop = models.Property(
            owner_id=owner.id,
            name=details.name.strip(),
            county=clean_text(details.county),
            town=clean_text(details.town),
            address=clean_text(details.address),
        )
        db.add(prop)
        # This gives the new building its id right away
        db.flush()
        property_id = prop.id
    for item in plan:
        db.add(models.Unit(
            property_id=property_id,
            unit_number=item["label"],
            unit_type=item["unit_type"],
            rent_amount=item["rent"],
            deposit_amount=item["deposit"],
            status="vacant",
        ))
    # Save everything together
    db.commit()
    return property_id


# Show what would happen, without saving anything
@router.post("/preview", response_model=BuildingResult)
def preview_building(
    data: BuildingRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can set up buildings
    require_owner(current_user)
    result, plan = plan_building(db, current_user, data)
    return result


# Save the building and its units (only if there is nothing wrong)
@router.post("/building", response_model=BuildingResult)
def create_building(
    data: BuildingRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can set up buildings
    require_owner(current_user)
    result, plan = plan_building(db, current_user, data)
    # If anything is wrong, nothing is saved
    if not result.ok:
        return result
    property_id = save_building(db, current_user, data, plan)
    result.property_id = property_id
    result.created = len(plan)
    return result