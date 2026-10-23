# Import the date tools
from datetime import date, datetime, timedelta
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Request
# Import the tools that describe and check data shapes
from pydantic import BaseModel, EmailStr, Field, field_validator
# Import the tool that counts and adds up rows
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import security
from admin_models import (
    AdminEvent,
    OwnerAccount,
    SubscriptionPayment,
    add_months,
    effective_state,
    get_or_create_account,
    log_admin,
    owner_id_of,
)
from dependencies import get_db, get_current_user
from portal_models import TENANT_EMAIL_DOMAIN, TenantAccount
from routers.account import PasswordChange, refuse_if_locked, validate_new_password
from routers.portal import make_temp_password
from schemas import clean_phone
import ratelimit
from security_models import LoginAttempt, UserTotp, mark_password_changed

# The endpoints only the admin can use
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
# The endpoints landlords and caretakers use for first-time setup and to see their account status
setup_router = APIRouter(prefix="/setup", tags=["Account setup"])


# Everything the admin sees about one landlord (counts only, never their tenants' details)
class AccountRow(BaseModel):
    # The landlord
    owner_id: int
    full_name: str
    email: str
    phone: str | None
    created_at: datetime
    # The last time they signed in (only the last 30 days are remembered)
    last_sign_in: datetime | None
    # Whether 2-step login is on
    two_step: bool
    # Their plan and status, and what the account can really do today
    plan: str
    status: str
    state: str
    state_message: str | None
    # When their access ends, and how many days are left (negative means it ended)
    paid_until: date | None
    days_left: int | None
    # Their unit limit and how much they use
    unit_limit: int | None
    properties: int
    units: int
    occupied_units: int
    tenants: int
    caretakers: int
    portal_users: int
    # Private notes, and the message the landlord sees
    notes: str | None
    status_note: str | None
    # Whether they still have to choose their own password
    must_change_password: bool
    closed_at: datetime | None


# One payment a landlord made to us
class PaymentOut(BaseModel):
    # The payment's id
    id: int
    # The landlord
    owner_id: int
    owner_name: str
    # The money
    amount: int
    method: str
    reference: str | None
    months: int
    # The day it was received, and the last day of access it bought
    paid_on: date
    covers_until: date
    note: str | None


# One thing the admin did
class EventOut(BaseModel):
    # The event's id
    id: int
    # What was done
    action: str
    detail: str | None
    # The landlord it was about (if any)
    owner_id: int | None
    owner_name: str | None
    # When it happened
    created_at: datetime


# Everything the overview page needs
class Overview(BaseModel):
    # How many landlords there are, and how many are in each state
    landlords: int
    active: int
    read_only: int
    suspended: int
    closed: int
    # Totals across all landlords (just numbers)
    units: int
    occupied_units: int
    tenants: int
    # What the admin was paid
    revenue_this_month: int
    revenue_last_month: int
    revenue_total: int
    # Active landlords whose access ends in the next 14 days
    expiring: list[AccountRow]
    # Landlords who are read-only right now
    read_only_accounts: list[AccountRow]
    # The latest payments
    recent_payments: list[PaymentOut]


# The data we ask for when adding a landlord
class AccountCreate(BaseModel):
    # Their name and email
    full_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    phone: str | None = None
    # Their plan, and the last day of their access (empty means no end date)
    plan: str = Field(default="pilot", pattern="^(pilot|paid)$")
    access_until: date | None = None
    # The most units they may have (empty means no limit)
    unit_limit: int | None = Field(default=None, ge=1, le=10000)
    # Private notes
    notes: str | None = Field(default=None, max_length=1000)

    # Clean the phone number before saving
    @field_validator("phone")
    @classmethod
    def check_phone(cls, value):
        if value is None or value.strip() == "":
            return None
        return clean_phone(value)


# What we send back after adding a landlord or making a new password (the password is shown only this once)
class CredentialsOut(BaseModel):
    # The landlord
    owner_id: int
    full_name: str
    email: str
    phone: str | None
    # The temporary password
    temporary_password: str


