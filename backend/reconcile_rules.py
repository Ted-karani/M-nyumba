# reconcile_rules.py - reads an M-Pesa statement and compares it with the payments in EstateLoom
# (no database in here, so it is easy to test)

# Import the tools we need
import csv
import io
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# The most rows we read from one statement
MAX_ROWS = 20000
# How many rows at the top we look through for the heading row
HEADER_SEARCH_ROWS = 40
# What an M-Pesa code looks like (10 letters and numbers; we allow a few more or fewer)
RECEIPT = re.compile(r"^[A-Z0-9]{8,12}$")
# An M-Pesa code inside a longer text
RECEIPT_IN_TEXT = re.compile(r"(?<![A-Z0-9])[A-Z0-9]{10}(?![A-Z0-9])")
# A Kenyan phone number inside a text (07..., 01..., 2547... or 2541...)
PHONE = re.compile(r"(?<!\d)(?:254|0)([17]\d{8})(?!\d)")
# Words that tell us a row is the heading row
HEADER_WORDS = ("receipt", "completion", "paid in", "withdrawn", "details", "status", "balance", "transaction")
# A status that means the payment really happened (an empty one counts too, for statements with no status column)
GOOD_STATUS = ("", "completed", "complete", "success", "successful", "confirmed")

# The things we need from each row of a statement
FIELDS = ("receipt", "date", "amount_in", "amount_out", "status", "details", "party", "account", "linked")
REQUIRED = ("receipt", "date", "amount_in")
# Heading words that tell us which column is which (tried in this order, and each column is used once)
ORDER = ("linked", "receipt", "date", "amount_in", "amount_out", "status", "details", "party", "account")
KEYWORDS = {
    "linked": ("linked",),
    "receipt": ("receipt", "transaction id", "trans id", "mpesa code", "transaction code", "reference no"),
    "date": ("completion time", "completion", "transaction date", "date", "time"),
    "amount_in": ("paid in", "credit", "money in", "amount in", "received"),
    "amount_out": ("withdrawn", "debit", "money out", "paid out", "amount out"),
    "status": ("status",),
    "details": ("details", "description", "narration"),
    "party": ("other party", "party info", "sender", "msisdn", "phone", "customer"),
    "account": ("a/c", "account", "bill ref"),
}

# The date writings we understand (day first, as people write it in Kenya)
DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
    "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M", "%d/%m/%y",
)


# ---------- reading the file ----------

# Turn one cell into plain text
def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


# Remove empty cells at the end of a row
def tidy_row(cells: list) -> list:
    cells = [cell_text(cell) for cell in cells]
    while cells and cells[-1] == "":
        cells.pop()
    return cells


# Read a CSV file into rows of text (empty rows are dropped)
def read_csv_rows(data: bytes) -> list:
    text = ""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    delimiter = max([",", ";", "\t"], key=sample.count)
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        cells = tidy_row(row)
        if cells:
            rows.append(cells)
        if len(rows) > MAX_ROWS + HEADER_SEARCH_ROWS:
            raise ValueError(f"This statement has more than {MAX_ROWS:,} rows. Please upload a shorter period")
    return rows


# Read an Excel (.xlsx) file into rows of text (empty rows are dropped)
def read_xlsx_rows(data: bytes) -> list:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise ValueError("This Excel file could not be opened. Try saving it again as .xlsx or .csv")
    rows = []
    try:
        for row in workbook.active.iter_rows(values_only=True):
            cells = tidy_row(list(row))
            if cells:
                rows.append(cells)
            if len(rows) > MAX_ROWS + HEADER_SEARCH_ROWS:
                raise ValueError(f"This statement has more than {MAX_ROWS:,} rows. Please upload a shorter period")
    finally:
        workbook.close()
    return rows


# Read a statement file (CSV or Excel) into rows of text
def read_rows(data: bytes, filename: str = "") -> list:
    if data[:2] == b"PK":
        rows = read_xlsx_rows(data)
    elif data[:4] == b"\xd0\xcf\x11\xe0":
        raise ValueError("Old .xls files are not supported. Open it in Excel and save it as .xlsx or .csv")
    else:
        rows = read_csv_rows(data)
    if not rows:
        raise ValueError("The file is empty")
    return rows


# ---------- understanding the columns ----------

# Find the heading row (statements often have a few lines of text above it)
def find_header_row(rows: list):
    best = None
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        text = " | ".join(row).lower()
        hits = sum(1 for word in HEADER_WORDS if word in text)
        if hits >= 3:
            return index
        if hits >= 2 and best is None:
            best = index
    return best


# Guess which column is which, from their headings: {field: column number or None}
def suggest_mapping(columns: list) -> dict:
    lowered = [column.strip().lower() for column in columns]
    used = set()
    result = {field: None for field in FIELDS}
    for field in ORDER:
        for word in KEYWORDS[field]:
            found = next((index for index, name in enumerate(lowered) if index not in used and word in name), None)
            if found is not None:
                result[field] = found
                used.add(found)
                break
    return result


# ---------- reading the numbers ----------

# Turn an amount like "6,000.00" or "KSh 6,000" into whole shillings (None if it is not a number)
def parse_amount(text):
    if text is None:
        return None
    value = str(text).strip()
    for junk in (",", " ", "KSh", "Ksh", "KES", "kes"):
        value = value.replace(junk, "")
    if value in ("", "-"):
        return None
    negative = value.startswith("-") or (value.startswith("(") and value.endswith(")"))
    value = value.strip("()-")
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    whole = int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return -whole if negative else whole


