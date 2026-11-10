# Import the tools we need
import json
from datetime import date

# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
# Import the tool that catches "this already exists" errors
from sqlalchemy.exc import IntegrityError
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import reconcile_rules as rules
from dependencies import get_db, get_current_user
from ownership import chunks
from routers.properties import require_owner

# Make a group of endpoints that all start with /reconcile
router = APIRouter(prefix="/reconcile", tags=["M-Pesa statement check"])
# The biggest statement file we accept
MAX_BYTES = 5 * 1024 * 1024
# The most payments one request may record
MAX_RECORD = 300


# What we found in a file, before the columns are chosen
class PreviewOut(BaseModel):
    # False if we could not find a heading row (the first row is used, and the person should check)
    header_found: bool
    header_row: int
    columns: list[str]
    # The first few rows under the headings
    sample: list[list[str]]
    # Our guess: {field: column number or null}
    suggested: dict[str, int | None]
    rows_found: int


# Which column holds what (sent back by the screen, after the person has checked it)
class ColumnMapping(BaseModel):
    header_row: int = Field(ge=0, le=100)
    receipt: int = Field(ge=0, le=200)
    date: int = Field(ge=0, le=200)
    amount_in: int = Field(ge=0, le=200)
    amount_out: int | None = Field(default=None, ge=0, le=200)
    status: int | None = Field(default=None, ge=0, le=200)
    details: int | None = Field(default=None, ge=0, le=200)
    party: int | None = Field(default=None, ge=0, le=200)
    account: int | None = Field(default=None, ge=0, le=200)
    linked: int | None = Field(default=None, ge=0, le=200)


# A payment recorded in EstateLoom
class PaymentRef(BaseModel):
    payment_id: int
    receipt: str
    amount: int
    paid_on: date
    tenant_id: int
    tenant_name: str
    unit_number: str
    property_name: str


class MismatchRow(PaymentRef):
    # What the statement says
    statement_amount: int


class ReversedRow(PaymentRef):
    # Why we think it did not happen
    why: str


# Money that is in the statement but not in EstateLoom
class MissingRow(BaseModel):
    receipt: str
    amount: int
    paid_on: date
    details: str
    party: str
    account: str
    # The tenancies it could belong to (best guess first)
    candidates: list[int]
    suggested_lease_id: int | None


# A tenancy to choose from
class LeaseOption(BaseModel):
    lease_id: int
    label: str
    active: bool


class Summary(BaseModel):
    credit_count: int
    credit_total: int
    first_date: date | None
    last_date: date | None
    matched: int
    # Rows that are not payments (heading lines, fees, totals) or could not be read
    skipped: int
    duplicates: int


class AnalyzeOut(BaseModel):
    summary: Summary
    missing: list[MissingRow]
    mismatched: list[MismatchRow]
    reversed: list[ReversedRow]
    not_in_statement: list[PaymentRef]
    leases: list[LeaseOption]


# One payment to record: the M-Pesa code, and the tenancy it belongs to
class Assignment(BaseModel):
    receipt: str = Field(min_length=8, max_length=12)
    lease_id: int


class RecordOut(BaseModel):
    recorded: int
    skipped: int
    problems: list[str]


# Read the uploaded file (never more than the limit)
async def read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="This file is too large. The limit is 5 MB")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="This file is empty")
    return data


# Read the rows of the file (a readable error if it is not a statement file)
def rows_of(data: bytes, filename: str) -> list:
    try:
        return rules.read_rows(data, filename)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


# Read the chosen columns, and check they make sense for this file
def read_mapping(text: str, rows: list) -> ColumnMapping:
    try:
        mapping = ColumnMapping.model_validate_json(text)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Choose the columns for the M-Pesa code, the date and the money received")
    if mapping.header_row >= len(rows):
        raise HTTPException(status_code=422, detail="The heading row is not in this file")
    width = max(len(row) for row in rows[: mapping.header_row + 1 + 50])
    chosen = [value for key, value in mapping.model_dump().items() if key != "header_row" and value is not None]
    if any(value >= width for value in chosen):
        raise HTTPException(status_code=422, detail="One of the chosen columns is not in this file")
    return mapping


# Read the statement into payments
def entries_of(rows: list, mapping: ColumnMapping):
    chosen = mapping.model_dump()
    entries, skipped = rules.build_entries(rows, mapping.header_row, chosen)
    if not entries:
        raise HTTPException(status_code=400, detail="No payments were found with these columns. Check that the code, date and money received columns are right")
    return entries, skipped


# All of this landlord's tenancies, as plain data
def owner_leases(db: Session, owner_id: int) -> list:
    rows = (
        db.query(models.Lease, models.Unit, models.Property, models.Tenant)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == owner_id)
        .all()
    )
    leases = [
        {
            "lease_id": lease.id,
            "tenant_id": tenant.id,
            "tenant_name": tenant.full_name,
            "tenant_phone": tenant.phone,
            "unit_number": unit.unit_number,
            "property_name": prop.name,
            "active": lease.status == "active",
        }
        for lease, unit, prop, tenant in rows
    ]
    leases.sort(key=lambda item: (not item["active"], item["property_name"].lower(), item["unit_number"].lower()))
    return leases


