# Import the tool that makes random names
import uuid
# Import the date and time tools
from datetime import date, datetime, timedelta
# Import the tool that works with file paths
from pathlib import Path
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints, errors, and file uploads
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the column types we need for the table
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from database import Base
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.properties import get_owned_property, require_owner
from routers.tenants import get_owned_tenant

# Make a group of endpoints that all start with /documents
router = APIRouter(prefix="/documents", tags=["Documents"])

# The folder where uploaded files are kept (it is created if it does not exist)
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# The biggest file we accept: 10 MB
MAX_BYTES = 10 * 1024 * 1024

# The kinds of document we know about
KIND_VALUES = ("lease_agreement", "title_deed", "permit", "insurance", "id_copy", "receipt", "other")
KindType = Literal["lease_agreement", "title_deed", "permit", "insurance", "id_copy", "receipt", "other"]

# The file endings we accept, with the type we will serve them as and the kind of file we expect inside
ALLOWED = {
    ".pdf": ("application/pdf", "pdf"),
    ".jpg": ("image/jpeg", "jpeg"),
    ".jpeg": ("image/jpeg", "jpeg"),
    ".png": ("image/png", "png"),
    ".webp": ("image/webp", "webp"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "zip"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "zip"),
    ".doc": ("application/msword", "ole"),
    ".xls": ("application/vnd.ms-excel", "ole"),
}


# This class is the "documents" table. Each uploaded file is one row.
class Document(Base):
    # The name of the table inside the database
    __tablename__ = "documents"

    # A unique number for each document, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner this document belongs to (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The property it is about (optional)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    # The tenant it is about (optional)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    # What kind of document it is
    kind = Column(String, nullable=False, default="other")
    # A name for it, like "Kinoru title deed"
    title = Column(String, nullable=False)
    # The name the file had on the person's computer
    original_name = Column(String, nullable=False)
    # The type we serve it as, like "application/pdf"
    content_type = Column(String, nullable=False)
    # The size in bytes
    size_bytes = Column(Integer, nullable=False)
    # The random name it is saved under on the server
    stored_name = Column(String, nullable=False, unique=True)
    # The date it expires (for permits, insurance, and so on)
    expires_on = Column(Date, nullable=True)
    # The user who uploaded it (points to the users table)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The date and time it was uploaded
    created_at = Column(DateTime, default=datetime.utcnow)


# The data we accept when editing a document's details
class DocumentUpdate(BaseModel):
    # New title
    title: str | None = Field(default=None, min_length=1, max_length=150)
    # New kind
    kind: KindType | None = None
    # New expiry date (send null to clear it)
    expires_on: date | None = None


# The data we send back about a document
class DocumentOut(BaseModel):
    # The document's id
    id: int
    # Its title
    title: str
    # Its kind
    kind: str
    # The name the file had on the person's computer
    original_name: str
    # The type it is served as
    content_type: str
    # The size in bytes
    size_bytes: int
    # The property it is about
    property_id: int | None
    property_name: str | None
    # The tenant it is about
    tenant_id: int | None
    tenant_name: str | None
    # The date it expires
    expires_on: date | None
    # How many days until it expires (negative means it already expired)
    days_to_expiry: int | None
    # The name of the person who uploaded it
    uploaded_by_name: str | None
    # When it was uploaded
    created_at: datetime


# Check that the first bytes of a file match what its ending claims it is
def looks_right(head: bytes, family: str) -> bool:
    # A PDF starts with "%PDF"
    if family == "pdf":
        return head.startswith(b"%PDF")
    # A JPEG starts with these three bytes
    if family == "jpeg":
        return head.startswith(b"\xff\xd8\xff")
    # A PNG starts with this fixed signature
    if family == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    # A WebP is a "RIFF" file with "WEBP" inside
    if family == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    # Word and Excel files (.docx, .xlsx) are zip files
    if family == "zip":
        return head.startswith(b"PK\x03\x04")
    # Old Word and Excel files (.doc, .xls) have this signature
    if family == "ole":
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    # Anything else is not allowed
    return False


# Turn a document and its related rows into the shape we send back
def to_out(document, prop, tenant, uploader) -> DocumentOut:
    # How many days until it expires
    days = (document.expires_on - date.today()).days if document.expires_on else None
    return DocumentOut(
        id=document.id,
        title=document.title,
        kind=document.kind,
        original_name=document.original_name,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        property_id=document.property_id,
        property_name=prop.name if prop else None,
        tenant_id=document.tenant_id,
        tenant_name=tenant.full_name if tenant else None,
        expires_on=document.expires_on,
        days_to_expiry=days,
        uploaded_by_name=uploader.full_name if uploader else None,
        created_at=document.created_at,
    )


# Find a document, but only if it belongs to this owner
def find_document(db: Session, document_id: int, owner: models.User):
    # Look for a document with this id AND this owner
    document = db.query(Document).filter(Document.id == document_id, Document.owner_id == owner.id).first()
    # Say "not found" for missing and for someone else's, so nothing leaks
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Hand back the document
    return document


