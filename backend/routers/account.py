# Import the tool that reads lists written as text
import json
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
import twofactor
from dependencies import get_db, get_current_user
from routers.properties import require_owner
from security_models import AuditLog, UserTotp, mark_password_changed

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


# Whether 2-step login is on
class TwoStepStatus(BaseModel):
    # True if it is on
    enabled: bool
    # How many recovery codes are still unused
    recovery_codes_left: int


# What we send back when starting the setup
class TwoStepSetup(BaseModel):
    # The secret to type into an authenticator app by hand
    secret: str
    # The address that the QR code holds
    otpauth_url: str


# A code typed by the person
class CodeIn(BaseModel):
    # The 6-digit code
    code: str = Field(min_length=4, max_length=20)


# What we send back once 2-step login is on
class TwoStepEnabled(BaseModel):
    # The recovery codes (shown only this once)
    recovery_codes: list[str]


# The data we ask for when turning 2-step login off
class TwoStepDisable(BaseModel):
    # Their password
    password: str = Field(min_length=1, max_length=64)
    # A code from the app, or a recovery code
    code: str = Field(min_length=4, max_length=20)


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


# Make someone wait if they have tried too many wrong passwords or codes
def refuse_if_locked(db: Session, email: str, ip: str | None):
    wait = ratelimit.seconds_locked(db, email, ip)
    if wait > 0:
        minutes = (wait + 59) // 60
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )


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
    refuse_if_locked(db, current_user.email, ip)
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


# Show whether 2-step login is on
@router.get("/2fa", response_model=TwoStepStatus)
def two_step_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = db.query(UserTotp).filter(UserTotp.user_id == current_user.id).first()
    enabled = bool(row and row.enabled)
    left = len(json.loads(row.recovery_hashes or "[]")) if enabled else 0
    return TwoStepStatus(enabled=enabled, recovery_codes_left=left)


# Start setting up 2-step login: make a secret for the authenticator app (it is not on until a code is confirmed)
@router.post("/2fa/setup", response_model=TwoStepSetup)
def two_step_setup(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = db.query(UserTotp).filter(UserTotp.user_id == current_user.id).first()
    if row and row.enabled:
        raise HTTPException(status_code=400, detail="2-step login is already on")
    secret = twofactor.new_secret()
    if row:
        # Replace an unfinished setup
        row.secret = secret
        row.last_counter = 0
    else:
        db.add(UserTotp(user_id=current_user.id, secret=secret, enabled=False))
    db.commit()
    return TwoStepSetup(secret=secret, otpauth_url=twofactor.otpauth_url(secret, current_user.email))


# Finish the setup by proving the app works, then turn 2-step login on
@router.post("/2fa/enable", response_model=TwoStepEnabled)
def two_step_enable(
    request: Request,
    data: CodeIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ip = request.client.host if request.client else None
    refuse_if_locked(db, current_user.email, ip)
    row = db.query(UserTotp).filter(UserTotp.user_id == current_user.id).first()
    if row is None or row.enabled:
        raise HTTPException(status_code=400, detail="Start the setup first")
    # The code must be right
    if not twofactor.check_code(row, data.code):
        ratelimit.record(db, current_user.email, ip, success=False)
        raise HTTPException(status_code=400, detail="That code is not right. Check the time on your phone and try again")
    # Turn it on and make the recovery codes
    codes = twofactor.make_recovery_codes()
    row.recovery_hashes = twofactor.hash_codes(codes)
    row.enabled = True
    row.enabled_at = datetime.utcnow()
    db.commit()
    return TwoStepEnabled(recovery_codes=codes)


# Turn 2-step login off (needs the password and a code)
@router.post("/2fa/disable", status_code=204)
def two_step_disable(
    request: Request,
    data: TwoStepDisable,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ip = request.client.host if request.client else None
    refuse_if_locked(db, current_user.email, ip)
    row = db.query(UserTotp).filter(UserTotp.user_id == current_user.id, UserTotp.enabled.is_(True)).first()
    if row is None:
        raise HTTPException(status_code=400, detail="2-step login is not on")
    # The password must be right
    if not security.verify_password(data.password, current_user.password_hash):
        ratelimit.record(db, current_user.email, ip, success=False)
        raise HTTPException(status_code=400, detail="Your password is not correct")
    # The code must be right (a recovery code works too)
    if not (twofactor.check_code(row, data.code) or twofactor.use_recovery_code(row, data.code)):
        ratelimit.record(db, current_user.email, ip, success=False)
        raise HTTPException(status_code=400, detail="That code is not right")
    # Remove the 2-step login settings
    db.delete(row)
    db.commit()