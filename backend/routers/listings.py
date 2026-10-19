# Import the tools we need
import html
import json
import os
import secrets
import uuid
# Import the date and time tools
from datetime import date, datetime
# Import FastAPI tools for building endpoints, errors, and file uploads
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, field_validator
# Import the column types and tools we need for the tables
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from database import Base
from dependencies import get_db, get_current_user
# Reuse the file safety tools from the documents feature
from routers.documents import ALLOWED, MAX_BYTES, UPLOAD_DIR, looks_right
from routers.properties import require_owner
from schemas import clean_phone

# The endpoints owners use to manage their listings (these need a login)
router = APIRouter(prefix="/listings", tags=["Listings"])
# The endpoints anyone can open (no login)
public_router = APIRouter(tags=["Public listings"])

# Only pictures are accepted as photos
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
# The most photos one listing can have
MAX_PHOTOS = 10


# This class is the "listings" table. Each unit advertised for rent is one row.
class Listing(Base):
    # The name of the table inside the database
    __tablename__ = "listings"
    # Rule: a unit can only have one listing
    __table_args__ = (UniqueConstraint("unit_id", name="one_listing_per_unit"),)

    # A unique number for each listing, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner who made it (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The unit being advertised (points to the units table)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    # The secret code in the public link
    token = Column(String, nullable=False, unique=True, index=True)
    # The headline, like "Bedsitter for rent in Makutano"
    title = Column(String, nullable=False)
    # A longer description
    description = Column(Text, nullable=True)
    # The amenities, written as a list in text form
    amenities = Column(Text, nullable=True)
    # The date the unit is available from
    available_from = Column(Date, nullable=True)
    # The name people should ask for
    contact_name = Column(String, nullable=True)
    # The phone number people should call (shown publicly)
    contact_phone = Column(String, nullable=True)
    # Whether the building name and exact address are shown publicly
    show_exact_address = Column(Boolean, nullable=False, default=False)
    # Whether the public link works
    is_active = Column(Boolean, nullable=False, default=True)
    # How many times the public page was opened
    views = Column(Integer, nullable=False, default=0)
    # When it was made, and when it was last changed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# This class is the "listing_photos" table. Each photo is one row.
class ListingPhoto(Base):
    # The name of the table inside the database
    __tablename__ = "listing_photos"

    # A unique number for each photo, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The listing it belongs to (points to the listings table)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    # The name the file had on the person's phone
    original_name = Column(String, nullable=False)
    # The type we serve it as
    content_type = Column(String, nullable=False)
    # The size in bytes
    size_bytes = Column(Integer, nullable=False)
    # The random name it is saved under on the server
    stored_name = Column(String, nullable=False, unique=True)
    # Where it sits in the gallery (the first one is the cover)
    position = Column(Integer, nullable=False, default=0)
    # The date and time it was uploaded
    created_at = Column(DateTime, default=datetime.utcnow)


# Clean a phone number (empty stays empty)
def tidy_phone(value: str | None):
    # Nothing was typed
    if value is None or value.strip() == "":
        return None
    # Turn it into the 254... format, or raise an error if it is not valid
    return clean_phone(value)


# The data we ask for when making a listing
class ListingCreate(BaseModel):
    # The unit to advertise
    unit_id: int
    # The headline (empty means we write one)
    title: str | None = Field(default=None, min_length=3, max_length=120)
    # A longer description
    description: str | None = Field(default=None, max_length=2000)
    # The amenities
    amenities: list[str] = Field(default_factory=list, max_length=12)
    # The date it is available from
    available_from: date | None = None
    # The name people should ask for
    contact_name: str | None = Field(default=None, max_length=80)
    # The phone number people should call
    contact_phone: str | None = None
    # Whether to show the building name and exact address
    show_exact_address: bool = False

    # Clean the phone number before saving
    @field_validator("contact_phone")
    @classmethod
    def check_phone(cls, value):
        return tidy_phone(value)


# The data we accept when editing a listing (every field is optional, send only what changed)
class ListingUpdate(BaseModel):
    # New headline
    title: str | None = Field(default=None, min_length=3, max_length=120)
    # New description
    description: str | None = Field(default=None, max_length=2000)
    # New amenities
    amenities: list[str] | None = Field(default=None, max_length=12)
    # New available date (send null to clear it)
    available_from: date | None = None
    # New contact name
    contact_name: str | None = Field(default=None, max_length=80)
    # New contact phone
    contact_phone: str | None = None
    # Show or hide the building name and exact address
    show_exact_address: bool | None = None
    # Switch the public link on or off
    is_active: bool | None = None

    # Clean the phone number before saving
    @field_validator("contact_phone")
    @classmethod
    def check_phone(cls, value):
        return tidy_phone(value)


