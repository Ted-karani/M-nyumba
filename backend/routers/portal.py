# Import the tool that makes random passwords
import secrets
# Import the date tool
from datetime import date
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Request
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, field_validator
# Import tools for adding up numbers and for "this or that" filters
from sqlalchemy import func, or_
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import ratelimit
import security
from dependencies import get_db, get_current_user
from portal_models import Notice, OwnerSettings, TenantAccount, tenant_email
from routers.account import PasswordChange, refuse_if_locked, validate_new_password
from routers.properties import require_owner
from security_models import mark_password_changed

# The endpoints tenants use (they all start with /portal)
tenant_router = APIRouter(prefix="/portal", tags=["Tenant portal"])
# The endpoints owners use to give tenants access and set the payment details
access_router = APIRouter(prefix="/portal-access", tags=["Portal access"])
# The endpoints owners use for the notice board
notices_router = APIRouter(prefix="/notices", tags=["Notices"])

# The words shown for each kind of charge and payment
CHARGE_LABELS = {"rent": "Rent", "deposit": "Deposit", "water": "Water", "electricity": "Electricity", "wifi": "Wi-Fi", "other": "Other"}
METHOD_LABELS = {"mpesa": "M-Pesa", "cash": "Cash", "bank": "Bank"}
# The most problems one tenant can have open at the same time
MAX_OPEN_REPAIRS = 5


# One home (a lease the tenant is living in right now)
class Tenancy(BaseModel):
    # The lease's id
    lease_id: int
    # The unit and property
    unit_number: str
    unit_type: str | None
    property_name: str
    # The money
    rent_amount: int
    total_charged: int
    total_paid: int
    # What the tenant owes (negative means they are in credit)
    balance: int
    # The day they moved in
    start_date: date


# How the landlord wants to be paid
class PaymentInfo(BaseModel):
    # The Paybill or Till number
    paybill_number: str | None
    # What to type as the account
    account_hint: str | None
    # Other words about paying
    instructions: str | None
    # The landlord's name and phone, so the tenant can ask
    contact_name: str
    contact_phone: str | None


# One notice, as a tenant sees it
class PortalNotice(BaseModel):
    # The notice's id
    id: int
    # The words
    title: str
    body: str
    # Whether it is pinned
    pinned: bool
    # The property it is for (empty means everyone)
    property_name: str | None
    # The day it was posted, and the last day it is shown
    posted_on: date
    expires_on: date | None


# Everything the tenant's home screen needs
class PortalHome(BaseModel):
    # The tenant's name
    tenant_name: str
    # Where they live now
    tenancies: list[Tenancy]
    # How to pay
    payment_info: PaymentInfo
    # The latest few notices
    notices: list[PortalNotice]


# Whether the tenant still has to choose their own password
class PortalStatus(BaseModel):
    # True until they have chosen one
    must_change_password: bool
    # The tenant's name
    tenant_name: str


# A fresh login token (given after the password changes, so the tenant stays signed in)
class PortalToken(BaseModel):
    # The login token
    access_token: str
    # The kind of token
    token_type: str = "bearer"


# One line of the statement
class StatementRow(BaseModel):
    # "charge" or "payment"
    kind: str
    # The day it happened
    date: date
    # What it was
    title: str
    # The amount
    amount: int
    # The M-Pesa code, when there is one
    reference: str | None
    # What the tenant owed right after this line
    balance_after: int


# The data we ask for when a tenant reports a problem
class RepairCreate(BaseModel):
    # A short title
    title: str = Field(min_length=3, max_length=100)
    # More details
    description: str | None = Field(default=None, max_length=1000)
    # How urgent it is
    priority: str = Field(default="normal", pattern="^(normal|urgent)$")
    # Which home it is in (empty means the first one)
    lease_id: int | None = None


# One problem, as the tenant sees it (no costs, no contractors)
class PortalRepair(BaseModel):
    # The request's id
    id: int
    # The words
    title: str
    description: str | None
    # How urgent and how far along
    priority: str
    status: str
    # The unit it is in
    unit_number: str | None
    # The day it was reported, and the day it was fixed
    reported_on: date
    resolved_on: date | None


