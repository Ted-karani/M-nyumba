# Import the date tool so we can work with months and due dates
from datetime import date
# Import the tool that groups things together
from collections import defaultdict
# Import FastAPI tools for building endpoints
from fastapi import APIRouter, Depends
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user
# Reuse the owner check we wrote for properties
from routers.properties import require_owner

# Make a group of endpoints that all start with /billing
router = APIRouter(prefix="/billing", tags=["Rent"])


# One tenant's rent that is waiting to be added
class RentPreviewItem(BaseModel):
    # The lease's id
    lease_id: int
    # The tenant's name
    tenant_name: str
    # The unit number, like "A1"
    unit_number: str
    # The name of the property
    property_name: str
    # The monthly rent
    rent_amount: int
    # The months that will be charged, like ["2026-09", "2026-10"]
    periods: list[str]
    # The total for those months
    amount: int


# Everything the dashboard needs to show the "rent is ready" card
class RentPreview(BaseModel):
    # Today's date
    as_of: date
    # How many tenants will be charged
    lease_count: int
    # How many charges will be created
    charge_count: int
    # The total of all those charges
    total_amount: int
    # The details for each tenant
    items: list[RentPreviewItem]


# What we send back after the rent has been added
class RentGenerated(BaseModel):
    # How many tenants were charged
    lease_count: int
    # How many charges were created
    created_count: int
    # The total of all those charges
    total_amount: int


# Get the month after a given one: (2026, 12) becomes (2027, 1)
def next_month(year: int, month: int):
    # December rolls over into January of the next year
    if month == 12:
        return year + 1, 1
    # Any other month just moves forward by one
    return year, month + 1


# Work out which rent charges are missing for this owner's active leases
def find_pending_rent(db: Session, user: models.User, today: date):
    # Get every active lease of this owner, with its unit, property, and tenant
    rows = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == user.id, models.Lease.status == "active")
        .order_by(models.Property.name, models.Unit.unit_number)
        .all()
    )
    # The ids of those leases
    lease_ids = [row[0].id for row in rows]
    # For each lease, collect the months that already have a rent charge
    existing = defaultdict(set)
    if lease_ids:
        rent_rows = (
            db.query(models.Charge.lease_id, models.Charge.period)
            .filter(
                models.Charge.lease_id.in_(lease_ids),
                models.Charge.charge_type == "rent",
                models.Charge.period.isnot(None),
            )
            .all()
        )
        for lease_id, period in rent_rows:
            existing[lease_id].add(period)

    # This month written like "2026-10"
    current_period = f"{today.year}-{today.month:02d}"
    # The list of leases that need rent
    pending = []

    for lease, unit, prop, tenant in rows:
        # A lease with no rent amount has nothing to charge
        if lease.rent_amount <= 0:
            continue
        # The months this lease already has rent for
        have = existing[lease.id]
        # Find the latest month that already has rent (up to this month)
        earlier = [period for period in have if period <= current_period]
        if earlier:
            # Start from the month after it
            latest = max(earlier)
            year, month = next_month(int(latest[:4]), int(latest[5:7]))
        else:
            # No rent yet, so start from the month the tenant moved in
            year, month = lease.start_date.year, lease.start_date.month
        # Rent is due on the same day of the month as the move-in (never later than the 28th)
        due_day = min(lease.start_date.day, 28)
        # Collect every missing month up to and including this month
        periods = []
        while (year, month) <= (today.year, today.month):
            # Stop if the lease has a leaving date before this month even starts
            if lease.end_date is not None and date(year, month, 1) > lease.end_date:
                break
            period = f"{year}-{month:02d}"
            # Skip months that already have rent
            if period not in have:
                periods.append((period, date(year, month, due_day)))
            year, month = next_month(year, month)
        # Remember this lease if it has anything missing
        if periods:
            pending.append((lease, unit, prop, tenant, periods))

    # Send back the list
    return pending


# Show what rent would be added, without adding anything
@router.get("/rent-preview", response_model=RentPreview)
def rent_preview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Today's date
    today = date.today()
    # Find the missing rent
    pending = find_pending_rent(db, current_user, today)
    # Build one line for each tenant
    items = [
        RentPreviewItem(
            lease_id=lease.id,
            tenant_name=tenant.full_name,
            unit_number=unit.unit_number,
            property_name=prop.name,
            rent_amount=lease.rent_amount,
            periods=[period for period, due in periods],
            amount=lease.rent_amount * len(periods),
        )
        for lease, unit, prop, tenant, periods in pending
    ]
    # Add up the counts and the money
    charge_count = sum(len(item.periods) for item in items)
    total_amount = sum(item.amount for item in items)
    # Send it all back
    return RentPreview(
        as_of=today,
        lease_count=len(items),
        charge_count=charge_count,
        total_amount=total_amount,
        items=items,
    )


# Add the missing rent charges for everyone at once
@router.post("/generate-rent", response_model=RentGenerated)
def generate_rent(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add charges
    require_owner(current_user)
    # Find the missing rent
    pending = find_pending_rent(db, current_user, date.today())
    # Count what we create
    created = 0
    total = 0
    # Add one charge for each missing month
    for lease, unit, prop, tenant, periods in pending:
        for period, due_date in periods:
            db.add(models.Charge(
                lease_id=lease.id,
                charge_type="rent",
                amount=lease.rent_amount,
                period=period,
                due_date=due_date,
                description=f"Rent for {period}",
            ))
            created += 1
            total += lease.rent_amount
    # Save everything together (all of it is added, or none of it)
    if created:
        db.commit()
    # Tell the caller what happened
    return RentGenerated(lease_count=len(pending), created_count=created, total_amount=total)