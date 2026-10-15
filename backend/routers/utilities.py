# Import the tool that groups things together
from collections import defaultdict
# Import the date tool
from datetime import date
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote for properties
from routers.properties import require_owner, get_owned_property

# Make a group of endpoints that all start with /utilities
router = APIRouter(prefix="/utilities", tags=["Utilities"])

# The shape a month must have, like "2026-10"
PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
# The words we use for each metered utility
UTILITY_LABELS = {"water": "Water", "electricity": "Electricity"}


# One unit's line on the meter reading sheet
class SheetRow(BaseModel):
    # The unit's id
    unit_id: int
    # The unit number, like "A1"
    unit_number: str
    # The tenant living there
    tenant_name: str
    # The lease's id
    lease_id: int
    # The meter number written on the unit (if saved)
    meter_no: str | None
    # The last reading before this month (nothing if this is the first one)
    previous_reading: float | None
    # The id of this month's reading, if one was already saved
    reading_id: int | None
    # This month's reading, if one was already saved
    reading: float | None
    # Units used this month, if billed
    units_used: float | None
    # The price per unit used, if billed
    rate: float | None
    # The amount billed, if billed
    amount: int | None
    # True if a charge exists for this reading
    charged: bool


# The whole meter reading sheet
class MeterSheet(BaseModel):
    # The property the sheet is for
    property_id: int
    # "water" or "electricity"
    utility: str
    # The month, like "2026-10"
    period: str
    # One line for every occupied unit
    rows: list[SheetRow]


# One meter reading typed in by the landlord
class ReadingEntry(BaseModel):
    # The unit it is for
    unit_id: int
    # The number on the meter
    reading: float = Field(ge=0)


# The data we ask for when billing from meter readings
class BillRequest(BaseModel):
    # The property the readings are for
    property_id: int
    # "water" or "electricity"
    utility: Literal["water", "electricity"]
    # The month, like "2026-10"
    period: str = Field(pattern=PERIOD_PATTERN)
    # The price for each unit used, in shillings
    rate_per_unit: float = Field(default=0, ge=0)
    # The date the money must be paid by
    due_date: date
    # The readings, one for each unit
    readings: list[ReadingEntry] = Field(min_length=1, max_length=500)


# What we send back after billing
class BillResult(BaseModel):
    # How many readings were saved
    saved: int
    # How many charges were created
    charged: int
    # How many readings were saved as a first (starting) reading with no charge
    baselines: int
    # The total of all the charges created
    total_amount: int


# One unit's line on the Wi-Fi sheet
class WifiRow(BaseModel):
    # The unit's id
    unit_id: int
    # The unit number
    unit_number: str
    # The tenant living there
    tenant_name: str
    # The lease's id
    lease_id: int
    # True if Wi-Fi has already been charged for this month
    already_charged: bool


# The whole Wi-Fi sheet
class WifiSheet(BaseModel):
    # The property the sheet is for
    property_id: int
    # The month, like "2026-10"
    period: str
    # One line for every occupied unit
    rows: list[WifiRow]


# The data we ask for when charging Wi-Fi
class WifiBillRequest(BaseModel):
    # The property the charge is for
    property_id: int
    # The month, like "2026-10"
    period: str = Field(pattern=PERIOD_PATTERN)
    # The flat fee in shillings
    amount: int = Field(gt=0)
    # The date the money must be paid by
    due_date: date
    # The units to charge
    unit_ids: list[int] = Field(min_length=1, max_length=500)


# What we send back after charging Wi-Fi
class WifiBillResult(BaseModel):
    # How many tenants were charged
    charged: int
    # How many were skipped because they already had Wi-Fi charged this month
    skipped: int
    # The total of all the charges created
    total_amount: int


# Get the occupied units of a property, each with its active lease and tenant
def active_leases(db: Session, property_id: int):
    # Join leases to units and tenants, keeping only active leases in this property
    return (
        db.query(models.Lease, models.Unit, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Unit.property_id == property_id, models.Lease.status == "active")
        .order_by(models.Unit.unit_number)
        .all()
    )