# One row of the owner's "who has access" list
class AccessRow(BaseModel):
    # The tenant
    tenant_id: int
    tenant_name: str
    phone: str
    # Where they live now (empty if they have no active tenancy)
    unit_number: str | None
    property_name: str | None
    # Whether they have a login, whether it is switched on, and whether they still use the temporary password
    has_access: bool
    is_active: bool
    must_change_password: bool


# What we send back after giving access (the password is shown only this once)
class AccessGranted(BaseModel):
    # The tenant
    tenant_id: int
    tenant_name: str
    # The phone number they sign in with
    phone: str
    # The temporary password
    temporary_password: str


# The data we accept when switching access on or off
class AccessSwitch(BaseModel):
    # True to switch it on, false to switch it off
    is_active: bool


# The payment details an owner sets
class PaymentDetails(BaseModel):
    # The Paybill or Till number
    paybill_number: str | None = None
    # What to type as the account
    account_hint: str | None = Field(default=None, max_length=80)
    # Other words about paying
    instructions: str | None = Field(default=None, max_length=500)

    # Check the number: 5 to 7 digits
    @field_validator("paybill_number")
    @classmethod
    def check_paybill(cls, value):
        if value is None or value.strip() == "":
            return None
        digits = value.strip().replace(" ", "")
        if not digits.isdigit() or not 5 <= len(digits) <= 7:
            raise ValueError("The Paybill or Till number must be 5 to 7 digits")
        return digits


# A property's id and name
class PropertyRef(BaseModel):
    # The property's id
    id: int
    # The property's name
    name: str


# The data we ask for when posting a notice
class NoticeCreate(BaseModel):
    # The headline
    title: str = Field(min_length=3, max_length=120)
    # The message
    body: str = Field(min_length=1, max_length=2000)
    # The property it is for (empty means all)
    property_id: int | None = None
    # Whether to pin it
    pinned: bool = False
    # The last day it is shown
    expires_on: date | None = None


# The data we accept when editing a notice (every field is optional, send only what changed)
class NoticeUpdate(BaseModel):
    # New headline
    title: str | None = Field(default=None, min_length=3, max_length=120)
    # New message
    body: str | None = Field(default=None, min_length=1, max_length=2000)
    # New property (send null for all properties)
    property_id: int | None = None
    # Pin or unpin
    pinned: bool | None = None
    # New last day (send null to never expire)
    expires_on: date | None = None


# One notice, as the owner sees it
class NoticeOut(BaseModel):
    # The notice's id
    id: int
    # The words
    title: str
    body: str
    # The property it is for
    property_id: int | None
    property_name: str | None
    # Whether it is pinned
    pinned: bool
    # The last day it is shown, and whether that day has passed
    expires_on: date | None
    expired: bool
    # The day it was posted
    posted_on: date


# Everything the notice board page needs
class NoticesOverview(BaseModel):
    # The notices, newest first
    notices: list[NoticeOut]
    # The owner's properties (for the "who is this for" choice)
    properties: list[PropertyRef]


# Make sure the person is a tenant with a portal account, and return the account and the tenant
def tenant_context(db: Session, user: models.User):
    # Only tenants may use these pages
    if user.role != "tenant":
        raise HTTPException(status_code=403, detail="This page is for tenants")
    account = db.query(TenantAccount).filter(TenantAccount.user_id == user.id).first()
    tenant = db.get(models.Tenant, account.tenant_id) if account else None
    if account is None or tenant is None:
        raise HTTPException(status_code=403, detail="This account is not linked to a tenant")
    return account, tenant


# The same, but the tenant must also have chosen their own password
def ready_context(db: Session, user: models.User):
    account, tenant = tenant_context(db, user)
    if account.must_change_password:
        raise HTTPException(status_code=403, detail="Please choose your own password first")
    return account, tenant


# Get the leases a tenant is living in right now, with their units and properties
def active_leases(db: Session, tenant_id: int):
    return (
        db.query(models.Lease, models.Unit, models.Property)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Lease.tenant_id == tenant_id, models.Lease.status == "active")
        .order_by(models.Lease.start_date.desc(), models.Lease.id.desc())
        .all()
    )


