# Import the tool that finds the nearest spelling
import difflib
# Import the tool that checks text patterns
import re
# Import the date tool
from datetime import date
# Import FastAPI tools for building endpoints
from fastapi import APIRouter, Depends
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, ValidationError, field_validator
# Import the tool that lets us compare text without caring about capital letters
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user
# Reuse the owner check and the phone cleaner we wrote earlier
from routers.properties import require_owner
from schemas import clean_phone

# Make a group of endpoints that all start with /onboarding
router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

# The most rows we accept in one list
MAX_ROWS = 300


# Turn empty text into "nothing"
def blank_to_none(value):
    # Nothing was given
    if value is None:
        return None
    # Only spaces were given
    if isinstance(value, str) and value.strip() == "":
        return None
    # Something real was given
    return value


# Turn an amount typed in any style into a whole number: "6,000", "KSh 6000", and 6000 all become 6000
def clean_money(value):
    # Nothing was given means zero
    if value is None:
        return 0
    # A number stays a number
    if isinstance(value, (int, float)):
        return int(value)
    # Read it as text
    text = str(value).strip()
    if text == "":
        return 0
    # Amounts cannot be negative
    if text.startswith("-"):
        raise ValueError("Amounts cannot be negative")
    # Keep only the digits before any decimal point
    digits = re.sub(r"[^\d]", "", text.split(".")[0])
    if digits == "":
        raise ValueError("Write the amount as a number, like 6000")
    return int(digits)


