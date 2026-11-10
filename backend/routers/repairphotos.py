# Import the tools we need
import uuid
from datetime import datetime

# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the tool that counts rows
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user
from repair_photo_models import RepairPhoto
from routers import documents
from routers.maintenance import load_item
from routers.portal import ready_context

# Only pictures are accepted
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
# The most photos on one repair (all people together), and the most a tenant may add to one report
MAX_PHOTOS_PER_REPAIR = 8
MAX_TENANT_PHOTOS_PER_REPAIR = 4

# The endpoints for landlords and caretakers
staff_router = APIRouter(prefix="/maintenance", tags=["Repair photos"])
# The endpoints for tenants
tenant_router = APIRouter(prefix="/portal/repairs", tags=["Repair photos (tenant)"])


# One photo, as we send it back
class PhotoOut(BaseModel):
    id: int
    created_at: datetime
    # True if a tenant added it
    by_tenant: bool
    # Who added it
    uploaded_by_name: str | None
    # Whether the person asking may remove it
    can_delete: bool


# Check a picture and save it: the file goes on the disk, and the details go in the database
async def save_photo(db: Session, repair: models.MaintenanceRequest, uploader: models.User, file: UploadFile) -> RepairPhoto:
    # Count what is there already
    total = db.query(func.count(RepairPhoto.id)).filter(RepairPhoto.repair_id == repair.id).scalar()
    if total >= MAX_PHOTOS_PER_REPAIR:
        raise HTTPException(status_code=400, detail=f"A repair can have at most {MAX_PHOTOS_PER_REPAIR} photos")
    if uploader.role == "tenant":
        own = db.query(func.count(RepairPhoto.id)).filter(RepairPhoto.repair_id == repair.id, RepairPhoto.uploaded_by_id == uploader.id).scalar()
        if own >= MAX_TENANT_PHOTOS_PER_REPAIR:
            raise HTTPException(status_code=400, detail=f"You can add at most {MAX_TENANT_PHOTOS_PER_REPAIR} photos to one report")
    # Check the file's ending: only pictures are allowed
    original_name = (file.filename or "photo").split("/")[-1][:200]
    extension = "." + original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only pictures are allowed here (JPG, PNG, or WebP)")
    content_type, family = documents.ALLOWED[extension]
    # Read the file, but never more than the limit
    data = await file.read(documents.MAX_BYTES + 1)
    if len(data) > documents.MAX_BYTES:
        raise HTTPException(status_code=413, detail="This picture is too large. The limit is 10 MB")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="This file is empty")
    # Make sure the inside of the file matches its ending
    if not documents.looks_right(data[:16], family):
        raise HTTPException(status_code=400, detail=f"This file does not look like a real {extension[1:].upper()} picture")
    # Save the file under a random name, and the details in the database
    stored_name = f"{uuid.uuid4().hex}{extension}"
    path = documents.UPLOAD_DIR / stored_name
    path.write_bytes(data)
    photo = RepairPhoto(
        repair_id=repair.id,
        uploaded_by_id=uploader.id,
        original_name=original_name,
        content_type=content_type,
        size_bytes=len(data),
        stored_name=stored_name,
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
    return photo


# Send a photo's file (private, and never guessed to be anything else)
def send_file(photo: RepairPhoto):
    path = documents.UPLOAD_DIR / photo.stored_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path, media_type=photo.content_type, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


# Find a photo (or say it was not found)
def find_photo(db: Session, photo_id: int) -> RepairPhoto:
    photo = db.get(RepairPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


# ---------- Landlords and caretakers ----------

# Everyone's photos on a repair they may work with
@staff_router.get("/{repair_id}/photos", response_model=list[PhotoOut])
def staff_list(
    repair_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    repair, prop, unit, creator = load_item(db, repair_id, current_user)
    rows = (
        db.query(RepairPhoto, models.User)
        .outerjoin(models.User, RepairPhoto.uploaded_by_id == models.User.id)
        .filter(RepairPhoto.repair_id == repair.id)
        .order_by(RepairPhoto.id)
        .all()
    )
    return [
        PhotoOut(
            id=photo.id,
            created_at=photo.created_at,
            by_tenant=bool(uploader and uploader.role == "tenant"),
            uploaded_by_name=uploader.full_name if uploader else None,
            can_delete=current_user.role == "owner" or photo.uploaded_by_id == current_user.id,
        )
        for photo, uploader in rows
    ]


# Add a photo to a repair
@staff_router.post("/{repair_id}/photos", response_model=PhotoOut, status_code=201)
async def staff_upload(
    repair_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    repair, prop, unit, creator = load_item(db, repair_id, current_user)
    photo = await save_photo(db, repair, current_user, file)
    return PhotoOut(id=photo.id, created_at=photo.created_at, by_tenant=False, uploaded_by_name=current_user.full_name, can_delete=True)


# Get a photo's file
@staff_router.get("/photos/{photo_id}/file")
def staff_file(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    photo = find_photo(db, photo_id)
    # Say "not found" if this person may not work with the repair's property
    load_item(db, photo.repair_id, current_user)
    return send_file(photo)


# Remove a photo (a landlord can remove any; a caretaker only their own)
@staff_router.delete("/photos/{photo_id}", status_code=204)
def staff_delete(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    photo = find_photo(db, photo_id)
    load_item(db, photo.repair_id, current_user)
    if current_user.role != "owner" and photo.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only remove photos you added")
    name = photo.stored_name
    db.delete(photo)
    db.commit()
    (documents.UPLOAD_DIR / name).unlink(missing_ok=True)
    return Response(status_code=204)


# ---------- Tenants ----------

# Find a report that this tenant made themselves
def tenant_repair(db: Session, repair_id: int, user: models.User) -> models.MaintenanceRequest:
    ready_context(db, user)
    repair = db.query(models.MaintenanceRequest).filter(models.MaintenanceRequest.id == repair_id, models.MaintenanceRequest.created_by_id == user.id).first()
    # Say "not found" for missing and for someone else's, so nothing leaks
    if repair is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return repair


# Find a photo that this tenant added themselves, on a report they made
def tenant_photo(db: Session, photo_id: int, user: models.User):
    photo = find_photo(db, photo_id)
    repair = tenant_repair(db, photo.repair_id, user)
    if photo.uploaded_by_id != user.id:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo, repair


# The tenant's own photos on one of their reports
@tenant_router.get("/{repair_id}/photos", response_model=list[PhotoOut])
def tenant_list(
    repair_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    repair = tenant_repair(db, repair_id, current_user)
    photos = db.query(RepairPhoto).filter(RepairPhoto.repair_id == repair.id, RepairPhoto.uploaded_by_id == current_user.id).order_by(RepairPhoto.id).all()
    return [PhotoOut(id=photo.id, created_at=photo.created_at, by_tenant=True, uploaded_by_name=current_user.full_name, can_delete=repair.status != "fixed") for photo in photos]


# Add a photo to one of the tenant's reports (until it is fixed)
@tenant_router.post("/{repair_id}/photos", response_model=PhotoOut, status_code=201)
async def tenant_upload(
    repair_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    repair = tenant_repair(db, repair_id, current_user)
    if repair.status == "fixed":
        raise HTTPException(status_code=400, detail="This problem is already fixed. Please make a new report")
    photo = await save_photo(db, repair, current_user, file)
    return PhotoOut(id=photo.id, created_at=photo.created_at, by_tenant=True, uploaded_by_name=current_user.full_name, can_delete=True)


# Get one of the tenant's own photos
@tenant_router.get("/photos/{photo_id}/file")
def tenant_file(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    photo, repair = tenant_photo(db, photo_id, current_user)
    return send_file(photo)


# Remove one of the tenant's own photos (until the report is fixed)
@tenant_router.delete("/photos/{photo_id}", status_code=204)
def tenant_delete(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    photo, repair = tenant_photo(db, photo_id, current_user)
    if repair.status == "fixed":
        raise HTTPException(status_code=400, detail="This problem is already fixed")
    name = photo.stored_name
    db.delete(photo)
    db.commit()
    (documents.UPLOAD_DIR / name).unlink(missing_ok=True)
    return Response(status_code=204)