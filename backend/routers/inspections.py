# Import the tool that groups things together
from collections import defaultdict
# Import the tool that makes random names
import uuid
# Import the date and time tools
from datetime import date, datetime
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints, errors, and file uploads
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the column types and tools we need for the tables
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from access import property_scope
from database import Base
from dependencies import get_db, get_current_user
# Reuse the file safety tools from the documents feature
from routers.documents import ALLOWED, MAX_BYTES, UPLOAD_DIR, looks_right
from routers.properties import require_owner

# Make a group of endpoints that all start with /inspections
router = APIRouter(prefix="/inspections", tags=["Inspections"])

# Only pictures are accepted as photos
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
# The most photos for one area, and for one whole checklist
MAX_PHOTOS_PER_ITEM = 8
MAX_PHOTOS_PER_INSPECTION = 60
# The most areas on one checklist
MAX_ITEMS = 40

# The areas every new checklist starts with
DEFAULT_AREAS = [
    "Walls and paint",
    "Ceiling",
    "Floor",
    "Doors and locks",
    "Windows and curtain rails",
    "Electrical sockets and switches",
    "Lights and bulbs",
    "Kitchen sink and taps",
    "Cupboards and shelves",
    "Toilet",
    "Shower and bathroom",
    "Water supply",
    "Keys handed over",
]


# This class is the "inspections" table. Each move-in or move-out checklist is one row.
class Inspection(Base):
    # The name of the table inside the database
    __tablename__ = "inspections"
    # Rule: a lease can only have one move-in and one move-out checklist
    __table_args__ = (UniqueConstraint("lease_id", "kind", name="one_inspection_per_lease_and_kind"),)

    # A unique number for each checklist, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The lease it is about (points to the leases table)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    # "move_in" or "move_out"
    kind = Column(String, nullable=False)
    # The day the walkthrough was done
    done_on = Column(Date, nullable=False)
    # General notes
    notes = Column(Text, nullable=True)
    # Whether the tenant was there for the walkthrough
    tenant_present = Column(Boolean, nullable=False, default=False)
    # Anything the tenant wanted to say
    tenant_comment = Column(Text, nullable=True)
    # When the checklist was locked (empty while it can still be changed)
    finalized_at = Column(DateTime, nullable=True)
    # The user who started it (points to the users table)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The date and time it was started
    created_at = Column(DateTime, default=datetime.utcnow)


# This class is the "inspection_items" table. Each area on a checklist is one row.
class InspectionItem(Base):
    # The name of the table inside the database
    __tablename__ = "inspection_items"

    # A unique number for each area, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The checklist it belongs to (points to the inspections table)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False)
    # The name of the area, like "Walls and paint"
    area = Column(String, nullable=False)
    # How it looks: "good", "fair", "poor", "damaged" (empty until it is rated)
    condition = Column(String, nullable=True)
    # A note about it
    note = Column(Text, nullable=True)
    # Where it sits in the list
    position = Column(Integer, nullable=False, default=0)


# This class is the "inspection_photos" table. Each photo is one row.
class InspectionPhoto(Base):
    # The name of the table inside the database
    __tablename__ = "inspection_photos"

    # A unique number for each photo, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The checklist it belongs to (points to the inspections table)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False)
    # The area it shows (empty means a general photo)
    item_id = Column(Integer, ForeignKey("inspection_items.id"), nullable=True)
    # A short caption
    caption = Column(String, nullable=True)
    # The name the file had on the person's phone
    original_name = Column(String, nullable=False)
    # The type we serve it as
    content_type = Column(String, nullable=False)
    # The size in bytes
    size_bytes = Column(Integer, nullable=False)
    # The random name it is saved under on the server
    stored_name = Column(String, nullable=False, unique=True)
    # The user who uploaded it (points to the users table)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The date and time it was uploaded
    created_at = Column(DateTime, default=datetime.utcnow)


