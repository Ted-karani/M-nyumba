# admin_models.py - the tables and rules for landlord accounts, plans and subscription payments

# Import the tools we need
import calendar
import re
# Import the date and time tools
from datetime import date, datetime, timedelta
# Import FastAPI tools for errors and requests
from fastapi import HTTPException, Request
# Import the column types and tools we need for the tables
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from database import Base
from portal_models import TenantAccount

# After a landlord's access ends, they get this many days before the account turns read-only
GRACE_DAYS = 7
# The kinds of request that change things
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# In read-only mode these addresses still work (changing your own password, 2-step login, and tenants paying)
READ_ONLY_OK = ("/account/", "/setup/", "/portal/change-password", "/portal/mpesa/")
# The addresses that make new units (so the unit limit can be checked)
UNIT_CREATING = (re.compile(r"^/properties/\d+/units$"), re.compile(r"^/onboarding/existing-tenants$"))


# This class is the "owner_accounts" table. Each landlord has one row: their plan, status and limits.
class OwnerAccount(Base):
    # The name of the table inside the database
    __tablename__ = "owner_accounts"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord (points to the users table, one row per landlord)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # Their plan: "pilot" (free trial) or "paid"
    plan = Column(String, nullable=False, default="pilot")
    # What the admin set: "active", "read_only", "suspended" or "closed"
    status = Column(String, nullable=False, default="active")
    # The last day their access is paid for (empty means no end date)
    paid_until = Column(Date, nullable=True)
    # The most units they may have (empty means no limit)
    unit_limit = Column(Integer, nullable=True)
    # Private notes only the admin sees
    notes = Column(Text, nullable=True)
    # A message the landlord sees when their account is read-only, suspended or closed
    status_note = Column(String, nullable=True)
    # True until the landlord has chosen their own password
    must_change_password = Column(Boolean, nullable=False, default=False)
    # When the account was closed
    closed_at = Column(DateTime, nullable=True)
    # When the row was made, and last changed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# This class is the "subscription_payments" table. Each payment a landlord made to us is one row.
class SubscriptionPayment(Base):
    # The name of the table inside the database
    __tablename__ = "subscription_payments"

    # A unique number for each payment, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord who paid (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # The amount in shillings
    amount = Column(Integer, nullable=False)
    # How it was paid: "mpesa", "cash", "bank" or "other"
    method = Column(String, nullable=False, default="mpesa")
    # The M-Pesa code or other reference
    reference = Column(String, nullable=True)
    # How many months this payment bought
    months = Column(Integer, nullable=False)
    # The day the money was received
    paid_on = Column(Date, nullable=False)
    # The last day of access after this payment
    covers_until = Column(Date, nullable=False)
    # The admin who recorded it (points to the users table)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # A short note
    note = Column(String, nullable=True)
    # When it was recorded
    created_at = Column(DateTime, default=datetime.utcnow)


# This class is the "admin_events" table. Each thing the admin did to an account is one row.
class AdminEvent(Base):
    # The name of the table inside the database
    __tablename__ = "admin_events"

    # A unique number for each event, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The admin who did it (points to the users table)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The landlord it was done to (empty if it was not about one landlord)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # What was done, in words
    action = Column(String, nullable=False)
    # More detail
    detail = Column(String, nullable=True)
    # When it happened
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# Add a number of months to a date (the day is kept, or moved back to the last day of a shorter month)
def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


# Find which landlord's business a person belongs to (owners themselves, their caretakers, and their tenants)
def owner_id_of(db: Session, user: models.User):
    if user.role == "owner":
        return user.id
    if user.role == "caretaker":
        account = db.query(models.CaretakerAccount).filter(models.CaretakerAccount.user_id == user.id).first()
        return account.owner_id if account else None
    if user.role == "tenant":
        account = db.query(TenantAccount).filter(TenantAccount.user_id == user.id).first()
        return account.owner_id if account else None
    return None


# Get a landlord's account row, making one (a free pilot with no end date) if they do not have one yet
def get_or_create_account(db: Session, owner_id: int) -> OwnerAccount:
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).first()
    if account is None:
        account = OwnerAccount(owner_id=owner_id, plan="pilot", status="active", must_change_password=False)
        db.add(account)
        db.flush()
    return account


# Work out what an account can really do today: "active", "read_only", "suspended" or "closed", plus a message
def effective_state(account: OwnerAccount, today: date | None = None):
    today = today or date.today()
    # The admin switched the account off
    if account.status in ("suspended", "closed"):
        return account.status, account.status_note
    # The admin set it to read-only
    if account.status == "read_only":
        return "read_only", account.status_note or "This account is read-only."
    # Access ended more than a few days ago
    if account.paid_until is not None and today > account.paid_until + timedelta(days=GRACE_DAYS):
        label = "Your free trial ended" if account.plan == "pilot" else "Your subscription ended"
        return "read_only", f"{label} on {account.paid_until.strftime('%d %b %Y')}. Please contact support to continue."
    return "active", None


# If a person's business is suspended or closed, give the message to show at sign-in (otherwise nothing)
def login_block_message(db: Session, user: models.User):
    owner_id = owner_id_of(db, user)
    if owner_id is None:
        return None
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).first()
    if account is None:
        return None
    state, message = effective_state(account)
    if state == "suspended":
        return message or "This account is suspended. Please contact support."
    if state == "closed":
        return message or "This account has been closed."
    return None


# The account rules every signed-in request must pass: suspended, first password, read-only, and the unit limit
def enforce_account_rules(db: Session, user: models.User, request: Request):
    # Admins are not part of any landlord's business
    owner_id = owner_id_of(db, user)
    if owner_id is None:
        return
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).first()
    # Landlords with no account row yet are treated as active with no limits
    if account is None:
        return
    path = request.url.path
    state, message = effective_state(account)
    # Suspended and closed businesses are shut out completely
    if state == "suspended":
        raise HTTPException(status_code=403, detail=message or "This account is suspended. Please contact support.")
    if state == "closed":
        raise HTTPException(status_code=403, detail=message or "This account has been closed.")
    # A new landlord must choose their own password before anything else
    if user.role == "owner" and account.must_change_password:
        if not (path.startswith("/setup/") or path == "/auth/me"):
            raise HTTPException(status_code=403, detail="Please choose your own password first")
    # Read-only means nothing can be changed (except the few things listed above)
    if state == "read_only" and request.method in WRITE_METHODS and not path.startswith(READ_ONLY_OK):
        raise HTTPException(status_code=403, detail=f"{message} You can look at everything, but not change anything.")
    # The unit limit
    if account.unit_limit is not None and request.method == "POST" and any(pattern.match(path) for pattern in UNIT_CREATING):
        count = (
            db.query(func.count(models.Unit.id))
            .join(models.Property, models.Unit.property_id == models.Property.id)
            .filter(models.Property.owner_id == owner_id)
            .scalar()
        )
        if count >= account.unit_limit:
            raise HTTPException(status_code=403, detail=f"Your plan allows {account.unit_limit} units. Please contact support to add more.")


# Write down something the admin did (the caller saves it to the database)
def log_admin(db: Session, admin: models.User, owner_id, action: str, detail: str | None = None):
    db.add(AdminEvent(admin_id=admin.id, owner_id=owner_id, action=action, detail=detail))