# List this owner's documents (optionally one kind, one property, one tenant, or only the ones about to expire)
@router.get("", response_model=list[DocumentOut])
def list_documents(
    kind: KindType | None = Query(default=None),
    property_id: int | None = Query(default=None),
    tenant_id: int | None = Query(default=None),
    expiring: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see documents
    require_owner(current_user)
    # Always start with only this owner's documents
    conditions = [Document.owner_id == current_user.id]
    if kind:
        conditions.append(Document.kind == kind)
    if property_id:
        conditions.append(Document.property_id == property_id)
    if tenant_id:
        conditions.append(Document.tenant_id == tenant_id)
    # "Expiring" means it has an expiry date within the next 30 days (or already passed)
    if expiring:
        conditions.append(Document.expires_on.isnot(None))
        conditions.append(Document.expires_on <= date.today() + timedelta(days=30))
    query = (
        db.query(Document, models.Property, models.Tenant, models.User)
        .outerjoin(models.Property, Document.property_id == models.Property.id)
        .outerjoin(models.Tenant, Document.tenant_id == models.Tenant.id)
        .outerjoin(models.User, Document.uploaded_by_id == models.User.id)
        .filter(*conditions)
    )
    # The ones about to expire come first, otherwise the newest come first
    if expiring:
        query = query.order_by(Document.expires_on, Document.id)
    else:
        query = query.order_by(Document.created_at.desc(), Document.id.desc())
    rows = query.limit(500).all()
    # Send them back
    return [to_out(document, prop, tenant, uploader) for document, prop, tenant, uploader in rows]


# Upload a document
@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=150),
    kind: str = Form(default="other"),
    property_id: int | None = Form(default=None),
    tenant_id: int | None = Form(default=None),
    expires_on: date | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can upload documents
    require_owner(current_user)
    # The kind must be one we know
    if kind not in KIND_VALUES:
        raise HTTPException(status_code=400, detail="Choose a valid kind of document")
    # Clean up the file's name and find its ending
    original_name = Path(file.filename or "").name[:200]
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED:
        raise HTTPException(status_code=400, detail="This file type is not allowed. Use PDF, JPG, PNG, WebP, Word, or Excel")
    content_type, family = ALLOWED[extension]
    # Read the file, but never more than the limit (plus one byte, to know if it was too big)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="This file is too large. The limit is 10 MB")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="This file is empty")
    # Make sure the inside of the file matches its ending
    if not looks_right(data[:16], family):
        raise HTTPException(status_code=400, detail=f"This file does not look like a real {extension[1:].upper()} file")
    # If a property or tenant was given, make sure they are theirs
    prop = get_owned_property(db, property_id, current_user) if property_id is not None else None
    tenant = get_owned_tenant(db, tenant_id, current_user) if tenant_id is not None else None
    # Save the file under a random name
    stored_name = f"{uuid.uuid4().hex}{extension}"
    path = UPLOAD_DIR / stored_name
    path.write_bytes(data)
    # Save the details in the database
    document = Document(
        owner_id=current_user.id,
        property_id=prop.id if prop else None,
        tenant_id=tenant.id if tenant else None,
        kind=kind,
        title=title.strip() or original_name,
        original_name=original_name,
        content_type=content_type,
        size_bytes=len(data),
        stored_name=stored_name,
        expires_on=expires_on,
        uploaded_by_id=current_user.id,
    )
    try:
        db.add(document)
        db.commit()
    except Exception:
        # If saving the details failed, do not leave the file behind
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(document)
    # Send it back
    return to_out(document, prop, tenant, current_user)


# Get the file itself (only for its owner)
@router.get("/{document_id}/file")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can open documents
    require_owner(current_user)
    # Find it, but only if it is theirs
    document = find_document(db, document_id, current_user)
    # Find the file on the server
    path = UPLOAD_DIR / document.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="The file is missing from the server")
    # Send it, shown in the browser where possible
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


# Edit a document's details (send only the fields that changed)
@router.put("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit documents
    require_owner(current_user)
    # Find it, but only if it is theirs
    document = find_document(db, document_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # Apply each change
    for field, value in changes.items():
        # The title and kind cannot be emptied out
        if field in ("title", "kind") and value is None:
            continue
        # Tidy up the title
        if field == "title":
            value = value.strip()
            if not value:
                raise HTTPException(status_code=400, detail="The title cannot be empty")
        # Save the new value
        setattr(document, field, value)
    # Save the changes
    db.commit()
    db.refresh(document)
    # Send it back
    prop = db.get(models.Property, document.property_id) if document.property_id else None
    tenant = db.get(models.Tenant, document.tenant_id) if document.tenant_id else None
    uploader = db.get(models.User, document.uploaded_by_id) if document.uploaded_by_id else None
    return to_out(document, prop, tenant, uploader)


# Delete a document and its file
@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete documents
    require_owner(current_user)
    # Find it, but only if it is theirs
    document = find_document(db, document_id, current_user)
    stored_name = document.stored_name
    # Delete the details first, then the file
    db.delete(document)
    db.commit()
    (UPLOAD_DIR / stored_name).unlink(missing_ok=True)