# One photo, as we send it back
class PhotoOut(BaseModel):
    # The photo's id
    id: int
    # The area it shows (empty means a general photo)
    item_id: int | None
    # Its caption
    caption: str | None
    # When it was uploaded
    created_at: datetime


# One area, as we send it back
class ItemOut(BaseModel):
    # The area's id
    id: int
    # Its name
    area: str
    # Its rating (empty until it is rated)
    condition: str | None
    # Its note
    note: str | None
    # The photos of this area
    photos: list[PhotoOut]


# One checklist, as we send it back
class InspectionOut(BaseModel):
    # The checklist's id
    id: int
    # The lease it is about
    lease_id: int
    # "move_in" or "move_out"
    kind: str
    # The day the walkthrough was done
    done_on: date
    # General notes
    notes: str | None
    # Whether the tenant was there
    tenant_present: bool
    # Anything the tenant wanted to say
    tenant_comment: str | None
    # When it was locked (empty while it can still be changed)
    finalized_at: datetime | None
    # The name of the person who started it
    created_by_name: str | None
    # The areas, in order
    items: list[ItemOut]
    # Photos that are not tied to one area
    general_photos: list[PhotoOut]


# A short description of the lease the checklist is about (no money in here)
class LeaseBrief(BaseModel):
    # The lease's id
    lease_id: int
    # The tenant's id and name
    tenant_id: int
    tenant_name: str
    # The unit and property
    unit_number: str
    property_name: str
    # The lease dates and status
    start_date: date
    end_date: date | None
    status: str


# Both checklists of one lease
class LeaseInspections(BaseModel):
    # The lease
    lease: LeaseBrief
    # The move-in checklist (empty if not started)
    move_in: InspectionOut | None
    # The move-out checklist (empty if not started)
    move_out: InspectionOut | None
    # True if this person can unlock and delete checklists (owners only)
    can_unlock: bool


# The data we ask for when starting a checklist
class InspectionCreate(BaseModel):
    # The day the walkthrough is done (empty means today)
    done_on: date | None = None
    # General notes (optional)
    notes: str | None = Field(default=None, max_length=1000)


# The data we accept when editing a checklist (every field is optional, send only what changed)
class InspectionUpdate(BaseModel):
    # New date
    done_on: date | None = None
    # New notes
    notes: str | None = Field(default=None, max_length=1000)
    # Whether the tenant was there
    tenant_present: bool | None = None
    # Anything the tenant wanted to say
    tenant_comment: str | None = Field(default=None, max_length=1000)


# The data we ask for when adding an area
class ItemCreate(BaseModel):
    # The name of the area
    area: str = Field(min_length=2, max_length=80)


# The data we accept when editing an area (send only what changed; null clears it)
class ItemUpdate(BaseModel):
    # The rating
    condition: Literal["good", "fair", "poor", "damaged"] | None = None
    # The note
    note: str | None = Field(default=None, max_length=300)


# Find a lease this person may work with, together with its unit, property, and tenant
def scoped_lease(db: Session, lease_id: int, user: models.User):
    # Which properties may this person work with?
    scope = property_scope(db, user)
    row = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Lease.id == lease_id, models.Property.id.in_(scope))
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if row is None:
        raise HTTPException(status_code=404, detail="Lease not found")
    return row


