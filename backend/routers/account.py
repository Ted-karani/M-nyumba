# Import the date tools
from datetime import datetime, timedelta
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query, Request
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import ratelimit
import security
from dependencies import get_db, get_current_user
from routers.properties import require_owner
from security_models import AuditLog, mark_password_changed

# Make a group of endpoints that all start with /account
router = APIRouter(prefix="/account", tags=["Account"])

# Passwords that thousands of people use (and that attackers try first)
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwertyuiop", "qwerty123", "iloveyou", "11111111", "00000000", "abcd1234",
    "admin123", "letmein123", "welcome123", "kenya2024", "nairobi123", "mnyumba123",
}


# The data we ask for when changing a password
class PasswordChange(BaseModel):
    # The password they use now
    current_password: str = Field(min_length=1, max_length=64)
    # The new password
    new_password: str = Field(min_length=8, max_length=64)


# One line in the activity log
class ActivityItem(BaseModel):
    # The entry's id
    id: int
    # Who did it
    actor_id: int | None
    actor_name: str
    actor_role: str
    # What they did
    summary: str
    # When they did it
    created_at: datetime
    # The address it came from
    ip: str | None


# A person who appears in the log (for the filter)
class ActivityPerson(BaseModel):
    # Their id
    id: int
    # Their name
    name: str


# Everything the activity page needs
class ActivityReport(BaseModel):
    # The people who did things in the last 90 days
    people: list[ActivityPerson]
    # The entries, newest first (up to 300)
    items: list[ActivityItem]
    # How many days back we looked
    days: int


# Refuse passwords that are too easy to guess
def validate_new_password(password: str, email: str | None = None):
    # Very common passwords are tried first by attackers
    if password.lower() in COMMON_PASSWORDS:
        raise HTTPException(status_code=400, detail="This password is too common. Choose a harder one")
    # Only digits (like a phone number or a birthday) are easy to guess
    if password.isdigit():
        raise HTTPException(status_code=400, detail="Add some letters to your password, not only numbers")
    # The email itself is not a good password
    if email and password.lower() == email.lower():
        raise HTTPException(status_code=400, detail="Your password cannot be the same as your email")


# Change your own password
@router.post("/change-password", status_code=204)
def change_password(
    request: Request,
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ip = request.client.host if request.client else None
    # Someone guessing the current password gets locked out like at sign-in
    wait = ratelimit.seconds_locked(db, current_user.email, ip)
    if wait > 0:
        minutes = (wait + 59) // 60
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )
    # The current password must be right
    if not security.verify_password(data.current_password, current_user.password_hash):
        ratelimit.record(db, current_user.email, ip, success=False)
        raise HTTPException(status_code=400, detail="Your current password is not correct")
    # The new one must be different and strong enough
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="Choose a password different from your current one")
    validate_new_password(data.new_password, current_user.email)
    # Save the new password, and sign everyone out of their old logins
    current_user.password_hash = security.hash_password(data.new_password)
    mark_password_changed(db, current_user.id)
    # This also saves the changes above
    ratelimit.record(db, current_user.email, ip, success=True)


# Show who did what (owners only)
@router.get("/activity", response_model=ActivityReport)
def activity(
    days: int = Query(default=7, ge=1, le=90),
    actor_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see the log
    require_owner(current_user)
    now = datetime.utcnow()
    # Always start with only this owner's business
    conditions = [AuditLog.owner_id == current_user.id, AuditLog.created_at >= now - timedelta(days=days)]
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    # Get the entries, newest first
    rows = db.query(AuditLog).filter(*conditions).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(300).all()
    # Find the people to offer in the filter
    people_rows = (
        db.query(AuditLog.actor_id, AuditLog.actor_name)
        .filter(AuditLog.owner_id == current_user.id, AuditLog.created_at >= now - timedelta(days=90))
        .distinct()
        .all()
    )
    people = {}
    for person_id, name in people_rows:
        if person_id is not None:
            people[person_id] = name
    # Send it all back
    return ActivityReport(
        people=[ActivityPerson(id=person_id, name=name) for person_id, name in sorted(people.items(), key=lambda item: item[1])],
        items=[
            ActivityItem(
                id=row.id,
                actor_id=row.actor_id,
                actor_name=row.actor_name,
                actor_role=row.actor_role,
                summary=row.summary,
                created_at=row.created_at,
                ip=row.ip,
            )
            for row in rows
        ],
        days=days,
    )