# Turn a date writing into a date and time (None if we cannot read it)
def parse_date(text):
    value = (text or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        pass
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


# Read the cell of a row (empty if the row is shorter, or no column was chosen)
def cell(row: list, index) -> str:
    return row[index] if index is not None and 0 <= index < len(row) else ""


# Turn the rows of a statement into a list of payments. Rows that are not transactions are counted and skipped.
def build_entries(rows: list, header_row: int, mapping: dict):
    entries = []
    skipped = 0
    for row in rows[header_row + 1:]:
        receipt = cell(row, mapping.get("receipt")).strip().upper().replace(" ", "")
        when = parse_date(cell(row, mapping.get("date")))
        if not RECEIPT.match(receipt) or when is None:
            skipped += 1
            continue
        entries.append({
            "receipt": receipt,
            "when": when,
            "credit": max(parse_amount(cell(row, mapping.get("amount_in"))) or 0, 0),
            "debit": abs(parse_amount(cell(row, mapping.get("amount_out"))) or 0),
            "status": cell(row, mapping.get("status")).strip(),
            "details": cell(row, mapping.get("details")).strip(),
            "party": cell(row, mapping.get("party")).strip(),
            "account": cell(row, mapping.get("account")).strip(),
            "linked": cell(row, mapping.get("linked")).strip(),
        })
    return entries, skipped


# ---------- comparing with the payments in EstateLoom ----------

# Sort the rows into: real payments in, payments that did not complete, and reversal rows
def split_entries(entries: list):
    credits = {}
    failed = {}
    reversals = []
    duplicates = 0
    for entry in entries:
        status = entry["status"].strip()
        if "revers" in status.lower() and entry["credit"] > 0:
            # The payment itself is marked as reversed
            failed.setdefault(entry["receipt"], status)
            continue
        if "revers" in f"{status} {entry['details']}".lower():
            reversals.append(entry)
            continue
        if entry["credit"] > 0:
            if status.lower() not in GOOD_STATUS:
                failed.setdefault(entry["receipt"], status)
            elif entry["receipt"] in credits:
                duplicates += 1
            else:
                credits[entry["receipt"]] = entry
    return credits, failed, reversals, duplicates


# Make an account number or unit number comparable ("A-1" and "a1" are the same)
def simple(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


# Which tenancies could a payment belong to? (by the phone number in the statement, then by the account number)
def suggest_leases(entry: dict, leases: list) -> list:
    found = []
    phones = {"254" + digits for digits in PHONE.findall(f"{entry['details']} {entry['party']}")}
    for lease in leases:
        if lease["tenant_phone"] in phones and lease["lease_id"] not in found:
            found.append(lease["lease_id"])
    account = simple(entry["account"])
    if account:
        for lease in leases:
            if lease["active"] and simple(lease["unit_number"]) == account and lease["lease_id"] not in found:
                found.append(lease["lease_id"])
    return found


# Compare a statement with the payments in EstateLoom.
# payments: [{payment_id, reference, amount, paid_on, method, tenant_id, tenant_name, unit_number, property_name}]
# leases: [{lease_id, tenant_phone, unit_number, active}]
def classify(entries: list, payments: list, leases: list) -> dict:
    by_ref = {item["reference"]: item for item in payments if item.get("reference")}
    credits, failed, reversals, duplicates = split_entries(entries)
    seen = {entry["receipt"] for entry in entries}

    # Payments we count that the statement says did not happen
    flagged = {}
    for receipt, status in failed.items():
        if receipt in by_ref:
            flagged[receipt] = f"The statement shows this payment as {status or 'not completed'}"
    for entry in reversals:
        text = f"{entry['details']} {entry['linked']} {entry['status']} {entry['party']}".upper()
        for token in RECEIPT_IN_TEXT.findall(text):
            if token != entry["receipt"] and token in by_ref and token not in flagged:
                flagged[token] = "The statement shows a reversal that mentions this payment"

    matched = []
    mismatched = []
    missing = []
    for receipt, entry in credits.items():
        payment = by_ref.get(receipt)
        if receipt in flagged:
            continue
        if payment is None:
            candidates = suggest_leases(entry, leases)
            missing.append({
                "receipt": receipt,
                "amount": entry["credit"],
                "paid_on": entry["when"].date(),
                "details": entry["details"][:120],
                "party": entry["party"][:80],
                "account": entry["account"][:40],
                "candidates": candidates,
                "suggested_lease_id": candidates[0] if candidates else None,
            })
        elif payment["amount"] == entry["credit"]:
            matched.append(payment)
        else:
            mismatched.append({**payment, "statement_amount": entry["credit"]})

    dates = [entry["when"].date() for entry in entries]
    first = min(dates) if dates else None
    last = max(dates) if dates else None
    not_in_statement = [
        item for item in payments
        if item.get("reference") and item["method"] == "mpesa" and item["reference"] not in seen and first and first <= item["paid_on"] <= last
    ]
    return {
        "credit_count": len(credits),
        "credit_total": sum(entry["credit"] for entry in credits.values()),
        "first_date": first,
        "last_date": last,
        "duplicates": duplicates,
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
        "reversed": [{**by_ref[receipt], "why": why} for receipt, why in flagged.items()],
        "not_in_statement": not_in_statement,
        "credits": credits,
    }