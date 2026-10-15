# Import tools to group data and work with dates
from collections import defaultdict
from datetime import date, datetime, timedelta
# Import FastAPI tools for building endpoints
from fastapi import APIRouter, Depends, Query
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the tool that adds up and counts numbers in the database
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user

# Make a group of endpoints that all start with /dashboard
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# SETTING: days of grace after a due date before a charge counts as overdue
DEFAULT_GRACE_DAYS = 5
# SETTING: how many days ahead we look for leases that are ending
ENDING_SOON_DAYS = 30
# SETTING: how many repairs and vacant units the dashboard lists
MAX_REPAIRS_SHOWN = 5
MAX_VACANT_SHOWN = 50


# The unit numbers for the whole business or for one property
class UnitCounts(BaseModel):
    # How many units there are in total
    total: int
    # How many are occupied
    occupied: int
    # How many are vacant
    vacant: int
    # How many are under maintenance
    maintenance: int
    # The percentage of units that are occupied
    occupancy_percent: float


# One property's summary
class PropertySummary(BaseModel):
    # The property's id
    property_id: int
    # The property's name
    name: str
    # The county
    county: str | None
    # The town or estate
    town: str | None
    # The unit numbers for this property
    units: UnitCounts


# One tenant who is overdue
class OverdueItem(BaseModel):
    # The lease's id
    lease_id: int
    # The tenant's id
    tenant_id: int
    # The tenant's name
    tenant_name: str
    # The tenant's phone number (254... format, ready for WhatsApp later)
    tenant_phone: str
    # The unit number, like "A1"
    unit_number: str
    # The name of the property the unit is in
    property_name: str
    # Whether the lease is "active" or "ended"
    lease_status: str
    # How much is overdue in shillings
    amount_overdue: int
    # The due date of the oldest charge that is still unpaid
    oldest_due_date: date
    # How many days late that oldest charge is
    days_late: int


# One lease that is about to end
class EndingSoonItem(BaseModel):
    # The lease's id
    lease_id: int
    # The tenant's id
    tenant_id: int
    # The tenant's name
    tenant_name: str
    # The unit number
    unit_number: str
    # The name of the property
    property_name: str
    # The planned leaving date
    end_date: date
    # How many days are left
    days_left: int


# One empty unit
class VacantUnit(BaseModel):
    # The unit's id
    unit_id: int
    # The unit number
    unit_number: str
    # The kind of unit
    unit_type: str | None
    # The property it is in
    property_id: int
    # The property's name
    property_name: str
    # The monthly rent
    rent_amount: int


# One problem that is not fixed yet
class RepairBrief(BaseModel):
    # The request's id
    id: int
    # The title
    title: str
    # "low", "normal", or "urgent"
    priority: str
    # "open" or "in_progress"
    status: str
    # The property it is in
    property_name: str
    # The unit it is in (empty for the whole property)
    unit_number: str | None
    # When it was reported
    created_at: datetime


# A summary of the problems that are not fixed yet
class RepairsSummary(BaseModel):
    # How many are open
    open_count: int
    # How many are in progress
    in_progress_count: int
    # How many are urgent
    urgent_count: int
    # The most pressing ones (urgent first)
    items: list[RepairBrief]


# Everything the dashboard sends back
class Dashboard(BaseModel):
    # Today's date
    as_of: date
    # The grace days used for this calculation
    grace_days: int
    # The unit numbers across all properties
    units: UnitCounts
    # Money received since the 1st of this month
    collected_this_month: int
    # Total of all overdue amounts
    total_overdue: int
    # Everything tenants still owe, including charges not yet due
    total_outstanding: int
    # How many tenants are overdue
    overdue_count: int
    # The overdue tenants, the latest payers first
    overdue: list[OverdueItem]
    # Active leases ending within the next 30 days
    ending_soon: list[EndingSoonItem]
    # The empty units
    vacant_units: list[VacantUnit]
    # The problems that are not fixed yet
    repairs: RepairsSummary
    # The summary of each property
    properties: list[PropertySummary]


