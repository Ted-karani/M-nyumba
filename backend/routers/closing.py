# Import the tools we need
import secrets
from datetime import date, datetime, timedelta
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the tool for deleting rows
from sqlalchemy import delete
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import security
from admin_models import log_admin
from dependencies import get_db
from ownership import collect, erase, member_user_ids, stored_files
from routers import documents
from routers.admin import find_owner, require_admin
from security_models import LoginAttempt

# The endpoints for closing and deleting a landlord's account (admin only)
closing_router = APIRouter(prefix="/admin", tags=["Admin: closing accounts"])

# How long a landlord has to download their data before the account can be deleted
CLOSING_DAYS = 30
# An account can only be closing or deleted when it is already switched off in one of these ways
LIMITED = ("read_only", "suspended", "closed")


# Where closing stands for one landlord (counts only, never anyone's details)
class ClosingState(BaseModel):
    # The landlord
    owner_id: int
    full_name: str
    email: str
    status: str
    # True while closing is running
    closing: bool
    closing_started_at: datetime | None
    # The first day the account may be deleted, and how many days are left (0 or less means now)
    delete_allowed_on: date | None
    days_left: int | None
    can_delete: bool
    # How many records of each kind would be deleted, and how many files
    counts: dict[str, int]
    files: int


# The data we accept when starting to close
class StartClosing(BaseModel):
    # An extra sentence for the landlord (optional)
    note: str | None = Field(default=None, max_length=200)


# The data we ask for when deleting
class DeleteRequest(BaseModel):
    # The landlord's email, typed to be sure
    confirm_email: str = Field(min_length=3, max_length=200)
    # Delete before the closing days are over (only when the landlord asked for it)
    force: bool = False


# What we send back after deleting
class DeleteResult(BaseModel):
    rows_deleted: int
    files_deleted: int


# Hide most of an email, for the admin log: grace@example.com becomes g***@example.com
def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


# Work out where closing stands
def state_for(db: Session, owner: models.User, account) -> ClosingState:
    marked = collect(db, owner.id)
    started = account.closing_started_at if account.status in LIMITED else None
    allowed_on = (started + timedelta(days=CLOSING_DAYS)).date() if started else None
    days_left = (allowed_on - date.today()).days if allowed_on else None
    return ClosingState(
        owner_id=owner.id,
        full_name=owner.full_name,
        email=owner.email,
        status=account.status,
        closing=started is not None,
        closing_started_at=started,
        delete_allowed_on=allowed_on,
        days_left=days_left,
        can_delete=days_left is not None and days_left <= 0,
        counts={name: len(ids) for name, ids in sorted(marked.items())},
        files=len(stored_files(db, marked)),
    )


# Where does closing stand?
@closing_router.get("/accounts/{owner_id}/closing", response_model=ClosingState)
def closing_state(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    return state_for(db, owner, account)


# Start closing: the account becomes read-only, and the landlord has 30 days to download their data
@closing_router.post("/accounts/{owner_id}/start-closing", response_model=ClosingState)
def start_closing(
    owner_id: int,
    data: StartClosing,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    if account.closing_started_at is not None and account.status in LIMITED:
        raise HTTPException(status_code=400, detail="Closing has already started for this landlord")
    deadline = (datetime.utcnow() + timedelta(days=CLOSING_DAYS)).date()
    message = f"Your account is closing. Please download a copy of your data (My account, then Download my data) before {deadline.strftime('%d %b %Y')}. After that it will be deleted."
    if data.note and data.note.strip():
        message += " " + data.note.strip()
    account.status = "read_only"
    account.status_note = message[:300]
    account.closing_started_at = datetime.utcnow()
    log_admin(db, admin, owner.id, "Started closing an account", f"{CLOSING_DAYS} days to download their data")
    db.commit()
    return state_for(db, owner, account)


# Stop closing: the account is active again
@closing_router.post("/accounts/{owner_id}/cancel-closing", response_model=ClosingState)
def cancel_closing(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    account.closing_started_at = None
    account.status = "active"
    account.status_note = None
    log_admin(db, admin, owner.id, "Cancelled closing an account", None)
    db.commit()
    return state_for(db, owner, account)


# Delete the account for good: everything of theirs goes, and only what we must keep stays
@closing_router.post("/accounts/{owner_id}/delete", response_model=DeleteResult)
def delete_account(
    owner_id: int,
    data: DeleteRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    # The admin must type the landlord's email
    if data.confirm_email.strip().lower() != owner.email.lower():
        raise HTTPException(status_code=400, detail="The email you typed does not match this landlord's email")
    # An account that is in use can never be deleted
    if account.status not in LIMITED:
        raise HTTPException(status_code=400, detail="Switch the account off first: start closing it, or set it to read-only or suspended")
    # The 30 days must be over, unless the admin says the landlord asked for it
    state = state_for(db, owner, account)
    if not state.can_delete and not data.force:
        left = f"{state.days_left} more day(s)" if state.days_left is not None else "the closing period"
        raise HTTPException(
            status_code=400,
            detail=f"The {CLOSING_DAYS} days to download their data are not over ({left}). Delete earlier only if the landlord asked for it, with the override",
        )
    marked = collect(db, owner.id)
    files = stored_files(db, marked)
    total = sum(len(ids) for ids in marked.values())
    members = member_user_ids(db, owner.id)
    emails = [owner.email]
    if members:
        emails += [row[0] for row in db.query(models.User.email).filter(models.User.id.in_(members)).all()]
    masked = mask_email(owner.email)
    owner_number = owner.id
    try:
        # Delete everything of theirs, in one go
        erase(db, marked)
        db.execute(delete(LoginAttempt).where(LoginAttempt.email.in_(emails)))
        # Check that nothing of theirs is left (if there is, undo everything)
        leftover = collect(db, owner_number)
        if leftover:
            raise RuntimeError("some records were left behind: " + ", ".join(sorted(leftover)))
        # The login row stays, but with no personal details (our records of what they paid us point at it)
        owner.full_name = "Deleted account"
        owner.email = f"deleted-{owner_number}@deleted.invalid"
        owner.phone = None
        owner.password_hash = security.hash_password(secrets.token_urlsafe(32))
        owner.role = "deleted"
        owner.is_active = False
        account.status = "closed"
        account.status_note = None
        account.notes = None
        account.unit_limit = None
        account.must_change_password = False
        account.closing_started_at = None
        account.closed_at = datetime.utcnow()
        log_admin(db, admin, owner_number, "Deleted an account", f"{masked} (id {owner_number}): {total} records and {len(files)} files removed")
        db.commit()
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Nothing was deleted, because something went wrong: {error}")
    # Now that the database is final, remove the files from the disk
    removed = 0
    for table, row_id, stored, original in files:
        try:
            (documents.UPLOAD_DIR / stored).unlink(missing_ok=True)
            removed += 1
        except OSError:
            pass
    return DeleteResult(rows_deleted=total, files_deleted=removed)