# The data we accept when changing an account (send only what changed)
class AccountUpdate(BaseModel):
    # New plan
    plan: str | None = Field(default=None, pattern="^(pilot|paid)$")
    # New status
    status: str | None = Field(default=None, pattern="^(active|read_only|suspended|closed)$")
    # New end date (send null for no end date)
    paid_until: date | None = None
    # New unit limit (send null for no limit)
    unit_limit: int | None = Field(default=None, ge=1, le=10000)
    # New private notes
    notes: str | None = Field(default=None, max_length=1000)
    # New message for the landlord
    status_note: str | None = Field(default=None, max_length=300)


# The data we ask for when recording a payment
class PaymentIn(BaseModel):
    # The amount in shillings
    amount: int = Field(ge=1, le=10_000_000)
    # How many months it buys
    months: int = Field(ge=1, le=24)
    # How it was paid
    method: str = Field(default="mpesa", pattern="^(mpesa|cash|bank|other)$")
    # The M-Pesa code or other reference
    reference: str | None = Field(default=None, max_length=40)
    # The day it was received (empty means today)
    paid_on: date | None = None
    # A short note
    note: str | None = Field(default=None, max_length=200)


# What a landlord or caretaker sees about their account
class SetupStatus(BaseModel):
    # True until the landlord has chosen their own password
    must_change_password: bool
    # "active", "read_only", "suspended" or "closed"
    state: str
    # A message to show when the account is limited
    message: str | None
    # When access ends
    paid_until: date | None


# A fresh login token (given after the first password is chosen)
class SetupToken(BaseModel):
    # The token
    access_token: str
    # The kind of token
    token_type: str = "bearer"


# Only the admin may pass, and only once 2-step login is on
def require_admin(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    on = db.query(UserTotp).filter(UserTotp.user_id == current_user.id, UserTotp.enabled.is_(True)).first()
    if on is None:
        raise HTTPException(status_code=403, detail="Turn on 2-step login for this account first (My account, then 2-step login)")
    return current_user


# Find a landlord, and get their account row
def find_owner(db: Session, owner_id: int):
    owner = db.query(models.User).filter(models.User.id == owner_id, models.User.role == "owner").first()
    if owner is None:
        raise HTTPException(status_code=404, detail="Landlord not found")
    return owner, get_or_create_account(db, owner.id)


# Turn landlords into rows with their counts (this makes missing account rows too, and saves them)
def build_rows(db: Session, owners: list[models.User]) -> list[AccountRow]:
    ids = [owner.id for owner in owners]
    if not ids:
        return []
    accounts = {account.owner_id: account for account in db.query(OwnerAccount).filter(OwnerAccount.owner_id.in_(ids)).all()}
    for owner in owners:
        if owner.id not in accounts:
            account = OwnerAccount(owner_id=owner.id, plan="pilot", status="active", must_change_password=False)
            db.add(account)
            accounts[owner.id] = account
    db.flush()
    properties = dict(db.query(models.Property.owner_id, func.count(models.Property.id)).filter(models.Property.owner_id.in_(ids)).group_by(models.Property.owner_id).all())
    units = dict(
        db.query(models.Property.owner_id, func.count(models.Unit.id))
        .join(models.Unit, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id.in_(ids))
        .group_by(models.Property.owner_id)
        .all()
    )
    occupied = dict(
        db.query(models.Property.owner_id, func.count(models.Unit.id))
        .join(models.Unit, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id.in_(ids), models.Unit.status == "occupied")
        .group_by(models.Property.owner_id)
        .all()
    )
    tenants = dict(db.query(models.Tenant.owner_id, func.count(models.Tenant.id)).filter(models.Tenant.owner_id.in_(ids)).group_by(models.Tenant.owner_id).all())
    caretakers = dict(db.query(models.CaretakerAccount.owner_id, func.count(models.CaretakerAccount.id)).filter(models.CaretakerAccount.owner_id.in_(ids)).group_by(models.CaretakerAccount.owner_id).all())
    portal = dict(db.query(TenantAccount.owner_id, func.count(TenantAccount.id)).filter(TenantAccount.owner_id.in_(ids)).group_by(TenantAccount.owner_id).all())
    last_seen = dict(
        db.query(LoginAttempt.email, func.max(LoginAttempt.created_at))
        .filter(LoginAttempt.email.in_([owner.email for owner in owners]), LoginAttempt.success.is_(True))
        .group_by(LoginAttempt.email)
        .all()
    )
    two_step = {user_id for (user_id,) in db.query(UserTotp.user_id).filter(UserTotp.user_id.in_(ids), UserTotp.enabled.is_(True)).all()}
    today = date.today()
    rows = []
    for owner in owners:
        account = accounts[owner.id]
        state, message = effective_state(account, today)
        rows.append(AccountRow(
            owner_id=owner.id,
            full_name=owner.full_name,
            email=owner.email,
            phone=owner.phone,
            created_at=owner.created_at,
            last_sign_in=last_seen.get(owner.email),
            two_step=owner.id in two_step,
            plan=account.plan,
            status=account.status,
            state=state,
            state_message=message,
            paid_until=account.paid_until,
            days_left=(account.paid_until - today).days if account.paid_until else None,
            unit_limit=account.unit_limit,
            properties=properties.get(owner.id, 0),
            units=units.get(owner.id, 0),
            occupied_units=occupied.get(owner.id, 0),
            tenants=tenants.get(owner.id, 0),
            caretakers=caretakers.get(owner.id, 0),
            portal_users=portal.get(owner.id, 0),
            notes=account.notes,
            status_note=account.status_note,
            must_change_password=bool(account.must_change_password),
            closed_at=account.closed_at,
        ))
    db.commit()
    return rows


# Turn a payment row into the shape we send back
def payment_out(payment: SubscriptionPayment, owner_name: str) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        owner_id=payment.owner_id,
        owner_name=owner_name,
        amount=payment.amount,
        method=payment.method,
        reference=payment.reference,
        months=payment.months,
        paid_on=payment.paid_on,
        covers_until=payment.covers_until,
        note=payment.note,
    )