# A photo's id
class PhotoRef(BaseModel):
    # The photo's id
    id: int


# One listing, as the owner sees it
class OwnerListing(BaseModel):
    # The listing's id
    id: int
    # The unit it advertises
    unit_id: int
    unit_number: str
    unit_type: str | None
    # The property it is in
    property_id: int
    property_name: str
    # The rough area (town and county), safe to put in a message
    location: str | None
    # The unit's money details
    rent_amount: int
    deposit_amount: int
    # "live", "taken" (the unit is no longer empty), or "hidden" (switched off)
    state: str
    # The words
    title: str
    description: str | None
    amenities: list[str]
    available_from: date | None
    # The contact details
    contact_name: str | None
    contact_phone: str | None
    # Privacy and visibility
    show_exact_address: bool
    is_active: bool
    # The secret code in the public link
    token: str
    # How many times the public page was opened
    views: int
    # The photos, the first one is the cover
    photos: list[PhotoRef]
    created_at: datetime
    updated_at: datetime


# An empty unit that has no listing yet
class VacantUnit(BaseModel):
    # The unit
    unit_id: int
    unit_number: str
    unit_type: str | None
    # The property's name
    property_name: str
    # The monthly rent
    rent_amount: int


# Everything the listings page needs
class ListingsOverview(BaseModel):
    # The owner's listings, newest first
    listings: list[OwnerListing]
    # The empty units that could be listed
    vacant_units: list[VacantUnit]


# What anyone with the link sees (no tenant details, ever)
class PublicListing(BaseModel):
    # The words
    title: str
    description: str | None
    amenities: list[str]
    # The unit's details
    unit_type: str | None
    rent_amount: int
    deposit_amount: int
    # The area, or the full address if the owner chose to show it
    location: str | None
    # The building's name (only when the owner chose to show the exact address)
    property_name: str | None
    # False once the unit has been taken
    available: bool
    available_from: date | None
    # The contact details
    contact_name: str | None
    contact_phone: str | None
    # The ids of the photos, in order
    photo_ids: list[int]