# Build the unit numbers from three counts
def build_counts(vacant: int, occupied: int, maintenance: int) -> UnitCounts:
    # Add them up to get the total
    total = vacant + occupied + maintenance
    # Work out the occupancy percentage (0 if there are no units, to avoid dividing by zero)
    percent = round(occupied / total * 100, 1) if total else 0.0
    # Send back the finished numbers
    return UnitCounts(total=total, occupied=occupied, vacant=vacant, maintenance=maintenance, occupancy_percent=percent)


# Get the dashboard numbers for the logged-in owner
@router.get("", response_model=Dashboard)
def get_dashboard(
    grace_days: int = Query(default=DEFAULT_GRACE_DAYS, ge=0, le=60),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Today's date
    today = date.today()
    # Charges due on or before this date are overdue (today minus the grace days)
    cutoff = today - timedelta(days=grace_days)

    # ---- PROPERTIES AND UNIT COUNTS ----
    # Get all of this owner's properties
    properties = (
        db.query(models.Property)
        .filter(models.Property.owner_id == current_user.id)
        .order_by(models.Property.name)
        .all()
    )
    # Count this owner's units for each property and status
    unit_rows = (
        db.query(models.Unit.property_id, models.Unit.status, func.count(models.Unit.id))
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == current_user.id)
        .group_by(models.Unit.property_id, models.Unit.status)
        .all()
    )
    # Store the counts in a simple lookup: counts[property_id]["vacant"]
    counts = defaultdict(lambda: {"vacant": 0, "occupied": 0, "maintenance": 0})
    for property_id, status, number in unit_rows:
        counts[property_id][status] = number
    # Build the summary for each property and the totals for everything
    property_summaries = []
    all_vacant = all_occupied = all_maintenance = 0
    for prop in properties:
        # The counts for this property (zeros if it has no units yet)
        c = counts[prop.id]
        # Add them to the grand totals
        all_vacant += c["vacant"]
        all_occupied += c["occupied"]
        all_maintenance += c["maintenance"]
        # Save this property's summary
        property_summaries.append(PropertySummary(
            property_id=prop.id,
            name=prop.name,
            county=prop.county,
            town=prop.town,
            units=build_counts(c["vacant"], c["occupied"], c["maintenance"]),
        ))

    # ---- EMPTY UNITS ----
    # Get this owner's vacant units, grouped by property
    vacant_rows = (
        db.query(models.Unit, models.Property)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == current_user.id, models.Unit.status == "vacant")
        .order_by(models.Property.name, models.Unit.unit_number)
        .limit(MAX_VACANT_SHOWN)
        .all()
    )
    vacant_units = [
        VacantUnit(
            unit_id=unit.id,
            unit_number=unit.unit_number,
            unit_type=unit.unit_type,
            property_id=prop.id,
            property_name=prop.name,
            rent_amount=unit.rent_amount,
        )
        for unit, prop in vacant_rows
    ]

    # ---- PROBLEMS THAT ARE NOT FIXED YET ----
    # Get this owner's repairs that are still open or in progress, newest first
    repair_rows = (
        db.query(models.MaintenanceRequest, models.Property, models.Unit)
        .join(models.Property, models.MaintenanceRequest.property_id == models.Property.id)
        .outerjoin(models.Unit, models.MaintenanceRequest.unit_id == models.Unit.id)
        .filter(models.Property.owner_id == current_user.id, models.MaintenanceRequest.status != "fixed")
        .order_by(models.MaintenanceRequest.created_at.desc(), models.MaintenanceRequest.id.desc())
        .all()
    )
    # Put urgent problems first (the sort keeps "newest first" inside each group)
    priority_rank = {"urgent": 0, "normal": 1, "low": 2}
    repair_rows.sort(key=lambda row: priority_rank[row[0].priority])
    repairs = RepairsSummary(
        open_count=sum(1 for row in repair_rows if row[0].status == "open"),
        in_progress_count=sum(1 for row in repair_rows if row[0].status == "in_progress"),
        urgent_count=sum(1 for row in repair_rows if row[0].priority == "urgent"),
        items=[
            RepairBrief(
                id=repair.id,
                title=repair.title,
                priority=repair.priority,
                status=repair.status,
                property_name=prop.name,
                unit_number=unit.unit_number if unit else None,
                created_at=repair.created_at,
            )
            for repair, prop, unit in repair_rows[:MAX_REPAIRS_SHOWN]
        ],
    )

    # ---- MONEY COLLECTED THIS MONTH ----
    # The first day of this month
    month_start = today.replace(day=1)
    # Add up this owner's payments received since then
    collected = (
        db.query(func.coalesce(func.sum(models.Payment.amount), 0))
        .select_from(models.Payment)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == current_user.id, models.Payment.paid_on >= month_start)
        .scalar()
    )

    # ---- OVERDUE TENANTS AND ENDING SOON ----
    # Get every lease of this owner together with its unit, property, and tenant
    lease_rows = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == current_user.id)
        .all()
    )
    # The ids of those leases
    lease_ids = [row[0].id for row in lease_rows]
    # Group each lease's charges together, oldest due date first
    charges_by_lease = defaultdict(list)
    # Total paid for each lease
    paid_by_lease = {}
    if lease_ids:
        # Get all the charges for these leases
        charges = (
            db.query(models.Charge)
            .filter(models.Charge.lease_id.in_(lease_ids))
            .order_by(models.Charge.due_date, models.Charge.id)
            .all()
        )
        for charge in charges:
            charges_by_lease[charge.lease_id].append(charge)
        # Add up the payments for each lease
        paid_rows = (
            db.query(models.Payment.lease_id, func.sum(models.Payment.amount))
            .filter(models.Payment.lease_id.in_(lease_ids))
            .group_by(models.Payment.lease_id)
            .all()
        )
        paid_by_lease = {lease_id: total for lease_id, total in paid_rows}

    # Lists and totals we fill in below
    overdue_items = []
    ending_items = []
    total_overdue = 0
    total_outstanding = 0
    # The last day we count as "ending soon"
    ending_limit = today + timedelta(days=ENDING_SOON_DAYS)

    for lease, unit, prop, tenant in lease_rows:
        # What this lease has been charged and has paid
        lease_charges = charges_by_lease[lease.id]
        total_charged = sum(c.amount for c in lease_charges)
        paid = paid_by_lease.get(lease.id, 0)
        # Everything still owed (never below zero, so credits do not hide debts)
        total_outstanding += max(0, total_charged - paid)

        # Use the payments on the oldest charges first, and find what is still overdue
        pool = paid
        overdue_amount = 0
        oldest_due = None
        for charge in lease_charges:
            # How much of this charge the remaining payments cover
            covered = min(pool, charge.amount)
            pool -= covered
            remaining = charge.amount - covered
            # Count it as overdue if it is unpaid and past the grace period
            if remaining > 0 and charge.due_date <= cutoff:
                overdue_amount += remaining
                # Remember the due date of the oldest unpaid charge
                if oldest_due is None:
                    oldest_due = charge.due_date

        # Add this tenant to the overdue list if they owe anything past the grace period
        if overdue_amount > 0:
            total_overdue += overdue_amount
            overdue_items.append(OverdueItem(
                lease_id=lease.id,
                tenant_id=tenant.id,
                tenant_name=tenant.full_name,
                tenant_phone=tenant.phone,
                unit_number=unit.unit_number,
                property_name=prop.name,
                lease_status=lease.status,
                amount_overdue=overdue_amount,
                oldest_due_date=oldest_due,
                days_late=(today - oldest_due).days,
            ))

        # Add active leases that end within the next 30 days
        if lease.status == "active" and lease.end_date is not None and today <= lease.end_date <= ending_limit:
            ending_items.append(EndingSoonItem(
                lease_id=lease.id,
                tenant_id=tenant.id,
                tenant_name=tenant.full_name,
                unit_number=unit.unit_number,
                property_name=prop.name,
                end_date=lease.end_date,
                days_left=(lease.end_date - today).days,
            ))

    # The most late tenants first
    overdue_items.sort(key=lambda item: item.days_late, reverse=True)
    # The soonest endings first
    ending_items.sort(key=lambda item: item.end_date)

    # Put everything together and send it back
    return Dashboard(
        as_of=today,
        grace_days=grace_days,
        units=build_counts(all_vacant, all_occupied, all_maintenance),
        collected_this_month=collected,
        total_overdue=total_overdue,
        total_outstanding=total_outstanding,
        overdue_count=len(overdue_items),
        overdue=overdue_items,
        ending_soon=ending_items,
        vacant_units=vacant_units,
        repairs=repairs,
        properties=property_summaries,
    )