# Add up what a lease was charged and what was paid on it
def lease_totals(db: Session, lease_id: int):
    charged = db.query(func.coalesce(func.sum(models.Charge.amount), 0)).filter(models.Charge.lease_id == lease_id).scalar()
    paid = db.query(func.coalesce(func.sum(models.Payment.amount), 0)).filter(models.Payment.lease_id == lease_id).scalar()
    return int(charged), int(paid)


# Write what a charge is for
def charge_title(charge) -> str:
    if charge.description:
        return charge.description
    label = CHARGE_LABELS.get(charge.charge_type, charge.charge_type)
    return f"{label} · {charge.period}" if charge.period else label


# Get the payment details of an owner, together with their name and phone
def payment_info(db: Session, owner_id: int) -> PaymentInfo:
    settings = db.query(OwnerSettings).filter(OwnerSettings.owner_id == owner_id).first()
    owner = db.get(models.User, owner_id)
    return PaymentInfo(
        paybill_number=settings.paybill_number if settings else None,
        account_hint=settings.account_hint if settings else None,
        instructions=settings.instructions if settings else None,
        contact_name=owner.full_name,
        contact_phone=owner.phone,
    )


# Get the notices a tenant may see: from their landlord, for all properties or theirs, and not expired
def visible_notices(db: Session, owner_id: int, property_ids: list[int]) -> list[PortalNotice]:
    rows = (
        db.query(Notice, models.Property.name)
        .outerjoin(models.Property, Notice.property_id == models.Property.id)
        .filter(
            Notice.owner_id == owner_id,
            or_(Notice.property_id.is_(None), Notice.property_id.in_(property_ids or [0])),
            or_(Notice.expires_on.is_(None), Notice.expires_on >= date.today()),
        )
        .order_by(Notice.pinned.desc(), Notice.created_at.desc(), Notice.id.desc())
        .all()
    )
    return [
        PortalNotice(
            id=notice.id,
            title=notice.title,
            body=notice.body,
            pinned=bool(notice.pinned),
            property_name=property_name,
            posted_on=notice.created_at.date(),
            expires_on=notice.expires_on,
        )
        for notice, property_name in rows
    ]


# Turn a repair into the shape a tenant sees
def repair_out(repair, unit_number) -> PortalRepair:
    return PortalRepair(
        id=repair.id,
        title=repair.title,
        description=repair.description,
        priority=repair.priority,
        status=repair.status,
        unit_number=unit_number,
        reported_on=repair.created_at.date(),
        resolved_on=repair.resolved_on,
    )


# Make a temporary password with letters and numbers that are easy to read out loud
def make_temp_password() -> str:
    letters = "abcdefghjkmnpqrstuvwxyz"
    digits = "23456789"
    while True:
        text = "".join(secrets.choice(letters + digits) for _ in range(8))
        # It must have at least one letter and one number
        if any(char in letters for char in text) and any(char in digits for char in text):
            return text


# Turn a notice into the shape an owner sees
def notice_out(notice, property_name) -> NoticeOut:
    return NoticeOut(
        id=notice.id,
        title=notice.title,
        body=notice.body,
        property_id=notice.property_id,
        property_name=property_name,
        pinned=bool(notice.pinned),
        expires_on=notice.expires_on,
        expired=bool(notice.expires_on and notice.expires_on < date.today()),
        posted_on=notice.created_at.date(),
    )


# Find a notice, but only if it belongs to this owner
def find_notice(db: Session, notice_id: int, owner: models.User):
    notice = db.query(Notice).filter(Notice.id == notice_id, Notice.owner_id == owner.id).first()
    # Say "not found" for missing and for someone else's, so nothing leaks
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    return notice


# Tell the screen whether the tenant still has to choose their own password
@tenant_router.get("/status", response_model=PortalStatus)
def portal_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = tenant_context(db, current_user)
    return PortalStatus(must_change_password=bool(account.must_change_password), tenant_name=tenant.full_name)