# Tidy a list of amenities: no empty ones, no repeats, short, and at most 12
def clean_amenities(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        text = value.strip()[:40]
        if text and text.lower() not in [item.lower() for item in cleaned]:
            cleaned.append(text)
    return cleaned[:12]


# Read the amenities back from the text they are stored as
def amenities_list(listing) -> list[str]:
    try:
        return json.loads(listing.amenities or "[]")
    except ValueError:
        return []


# Get a listing's photos in order
def photo_refs(db: Session, listing_id: int) -> list[PhotoRef]:
    rows = db.query(ListingPhoto).filter(ListingPhoto.listing_id == listing_id).order_by(ListingPhoto.position, ListingPhoto.id).all()
    return [PhotoRef(id=photo.id) for photo in rows]


# Turn a listing into the shape the owner sees
def owner_out(db: Session, listing, unit, prop) -> OwnerListing:
    # Work out the state
    if not listing.is_active:
        state = "hidden"
    elif unit.status == "vacant":
        state = "live"
    else:
        state = "taken"
    return OwnerListing(
        id=listing.id,
        unit_id=unit.id,
        unit_number=unit.unit_number,
        unit_type=unit.unit_type,
        property_id=prop.id,
        property_name=prop.name,
        location=", ".join(part for part in (prop.town, prop.county) if part) or None,
        rent_amount=unit.rent_amount,
        deposit_amount=unit.deposit_amount,
        state=state,
        title=listing.title,
        description=listing.description,
        amenities=amenities_list(listing),
        available_from=listing.available_from,
        contact_name=listing.contact_name,
        contact_phone=listing.contact_phone,
        show_exact_address=bool(listing.show_exact_address),
        is_active=bool(listing.is_active),
        token=listing.token,
        views=listing.views or 0,
        photos=photo_refs(db, listing.id),
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


# Find a listing, but only if it belongs to this owner
def find_listing(db: Session, listing_id: int, owner: models.User):
    row = (
        db.query(Listing, models.Unit, models.Property)
        .join(models.Unit, Listing.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(Listing.id == listing_id, Listing.owner_id == owner.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if row is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return row


# Find a photo, but only if its listing belongs to this owner
def find_owned_photo(db: Session, photo_id: int, owner: models.User):
    photo = (
        db.query(ListingPhoto)
        .join(Listing, ListingPhoto.listing_id == Listing.id)
        .filter(ListingPhoto.id == photo_id, Listing.owner_id == owner.id)
        .first()
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


# Show the owner's listings, and the empty units that have none yet
@router.get("", response_model=ListingsOverview)
def list_listings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can manage listings
    require_owner(current_user)
    rows = (
        db.query(Listing, models.Unit, models.Property)
        .join(models.Unit, Listing.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(Listing.owner_id == current_user.id)
        .order_by(Listing.created_at.desc(), Listing.id.desc())
        .all()
    )
    listed_units = {listing.unit_id for listing, unit, prop in rows}
    # The empty units that are not listed yet
    vacant_rows = (
        db.query(models.Unit, models.Property)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == current_user.id, models.Unit.status == "vacant")
        .order_by(models.Property.name, models.Unit.unit_number)
        .all()
    )
    return ListingsOverview(
        listings=[owner_out(db, listing, unit, prop) for listing, unit, prop in rows],
        vacant_units=[
            VacantUnit(
                unit_id=unit.id,
                unit_number=unit.unit_number,
                unit_type=unit.unit_type,
                property_name=prop.name,
                rent_amount=unit.rent_amount,
            )
            for unit, prop in vacant_rows
            if unit.id not in listed_units
        ],
    )


# Make a listing for an empty unit
@router.post("", response_model=OwnerListing, status_code=201)
def create_listing(
    data: ListingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can make listings
    require_owner(current_user)
    # The unit must be theirs
    row = (
        db.query(models.Unit, models.Property)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Unit.id == data.unit_id, models.Property.owner_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    unit, prop = row
    # Only empty units can be advertised, and only once
    if unit.status != "vacant":
        raise HTTPException(status_code=400, detail="Only empty units can be listed")
    if db.query(Listing).filter(Listing.unit_id == unit.id).first():
        raise HTTPException(status_code=400, detail="This unit already has a listing")
    # Write a headline if none was given
    place = prop.town or prop.county or prop.name
    listing = Listing(
        owner_id=current_user.id,
        unit_id=unit.id,
        token=secrets.token_urlsafe(16),
        title=(data.title or f"{unit.unit_type or 'Unit'} for rent in {place}").strip(),
        description=(data.description or "").strip() or None,
        amenities=json.dumps(clean_amenities(data.amenities)),
        available_from=data.available_from,
        contact_name=(data.contact_name or current_user.full_name).strip(),
        contact_phone=data.contact_phone,
        show_exact_address=data.show_exact_address,
        is_active=True,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return owner_out(db, listing, unit, prop)


# Edit a listing (send only the fields that changed)
@router.put("/{listing_id}", response_model=OwnerListing)
def update_listing(
    listing_id: int,
    data: ListingUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit listings
    require_owner(current_user)
    listing, unit, prop = find_listing(db, listing_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        # These fields cannot be emptied out
        if field in ("title", "show_exact_address", "is_active") and value is None:
            continue
        if field == "amenities":
            value = json.dumps(clean_amenities(value or []))
        elif isinstance(value, str):
            value = value.strip() or None
        setattr(listing, field, value)
    db.commit()
    db.refresh(listing)
    return owner_out(db, listing, unit, prop)


# Make a new secret link (the old one stops working)
@router.post("/{listing_id}/regenerate-link", response_model=OwnerListing)
def regenerate_link(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can do this
    require_owner(current_user)
    listing, unit, prop = find_listing(db, listing_id, current_user)
    listing.token = secrets.token_urlsafe(16)
    db.commit()
    db.refresh(listing)
    return owner_out(db, listing, unit, prop)


# Delete a listing and its photos
@router.delete("/{listing_id}", status_code=204)
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete listings
    require_owner(current_user)
    listing, unit, prop = find_listing(db, listing_id, current_user)
    photos = db.query(ListingPhoto).filter(ListingPhoto.listing_id == listing.id).all()
    names = [photo.stored_name for photo in photos]
    for photo in photos:
        db.delete(photo)
    db.delete(listing)
    db.commit()
    # Delete the picture files last
    for name in names:
        (UPLOAD_DIR / name).unlink(missing_ok=True)


# Add a photo to a listing
@router.post("/{listing_id}/photos", response_model=PhotoRef, status_code=201)
async def upload_photo(
    listing_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add photos
    require_owner(current_user)
    listing, unit, prop = find_listing(db, listing_id, current_user)
    # A listing can only have so many photos
    count = db.query(func.count(ListingPhoto.id)).filter(ListingPhoto.listing_id == listing.id).scalar()
    if count >= MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"A listing can have at most {MAX_PHOTOS} photos")
    # Check the file's ending: only pictures are allowed
    original_name = (file.filename or "photo").split("/")[-1][:200]
    extension = "." + original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only pictures are allowed here (JPG, PNG, or WebP)")
    content_type, family = ALLOWED[extension]
    # Read the file, but never more than the limit
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="This picture is too large. The limit is 10 MB")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="This file is empty")
    # Make sure the inside of the file matches its ending
    if not looks_right(data[:16], family):
        raise HTTPException(status_code=400, detail=f"This file does not look like a real {extension[1:].upper()} picture")
    # Save the file under a random name
    stored_name = f"{uuid.uuid4().hex}{extension}"
    path = UPLOAD_DIR / stored_name
    path.write_bytes(data)
    photo = ListingPhoto(
        listing_id=listing.id,
        original_name=original_name,
        content_type=content_type,
        size_bytes=len(data),
        stored_name=stored_name,
        position=count,
    )
    try:
        db.add(photo)
        db.commit()
    except Exception:
        # If saving the details failed, do not leave the file behind
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(photo)
    return PhotoRef(id=photo.id)


# Get a photo's file for the owner (used by the owner's screens)
@router.get("/photos/{photo_id}/file")
def download_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can open their photos this way
    require_owner(current_user)
    photo = find_owned_photo(db, photo_id, current_user)
    path = UPLOAD_DIR / photo.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="The picture is missing from the server")
    return FileResponse(
        path,
        media_type=photo.content_type,
        filename=photo.original_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


# Delete a photo and its file
@router.delete("/photos/{photo_id}", status_code=204)
def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete photos
    require_owner(current_user)
    photo = find_owned_photo(db, photo_id, current_user)
    stored_name = photo.stored_name
    db.delete(photo)
    db.commit()
    (UPLOAD_DIR / stored_name).unlink(missing_ok=True)


# Find a listing by its secret code, but only if its public link is switched on
def find_public(db: Session, token: str):
    listing = db.query(Listing).filter(Listing.token == token, Listing.is_active.is_(True)).first()
    if listing is None:
        raise HTTPException(status_code=404, detail="This listing is not available")
    return listing


# Write the location for the public page: the area, or the full address if the owner chose to show it
def location_text(listing, prop):
    if listing.show_exact_address:
        full = ", ".join(part for part in (prop.address, prop.town, prop.county) if part)
        return full or None
    return ", ".join(part for part in (prop.town, prop.county) if part) or None


# What anyone with the link sees
@public_router.get("/public/listings/{token}", response_model=PublicListing)
def public_listing(token: str, db: Session = Depends(get_db)):
    listing = find_public(db, token)
    unit = db.get(models.Unit, listing.unit_id)
    prop = db.get(models.Property, unit.property_id)
    # Count the view
    db.query(Listing).filter(Listing.id == listing.id).update({Listing.views: Listing.views + 1})
    db.commit()
    return PublicListing(
        title=listing.title,
        description=listing.description,
        amenities=amenities_list(listing),
        unit_type=unit.unit_type,
        rent_amount=unit.rent_amount,
        deposit_amount=unit.deposit_amount,
        location=location_text(listing, prop),
        property_name=prop.name if listing.show_exact_address else None,
        available=unit.status == "vacant",
        available_from=listing.available_from,
        contact_name=listing.contact_name,
        contact_phone=listing.contact_phone,
        photo_ids=[photo.id for photo in photo_refs(db, listing.id)],
    )


# A photo on the public page (it needs the secret code as well as the photo's number)
@public_router.get("/public/listings/{token}/photos/{photo_id}")
def public_photo(token: str, photo_id: int, db: Session = Depends(get_db)):
    listing = find_public(db, token)
    photo = db.query(ListingPhoto).filter(ListingPhoto.id == photo_id, ListingPhoto.listing_id == listing.id).first()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    path = UPLOAD_DIR / photo.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(
        path,
        media_type=photo.content_type,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=3600"},
    )


# The link people share: a small page with a preview card for WhatsApp, which then opens the real listing page
@public_router.get("/share/{token}", response_class=HTMLResponse)
def share_page(token: str, db: Session = Depends(get_db)):
    listing = find_public(db, token)
    unit = db.get(models.Unit, listing.unit_id)
    prop = db.get(models.Property, unit.property_id)
    # Where the real listing page lives, and where the photos can be fetched from
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    api = os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8000").rstrip("/")
    target = f"{frontend}/l/{listing.token}"
    # Write the preview card (everything typed by people is made safe first)
    title = html.escape(listing.title, quote=True)
    place = location_text(listing, prop)
    description = f"KSh {unit.rent_amount:,} per month" + (f" · {place}" if place else "")
    first = db.query(ListingPhoto).filter(ListingPhoto.listing_id == listing.id).order_by(ListingPhoto.position, ListingPhoto.id).first()
    image = ""
    if first:
        photo_url = html.escape(f"{api}/public/listings/{listing.token}/photos/{first.id}", quote=True)
        image = f'<meta property="og:image" content="{photo_url}">'
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{html.escape(description, quote=True)}">
{image}
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0; url={html.escape(target, quote=True)}">
</head>
<body>
<p>Opening the listing... <a href="{html.escape(target, quote=True)}">Tap here if nothing happens</a></p>
<script>window.location.replace({json.dumps(target)});</script>
</body>
</html>"""
    return HTMLResponse(page)