# Find a checklist this person may work with
def scoped_inspection(db: Session, inspection_id: int, user: models.User):
    scope = property_scope(db, user)
    inspection = (
        db.query(Inspection)
        .join(models.Lease, Inspection.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(Inspection.id == inspection_id, models.Unit.property_id.in_(scope))
        .first()
    )
    if inspection is None:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return inspection


# Find an area this person may work with, together with its checklist
def scoped_item(db: Session, item_id: int, user: models.User):
    scope = property_scope(db, user)
    row = (
        db.query(InspectionItem, Inspection)
        .join(Inspection, InspectionItem.inspection_id == Inspection.id)
        .join(models.Lease, Inspection.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(InspectionItem.id == item_id, models.Unit.property_id.in_(scope))
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Area not found")
    return row


# Find a photo this person may work with, together with its checklist
def scoped_photo(db: Session, photo_id: int, user: models.User):
    scope = property_scope(db, user)
    row = (
        db.query(InspectionPhoto, Inspection)
        .join(Inspection, InspectionPhoto.inspection_id == Inspection.id)
        .join(models.Lease, Inspection.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(InspectionPhoto.id == photo_id, models.Unit.property_id.in_(scope))
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return row


# Refuse changes to a checklist that has been locked
def ensure_open(inspection: Inspection):
    if inspection.finalized_at is not None:
        raise HTTPException(status_code=409, detail="This checklist is locked. Ask the owner to unlock it to make changes")


# Turn a checklist, its areas, and its photos into the shape we send back
def build_out(db: Session, inspection: Inspection) -> InspectionOut:
    # The areas in order
    items = (
        db.query(InspectionItem)
        .filter(InspectionItem.inspection_id == inspection.id)
        .order_by(InspectionItem.position, InspectionItem.id)
        .all()
    )
    # The photos, grouped by area
    photos = (
        db.query(InspectionPhoto)
        .filter(InspectionPhoto.inspection_id == inspection.id)
        .order_by(InspectionPhoto.created_at, InspectionPhoto.id)
        .all()
    )
    by_item = defaultdict(list)
    general = []
    for photo in photos:
        out = PhotoOut(id=photo.id, item_id=photo.item_id, caption=photo.caption, created_at=photo.created_at)
        if photo.item_id is None:
            general.append(out)
        else:
            by_item[photo.item_id].append(out)
    creator = db.get(models.User, inspection.created_by_id) if inspection.created_by_id else None
    return InspectionOut(
        id=inspection.id,
        lease_id=inspection.lease_id,
        kind=inspection.kind,
        done_on=inspection.done_on,
        notes=inspection.notes,
        tenant_present=bool(inspection.tenant_present),
        tenant_comment=inspection.tenant_comment,
        finalized_at=inspection.finalized_at,
        created_by_name=creator.full_name if creator else None,
        items=[
            ItemOut(id=item.id, area=item.area, condition=item.condition, note=item.note, photos=by_item[item.id])
            for item in items
        ],
        general_photos=general,
    )


# Get both checklists of a lease
@router.get("/lease/{lease_id}", response_model=LeaseInspections)
def lease_inspections(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find the lease, but only if this person may work with its property
    lease, unit, prop, tenant = scoped_lease(db, lease_id, current_user)
    found = {item.kind: item for item in db.query(Inspection).filter(Inspection.lease_id == lease.id).all()}
    return LeaseInspections(
        lease=LeaseBrief(
            lease_id=lease.id,
            tenant_id=tenant.id,
            tenant_name=tenant.full_name,
            unit_number=unit.unit_number,
            property_name=prop.name,
            start_date=lease.start_date,
            end_date=lease.end_date,
            status=lease.status,
        ),
        move_in=build_out(db, found["move_in"]) if "move_in" in found else None,
        move_out=build_out(db, found["move_out"]) if "move_out" in found else None,
        can_unlock=current_user.role == "owner",
    )


# Start a move-in or move-out checklist
@router.post("/lease/{lease_id}/{kind}", response_model=InspectionOut, status_code=201)
def start_inspection(
    lease_id: int,
    kind: Literal["move_in", "move_out"],
    data: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find the lease, but only if this person may work with its property
    lease, unit, prop, tenant = scoped_lease(db, lease_id, current_user)
    # A lease can only have one checklist of each kind
    exists = db.query(Inspection).filter(Inspection.lease_id == lease.id, Inspection.kind == kind).first()
    if exists:
        raise HTTPException(status_code=400, detail="This checklist has already been started")
    # Build the checklist
    inspection = Inspection(
        lease_id=lease.id,
        kind=kind,
        done_on=data.done_on or date.today(),
        notes=(data.notes or "").strip() or None,
        created_by_id=current_user.id,
    )
    db.add(inspection)
    db.flush()
    # Start it with the usual areas
    for position, area in enumerate(DEFAULT_AREAS):
        db.add(InspectionItem(inspection_id=inspection.id, area=area, position=position))
    db.commit()
    db.refresh(inspection)
    # Send it back
    return build_out(db, inspection)


# Edit a checklist's date, notes, or the tenant's details
@router.put("/{inspection_id}", response_model=InspectionOut)
def update_inspection(
    inspection_id: int,
    data: InspectionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if this person may work with it
    inspection = scoped_inspection(db, inspection_id, current_user)
    # A locked checklist cannot be changed
    ensure_open(inspection)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        # These fields cannot be emptied out
        if field in ("done_on", "tenant_present") and value is None:
            continue
        # Tidy up text (empty text becomes "nothing")
        if isinstance(value, str):
            value = value.strip() or None
        setattr(inspection, field, value)
    db.commit()
    db.refresh(inspection)
    return build_out(db, inspection)


# Lock a checklist so nothing can be changed (every area must be rated first)
@router.post("/{inspection_id}/finalize", response_model=InspectionOut)
def finalize_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if this person may work with it
    inspection = scoped_inspection(db, inspection_id, current_user)
    # Count the areas that are not rated yet
    items = db.query(InspectionItem).filter(InspectionItem.inspection_id == inspection.id).all()
    missing = sum(1 for item in items if item.condition is None)
    if missing:
        raise HTTPException(status_code=400, detail=f"Rate every area first ({missing} left)")
    # Lock it (locking twice changes nothing)
    if inspection.finalized_at is None:
        inspection.finalized_at = datetime.utcnow()
        db.commit()
        db.refresh(inspection)
    return build_out(db, inspection)


# Unlock a checklist (owners only)
@router.post("/{inspection_id}/unlock", response_model=InspectionOut)
def unlock_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can unlock
    require_owner(current_user)
    # Find it, but only if it is theirs
    inspection = scoped_inspection(db, inspection_id, current_user)
    inspection.finalized_at = None
    db.commit()
    db.refresh(inspection)
    return build_out(db, inspection)


# Add an area to a checklist
@router.post("/{inspection_id}/items", response_model=InspectionOut, status_code=201)
def add_item(
    inspection_id: int,
    data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if this person may work with it
    inspection = scoped_inspection(db, inspection_id, current_user)
    ensure_open(inspection)
    # Look at the areas already there
    items = db.query(InspectionItem).filter(InspectionItem.inspection_id == inspection.id).all()
    if len(items) >= MAX_ITEMS:
        raise HTTPException(status_code=400, detail="This checklist already has the most areas allowed")
    area = data.area.strip()
    if len(area) < 2:
        raise HTTPException(status_code=400, detail="The name of the area is too short")
    if any(item.area.lower() == area.lower() for item in items):
        raise HTTPException(status_code=400, detail="This area is already on the list")
    # Add it at the end
    position = max([item.position for item in items] + [-1]) + 1
    db.add(InspectionItem(inspection_id=inspection.id, area=area, position=position))
    db.commit()
    return build_out(db, inspection)


# Rate an area or change its note
@router.put("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if this person may work with it
    item, inspection = scoped_item(db, item_id, current_user)
    ensure_open(inspection)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    # Send it back with its photos
    photos = db.query(InspectionPhoto).filter(InspectionPhoto.item_id == item.id).order_by(InspectionPhoto.id).all()
    return ItemOut(
        id=item.id,
        area=item.area,
        condition=item.condition,
        note=item.note,
        photos=[PhotoOut(id=p.id, item_id=p.item_id, caption=p.caption, created_at=p.created_at) for p in photos],
    )


# Remove an area (and its photos)
@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if this person may work with it
    item, inspection = scoped_item(db, item_id, current_user)
    ensure_open(inspection)
    # Delete its photos and their files
    photos = db.query(InspectionPhoto).filter(InspectionPhoto.item_id == item.id).all()
    names = [photo.stored_name for photo in photos]
    for photo in photos:
        db.delete(photo)
    db.delete(item)
    db.commit()
    for name in names:
        (UPLOAD_DIR / name).unlink(missing_ok=True)


# Upload a photo to a checklist
@router.post("/{inspection_id}/photos", response_model=PhotoOut, status_code=201)
async def upload_photo(
    inspection_id: int,
    file: UploadFile = File(...),
    item_id: int | None = Form(default=None),
    caption: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find the checklist, but only if this person may work with it
    inspection = scoped_inspection(db, inspection_id, current_user)
    ensure_open(inspection)
    # If an area was given, make sure it is on this checklist
    if item_id is not None:
        item = db.query(InspectionItem).filter(InspectionItem.id == item_id, InspectionItem.inspection_id == inspection.id).first()
        if item is None:
            raise HTTPException(status_code=400, detail="That area is not on this checklist")
        count_here = db.query(func.count(InspectionPhoto.id)).filter(InspectionPhoto.item_id == item_id).scalar()
        if count_here >= MAX_PHOTOS_PER_ITEM:
            raise HTTPException(status_code=400, detail=f"An area can have at most {MAX_PHOTOS_PER_ITEM} photos")
    # Count the photos on the whole checklist
    total = db.query(func.count(InspectionPhoto.id)).filter(InspectionPhoto.inspection_id == inspection.id).scalar()
    if total >= MAX_PHOTOS_PER_INSPECTION:
        raise HTTPException(status_code=400, detail=f"A checklist can have at most {MAX_PHOTOS_PER_INSPECTION} photos")
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
    # Save the details in the database
    photo = InspectionPhoto(
        inspection_id=inspection.id,
        item_id=item_id,
        caption=(caption or "").strip()[:150] or None,
        original_name=original_name,
        content_type=content_type,
        size_bytes=len(data),
        stored_name=stored_name,
        uploaded_by_id=current_user.id,
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
    return PhotoOut(id=photo.id, item_id=photo.item_id, caption=photo.caption, created_at=photo.created_at)


# Get a photo's file (only for people who may work with its property)
@router.get("/photos/{photo_id}/file")
def download_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if this person may work with it
    photo, inspection = scoped_photo(db, photo_id, current_user)
    # Find the file on the server
    path = UPLOAD_DIR / photo.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="The picture is missing from the server")
    # Send it, shown in the browser
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
    # Find it, but only if this person may work with it
    photo, inspection = scoped_photo(db, photo_id, current_user)
    ensure_open(inspection)
    stored_name = photo.stored_name
    # Delete the details first, then the file
    db.delete(photo)
    db.commit()
    (UPLOAD_DIR / stored_name).unlink(missing_ok=True)


# Delete a whole checklist with its areas and photos (owners only)
@router.delete("/{inspection_id}", status_code=204)
def delete_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete a checklist
    require_owner(current_user)
    # Find it, but only if it is theirs
    inspection = scoped_inspection(db, inspection_id, current_user)
    # Delete its photos, areas, and then the checklist itself
    photos = db.query(InspectionPhoto).filter(InspectionPhoto.inspection_id == inspection.id).all()
    names = [photo.stored_name for photo in photos]
    for photo in photos:
        db.delete(photo)
    for item in db.query(InspectionItem).filter(InspectionItem.inspection_id == inspection.id).all():
        db.delete(item)
    db.delete(inspection)
    db.commit()
    # Delete the picture files last
    for name in names:
        (UPLOAD_DIR / name).unlink(missing_ok=True)