# One existing tenant, as typed in the form or in a spreadsheet
class ExistingTenantRow(BaseModel):
    # The property's name (it must match one of your properties)
    property_name: str = Field(min_length=1)
    # The house or door number, like "A12" (created if it does not exist yet)
    unit_number: str = Field(min_length=1, max_length=20)
    # The kind of unit (only used when the unit is created)
    unit_type: str | None = None
    # The tenant's full name
    tenant_name: str = Field(min_length=2)
    # The tenant's phone number (cleaned to the 254... format)
    phone: str
    # The tenant's ID number (optional)
    id_number: str | None = None
    # The monthly rent (leave it empty when the unit already exists and has its rent set)
    rent_amount: int = Field(default=0, ge=0)
    # The deposit they paid (kept on the lease for the record, never charged again)
    deposit_amount: int = Field(default=0, ge=0)
    # What they owe today
    balance: int = Field(default=0, ge=0)
    # The first month the app should charge rent, like 2026-11 (empty means this month)
    billing_from: str | None = None
    # The day of the month rent is due
    due_day: int = Field(default=5, ge=1, le=28)
    # The date they first moved in, only kept as a note
    tenant_since: date | None = None

    # Empty boxes become "nothing"
    @field_validator("unit_type", "id_number", "billing_from", "tenant_since", mode="before")
    @classmethod
    def empty_is_none(cls, value):
        return blank_to_none(value)

    # Amounts can be typed in any style
    @field_validator("rent_amount", "deposit_amount", "balance", mode="before")
    @classmethod
    def money_is_clean(cls, value):
        return clean_money(value)

    # An empty due day means the 5th
    @field_validator("due_day", mode="before")
    @classmethod
    def day_is_clean(cls, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return 5
        try:
            return int(str(value).strip())
        except ValueError:
            raise ValueError("Write the day of the month as a number, like 5")

    # Clean the phone number, or complain if it is not a Kenyan number
    @field_validator("phone")
    @classmethod
    def phone_is_clean(cls, value):
        return clean_phone(value)

    # The billing month must look like 2026-11
    @field_validator("billing_from")
    @classmethod
    def month_is_clean(cls, value):
        if value is None:
            return None
        match = re.match(r"^(\d{4})-(\d{2})", value.strip())
        if not match or not 1 <= int(match.group(2)) <= 12:
            raise ValueError("Write the month like 2026-11")
        return f"{match.group(1)}-{match.group(2)}"


# The data we ask for: a list of rows, and whether to only check them
class ImportRequest(BaseModel):
    # The rows exactly as typed (we check each one ourselves, so one bad row does not hide the others)
    rows: list[dict] = Field(min_length=1, max_length=MAX_ROWS)
    # True means "only check, save nothing"
    dry_run: bool = True


# What we found out about one row
class RowResult(BaseModel):
    # Which row it is (1 is the first row)
    row_number: int
    # True if the row is fine
    ok: bool
    # "Ready to import", or what is wrong
    message: str
    # The tenant's name as typed
    tenant_name: str | None = None
    # The unit number as typed
    unit_number: str | None = None
    # True if the unit will be created
    new_unit: bool = False
    # True if the tenant will be created
    new_tenant: bool = False


# What we send back
class ImportResult(BaseModel):
    # True if every row is fine
    ok: bool
    # True if nothing was saved because it was only a check
    dry_run: bool
    # How many tenants were saved
    imported: int
    # How many rows have a problem
    error_count: int
    # What we found out about each row
    results: list[RowResult]


# Turn a validation error into one readable sentence
def first_error(err: ValidationError) -> str:
    # Take the first problem
    first = err.errors()[0]
    # Find which field it is about
    field = str(first["loc"][-1]) if first["loc"] else ""
    # Tidy up the message
    message = first["msg"].replace("Value error, ", "")
    # Show "field: message" when we know the field
    return f"{field.replace('_', ' ')}: {message}" if field else message


# Check every row and work out what would be created (nothing is saved here)
def plan_rows(db: Session, owner: models.User, raw_rows: list[dict]):
    # This owner's properties, found by their lowercase name
    properties = {
        prop.name.strip().lower(): prop
        for prop in db.query(models.Property).filter(models.Property.owner_id == owner.id).all()
    }
    results = []
    plan = []
    # Units and phone numbers we already met earlier in the same list
    seen_units = set()
    seen_phones = set()

    # Record a row that has a problem
    def fail(number, raw, message):
        results.append(RowResult(
            row_number=number,
            ok=False,
            message=message,
            tenant_name=str(raw.get("tenant_name") or "").strip() or None,
            unit_number=str(raw.get("unit_number") or "").strip() or None,
        ))

    for number, raw in enumerate(raw_rows, start=1):
        # Check the row's own values first
        try:
            row = ExistingTenantRow.model_validate(raw)
        except ValidationError as err:
            fail(number, raw, first_error(err))
            continue
        # The property must be one of theirs
        prop = properties.get(row.property_name.strip().lower())
        if prop is None:
            # Suggest the nearest building name, in case it is only a spelling mistake
            nearest = difflib.get_close_matches(row.property_name.strip().lower(), list(properties.keys()), n=1, cutoff=0.6)
            hint = f" Did you mean '{properties[nearest[0]].name}'?" if nearest else ""
            fail(number, raw, f"Property '{row.property_name.strip()}' was not found.{hint} New buildings are added with Quick setup (More, then Quick setup)")
            continue
        # The same unit cannot appear twice in one list
        unit_key = (prop.id, row.unit_number.strip().lower())
        if unit_key in seen_units:
            fail(number, raw, f"Unit {row.unit_number.strip()} appears twice in this list")
            continue
        seen_units.add(unit_key)
        # Find the unit if it already exists
        unit = (
            db.query(models.Unit)
            .filter(
                models.Unit.property_id == prop.id,
                func.lower(models.Unit.unit_number) == row.unit_number.strip().lower(),
            )
            .first()
        )
        # An occupied unit, or one under repair, cannot be given to a new tenant
        if unit is not None and unit.status == "occupied":
            fail(number, raw, f"Unit {unit.unit_number} is already occupied")
            continue
        if unit is not None and unit.status == "maintenance":
            fail(number, raw, f"Unit {unit.unit_number} is under repair. Set it to vacant first")
            continue
        # An empty rent means "use the unit's own rent"
        if row.rent_amount == 0:
            if unit is None:
                fail(number, raw, f"Rent amount is needed, because unit {row.unit_number.strip()} does not exist yet")
                continue
            if unit.rent_amount <= 0:
                fail(number, raw, f"No rent is set for unit {unit.unit_number}. Write the rent amount in your list")
                continue
            row.rent_amount = unit.rent_amount
        # Find the tenant if they already exist (matched by phone number)
        tenant = (
            db.query(models.Tenant)
            .filter(models.Tenant.owner_id == owner.id, models.Tenant.phone == row.phone)
            .first()
        )
        # A tenant who appears for the first time in this list will be created once
        is_new_tenant = tenant is None and row.phone not in seen_phones
        seen_phones.add(row.phone)
        results.append(RowResult(
            row_number=number,
            ok=True,
            message="Ready to import",
            tenant_name=row.tenant_name.strip(),
            unit_number=row.unit_number.strip(),
            new_unit=unit is None,
            new_tenant=is_new_tenant,
        ))
        plan.append((row, prop, unit, tenant))

    # Hand back what we found
    return results, plan


# Save everything in the plan (only called after every row was checked and found fine)
def create_rows(db: Session, owner: models.User, plan) -> int:
    today = date.today()
    # Tenants created during this import, so the same phone is only created once
    tenants_by_phone = {}
    created = 0
    for row, prop, unit, tenant in plan:
        # Create the unit if it does not exist yet
        if unit is None:
            unit = models.Unit(
                property_id=prop.id,
                unit_number=row.unit_number.strip(),
                unit_type=row.unit_type,
                rent_amount=row.rent_amount,
                deposit_amount=row.deposit_amount,
                status="vacant",
            )
            db.add(unit)
            db.flush()
        # Create the tenant if they do not exist yet
        if tenant is None:
            tenant = tenants_by_phone.get(row.phone)
            if tenant is None:
                tenant = models.Tenant(
                    owner_id=owner.id,
                    full_name=row.tenant_name.strip(),
                    phone=row.phone,
                    id_number=row.id_number,
                )
                db.add(tenant)
                db.flush()
                tenants_by_phone[row.phone] = tenant
        # The lease starts in the month rent billing should begin, on the rent due day
        period = row.billing_from or f"{today.year}-{today.month:02d}"
        start_date = date(int(period[:4]), int(period[5:7]), row.due_day)
        # Keep the real move-in date as a note
        notes = "Existing tenant"
        if row.tenant_since:
            notes += f", living here since {row.tenant_since.strftime('%d %b %Y')}"
        lease = models.Lease(
            unit_id=unit.id,
            tenant_id=tenant.id,
            start_date=start_date,
            rent_amount=row.rent_amount,
            deposit_amount=row.deposit_amount,
            status="active",
            notes=notes,
        )
        db.add(lease)
        db.flush()
        # What they owe today becomes one charge (no deposit and no past rent are charged)
        if row.balance > 0:
            db.add(models.Charge(
                lease_id=lease.id,
                charge_type="other",
                amount=row.balance,
                period=None,
                due_date=today,
                description="Balance brought forward",
            ))
        # The unit is occupied now
        unit.status = "occupied"
        created += 1
    # Save everything together
    db.commit()
    return created


# Check a list of existing tenants, and save it if every row is fine
@router.post("/existing-tenants", response_model=ImportResult)
def import_existing(
    data: ImportRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can set up tenants
    require_owner(current_user)
    # Check every row
    results, plan = plan_rows(db, current_user, data.rows)
    # Count the rows with problems
    errors = sum(1 for result in results if not result.ok)
    # Save only when every row is fine, and this is not just a check
    imported = 0
    if errors == 0 and not data.dry_run:
        imported = create_rows(db, current_user, plan)
    # Tell the caller what happened
    return ImportResult(
        ok=errors == 0,
        dry_run=data.dry_run,
        imported=imported,
        error_count=errors,
        results=results,
    )