# Add up the payments received from a day up to (but not including) another day
def revenue_between(db: Session, start: date, end: date | None = None) -> int:
    query = db.query(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).filter(SubscriptionPayment.paid_on >= start)
    if end is not None:
        query = query.filter(SubscriptionPayment.paid_on < end)
    return int(query.scalar())


# The overview page
@admin_router.get("/overview", response_model=Overview)
def admin_overview(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owners = db.query(models.User).filter(models.User.role == "owner").order_by(models.User.created_at).all()
    rows = build_rows(db, owners)
    today = date.today()
    this_month = today.replace(day=1)
    payments = (
        db.query(SubscriptionPayment, models.User.full_name)
        .join(models.User, SubscriptionPayment.owner_id == models.User.id)
        .order_by(SubscriptionPayment.paid_on.desc(), SubscriptionPayment.id.desc())
        .limit(8)
        .all()
    )
    return Overview(
        landlords=len(rows),
        active=sum(1 for row in rows if row.state == "active"),
        read_only=sum(1 for row in rows if row.state == "read_only"),
        suspended=sum(1 for row in rows if row.state == "suspended"),
        closed=sum(1 for row in rows if row.state == "closed"),
        units=sum(row.units for row in rows),
        occupied_units=sum(row.occupied_units for row in rows),
        tenants=sum(row.tenants for row in rows),
        revenue_this_month=revenue_between(db, this_month, add_months(this_month, 1)),
        revenue_last_month=revenue_between(db, add_months(this_month, -1), this_month),
        revenue_total=revenue_between(db, date(2000, 1, 1)),
        expiring=[row for row in rows if row.state == "active" and row.days_left is not None and 0 <= row.days_left <= 14],
        read_only_accounts=[row for row in rows if row.state == "read_only"],
        recent_payments=[payment_out(payment, name) for payment, name in payments],
    )


# The list of landlords
@admin_router.get("/accounts", response_model=list[AccountRow])
def list_accounts(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owners = db.query(models.User).filter(models.User.role == "owner").order_by(models.User.full_name).all()
    return build_rows(db, owners)


# One landlord
@admin_router.get("/accounts/{owner_id}", response_model=AccountRow)
def get_account(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    return build_rows(db, [owner])[0]


# Add a landlord (the temporary password is shown only once)
@admin_router.post("/accounts", response_model=CredentialsOut, status_code=201)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    email = data.email.lower()
    # The hidden login names used for tenants cannot be used here
    if email.endswith("@" + TENANT_EMAIL_DOMAIN):
        raise HTTPException(status_code=400, detail="This email address cannot be used")
    if db.query(models.User).filter(models.User.email == email).first() is not None:
        raise HTTPException(status_code=400, detail="This email is already registered")
    temporary = make_temp_password()
    user = models.User(
        full_name=data.full_name.strip(),
        email=email,
        phone=data.phone,
        password_hash=security.hash_password(temporary),
        role="owner",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(OwnerAccount(
        owner_id=user.id,
        plan=data.plan,
        status="active",
        paid_until=data.access_until,
        unit_limit=data.unit_limit,
        notes=(data.notes or "").strip() or None,
        must_change_password=True,
    ))
    mark_password_changed(db, user.id)
    log_admin(db, admin, user.id, "Added a landlord", f"{data.plan} plan")
    db.commit()
    return CredentialsOut(owner_id=user.id, full_name=user.full_name, email=user.email, phone=user.phone, temporary_password=temporary)


# Change a landlord's plan, status, end date, unit limit, notes, or message
@admin_router.put("/accounts/{owner_id}", response_model=AccountRow)
def update_account(
    owner_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    notes = []
    for field in ("plan", "status"):
        if changes.get(field) is not None and changes[field] != getattr(account, field):
            notes.append(f"{field}: {getattr(account, field)} to {changes[field]}")
            setattr(account, field, changes[field])
    if "paid_until" in changes and changes["paid_until"] != account.paid_until:
        notes.append(f"access until: {account.paid_until or 'no end'} to {changes['paid_until'] or 'no end'}")
        account.paid_until = changes["paid_until"]
    if "unit_limit" in changes and changes["unit_limit"] != account.unit_limit:
        notes.append(f"unit limit: {account.unit_limit or 'none'} to {changes['unit_limit'] or 'none'}")
        account.unit_limit = changes["unit_limit"]
    if "notes" in changes:
        account.notes = (changes["notes"] or "").strip() or None
        notes.append("notes edited")
    if "status_note" in changes:
        account.status_note = (changes["status_note"] or "").strip() or None
        notes.append("message edited")
    # Remember when an account was closed
    if account.status == "closed" and account.closed_at is None:
        account.closed_at = datetime.utcnow()
    if account.status != "closed":
        account.closed_at = None
    if notes:
        log_admin(db, admin, owner.id, "Changed an account", "; ".join(notes))
    db.commit()
    return build_rows(db, [owner])[0]


# Record a payment a landlord made to us, which extends their access
@admin_router.post("/accounts/{owner_id}/payments", response_model=PaymentOut, status_code=201)
def record_payment(
    owner_id: int,
    data: PaymentIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    today = date.today()
    paid_on = data.paid_on or today
    if paid_on > today:
        raise HTTPException(status_code=400, detail="The payment date cannot be in the future")
    reference = (data.reference or "").strip().upper() or None
    if reference and db.query(SubscriptionPayment).filter(SubscriptionPayment.reference == reference).first() is not None:
        raise HTTPException(status_code=400, detail="This reference has already been recorded")
    # The new access end is counted from today, or from the old end if that is still in the future
    start = max(today, account.paid_until) if account.paid_until else today
    covers_until = add_months(start, data.months)
    payment = SubscriptionPayment(
        owner_id=owner.id,
        amount=data.amount,
        method=data.method,
        reference=reference,
        months=data.months,
        paid_on=paid_on,
        covers_until=covers_until,
        recorded_by_id=admin.id,
        note=(data.note or "").strip() or None,
    )
    db.add(payment)
    account.plan = "paid"
    account.paid_until = covers_until
    # A payment brings back a limited account (but not a closed one)
    if account.status in ("read_only", "suspended"):
        account.status = "active"
        account.status_note = None
    log_admin(db, admin, owner.id, "Recorded a payment", f"KSh {data.amount:,} for {data.months} month(s), access until {covers_until}")
    db.commit()
    db.refresh(payment)
    return payment_out(payment, owner.full_name)


# The payments one landlord made to us
@admin_router.get("/accounts/{owner_id}/payments", response_model=list[PaymentOut])
def account_payments(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    rows = db.query(SubscriptionPayment).filter(SubscriptionPayment.owner_id == owner.id).order_by(SubscriptionPayment.paid_on.desc(), SubscriptionPayment.id.desc()).all()
    return [payment_out(payment, owner.full_name) for payment in rows]


# All the payments landlords made to us
@admin_router.get("/payments", response_model=list[PaymentOut])
def all_payments(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    rows = (
        db.query(SubscriptionPayment, models.User.full_name)
        .join(models.User, SubscriptionPayment.owner_id == models.User.id)
        .order_by(SubscriptionPayment.paid_on.desc(), SubscriptionPayment.id.desc())
        .limit(300)
        .all()
    )
    return [payment_out(payment, name) for payment, name in rows]


# Make a new temporary password for a landlord (they are signed out everywhere and must choose their own)
@admin_router.post("/accounts/{owner_id}/reset-password", response_model=CredentialsOut)
def reset_password(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    temporary = make_temp_password()
    owner.password_hash = security.hash_password(temporary)
    account.must_change_password = True
    mark_password_changed(db, owner.id)
    # Clear any lock from wrong passwords, so they can sign in straight away
    db.query(LoginAttempt).filter(LoginAttempt.email == owner.email).delete()
    log_admin(db, admin, owner.id, "Made a new password", None)
    db.commit()
    return CredentialsOut(owner_id=owner.id, full_name=owner.full_name, email=owner.email, phone=owner.phone, temporary_password=temporary)


# Turn off a landlord's 2-step login (for a lost phone), and sign them out
@admin_router.post("/accounts/{owner_id}/reset-2fa", status_code=204)
def reset_two_step(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    db.query(UserTotp).filter(UserTotp.user_id == owner.id).delete()
    mark_password_changed(db, owner.id)
    log_admin(db, admin, owner.id, "Reset 2-step login", None)
    db.commit()


# Sign a landlord out of every device
@admin_router.post("/accounts/{owner_id}/sign-out", status_code=204)
def force_sign_out(
    owner_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, account = find_owner(db, owner_id)
    mark_password_changed(db, owner.id)
    log_admin(db, admin, owner.id, "Signed out everywhere", None)
    db.commit()


# The log of what the admin did
@admin_router.get("/events", response_model=list[EventOut])
def list_events(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    rows = (
        db.query(AdminEvent, models.User.full_name)
        .outerjoin(models.User, AdminEvent.owner_id == models.User.id)
        .order_by(AdminEvent.created_at.desc(), AdminEvent.id.desc())
        .limit(300)
        .all()
    )
    return [
        EventOut(id=event.id, action=event.action, detail=event.detail, owner_id=event.owner_id, owner_name=name, created_at=event.created_at)
        for event, name in rows
    ]


# What a landlord or caretaker sees about their own account (first password, and whether it is limited)
@setup_router.get("/status", response_model=SetupStatus)
def setup_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    owner_id = owner_id_of(db, current_user)
    if current_user.role not in ("owner", "caretaker") or owner_id is None:
        raise HTTPException(status_code=403, detail="This page is for landlords and caretakers")
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).first()
    if account is None:
        return SetupStatus(must_change_password=False, state="active", message=None, paid_until=None)
    state, message = effective_state(account)
    return SetupStatus(
        must_change_password=bool(account.must_change_password) and current_user.role == "owner",
        state=state,
        message=message,
        paid_until=account.paid_until,
    )


# Choose your own password the first time (this keeps the landlord signed in)
@setup_router.post("/change-password", response_model=SetupToken)
def setup_change_password(
    request: Request,
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="This page is for landlords")
    ip = request.client.host if request.client else None
    # Guessing the current password gets locked out like at sign-in
    refuse_if_locked(db, current_user.email, ip)
    if not security.verify_password(data.current_password, current_user.password_hash):
        ratelimit.record(db, current_user.email, ip, success=False)
        raise HTTPException(status_code=400, detail="Your current password is not correct")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="Choose a password different from your current one")
    validate_new_password(data.new_password, current_user.email)
    # Save the new password, which signs out every old login
    current_user.password_hash = security.hash_password(data.new_password)
    mark_password_changed(db, current_user.id)
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == current_user.id).first()
    if account is not None:
        account.must_change_password = False
    # This also saves the changes above
    ratelimit.record(db, current_user.email, ip, success=True)
    # Give a fresh token, so the landlord stays signed in
    return SetupToken(access_token=security.create_access_token(current_user.id))