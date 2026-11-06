# adminactivity.py - the admin's view of who signed up, who signed in, and failed sign-in attempts
# (names of landlords and counts only: no tenants, no caretaker names, no internet addresses)

# Import the date and time tools
from datetime import datetime, timedelta
# Import FastAPI tools for building endpoints
from fastapi import APIRouter, Depends, Query
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the tools that count and compare rows
from sqlalchemy import func, select
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import ratelimit
from admin_models import AdminEvent, OwnerAccount, effective_state
from dependencies import get_db
from routers.admin import require_admin
from security_models import AuditLog, LoginAttempt

# Make a group of endpoints that all start with /admin (these are only for the admin)
router = APIRouter(prefix="/admin", tags=["Admin: sign-ups and sign-ins"])


# One landlord in the sign-ups list
class SignupRow(BaseModel):
    # The landlord
    owner_id: int
    full_name: str
    email: str
    # When the account was made
    created_at: datetime
    # "self" (they signed up themselves) or "admin" (you added them)
    source: str
    # The first time they signed in, and how many times in the last 30 days
    first_sign_in: datetime | None
    sign_ins_30d: int
    # True if they have never signed in
    never_signed_in: bool
    # What their account can do today: "active", "read_only", "suspended" or "closed"
    state: str


# One sign-in
class SigninRow(BaseModel):
    # The record's id
    id: int
    # When it happened
    created_at: datetime
    # The landlord's business it belongs to
    owner_id: int
    landlord_name: str
    # "landlord" or "caretaker" (never a name)
    who: str


# A landlord, for the filter
class PersonRef(BaseModel):
    owner_id: int
    name: str


# The sign-in feed
class SigninFeed(BaseModel):
    # The latest sign-ins (up to 300)
    items: list[SigninRow]
    # The landlords who signed in during this time
    people: list[PersonRef]
    # How many days back we looked
    days: int
    # How many sign-ins there were in all, by landlords and by caretakers
    landlord_total: int
    caretaker_total: int


# A landlord who had failed sign-ins
class SecurityAccount(BaseModel):
    owner_id: int
    full_name: str
    email: str
    # Wrong passwords or codes in the last 24 hours and the last 7 days
    failed_24h: int
    failed_7d: int
    # How many more minutes they are locked for (0 means not locked)
    locked_minutes: int
    # The last wrong attempt
    last_failed: datetime | None


# Everything the security tab needs
class SecurityOverview(BaseModel):
    # The landlords who had failed sign-ins in the last 7 days
    accounts: list[SecurityAccount]
    # How many landlords are locked right now
    locked_now: int
    # Failed attempts on emails that do not belong to anyone (counts only)
    unknown_failed_24h: int
    unknown_failed_7d: int
    # The admin account's own failed attempts, lock, and sign-ins
    admin_failed_24h: int
    admin_failed_7d: int
    admin_last_failed: datetime | None
    admin_locked_minutes: int
    admin_sign_ins_7d: int
    admin_last_sign_in: datetime | None


# Count the failed sign-ins for some emails since a time: {email: (how many, the last one)}
def failed_counts(db: Session, emails, since: datetime):
    emails = list(emails)
    if not emails:
        return {}
    rows = (
        db.query(LoginAttempt.email, func.count(LoginAttempt.id), func.max(LoginAttempt.created_at))
        .filter(LoginAttempt.success.is_(False), LoginAttempt.created_at >= since, LoginAttempt.email.in_(emails))
        .group_by(LoginAttempt.email)
        .all()
    )
    return {email: (count, last) for email, count, last in rows}


# Count the failed sign-ins on emails that belong to nobody
def unknown_failed(db: Session, since: datetime) -> int:
    return (
        db.query(func.count(LoginAttempt.id))
        .filter(
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
            LoginAttempt.email.not_in(select(models.User.email)),
        )
        .scalar()
    )