# The landlord's payments that matter for this statement: those with one of its codes, and M-Pesa payments within its dates
def owner_payments(db: Session, owner_id: int, receipts: set, first, last) -> list:
    base = (
        db.query(models.Payment, models.Unit, models.Property, models.Tenant)
        .join(models.Lease, models.Payment.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .join(models.Tenant, models.Lease.tenant_id == models.Tenant.id)
        .filter(models.Property.owner_id == owner_id)
    )
    found = {}
    for piece in chunks(sorted(receipts)):
        for row in base.filter(models.Payment.reference.in_(piece)).all():
            found[row[0].id] = row
    if first and last:
        for row in base.filter(models.Payment.method == "mpesa", models.Payment.paid_on >= first, models.Payment.paid_on <= last).all():
            found[row[0].id] = row
    return [
        {
            "payment_id": payment.id,
            "reference": (payment.reference or "").upper() or None,
            "receipt": (payment.reference or "").upper(),
            "amount": payment.amount,
            "paid_on": payment.paid_on,
            "method": payment.method,
            "tenant_id": tenant.id,
            "tenant_name": tenant.full_name,
            "unit_number": unit.unit_number,
            "property_name": prop.name,
        }
        for payment, unit, prop, tenant in found.values()
    ]


# Look at the file and guess which column is which (nothing is saved)
@router.post("/preview", response_model=PreviewOut)
async def preview_statement(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    rows = rows_of(await read_upload(file), file.filename or "")
    header = rules.find_header_row(rows)
    index = header if header is not None else 0
    columns = rows[index]
    width = max(len(row) for row in rows[index: index + 50])
    columns = columns + [""] * (width - len(columns))
    sample = [(row + [""] * width)[:width] for row in rows[index + 1: index + 5]]
    return PreviewOut(
        header_found=header is not None,
        header_row=index,
        columns=[name[:60] for name in columns],
        sample=[[value[:60] for value in row] for row in sample],
        suggested=rules.suggest_mapping(columns),
        rows_found=max(len(rows) - index - 1, 0),
    )


# Compare the statement with the payments recorded in EstateLoom (nothing is saved)
@router.post("/analyze", response_model=AnalyzeOut)
async def analyze_statement(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    rows = rows_of(await read_upload(file), file.filename or "")
    columns = read_mapping(mapping, rows)
    entries, skipped = entries_of(rows, columns)
    dates = [entry["when"].date() for entry in entries]
    leases = owner_leases(db, current_user.id)
    payments = owner_payments(db, current_user.id, {entry["receipt"] for entry in entries}, min(dates), max(dates))
    result = rules.classify(entries, payments, leases)
    keep = ("payment_id", "receipt", "amount", "paid_on", "tenant_id", "tenant_name", "unit_number", "property_name")
    return AnalyzeOut(
        summary=Summary(
            credit_count=result["credit_count"],
            credit_total=result["credit_total"],
            first_date=result["first_date"],
            last_date=result["last_date"],
            matched=len(result["matched"]),
            skipped=skipped,
            duplicates=result["duplicates"],
        ),
        missing=[MissingRow(**row) for row in result["missing"]],
        mismatched=[MismatchRow(**{key: row[key] for key in keep}, statement_amount=row["statement_amount"]) for row in result["mismatched"]],
        reversed=[ReversedRow(**{key: row[key] for key in keep}, why=row["why"]) for row in result["reversed"]],
        not_in_statement=[PaymentRef(**{key: row[key] for key in keep}) for row in result["not_in_statement"]],
        leases=[
            LeaseOption(lease_id=lease["lease_id"], label=f"{lease['unit_number']} · {lease['tenant_name']} ({lease['property_name']}){'' if lease['active'] else ' · moved out'}", active=lease["active"])
            for lease in leases[:600]
        ],
    )


# Record payments that are in the statement but not in EstateLoom (the amount and date come from the statement, not from the screen)
@router.post("/record", response_model=RecordOut)
async def record_from_statement(
    file: UploadFile = File(...),
    mapping: str = Form(...),
    assignments: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    try:
        chosen = TypeAdapter(list[Assignment]).validate_json(assignments)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Choose a tenant for each payment")
    if not chosen:
        raise HTTPException(status_code=422, detail="Choose at least one payment")
    if len(chosen) > MAX_RECORD:
        raise HTTPException(status_code=422, detail=f"You can record at most {MAX_RECORD} payments at a time")
    rows = rows_of(await read_upload(file), file.filename or "")
    entries, _ = entries_of(rows, read_mapping(mapping, rows))
    credits, _failed, _reversals, _duplicates = rules.split_entries(entries)
    own_leases = {lease["lease_id"] for lease in owner_leases(db, current_user.id)}
    recorded = 0
    skipped = 0
    problems = []
    for item in chosen:
        receipt = item.receipt.strip().upper()
        entry = credits.get(receipt)
        if entry is None:
            skipped += 1
            problems.append(f"{receipt}: this is not a completed payment in the statement")
            continue
        if item.lease_id not in own_leases:
            skipped += 1
            problems.append(f"{receipt}: choose one of your own tenants")
            continue
        try:
            # A small safe step, so one failure does not undo the others
            with db.begin_nested():
                db.add(models.Payment(
                    lease_id=item.lease_id,
                    amount=entry["credit"],
                    paid_on=entry["when"].date(),
                    method="mpesa",
                    reference=receipt,
                    recorded_by_id=current_user.id,
                    notes="Recorded from the M-Pesa statement",
                ))
            recorded += 1
        except IntegrityError:
            skipped += 1
            problems.append(f"{receipt}: this code could not be recorded (it may already be recorded)")
    db.commit()
    return RecordOut(recorded=recorded, skipped=skipped, problems=problems)