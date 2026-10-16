# Import the tool that groups things together
from collections import defaultdict
# Import the date tools
from datetime import date, timedelta
# Import the tool that holds a file in memory
from io import BytesIO
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, Query, Response
# Import the Excel tools
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import tools to add up numbers and to search with "or"
from sqlalchemy import func, or_
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user
from routers.expenses import CategoryTotal, Expense, PERIOD_PATTERN, month_range
from routers.properties import get_owned_property, require_owner

# Make a group of endpoints that all start with /reports
router = APIRouter(prefix="/reports", tags=["Reports"])


# The money received, split by how it was paid
class MethodTotals(BaseModel):
    # Received by M-Pesa
    mpesa: int = 0
    # Received in cash
    cash: int = 0
    # Received by bank
    bank: int = 0


# One property's line in the report
class PropertyRow(BaseModel):
    # The property's id
    property_id: int
    # The property's name
    name: str
    # Money received this month
    collected: int
    # Money spent this month (including repairs)
    expenses: int
    # What is left (collected minus expenses)
    net: int
    # How many units there are
    units_total: int
    # How many are occupied
    units_occupied: int
    # The percentage occupied
    occupancy_percent: float


# One empty unit
class VacantRow(BaseModel):
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
    # How many days it has been empty
    vacant_days: int
    # The date it became empty
    since: date


# One month in the chart
class TrendPoint(BaseModel):
    # The month, like "2026-10"
    month: str
    # Money received
    collected: int
    # Money spent
    spent: int


# Everything the monthly report shows
class MonthlyReport(BaseModel):
    # The month, like "2026-10"
    month: str
    # The property chosen (empty means all properties)
    property_id: int | None
    # The property's name
    property_name: str | None
    # The date the report was made
    generated_on: date
    # Money received this month
    collected: int
    # The money received, split by how it was paid
    by_method: MethodTotals
    # Everything that fell due this month
    billed: int
    # What tenants still owed at the end of the month (counting only charges due by then)
    owed_at_month_end: int
    # Money spent this month, including repairs
    expenses_total: int
    # Money spent, by kind (repairs are shown separately)
    expenses_by_category: list[CategoryTotal]
    # Repair costs for repairs fixed this month
    repairs_cost: int
    # The part of the spending that is not tied to one property
    general_expenses: int
    # What is left (collected minus expenses)
    net: int
    # How many units there are
    units_total: int
    # How many are occupied
    units_occupied: int
    # The percentage occupied
    occupancy_percent: float
    # "now" if occupancy is today's, or "month_end" if it was worked out from lease dates
    occupancy_basis: str
    # The units that are empty right now, longest empty first
    vacant_now: list[VacantRow]
    # One line for each property
    properties: list[PropertyRow]
    # The last 6 months, for the chart
    trend: list[TrendPoint]


# Move a month forwards or backwards: shift_month("2026-10", -1) is "2026-09"
def shift_month(month: str, change: int) -> str:
    # Count months from year zero, then turn it back into a year and a month
    index = int(month[:4]) * 12 + (int(month[5:7]) - 1) + change
    return f"{index // 12}-{index % 12 + 1:02d}"