# Who signed up, and have they ever come back?
@router.get("/signups", response_model=list[SignupRow])
def signups(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owners = db.query(models.User).filter(models.User.role == "owner").order_by(models.User.created_at.desc(), models.User.id.desc()).limit(200).all()
    ids = [owner.id for owner in owners]
    if not ids:
        return []
    month_ago = datetime.utcnow() - timedelta(days=30)
    # The first sign-in of each landlord, and how many in the last 30 days
    first = dict(
        db.query(AuditLog.actor_id, func.min(AuditLog.created_at))
        .filter(AuditLog.actor_id.in_(ids), AuditLog.actor_role == "owner", AuditLog.summary == "Signed in")
        .group_by(AuditLog.actor_id)
        .all()
    )
    recent = dict(
        db.query(AuditLog.actor_id, func.count(AuditLog.id))
        .filter(AuditLog.actor_id.in_(ids), AuditLog.actor_role == "owner", AuditLog.summary == "Signed in", AuditLog.created_at >= month_ago)
        .group_by(AuditLog.actor_id)
        .all()
    )
    # Which landlords were added by the admin
    added = {owner_id for (owner_id,) in db.query(AdminEvent.owner_id).filter(AdminEvent.action == "Added a landlord", AdminEvent.owner_id.in_(ids)).all()}
    accounts = {account.owner_id: account for account in db.query(OwnerAccount).filter(OwnerAccount.owner_id.in_(ids)).all()}
    rows = []
    for owner in owners:
        account = accounts.get(owner.id)
        state = effective_state(account)[0] if account else "active"
        rows.append(SignupRow(
            owner_id=owner.id,
            full_name=owner.full_name,
            email=owner.email,
            created_at=owner.created_at,
            source="admin" if owner.id in added else "self",
            first_sign_in=first.get(owner.id),
            sign_ins_30d=recent.get(owner.id, 0),
            never_signed_in=owner.id not in first,
            state=state,
        ))
    return rows


# Who signed in lately?
@router.get("/signins", response_model=SigninFeed)
def signins(
    days: int = Query(default=7, ge=1, le=30),
    owner_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    since = datetime.utcnow() - timedelta(days=days)
    base = [AuditLog.summary == "Signed in", AuditLog.created_at >= since]
    if owner_id:
        base.append(AuditLog.owner_id == owner_id)
    rows = (
        db.query(AuditLog, models.User.full_name)
        .join(models.User, AuditLog.owner_id == models.User.id)
        .filter(*base)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(300)
        .all()
    )
    people = (
        db.query(AuditLog.owner_id, models.User.full_name)
        .join(models.User, AuditLog.owner_id == models.User.id)
        .filter(AuditLog.summary == "Signed in", AuditLog.created_at >= since)
        .distinct()
        .all()
    )

    # How many sign-ins in all, by landlords and by caretakers
    def total(role: str) -> int:
        return db.query(func.count(AuditLog.id)).filter(*base, AuditLog.actor_role == role).scalar()

    return SigninFeed(
        items=[
            SigninRow(id=row.id, created_at=row.created_at, owner_id=row.owner_id, landlord_name=name, who="caretaker" if row.actor_role == "caretaker" else "landlord")
            for row, name in rows
        ],
        people=sorted((PersonRef(owner_id=person_id, name=name) for person_id, name in people), key=lambda person: person.name.lower()),
        days=days,
        landlord_total=total("owner"),
        caretaker_total=total("caretaker"),
    )


# Who is failing to sign in?
@router.get("/security", response_model=SecurityOverview)
def security_overview(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    now = datetime.utcnow()
    day = now - timedelta(days=1)
    week = now - timedelta(days=7)
    # The landlords
    owners = db.query(models.User).filter(models.User.role == "owner").all()
    by_email = {owner.email: owner for owner in owners}
    week_counts = failed_counts(db, by_email.keys(), week)
    day_counts = failed_counts(db, by_email.keys(), day)
    accounts = []
    for email, (count, last) in week_counts.items():
        owner = by_email[email]
        wait = ratelimit.seconds_locked(db, email, None)
        accounts.append(SecurityAccount(
            owner_id=owner.id,
            full_name=owner.full_name,
            email=owner.email,
            failed_24h=day_counts.get(email, (0, None))[0],
            failed_7d=count,
            locked_minutes=(wait + 59) // 60 if wait else 0,
            last_failed=last,
        ))
    accounts.sort(key=lambda row: (-row.locked_minutes, -row.failed_24h, -row.failed_7d, row.full_name.lower()))
    # The admin account itself
    admin_emails = [email for (email,) in db.query(models.User.email).filter(models.User.role == "admin").all()]
    admin_week = failed_counts(db, admin_emails, week)
    admin_day = failed_counts(db, admin_emails, day)
    admin_locked = max([ratelimit.seconds_locked(db, email, None) for email in admin_emails], default=0)
    sign_ins, last_sign_in = (
        db.query(func.count(AdminEvent.id), func.max(AdminEvent.created_at))
        .filter(AdminEvent.action == "Admin signed in", AdminEvent.created_at >= week)
        .one()
    )
    return SecurityOverview(
        accounts=accounts,
        locked_now=sum(1 for row in accounts if row.locked_minutes > 0),
        unknown_failed_24h=unknown_failed(db, day),
        unknown_failed_7d=unknown_failed(db, week),
        admin_failed_24h=sum(count for count, _ in admin_day.values()),
        admin_failed_7d=sum(count for count, _ in admin_week.values()),
        admin_last_failed=max([last for _, last in admin_week.values()], default=None),
        admin_locked_minutes=(admin_locked + 59) // 60 if admin_locked else 0,
        admin_sign_ins_7d=sign_ins,
        admin_last_sign_in=last_sign_in,
    )