# Import the tools we need
import os
import re
import shutil
import tempfile
import time
import zipfile
from datetime import date, datetime
from decimal import Decimal
# Import the tool for writing Excel files
from openpyxl import Workbook
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

# Import our own files
import models
from admin_models import OwnerAccount, SubscriptionPayment
from database import Base
from dependencies import get_db, get_current_user
from ownership import KEEP_TABLES, chunks, collect, member_user_ids, stored_files
from routers import documents
from routers.properties import require_owner
from security_models import AuditLog

# These endpoints sit under /account, next to the other account pages
router = APIRouter(prefix="/account", tags=["Account"])

# Tables we never put in the export (sign-in secrets and attempts)
EXCLUDE = {"user_security", "user_totp", "login_attempts", "idempotency_keys"}
# The most file bytes we put in one export (bigger ones are prepared by hand)
MAX_FILES_BYTES = 400 * 1024 * 1024
# Text that starts like this could be read by Excel as a formula, so we put a ' in front
FORMULA_STARTS = ("=", "+", "-", "@")
# When each landlord last downloaded (so nobody can start many heavy downloads at once)
LAST_EXPORT: dict[int, float] = {}
COOLDOWN_SECONDS = 60

# The text of the README file inside the download
README_TEXT = """EstateLoom: a copy of your data
Made on {today}

data.xlsx has one sheet for each kind of record (properties, units, tenants, leases, charges, payments and so on).
The "id" columns link the sheets: for example lease_id in "payments" is the id of a row in "leases".
Dates are shown as dates, and amounts are in Kenya shillings.

The files folder holds the documents and photos you uploaded. The sheets that list them show their original names.

This copy contains your tenants' personal information. Please keep it safe, and share it only with people who need it.
"""


# Make a file name safe
def clean_name(name: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", name or "file")[:80] or "file"


# Make a value safe to put in an Excel cell
def safe_cell(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, str):
        # Excel cells hold at most 32,767 characters
        text = value[:32000]
        return "'" + text if text.startswith(FORMULA_STARTS) else text
    return value


# Write the rows of one table to a sheet
def write_table(workbook, db: Session, table, ids) -> None:
    sheet = workbook.create_sheet(table.name[:31])
    sheet.append([column.name for column in table.columns])
    for piece in chunks(sorted(ids)):
        for row in db.execute(select(table).where(table.c.id.in_(piece)).order_by(table.c.id)).all():
            sheet.append([safe_cell(value) for value in row])


# Build the Excel file with everything the landlord has
def build_workbook(db: Session, owner: models.User, marked: dict[str, set[int]], path: str) -> None:
    workbook = Workbook()
    readme = workbook.active
    readme.title = "README"
    for line in README_TEXT.format(today=date.today().strftime("%d %B %Y")).splitlines():
        readme.append([line])
    # The landlord, their caretakers and their tenants' logins (never the password hashes)
    people = workbook.create_sheet("people")
    people.append(["id", "role", "full_name", "email", "phone", "created_at"])
    ids = [owner.id] + member_user_ids(db, owner.id)
    for user in db.query(models.User).filter(models.User.id.in_(ids)).order_by(models.User.id).all():
        people.append([user.id, user.role, safe_cell(user.full_name), user.email, user.phone, user.created_at])
    # Their plan, and what they paid us
    account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner.id).first()
    if account is not None:
        sheet = workbook.create_sheet("account")
        sheet.append(["plan", "status", "paid_until", "unit_limit", "created_at"])
        sheet.append([account.plan, account.status, account.paid_until, account.unit_limit, account.created_at])
    paid = db.query(SubscriptionPayment).filter(SubscriptionPayment.owner_id == owner.id).order_by(SubscriptionPayment.id).all()
    if paid:
        sheet = workbook.create_sheet("subscription_payments")
        sheet.append(["id", "amount", "method", "reference", "months", "paid_on", "covers_until", "note"])
        for item in paid:
            sheet.append([item.id, item.amount, item.method, item.reference, item.months, item.paid_on, item.covers_until, safe_cell(item.note)])
    # Every other table, in the order of the database
    for table in Base.metadata.sorted_tables:
        if table.name in EXCLUDE or table.name in KEEP_TABLES or not marked.get(table.name):
            continue
        write_table(workbook, db, table, marked[table.name])
    workbook.save(path)


# Make the ZIP: the Excel file, a README, and the uploaded files (it returns the folder and the ZIP's path)
def make_zip(db: Session, owner: models.User):
    marked = collect(db, owner.id)
    present = []
    total = 0
    for table, row_id, stored, original in stored_files(db, marked):
        path = documents.UPLOAD_DIR / stored
        if path.is_file():
            present.append((table, row_id, original or stored, path))
            total += path.stat().st_size
    if total > MAX_FILES_BYTES:
        raise HTTPException(status_code=413, detail="Your files are very large. Please contact support and we will prepare your copy for you")
    folder = tempfile.mkdtemp(prefix="export-")
    try:
        excel_path = os.path.join(folder, "data.xlsx")
        build_workbook(db, owner, marked, excel_path)
        zip_path = os.path.join(folder, "export.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(excel_path, "data.xlsx")
            archive.writestr("README.txt", README_TEXT.format(today=date.today().strftime("%d %B %Y")))
            for table, row_id, name, path in present:
                archive.write(path, f"files/{table}/{row_id}_{clean_name(name)}")
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder, zip_path


# Download a copy of all your data
@router.get("/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only landlords have a business to export
    require_owner(current_user)
    # One download a minute is plenty
    last = LAST_EXPORT.get(current_user.id)
    if last is not None and time.monotonic() - last < COOLDOWN_SECONDS:
        raise HTTPException(status_code=429, detail="Please wait a minute before downloading again")
    LAST_EXPORT[current_user.id] = time.monotonic()
    folder, zip_path = make_zip(db, current_user)
    # Remember that it happened
    db.add(AuditLog(
        owner_id=current_user.id,
        actor_id=current_user.id,
        actor_name=current_user.full_name,
        actor_role=current_user.role,
        summary="Downloaded a full copy of their data",
        method="GET",
        path="/account/export",
    ))
    db.commit()
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"estateloom-data-{datetime.utcnow().strftime('%Y-%m-%d')}.zip",
        # Remove the temporary files once the download is finished
        background=BackgroundTask(shutil.rmtree, folder, ignore_errors=True),
    )