# Get the meter reading sheet for a property, utility, and month
@router.get("/sheet", response_model=MeterSheet)
def meter_sheet(
    property_id: int = Query(...),
    utility: Literal["water", "electricity"] = Query(...),
    period: str = Query(..., pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Make sure the property is theirs
    prop = get_owned_property(db, property_id, current_user)
    # Get the occupied units
    rows = active_leases(db, prop.id)
    unit_ids = [unit.id for lease, unit, tenant in rows]
    # Group all the readings of these units for this utility, by unit
    readings_by_unit = defaultdict(list)
    if unit_ids:
        saved = (
            db.query(models.MeterReading)
            .filter(models.MeterReading.unit_id.in_(unit_ids), models.MeterReading.utility == utility)
            .all()
        )
        for item in saved:
            readings_by_unit[item.unit_id].append(item)
    # Find which of this month's charges still exist (they can be deleted on the tenant's page)
    charge_ids = [
        item.charge_id
        for items in readings_by_unit.values()
        for item in items
        if item.period == period and item.charge_id
    ]
    existing_charge_ids = set()
    if charge_ids:
        existing_charge_ids = {
            charge_id for (charge_id,) in db.query(models.Charge.id).filter(models.Charge.id.in_(charge_ids)).all()
        }
    # Build one line for each unit
    sheet_rows = []
    for lease, unit, tenant in rows:
        mine = readings_by_unit[unit.id]
        # This month's reading, if there is one
        this_month = next((item for item in mine if item.period == period), None)
        # The latest reading from an earlier month
        earlier = [item for item in mine if item.period < period]
        last = max(earlier, key=lambda item: item.period) if earlier else None
        sheet_rows.append(SheetRow(
            unit_id=unit.id,
            unit_number=unit.unit_number,
            tenant_name=tenant.full_name,
            lease_id=lease.id,
            meter_no=unit.water_meter_no if utility == "water" else unit.electricity_meter_no,
            previous_reading=this_month.previous_reading if this_month else (last.reading if last else None),
            reading_id=this_month.id if this_month else None,
            reading=this_month.reading if this_month else None,
            units_used=this_month.units_used if this_month else None,
            rate=this_month.rate if this_month else None,
            amount=this_month.amount if this_month else None,
            charged=bool(this_month and this_month.charge_id in existing_charge_ids),
        ))
    # Send the sheet back
    return MeterSheet(property_id=prop.id, utility=utility, period=period, rows=sheet_rows)


# Save meter readings and charge each tenant for what they used
@router.post("/bill", response_model=BillResult, status_code=201)
def bill_meters(
    data: BillRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can bill
    require_owner(current_user)
    # Make sure the property is theirs
    prop = get_owned_property(db, data.property_id, current_user)
    # The word we show for this utility
    label = UTILITY_LABELS[data.utility]
    # Look up each occupied unit by its id
    lease_by_unit = {unit.id: (lease, unit) for lease, unit, tenant in active_leases(db, prop.id)}

    # Check every reading BEFORE saving anything, so it is all saved or none of it is
    plan = []
    seen = set()
    for entry in data.readings:
        # The same unit cannot be listed twice
        if entry.unit_id in seen:
            raise HTTPException(status_code=400, detail="The same unit appears twice in the list")
        seen.add(entry.unit_id)
        # The unit must be occupied and inside this property
        if entry.unit_id not in lease_by_unit:
            raise HTTPException(status_code=400, detail="One of the units has no active tenant in this property")
        lease, unit = lease_by_unit[entry.unit_id]
        # A unit can only be billed once for each month
        already = (
            db.query(models.MeterReading)
            .filter(
                models.MeterReading.unit_id == unit.id,
                models.MeterReading.utility == data.utility,
                models.MeterReading.period == data.period,
            )
            .first()
        )
        if already:
            raise HTTPException(
                status_code=400,
                detail=f"Unit {unit.unit_number} already has a {label.lower()} reading for {data.period}. Undo it first to change it.",
            )
        # Find the latest reading from an earlier month
        earlier = (
            db.query(models.MeterReading)
            .filter(
                models.MeterReading.unit_id == unit.id,
                models.MeterReading.utility == data.utility,
                models.MeterReading.period < data.period,
            )
            .order_by(models.MeterReading.period.desc())
            .first()
        )
        previous = earlier.reading if earlier else None
        # A meter cannot go backwards
        if previous is not None and entry.reading < previous:
            raise HTTPException(
                status_code=400,
                detail=f"Unit {unit.unit_number}: the new reading ({entry.reading:g}) is lower than the last reading ({previous:g})",
            )
        # We need a price to charge anyone
        if previous is not None and data.rate_per_unit <= 0:
            raise HTTPException(status_code=400, detail="Enter the price per unit")
        plan.append((lease, unit, entry.reading, previous))

    # Everything checked out, so save it
    charged = 0
    baselines = 0
    total = 0
    for lease, unit, reading, previous in plan:
        # The very first reading is only a starting point, with nothing to charge
        if previous is None:
            db.add(models.MeterReading(
                unit_id=unit.id, utility=data.utility, period=data.period, reading=reading,
            ))
            baselines += 1
            continue
        # Work out how much was used and what it costs
        used = round(reading - previous, 3)
        amount = int(round(used * data.rate_per_unit))
        charge = None
        # Only create a charge if there is something to pay
        if amount > 0:
            charge = models.Charge(
                lease_id=lease.id,
                charge_type=data.utility,
                amount=amount,
                period=data.period,
                due_date=data.due_date,
                description=f"{label}: {used:g} units ({previous:g} to {reading:g}) at KSh {data.rate_per_unit:g}/unit",
            )
            db.add(charge)
            # This gives the charge its id right away, so the reading can point to it
            db.flush()
            charged += 1
            total += amount
        db.add(models.MeterReading(
            unit_id=unit.id,
            utility=data.utility,
            period=data.period,
            reading=reading,
            previous_reading=previous,
            rate=data.rate_per_unit,
            units_used=used,
            amount=amount,
            charge_id=charge.id if charge else None,
        ))
    # Save everything together
    db.commit()
    # Tell the caller what happened
    return BillResult(saved=len(plan), charged=charged, baselines=baselines, total_amount=total)


# Get the Wi-Fi sheet for a property and month
@router.get("/wifi-sheet", response_model=WifiSheet)
def wifi_sheet(
    property_id: int = Query(...),
    period: str = Query(..., pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Make sure the property is theirs
    prop = get_owned_property(db, property_id, current_user)
    # Get the occupied units
    rows = active_leases(db, prop.id)
    lease_ids = [lease.id for lease, unit, tenant in rows]
    # Find the leases that already have Wi-Fi charged for this month
    done = set()
    if lease_ids:
        done = {
            lease_id
            for (lease_id,) in db.query(models.Charge.lease_id)
            .filter(
                models.Charge.lease_id.in_(lease_ids),
                models.Charge.charge_type == "wifi",
                models.Charge.period == period,
            )
            .all()
        }
    # Build one line for each unit
    sheet_rows = [
        WifiRow(
            unit_id=unit.id,
            unit_number=unit.unit_number,
            tenant_name=tenant.full_name,
            lease_id=lease.id,
            already_charged=lease.id in done,
        )
        for lease, unit, tenant in rows
    ]
    # Send the sheet back
    return WifiSheet(property_id=prop.id, period=period, rows=sheet_rows)


# Charge a flat Wi-Fi fee to the chosen units
@router.post("/bill-wifi", response_model=WifiBillResult, status_code=201)
def bill_wifi(
    data: WifiBillRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can bill
    require_owner(current_user)
    # Make sure the property is theirs
    prop = get_owned_property(db, data.property_id, current_user)
    # Look up each occupied unit by its id
    lease_by_unit = {unit.id: lease for lease, unit, tenant in active_leases(db, prop.id)}
    # Find the leases that already have Wi-Fi charged for this month
        # The ids of all the occupied leases in this property
    all_lease_ids = [lease.id for lease in lease_by_unit.values()]
    already = set()
    if all_lease_ids:
        already = {
            lease_id
            for (lease_id,) in db.query(models.Charge.lease_id)
            .filter(
                models.Charge.lease_id.in_(all_lease_ids),
                models.Charge.charge_type == "wifi",
                models.Charge.period == data.period,
            )
            .all()
        }
    charged = 0
    skipped = 0
    total = 0
    # Check the units first, so nothing is saved if one of them is wrong
    for unit_id in set(data.unit_ids):
        if unit_id not in lease_by_unit:
            raise HTTPException(status_code=400, detail="One of the units has no active tenant in this property")
    # Add the charges
    for unit_id in set(data.unit_ids):
        lease = lease_by_unit[unit_id]
        # Never charge the same month twice
        if lease.id in already:
            skipped += 1
            continue
        db.add(models.Charge(
            lease_id=lease.id,
            charge_type="wifi",
            amount=data.amount,
            period=data.period,
            due_date=data.due_date,
            description=f"Wi-Fi for {data.period}",
        ))
        charged += 1
        total += data.amount
    # Save everything together
    db.commit()
    # Tell the caller what happened
    return WifiBillResult(charged=charged, skipped=skipped, total_amount=total)


# Undo a meter reading: removes the reading and the charge that came from it
@router.delete("/readings/{reading_id}", status_code=204)
def undo_reading(
    reading_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can undo
    require_owner(current_user)
    # Find the reading, but only if its unit's property belongs to this user
    reading = (
        db.query(models.MeterReading)
        .join(models.Unit, models.MeterReading.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.MeterReading.id == reading_id, models.Property.owner_id == current_user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    # Remove the charge that came from this reading (if it still exists)
    if reading.charge_id:
        charge = db.get(models.Charge, reading.charge_id)
        if charge:
            db.delete(charge)
    # Remove the reading itself
    db.delete(reading)
    db.commit()