# Work out the whole report
def build_report(db: Session, owner: models.User, month: str, property_id: int | None) -> MonthlyReport:
    start, end = month_range(month)
    last_day = end - timedelta(days=1)
    today = date.today()

    # Which properties are in this report?
    selected = None
    if property_id is not None:
        selected = get_owned_property(db, property_id, owner)
        properties = [selected]
    else:
        properties = (
            db.query(models.Property).filter(models.Property.owner_id == owner.id).order_by(models.Property.name).all()
        )
    prop_ids = [prop.id for prop in properties]

    # ---- MONEY IN ----
    payment_rows = (
        db.query(models.Payment.amount, models.Payment.method, models.Unit.property_id)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(
            models.Unit.property_id.in_(prop_ids),
            models.Payment.paid_on >= start,
            models.Payment.paid_on < end,
        )
        .all()
    )
    by_method = {"mpesa": 0, "cash": 0, "bank": 0}
    collected_by_property = defaultdict(int)
    collected = 0
    for amount, method, pid in payment_rows:
        by_method[method] = by_method.get(method, 0) + amount
        collected_by_property[pid] += amount
        collected += amount

    # Everything that fell due this month
    billed = (
        db.query(func.coalesce(func.sum(models.Charge.amount), 0))
        .join(models.Lease, models.Charge.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(
            models.Unit.property_id.in_(prop_ids),
            models.Charge.due_date >= start,
            models.Charge.due_date < end,
        )
        .scalar()
    )

    # What tenants still owed at the end of the month
    charge_rows = (
        db.query(models.Charge.lease_id, func.sum(models.Charge.amount))
        .join(models.Lease, models.Charge.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(models.Unit.property_id.in_(prop_ids), models.Charge.due_date <= last_day)
        .group_by(models.Charge.lease_id)
        .all()
    )
    paid_rows = (
        db.query(models.Payment.lease_id, func.sum(models.Payment.amount))
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(models.Unit.property_id.in_(prop_ids), models.Payment.paid_on <= last_day)
        .group_by(models.Payment.lease_id)
        .all()
    )
    paid_by_lease = {lease_id: int(total) for lease_id, total in paid_rows}
    owed = sum(max(0, int(total) - paid_by_lease.get(lease_id, 0)) for lease_id, total in charge_rows)

    # ---- MONEY OUT ----
    expense_conditions = [Expense.owner_id == owner.id, Expense.spent_on >= start, Expense.spent_on < end]
    if property_id is not None:
        expense_conditions.append(Expense.property_id == property_id)
    expense_rows = db.query(Expense.category, Expense.amount, Expense.property_id).filter(*expense_conditions).all()
    category_totals = defaultdict(int)
    expenses_by_property = defaultdict(int)
    general = 0
    manual_total = 0
    for category, amount, pid in expense_rows:
        category_totals[category] += amount
        manual_total += amount
        if pid is None:
            general += amount
        else:
            expenses_by_property[pid] += amount

    # Repair costs for repairs fixed this month
    repair_rows = (
        db.query(models.MaintenanceRequest.cost, models.MaintenanceRequest.property_id)
        .filter(
            models.MaintenanceRequest.property_id.in_(prop_ids),
            models.MaintenanceRequest.status == "fixed",
            models.MaintenanceRequest.cost.isnot(None),
            models.MaintenanceRequest.resolved_on >= start,
            models.MaintenanceRequest.resolved_on < end,
        )
        .all()
    )
    repairs_cost = 0
    for cost, pid in repair_rows:
        repairs_cost += cost
        expenses_by_property[pid] += cost
    expenses_total = manual_total + repairs_cost

    # ---- OCCUPANCY ----
    units = db.query(models.Unit).filter(models.Unit.property_id.in_(prop_ids)).all()
    if last_day >= today:
        # For this month and future months, use each unit's status right now
        scope_units = units
        occupied_ids = {unit.id for unit in units if unit.status == "occupied"}
        basis = "now"
    else:
        # For past months, use the lease dates: who was living there on the last day of the month
        scope_units = [unit for unit in units if unit.created_at.date() < end]
        scope_ids = [unit.id for unit in scope_units]
        occupied_ids = set()
        if scope_ids:
            lease_rows = (
                db.query(models.Lease.unit_id)
                .filter(
                    models.Lease.unit_id.in_(scope_ids),
                    models.Lease.start_date <= last_day,
                    or_(models.Lease.end_date.is_(None), models.Lease.end_date >= last_day),
                )
                .all()
            )
            occupied_ids = {unit_id for (unit_id,) in lease_rows}
        basis = "month_end"
    total_by_property = defaultdict(int)
    occupied_by_property = defaultdict(int)
    for unit in scope_units:
        total_by_property[unit.property_id] += 1
        if unit.id in occupied_ids:
            occupied_by_property[unit.property_id] += 1
    units_total = len(scope_units)
    units_occupied = sum(1 for unit in scope_units if unit.id in occupied_ids)

    # ---- EMPTY UNITS RIGHT NOW ----
    vacant_units = [unit for unit in units if unit.status == "vacant"]
    last_end = {}
    if vacant_units:
        end_rows = (
            db.query(models.Lease.unit_id, func.max(models.Lease.end_date))
            .filter(models.Lease.unit_id.in_([unit.id for unit in vacant_units]))
            .group_by(models.Lease.unit_id)
            .all()
        )
        for unit_id, ended in end_rows:
            # Some databases hand back dates as text
            last_end[unit_id] = date.fromisoformat(ended) if isinstance(ended, str) else ended
    vacant_now = []
    for unit in vacant_units:
        since = last_end.get(unit.id) or unit.created_at.date()
        vacant_now.append(VacantRow(
            unit_id=unit.id,
            unit_number=unit.unit_number,
            unit_type=unit.unit_type,
            property_id=unit.property_id,
            property_name=next(prop.name for prop in properties if prop.id == unit.property_id),
            rent_amount=unit.rent_amount,
            vacant_days=max(0, (today - since).days),
            since=since,
        ))
    vacant_now.sort(key=lambda row: row.vacant_days, reverse=True)

    # ---- ONE LINE PER PROPERTY ----
    property_rows = []
    for prop in properties:
        prop_collected = collected_by_property[prop.id]
        prop_expenses = expenses_by_property[prop.id]
        prop_total = total_by_property[prop.id]
        prop_occupied = occupied_by_property[prop.id]
        property_rows.append(PropertyRow(
            property_id=prop.id,
            name=prop.name,
            collected=prop_collected,
            expenses=prop_expenses,
            net=prop_collected - prop_expenses,
            units_total=prop_total,
            units_occupied=prop_occupied,
            occupancy_percent=round(prop_occupied / prop_total * 100, 1) if prop_total else 0.0,
        ))

    # ---- THE LAST 6 MONTHS ----
    months = [shift_month(month, -offset) for offset in range(5, -1, -1)]
    trend_start = month_range(months[0])[0]
    collected_by_month = defaultdict(int)
    spent_by_month = defaultdict(int)
    trend_payments = (
        db.query(models.Payment.amount, models.Payment.paid_on)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .filter(
            models.Unit.property_id.in_(prop_ids),
            models.Payment.paid_on >= trend_start,
            models.Payment.paid_on < end,
        )
        .all()
    )
    for amount, paid_on in trend_payments:
        collected_by_month[paid_on.strftime("%Y-%m")] += amount
    trend_conditions = [Expense.owner_id == owner.id, Expense.spent_on >= trend_start, Expense.spent_on < end]
    if property_id is not None:
        trend_conditions.append(Expense.property_id == property_id)
    for amount, spent_on in db.query(Expense.amount, Expense.spent_on).filter(*trend_conditions).all():
        spent_by_month[spent_on.strftime("%Y-%m")] += amount
    trend_repairs = (
        db.query(models.MaintenanceRequest.cost, models.MaintenanceRequest.resolved_on)
        .filter(
            models.MaintenanceRequest.property_id.in_(prop_ids),
            models.MaintenanceRequest.status == "fixed",
            models.MaintenanceRequest.cost.isnot(None),
            models.MaintenanceRequest.resolved_on >= trend_start,
            models.MaintenanceRequest.resolved_on < end,
        )
        .all()
    )
    for cost, resolved_on in trend_repairs:
        spent_by_month[resolved_on.strftime("%Y-%m")] += cost
    trend = [
        TrendPoint(month=name, collected=collected_by_month[name], spent=spent_by_month[name]) for name in months
    ]

    # Put everything together
    return MonthlyReport(
        month=month,
        property_id=selected.id if selected else None,
        property_name=selected.name if selected else None,
        generated_on=today,
        collected=collected,
        by_method=MethodTotals(**by_method),
        billed=int(billed),
        owed_at_month_end=owed,
        expenses_total=expenses_total,
        expenses_by_category=sorted(
            [CategoryTotal(category=name, total=total) for name, total in category_totals.items()],
            key=lambda item: item.total,
            reverse=True,
        ),
        repairs_cost=repairs_cost,
        general_expenses=general,
        net=collected - expenses_total,
        units_total=units_total,
        units_occupied=units_occupied,
        occupancy_percent=round(units_occupied / units_total * 100, 1) if units_total else 0.0,
        occupancy_basis=basis,
        vacant_now=vacant_now[:50],
        properties=property_rows,
        trend=trend,
    )


# Get the monthly report
@router.get("/monthly", response_model=MonthlyReport)
def monthly_report(
    month: str = Query(..., pattern=PERIOD_PATTERN),
    property_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see reports
    require_owner(current_user)
    # Work it out and send it back
    return build_report(db, current_user, month, property_id)


# Write a heading row and the data rows into an Excel sheet
def write_table(sheet, headers, rows, money_columns=()):
    # The heading row, in white on forest green
    sheet.append(headers)
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B4D3A")
        cell.alignment = Alignment(vertical="center")
    # The data rows
    for row in rows:
        sheet.append(row)
    # Show money columns with thousands separators
    for column in money_columns:
        for row_number in range(2, sheet.max_row + 1):
            sheet.cell(row=row_number, column=column).number_format = "#,##0"
    # Make each column wide enough
    for index, header in enumerate(headers, start=1):
        longest = max([len(str(header))] + [len(str(row[index - 1])) for row in rows])
        sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 45)


# Download the monthly report as an Excel file
@router.get("/monthly/excel")
def monthly_excel(
    month: str = Query(..., pattern=PERIOD_PATTERN),
    property_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can download reports
    require_owner(current_user)
    # Work out the report, and the month's dates
    report = build_report(db, current_user, month, property_id)
    start, end = month_range(month)
    prop_ids = [row.property_id for row in report.properties]
    workbook = Workbook()

    # ---- SHEET 1: SUMMARY ----
    summary = workbook.active
    summary.title = "Summary"
    summary.append(["M-nyumba monthly report"])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append(["Month", month])
    summary.append(["Property", report.property_name or "All properties"])
    summary.append(["Prepared for", current_user.full_name])
    summary.append(["Made on", report.generated_on.strftime("%d %b %Y")])
    summary.append([])
    lines = [
        ("MONEY IN", None),
        ("Collected this month", report.collected),
        ("   M-Pesa", report.by_method.mpesa),
        ("   Cash", report.by_method.cash),
        ("   Bank", report.by_method.bank),
        ("Billed this month (charges due)", report.billed),
        ("Still owed at month end", report.owed_at_month_end),
        ("MONEY OUT", None),
    ]
    for item in report.expenses_by_category:
        lines.append((f"   {item.category}", item.total))
    lines += [
        ("   repairs (from the Repairs page)", report.repairs_cost),
        ("Total spent", report.expenses_total),
        ("LEFT OVER (collected minus spent)", report.net),
        ("OCCUPANCY", None),
        ("Units occupied", report.units_occupied),
        ("Units in total", report.units_total),
        ("Occupancy %", report.occupancy_percent),
    ]
    for label, value in lines:
        summary.append([label, value])
        if value is None:
            summary.cell(row=summary.max_row, column=1).font = Font(bold=True, color="1B4D3A")
        elif label != "Occupancy %":
            summary.cell(row=summary.max_row, column=2).number_format = "#,##0"
    summary.column_dimensions["A"].width = 42
    summary.column_dimensions["B"].width = 22

    # ---- SHEET 2: BY PROPERTY ----
    by_property = workbook.create_sheet("By property")
    write_table(
        by_property,
        ["Property", "Collected", "Spent", "Left over", "Units", "Occupied", "Occupancy %"],
        [
            [row.name, row.collected, row.expenses, row.net, row.units_total, row.units_occupied, row.occupancy_percent]
            for row in report.properties
        ],
        money_columns=(2, 3, 4),
    )

    # ---- SHEET 3: PAYMENTS ----
    payment_sheet = workbook.create_sheet("Payments")
    payments = (
        db.query(models.Payment, models.Tenant, models.Unit, models.Property)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(
            models.Unit.property_id.in_(prop_ids),
            models.Payment.paid_on >= start,
            models.Payment.paid_on < end,
        )
        .order_by(models.Payment.paid_on, models.Payment.id)
        .all()
    )
    write_table(
        payment_sheet,
        ["Date", "Tenant", "Unit", "Property", "Method", "Reference", "Amount"],
        [
            [
                payment.paid_on.strftime("%d %b %Y"),
                tenant.full_name,
                unit.unit_number,
                prop.name,
                payment.method,
                payment.reference or "",
                payment.amount,
            ]
            for payment, tenant, unit, prop in payments
        ],
        money_columns=(7,),
    )

    # ---- SHEET 4: EXPENSES ----
    expense_sheet = workbook.create_sheet("Expenses")
    expense_conditions = [Expense.owner_id == current_user.id, Expense.spent_on >= start, Expense.spent_on < end]
    if property_id is not None:
        expense_conditions.append(Expense.property_id == property_id)
    manual = (
        db.query(Expense, models.Property)
        .outerjoin(models.Property, Expense.property_id == models.Property.id)
        .filter(*expense_conditions)
        .order_by(Expense.spent_on, Expense.id)
        .all()
    )
    expense_lines = [
        [
            expense.spent_on.strftime("%d %b %Y"),
            expense.category,
            prop.name if prop else "General",
            expense.description or "",
            expense.paid_to or "",
            expense.amount,
        ]
        for expense, prop in manual
    ]
    repairs = (
        db.query(models.MaintenanceRequest, models.Property)
        .join(models.Property, models.MaintenanceRequest.property_id == models.Property.id)
        .filter(
            models.MaintenanceRequest.property_id.in_(prop_ids),
            models.MaintenanceRequest.status == "fixed",
            models.MaintenanceRequest.cost.isnot(None),
            models.MaintenanceRequest.resolved_on >= start,
            models.MaintenanceRequest.resolved_on < end,
        )
        .order_by(models.MaintenanceRequest.resolved_on)
        .all()
    )
    for repair, prop in repairs:
        expense_lines.append([
            repair.resolved_on.strftime("%d %b %Y"),
            "repairs",
            prop.name,
            repair.title,
            repair.contractor_name or "",
            repair.cost,
        ])
    write_table(
        expense_sheet,
        ["Date", "Kind", "Property", "Note", "Paid to", "Amount"],
        expense_lines,
        money_columns=(6,),
    )

    # ---- SHEET 5: EMPTY UNITS ----
    vacant_sheet = workbook.create_sheet("Vacant units")
    write_table(
        vacant_sheet,
        ["Property", "Unit", "Type", "Rent", "Empty since", "Days empty"],
        [
            [
                row.property_name,
                row.unit_number,
                row.unit_type or "",
                row.rent_amount,
                row.since.strftime("%d %b %Y"),
                row.vacant_days,
            ]
            for row in report.vacant_now
        ],
        money_columns=(4,),
    )

    # Save the workbook in memory and send it back as a download
    buffer = BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mnyumba-report-{month}.xlsx"'},
    )