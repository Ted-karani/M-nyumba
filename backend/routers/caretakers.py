# Import the tool that groups things together
from collections import defaultdict
# Import the date and time tool
from datetime import datetime
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the tools that describe and check data shapes
from pydantic import BaseModel, EmailStr, Field, field_validator
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import security
from dependencies import get_db, get_current_user
# Reuse the owner check, the password check, and the phone cleaner we wrote earlier
from routers.account import validate_new_password
from routers.properties import require_owner
from schemas import clean_phone
from security_models import mark_password_changed

# Make a group of endpoints that all start with /caretakers
router = APIRouter(prefix="/caretakers", tags=["Caretakers"])


# Clean a phone number (empty stays empty)
def tidy_phone(value: str | None):
    # Nothing was typed
    if value is None or value.strip() == "":
        return None
    # Turn it into the 254... format, or raise an error if it is not valid
    return clean_phone(value)


# A property's id and name, shown inside a caretaker's details
class PropertyRef(BaseModel):
    # The property's id
    id: int
    # The property's name
    name: str


# The data we ask for when adding a caretaker
class CaretakerCreate(BaseModel):
    # The caretaker's full name
    full_name: str = Field(min_length=2)
    # The email they will log in with
    email: EmailStr
    # Their phone number (optional)
    phone: str | None = None
    # The password the owner chooses for them
    password: str = Field(min_length=8, max_length=64)
    # The properties they will look after
    property_ids: list[int] = Field(default_factory=list, max_length=100)

    # Clean the phone number before saving
    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        return tidy_phone(value)


# The data we accept when editing a caretaker (every field is optional, send only what changed)
class CaretakerUpdate(BaseModel):
    # New name
    full_name: str | None = Field(default=None, min_length=2)
    # New phone number
    phone: str | None = None
    # A new password (this is how the owner resets a forgotten one)
    password: str | None = Field(default=None, min_length=8, max_length=64)
    # Switch the account on or off
    is_active: bool | None = None
    # The full new list of properties they look after
    property_ids: list[int] | None = Field(default=None, max_length=100)

    # Clean the phone number before saving
    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        return tidy_phone(value)


# The data we send back about a caretaker (never the password)
class CaretakerOut(BaseModel):
    # The caretaker's id
    id: int
    # Their name
    full_name: str
    # Their email
    email: str
    # Their phone number
    phone: str | None
    # Whether they can log in
    is_active: bool
    # The properties they look after
    properties: list[PropertyRef]
    # When they were added
    created_at: datetime


# Make sure every property id in a list belongs to this owner
def check_properties(db: Session, owner: models.User, property_ids: list[int]) -> set[int]:
    # Remove duplicates
    wanted = set(property_ids)
    # Count how many of them really belong to this owner
    if wanted:
        found = (
            db.query(models.Property.id)
            .filter(models.Property.id.in_(wanted), models.Property.owner_id == owner.id)
            .count()
        )
        # If any is missing or someone else's, refuse
        if found != len(wanted):
            raise HTTPException(status_code=400, detail="One of the properties was not found")
    # Hand back the checked ids
    return wanted