# Choose a new password (this also works for the first-time password, and keeps the tenant signed in)
@tenant_router.post("/change-password", response_model=PortalToken)
def portal_change_password(
    request: Request,
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = tenant_context(db, current_user)
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
    account.must_change_password = False
    # This also saves the changes above
    ratelimit.record(db, current_user.email, ip, success=True)
    # Give a fresh token, so the tenant stays signed in
    return PortalToken(access_token=security.create_access_token(current_user.id))


# The tenant's home screen: balance, how to pay, and the latest notices
@tenant_router.get("/home", response_model=PortalHome)
def portal_home(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    tenancies = []
    property_ids = []
    for lease, unit, prop in active_leases(db, tenant.id):
        charged, paid = lease_totals(db, lease.id)
        tenancies.append(Tenancy(
            lease_id=lease.id,
            unit_number=unit.unit_number,
            unit_type=unit.unit_type,
            property_name=prop.name,
            rent_amount=lease.rent_amount,
            total_charged=charged,
            total_paid=paid,
            balance=charged - paid,
            start_date=lease.start_date,
        ))
        property_ids.append(prop.id)
    return PortalHome(
        tenant_name=tenant.full_name,
        tenancies=tenancies,
        payment_info=payment_info(db, account.owner_id),
        notices=visible_notices(db, account.owner_id, property_ids)[:3],
    )


# The statement of one of the tenant's own leases, newest first, with the balance after each line
@tenant_router.get("/statement/{lease_id}", response_model=list[StatementRow])
def portal_statement(
    lease_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    # The lease must be this tenant's own
    lease = db.query(models.Lease).filter(models.Lease.id == lease_id, models.Lease.tenant_id == tenant.id).first()
    if lease is None:
        raise HTTPException(status_code=404, detail="Lease not found")
    # Put the charges and payments into one list, oldest first (on the same day, charges come before payments)
    items = []
    for charge in db.query(models.Charge).filter(models.Charge.lease_id == lease.id).all():
        items.append((charge.due_date, 0, charge.id, "charge", charge))
    for payment in db.query(models.Payment).filter(models.Payment.lease_id == lease.id).all():
        items.append((payment.paid_on, 1, payment.id, "payment", payment))
    items.sort(key=lambda item: (item[0], item[1], item[2]))
    # Walk through them, keeping a running balance
    running = 0
    rows = []
    for day, _, _, kind, record in items:
        if kind == "charge":
            running += record.amount
            title = charge_title(record)
            reference = None
        else:
            running -= record.amount
            title = f"{METHOD_LABELS.get(record.method, record.method)} payment"
            reference = record.reference
        rows.append(StatementRow(kind=kind, date=day, title=title, amount=record.amount, reference=reference, balance_after=running))
    # Newest first
    rows.reverse()
    return rows


# All the notices the tenant may see
@tenant_router.get("/notices", response_model=list[PortalNotice])
def portal_notices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    property_ids = [prop.id for lease, unit, prop in active_leases(db, tenant.id)]
    return visible_notices(db, account.owner_id, property_ids)


# The problems this tenant reported
@tenant_router.get("/repairs", response_model=list[PortalRepair])
def portal_repairs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ready_context(db, current_user)
    rows = (
        db.query(models.MaintenanceRequest, models.Unit.unit_number)
        .outerjoin(models.Unit, models.MaintenanceRequest.unit_id == models.Unit.id)
        .filter(models.MaintenanceRequest.created_by_id == current_user.id)
        .order_by(models.MaintenanceRequest.created_at.desc(), models.MaintenanceRequest.id.desc())
        .all()
    )
    return [repair_out(repair, unit_number) for repair, unit_number in rows]


# Report a problem in the tenant's home
@tenant_router.post("/repairs", response_model=PortalRepair, status_code=201)
def report_repair(
    data: RepairCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    homes = active_leases(db, tenant.id)
    if not homes:
        raise HTTPException(status_code=400, detail="You have no active tenancy to report a problem for")
    # Pick the home: the one asked for, or the newest
    chosen = homes[0]
    if data.lease_id is not None:
        matches = [row for row in homes if row[0].id == data.lease_id]
        if not matches:
            raise HTTPException(status_code=404, detail="Lease not found")
        chosen = matches[0]
    lease, unit, prop = chosen
    # Stop one tenant from filling the list
    open_count = (
        db.query(func.count(models.MaintenanceRequest.id))
        .filter(models.MaintenanceRequest.created_by_id == current_user.id, models.MaintenanceRequest.status != "fixed")
        .scalar()
    )
    if open_count >= MAX_OPEN_REPAIRS:
        raise HTTPException(status_code=400, detail=f"You already have {MAX_OPEN_REPAIRS} open problems. Please wait for some to be fixed")
    repair = models.MaintenanceRequest(
        property_id=prop.id,
        unit_id=unit.id,
        title=data.title.strip(),
        description=(data.description or "").strip() or None,
        priority=data.priority,
        status="open",
        created_by_id=current_user.id,
    )
    db.add(repair)
    db.commit()
    db.refresh(repair)
    return repair_out(repair, unit.unit_number)


# The owner's list of tenants and whether they have access
@access_router.get("", response_model=list[AccessRow])
def access_list(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    rows = {}
    # Tenants who live somewhere now
    living = (
        db.query(models.Tenant, models.Unit, models.Property)
        .join(models.Lease, models.Lease.tenant_id == models.Tenant.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Tenant.owner_id == current_user.id, models.Lease.status == "active")
        .order_by(models.Tenant.full_name)
        .all()
    )
    for tenant, unit, prop in living:
        if tenant.id not in rows:
            rows[tenant.id] = (tenant, unit.unit_number, prop.name)
    # The accounts (so tenants who left but still have access can be switched off)
    accounts = {account.tenant_id: account for account in db.query(TenantAccount).filter(TenantAccount.owner_id == current_user.id).all()}
    for tenant_id in accounts:
        if tenant_id not in rows:
            tenant = db.get(models.Tenant, tenant_id)
            if tenant:
                rows[tenant_id] = (tenant, None, None)
    users = {}
    if accounts:
        users = {user.id: user for user in db.query(models.User).filter(models.User.id.in_([a.user_id for a in accounts.values()])).all()}
    result = []
    for tenant_id, (tenant, unit_number, property_name) in rows.items():
        account = accounts.get(tenant_id)
        user = users.get(account.user_id) if account else None
        result.append(AccessRow(
            tenant_id=tenant_id,
            tenant_name=tenant.full_name,
            phone=tenant.phone,
            unit_number=unit_number,
            property_name=property_name,
            has_access=account is not None,
            is_active=bool(user and user.is_active),
            must_change_password=bool(account and account.must_change_password),
        ))
    result.sort(key=lambda row: row.tenant_name.lower())
    return result


# Get the payment details tenants see
@access_router.get("/payment-details", response_model=PaymentDetails)
def get_payment_details(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    settings = db.query(OwnerSettings).filter(OwnerSettings.owner_id == current_user.id).first()
    if settings is None:
        return PaymentDetails()
    return PaymentDetails(paybill_number=settings.paybill_number, account_hint=settings.account_hint, instructions=settings.instructions)


# Save the payment details tenants see
@access_router.put("/payment-details", response_model=PaymentDetails)
def save_payment_details(
    data: PaymentDetails,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    settings = db.query(OwnerSettings).filter(OwnerSettings.owner_id == current_user.id).first()
    if settings is None:
        settings = OwnerSettings(owner_id=current_user.id)
        db.add(settings)
    settings.paybill_number = data.paybill_number
    settings.account_hint = (data.account_hint or "").strip() or None
    settings.instructions = (data.instructions or "").strip() or None
    db.commit()
    return data


# Give a tenant portal access, or make a new temporary password for them
@access_router.post("/{tenant_id}", response_model=AccessGranted)
def give_access(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    # The tenant must be this owner's
    tenant = db.query(models.Tenant).filter(models.Tenant.id == tenant_id, models.Tenant.owner_id == current_user.id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    email = tenant_email(tenant.phone)
    temporary = make_temp_password()
    account = db.query(TenantAccount).filter(TenantAccount.tenant_id == tenant.id).first()
    # Is this phone number's login already taken by someone else?
    clash = db.query(models.User).filter(models.User.email == email).first()
    if account is None:
        if clash is not None:
            raise HTTPException(status_code=400, detail="This phone number already has a portal login (maybe with another landlord)")
        # Make the login
        user = models.User(
            full_name=tenant.full_name,
            email=email,
            phone=tenant.phone,
            password_hash=security.hash_password(temporary),
            role="tenant",
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(TenantAccount(tenant_id=tenant.id, user_id=user.id, owner_id=current_user.id, must_change_password=True))
    else:
        # The tenant already has a login: make a new temporary password (and follow a changed phone number)
        user = db.get(models.User, account.user_id)
        if clash is not None and clash.id != user.id:
            raise HTTPException(status_code=400, detail="This phone number already has a portal login (maybe with another landlord)")
        user.email = email
        user.phone = tenant.phone
        user.full_name = tenant.full_name
        user.password_hash = security.hash_password(temporary)
        user.is_active = True
        account.must_change_password = True
    # Sign them out of any old login
    mark_password_changed(db, user.id)
    db.commit()
    return AccessGranted(tenant_id=tenant.id, tenant_name=tenant.full_name, phone=tenant.phone, temporary_password=temporary)


# Switch a tenant's access on or off
@access_router.put("/{tenant_id}", response_model=AccessRow)
def set_access_active(
    tenant_id: int,
    data: AccessSwitch,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    account = db.query(TenantAccount).filter(TenantAccount.tenant_id == tenant_id, TenantAccount.owner_id == current_user.id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="This tenant has no portal access")
    user = db.get(models.User, account.user_id)
    tenant = db.get(models.Tenant, tenant_id)
    user.is_active = data.is_active
    db.commit()
    return AccessRow(
        tenant_id=tenant.id,
        tenant_name=tenant.full_name,
        phone=tenant.phone,
        unit_number=None,
        property_name=None,
        has_access=True,
        is_active=bool(user.is_active),
        must_change_password=bool(account.must_change_password),
    )


# The owner's notice board
@notices_router.get("", response_model=NoticesOverview)
def list_notices(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    rows = (
        db.query(Notice, models.Property.name)
        .outerjoin(models.Property, Notice.property_id == models.Property.id)
        .filter(Notice.owner_id == current_user.id)
        .order_by(Notice.pinned.desc(), Notice.created_at.desc(), Notice.id.desc())
        .all()
    )
    properties = db.query(models.Property).filter(models.Property.owner_id == current_user.id).order_by(models.Property.name).all()
    return NoticesOverview(
        notices=[notice_out(notice, property_name) for notice, property_name in rows],
        properties=[PropertyRef(id=prop.id, name=prop.name) for prop in properties],
    )


# Post a notice
@notices_router.post("", response_model=NoticeOut, status_code=201)
def create_notice(
    data: NoticeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    property_name = None
    # If it is for one property, that property must be theirs
    if data.property_id is not None:
        prop = db.query(models.Property).filter(models.Property.id == data.property_id, models.Property.owner_id == current_user.id).first()
        if prop is None:
            raise HTTPException(status_code=404, detail="Property not found")
        property_name = prop.name
    notice = Notice(
        owner_id=current_user.id,
        property_id=data.property_id,
        title=data.title.strip(),
        body=data.body.strip(),
        pinned=data.pinned,
        expires_on=data.expires_on,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice_out(notice, property_name)


# Edit a notice (send only the fields that changed)
@notices_router.put("/{notice_id}", response_model=NoticeOut)
def update_notice(
    notice_id: int,
    data: NoticeUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    notice = find_notice(db, notice_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    if "property_id" in changes and changes["property_id"] is not None:
        prop = db.query(models.Property).filter(models.Property.id == changes["property_id"], models.Property.owner_id == current_user.id).first()
        if prop is None:
            raise HTTPException(status_code=404, detail="Property not found")
    for field, value in changes.items():
        # These fields cannot be emptied out
        if field in ("title", "body", "pinned") and value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        setattr(notice, field, value)
    db.commit()
    db.refresh(notice)
    property_name = db.get(models.Property, notice.property_id).name if notice.property_id else None
    return notice_out(notice, property_name)


# Delete a notice
@notices_router.delete("/{notice_id}", status_code=204)
def delete_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    notice = find_notice(db, notice_id, current_user)
    db.delete(notice)
    db.commit()