# Find a caretaker, but only if this owner created them
def find_caretaker(db: Session, caretaker_id: int, owner: models.User):
    # Join the login to the account that links it to an owner
    row = (
        db.query(models.User, models.CaretakerAccount)
        .join(models.CaretakerAccount, models.CaretakerAccount.user_id == models.User.id)
        .filter(models.User.id == caretaker_id, models.CaretakerAccount.owner_id == owner.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if row is None:
        raise HTTPException(status_code=404, detail="Caretaker not found")
    # Hand back the login and the account
    return row


# Turn caretakers into the shape we send back, with their properties
def build_out(db: Session, owner: models.User, rows) -> list[CaretakerOut]:
    # The ids of these caretakers
    ids = [user.id for user, account in rows]
    # Find which properties each one looks after
    assigned = defaultdict(list)
    if ids:
        pairs = (
            db.query(models.PropertyCaretaker.caretaker_id, models.Property)
            .join(models.Property, models.PropertyCaretaker.property_id == models.Property.id)
            .filter(models.PropertyCaretaker.caretaker_id.in_(ids), models.Property.owner_id == owner.id)
            .order_by(models.Property.name)
            .all()
        )
        for caretaker_id, prop in pairs:
            assigned[caretaker_id].append(PropertyRef(id=prop.id, name=prop.name))
    # Build one entry for each caretaker
    return [
        CaretakerOut(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            is_active=bool(user.is_active),
            properties=assigned[user.id],
            created_at=user.created_at,
        )
        for user, account in rows
    ]


# List this owner's caretakers
@router.get("", response_model=list[CaretakerOut])
def list_caretakers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see their team
    require_owner(current_user)
    # Get the caretakers this owner created
    rows = (
        db.query(models.User, models.CaretakerAccount)
        .join(models.CaretakerAccount, models.CaretakerAccount.user_id == models.User.id)
        .filter(models.CaretakerAccount.owner_id == current_user.id)
        .order_by(models.User.full_name)
        .all()
    )
    # Send them back
    return build_out(db, current_user, rows)


# Add a caretaker
@router.post("", response_model=CaretakerOut, status_code=201)
def create_caretaker(
    data: CaretakerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add caretakers
    require_owner(current_user)
    # Store emails in lowercase so "A@x.com" and "a@x.com" are the same
    email = data.email.lower()
    # Check if this email already has an account
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="This email is already registered")
    # The password must not be too easy to guess
    validate_new_password(data.password, email)
    # Make sure the properties are theirs
    property_ids = check_properties(db, current_user, data.property_ids)
    # Build the login, with the role fixed to "caretaker" and only the scrambled password saved
    user = models.User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone,
        password_hash=security.hash_password(data.password),
        role="caretaker",
    )
    db.add(user)
    # This gives the new login its id right away
    db.flush()
    # Link the login to this owner
    db.add(models.CaretakerAccount(user_id=user.id, owner_id=current_user.id))
    # Assign the properties
    for property_id in property_ids:
        db.add(models.PropertyCaretaker(property_id=property_id, caretaker_id=user.id))
    # Save everything together
    db.commit()
    db.refresh(user)
    # Send the caretaker back
    account = db.query(models.CaretakerAccount).filter(models.CaretakerAccount.user_id == user.id).first()
    return build_out(db, current_user, [(user, account)])[0]


# Edit a caretaker (send only the fields that changed)
@router.put("/{caretaker_id}", response_model=CaretakerOut)
def update_caretaker(
    caretaker_id: int,
    data: CaretakerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit caretakers
    require_owner(current_user)
    # Find the caretaker, but only if this owner created them
    user, account = find_caretaker(db, caretaker_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # Change the name
    if changes.get("full_name") is not None:
        user.full_name = changes["full_name"].strip()
    # Change the phone number (sending nothing clears it)
    if "phone" in changes:
        user.phone = changes["phone"]
    # Reset the password, and sign the caretaker out of every device they are logged in on
    if changes.get("password") is not None:
        validate_new_password(changes["password"], user.email)
        user.password_hash = security.hash_password(changes["password"])
        mark_password_changed(db, user.id)
    # Switch the account on or off
    if changes.get("is_active") is not None:
        user.is_active = changes["is_active"]
    # Replace the list of properties
    if changes.get("property_ids") is not None:
        property_ids = check_properties(db, current_user, changes["property_ids"])
        # Remove the old assignments, then add the new ones
        db.query(models.PropertyCaretaker).filter(models.PropertyCaretaker.caretaker_id == user.id).delete(
            synchronize_session=False
        )
        for property_id in property_ids:
            db.add(models.PropertyCaretaker(property_id=property_id, caretaker_id=user.id))
    # Save everything together
    db.commit()
    db.refresh(user)
    # Send the caretaker back
    return build_out(db, current_user, [(user, account)])[0]