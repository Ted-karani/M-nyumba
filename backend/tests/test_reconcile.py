# Import the tools we need
import io
import json
from datetime import date, datetime

from openpyxl import Workbook

# Import our own files
import models
import reconcile_rules as rules
from database import SessionLocal

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner
from test_admin import admin_ready
from test_portal import sign_in_tenant

# A statement like the ones Safaricom's business portal gives (with some lines of text above the headings)
HEADINGS = "Receipt No.,Completion Time,Initiation Time,Details,Transaction Status,Paid In,Withdrawn,Balance,Balance Confirmed,Reason Type,Other Party Info,Linked Transaction ID,A/C No."


def row(receipt, when, details="Pay Bill from 254700000000 - SOMEONE", status="Completed", paid_in="", withdrawn="", party="", linked="", account=""):
    return f'{receipt},{when},{when},"{details}",{status},"{paid_in}","{withdrawn}",0,True,Pay Bill,"{party}",{linked},{account}'


def statement(*rows, preamble=True):
    lines = ["Account Statement", "Organization: Test Landlord", ""] if preamble else []
    return "\n".join(lines + [HEADINGS, *rows]).encode()


# ---------- reading the file ----------

def test_the_heading_row_is_found_below_a_few_lines_of_text():
    rows = rules.read_rows(statement(row("ABC1234567", "2025-10-03 10:00:00", paid_in="6,000.00")))
    assert rules.find_header_row(rows) == 2
    assert rules.find_header_row([["Hello"], ["world"]]) is None


def test_the_columns_are_guessed_from_their_headings():
    columns = HEADINGS.split(",")
    mapping = rules.suggest_mapping(columns)
    assert mapping == {"receipt": 0, "date": 1, "amount_in": 5, "amount_out": 6, "status": 4, "details": 3, "party": 10, "account": 12, "linked": 11}
    assert rules.suggest_mapping(["Code", "When", "Money"]) == {field: None for field in rules.FIELDS}


def test_amounts_and_dates_are_read_in_the_ways_people_write_them():
    for text, expected in [("6,000.00", 6000), ("KSh 6,000", 6000), ("-500", -500), ("(500)", -500), ("1234.5", 1235), ("  75 ", 75), ("", None), ("-", None), ("abc", None)]:
        assert rules.parse_amount(text) == expected, text
    for text in ["2025-10-14 13:22:01", "14-10-2025 13:22", "14/10/2025", "2025-10-14T13:22:01", "14/10/25 13:22:01"]:
        assert rules.parse_date(text).date() == date(2025, 10, 14), text
    assert rules.parse_date("not a date") is None and rules.parse_date("") is None


def test_semicolons_and_excel_files_are_read_too():
    semicolons = "Receipt No.;Completion Time;Paid In\nABC1234567;2025-10-03 10:00:00;6000\n".encode()
    rows = rules.read_rows(semicolons)
    assert rows[0] == ["Receipt No.", "Completion Time", "Paid In"] and rows[1][2] == "6000"
    book = Workbook()
    sheet = book.active
    sheet.append(["Receipt No.", "Completion Time", "Paid In"])
    sheet.append(["ABC1234567", datetime(2025, 10, 3, 10, 0, 0), 6000.0])
    buffer = io.BytesIO()
    book.save(buffer)
    excel_rows = rules.read_rows(buffer.getvalue())
    assert excel_rows == [["Receipt No.", "Completion Time", "Paid In"], ["ABC1234567", "2025-10-03 10:00:00", "6000"]]


def test_rows_that_are_not_payments_are_skipped_and_counted():
    rows = rules.read_rows(statement(row("ABC1234567", "2025-10-03 10:00:00", paid_in="6000"), "TOTAL,,,,,,,,,,,,", row("BAD", "2025-10-03 10:00:00", paid_in="1"), row("XYZ9999999", "not a date", paid_in="5")))
    mapping = rules.suggest_mapping(rows[2])
    entries, skipped = rules.build_entries(rows, 2, mapping)
    assert [entry["receipt"] for entry in entries] == ["ABC1234567"] and skipped == 3


def test_files_that_are_not_statements_are_refused():
    for data in [b"", b"\n\n,,\n", b"\xd0\xcf\x11\xe0 old excel"]:
        try:
            rules.read_rows(data)
            assert False, data
        except ValueError:
            pass


# ---------- the comparison ----------

# One landlord with two tenants: a bedsitter A1 (phone 254711000001) and A2 (phone 254722333444)
def seed(client, owner):
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        prop = models.Property(owner_id=owner_id, name="Block A")
        db.add(prop)
        db.flush()
        leases = []
        for number, phone in (("A1", "254711000001"), ("A2", "254722333444")):
            unit = models.Unit(property_id=prop.id, unit_number=number, unit_type="Bedsitter", rent_amount=6000, status="occupied")
            tenant = models.Tenant(owner_id=owner_id, full_name=f"Tenant {number}", phone=phone)
            db.add_all([unit, tenant])
            db.flush()
            lease = models.Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=date(2025, 9, 1), rent_amount=6000, status="active")
            db.add(lease)
            db.flush()
            leases.append(lease.id)
        db.commit()
        return leases


def pay(lease_id, reference, amount, day=3, method="mpesa"):
    with SessionLocal() as db:
        db.add(models.Payment(lease_id=lease_id, amount=amount, paid_on=date(2025, 10, day), method=method, reference=reference))
        db.commit()


def analysis(client, owner, data, filename="statement.csv"):
    files = {"file": (filename, data, "text/csv")}
    preview = client.post("/reconcile/preview", files=files, headers=owner)
    assert preview.status_code == 200, preview.text
    shown = preview.json()
    mapping = {"header_row": shown["header_row"], **{key: value for key, value in shown["suggested"].items() if value is not None}}
    response = client.post("/reconcile/analyze", files=files, data={"mapping": json.dumps(mapping)}, headers=owner)
    assert response.status_code == 200, response.text
    return response.json(), mapping


def everything(client, owner):
    a1, a2 = seed(client, owner)
    pay(a1, "AAA1111111", 6000)
    pay(a1, "BBB2222222", 5000)
    pay(a1, "DDD4444444", 3000, day=5)
    pay(a2, "EEE5555555", 2000, day=6)
    pay(a2, "FFF6666666", 4000, day=7)
    pay(a2, None, 1500, day=8, method="cash")
    data = statement(
        row("AAA1111111", "2025-10-03 10:00:00", paid_in="6,000.00"),
        row("BBB2222222", "2025-10-04 10:00:00", paid_in="6,000.00"),
        row("CCC3333333", "2025-10-04 11:00:00", details="Pay Bill from 254722333444 - JANE", paid_in="6,000.00", party="254722333444 - JANE", account="A2"),
        row("DDD4444444", "2025-10-05 09:00:00", paid_in="3,000.00"),
        row("RRR9999999", "2025-10-05 15:00:00", details="Reversal of transaction DDD4444444", status="Completed", withdrawn="3,000.00", linked="DDD4444444"),
        row("EEE5555555", "2025-10-06 09:00:00", status="Failed", paid_in="2,000.00"),
        row("HHH8888888", "2025-10-09 09:00:00", details="Pay Bill from 254799999999 - UNKNOWN", paid_in="1,000.00"),
        row("FEE0000001", "2025-10-09 09:00:00", details="Pay Bill Charge", withdrawn="23.00"),
    )
    return a1, a2, data


def test_the_statement_is_compared_with_the_payments(client):
    owner = make_owner(client)
    a1, a2, data = everything(client, owner)
    result, _ = analysis(client, owner, data)
    summary = result["summary"]
    assert summary["credit_count"] == 5 and summary["credit_total"] == 22000
    assert summary["first_date"] == "2025-10-03" and summary["last_date"] == "2025-10-09" and summary["matched"] == 1
    # The same code with another amount
    assert [(row["receipt"], row["amount"], row["statement_amount"]) for row in result["mismatched"]] == [("BBB2222222", 5000, 6000)]
    # The reversed and the failed payments that EstateLoom still counts
    reversed_rows = {row["receipt"]: row["why"] for row in result["reversed"]}
    assert set(reversed_rows) == {"DDD4444444", "EEE5555555"}
    assert "reversal" in reversed_rows["DDD4444444"].lower() and "Failed" in reversed_rows["EEE5555555"]
    # Money nobody recorded, with a suggested tenant from the phone number or the account
    missing = {row["receipt"]: row for row in result["missing"]}
    assert set(missing) == {"CCC3333333", "HHH8888888"}
    assert missing["CCC3333333"]["suggested_lease_id"] == a2 and missing["CCC3333333"]["amount"] == 6000 and missing["CCC3333333"]["paid_on"] == "2025-10-04"
    assert missing["HHH8888888"]["candidates"] == [] and missing["HHH8888888"]["suggested_lease_id"] is None
    # An M-Pesa payment in the dates that the statement does not show (cash payments and fees are ignored)
    assert [row["receipt"] for row in result["not_in_statement"]] == ["FFF6666666"]
    assert {option["lease_id"] for option in result["leases"]} == {a1, a2}


def test_a_matching_statement_has_nothing_to_check(client):
    owner = make_owner(client)
    a1, a2 = seed(client, owner)
    pay(a1, "AAA1111111", 6000)
    pay(a2, "BBB2222222", 6000, day=4)
    data = statement(row("AAA1111111", "2025-10-03 10:00:00", paid_in="6000"), row("BBB2222222", "2025-10-04 10:00:00", paid_in="6000"))
    result, _ = analysis(client, owner, data)
    assert result["summary"]["matched"] == 2 and result["missing"] == [] and result["mismatched"] == [] and result["reversed"] == [] and result["not_in_statement"] == []


def test_a_repeated_code_is_counted_once(client):
    owner = make_owner(client)
    a1, _ = seed(client, owner)
    pay(a1, "AAA1111111", 6000)
    data = statement(row("AAA1111111", "2025-10-03 10:00:00", paid_in="6000"), row("AAA1111111", "2025-10-03 10:00:00", paid_in="6000"))
    result, _ = analysis(client, owner, data)
    assert result["summary"]["duplicates"] == 1 and result["summary"]["matched"] == 1


def test_missing_payments_are_recorded_from_the_statement_not_from_the_screen(client):
    owner = make_owner(client)
    a1, a2, data = everything(client, owner)
    _, mapping = analysis(client, owner, data)
    files = {"file": ("statement.csv", data, "text/csv")}
    done = client.post("/reconcile/record", files=files, data={"mapping": json.dumps(mapping), "assignments": json.dumps([{"receipt": "CCC3333333", "lease_id": a2}])}, headers=owner)
    assert done.status_code == 200 and done.json() == {"recorded": 1, "skipped": 0, "problems": []}
    with SessionLocal() as db:
        payment = db.query(models.Payment).filter(models.Payment.reference == "CCC3333333").one()
        assert (payment.lease_id, payment.amount, payment.paid_on, payment.method) == (a2, 6000, date(2025, 10, 4), "mpesa")
    # Now it matches, and recording it again does nothing
    result, _ = analysis(client, owner, data)
    assert [row["receipt"] for row in result["missing"]] == ["HHH8888888"] and result["summary"]["matched"] == 2
    again = client.post("/reconcile/record", files=files, data={"mapping": json.dumps(mapping), "assignments": json.dumps([{"receipt": "CCC3333333", "lease_id": a2}])}, headers=owner)
    assert again.json()["recorded"] == 0 and again.json()["skipped"] == 1
    summaries = [item["summary"] for item in client.get("/account/activity", headers=owner).json()["items"]]
    assert "Recorded payments from an M-Pesa statement" in summaries
    assert not any(line.startswith("POST /reconcile") for line in summaries)


def test_only_real_completed_payments_of_your_own_tenants_can_be_recorded(client):
    owner = make_owner(client)
    a1, a2, data = everything(client, owner)
    _, mapping = analysis(client, owner, data)
    other = make_owner(client, "other@example.com")
    business = make_business(client, other)
    files = {"file": ("statement.csv", data, "text/csv")}
    attempts = [
        {"receipt": "EEE5555555", "lease_id": a1},
        {"receipt": "RRR9999999", "lease_id": a1},
        {"receipt": "ZZZ0000000", "lease_id": a1},
        {"receipt": "HHH8888888", "lease_id": business["lease"]["id"]},
    ]
    done = client.post("/reconcile/record", files=files, data={"mapping": json.dumps(mapping), "assignments": json.dumps(attempts)}, headers=owner)
    assert done.status_code == 200 and done.json()["recorded"] == 0 and done.json()["skipped"] == 4
    with SessionLocal() as db:
        assert db.query(models.Payment).filter(models.Payment.reference == "HHH8888888").count() == 0
    # Too many, or none, are refused
    assert client.post("/reconcile/record", files=files, data={"mapping": json.dumps(mapping), "assignments": "[]"}, headers=owner).status_code == 422
    many = [{"receipt": "HHH8888888", "lease_id": a1}] * 301
    assert client.post("/reconcile/record", files=files, data={"mapping": json.dumps(mapping), "assignments": json.dumps(many)}, headers=owner).status_code == 422


def test_another_landlords_payments_are_never_shown_or_touched(client):
    owner = make_owner(client)
    a1, a2 = seed(client, owner)
    other = make_owner(client, "other@example.com")
    business = make_business(client, other)
    with SessionLocal() as db:
        db.add(models.Payment(lease_id=business["lease"]["id"], amount=7000, paid_on=date(2025, 10, 4), method="mpesa", reference="OTH1111111"))
        db.commit()
    data = statement(row("OTH1111111", "2025-10-04 10:00:00", paid_in="7000"))
    result, mapping = analysis(client, owner, data)
    # It is not matched with the other landlord's payment, and nothing of theirs shows up
    assert result["summary"]["matched"] == 0 and [row["receipt"] for row in result["missing"]] == ["OTH1111111"]
    assert "Tenant" not in json.dumps(result["mismatched"] + result["reversed"] + result["not_in_statement"])
    # Recording it fails safely, because that code already belongs to another account
    done = client.post("/reconcile/record", files={"file": ("s.csv", data, "text/csv")}, data={"mapping": json.dumps(mapping), "assignments": json.dumps([{"receipt": "OTH1111111", "lease_id": a1}])}, headers=owner)
    assert done.json()["recorded"] == 0 and done.json()["skipped"] == 1
    with SessionLocal() as db:
        assert db.query(models.Payment).filter(models.Payment.reference == "OTH1111111").one().lease_id == business["lease"]["id"]


def test_bad_files_and_bad_columns_are_explained(client):
    owner = make_owner(client)
    seed(client, owner)
    good = statement(row("AAA1111111", "2025-10-03 10:00:00", paid_in="6000"))
    assert client.post("/reconcile/preview", files={"file": ("a.csv", b"", "text/csv")}, headers=owner).status_code == 400
    assert client.post("/reconcile/preview", files={"file": ("a.xls", b"\xd0\xcf\x11\xe0 old", "application/vnd.ms-excel")}, headers=owner).status_code == 400
    assert client.post("/reconcile/preview", files={"file": ("big.csv", b"x" * (5 * 1024 * 1024 + 1), "text/csv")}, headers=owner).status_code == 413
    files = {"file": ("a.csv", good, "text/csv")}
    for mapping in ["not json", json.dumps({"header_row": 2}), json.dumps({"header_row": 2, "receipt": 0, "date": 1})]:
        assert client.post("/reconcile/analyze", files=files, data={"mapping": mapping}, headers=owner).status_code == 422
    assert client.post("/reconcile/analyze", files=files, data={"mapping": json.dumps({"header_row": 2, "receipt": 0, "date": 1, "amount_in": 99})}, headers=owner).status_code == 422
    assert client.post("/reconcile/analyze", files=files, data={"mapping": json.dumps({"header_row": 50, "receipt": 0, "date": 1, "amount_in": 5})}, headers=owner).status_code == 422
    # The wrong columns find no payments
    nothing = client.post("/reconcile/analyze", files=files, data={"mapping": json.dumps({"header_row": 2, "receipt": 3, "date": 3, "amount_in": 3})}, headers=owner)
    assert nothing.status_code == 400 and "No payments were found" in nothing.json()["detail"]


def test_an_excel_statement_works_end_to_end(client):
    owner = make_owner(client)
    a1, _ = seed(client, owner)
    pay(a1, "AAA1111111", 6000)
    book = Workbook()
    sheet = book.active
    for line in ["Account Statement", ""]:
        sheet.append([line])
    sheet.append(HEADINGS.split(","))
    sheet.append(["AAA1111111", datetime(2025, 10, 3, 10), datetime(2025, 10, 3, 10), "Pay Bill", "Completed", 6000.0, None, 0, "True", "Pay Bill", "", "", ""])
    sheet.append(["CCC3333333", datetime(2025, 10, 4, 10), datetime(2025, 10, 4, 10), "Pay Bill", "Completed", 6000.0, None, 0, "True", "Pay Bill", "", "", "A1"])
    buffer = io.BytesIO()
    book.save(buffer)
    result, _ = analysis(client, owner, buffer.getvalue(), filename="statement.xlsx")
    assert result["summary"]["matched"] == 1 and result["missing"][0]["receipt"] == "CCC3333333" and result["missing"][0]["suggested_lease_id"] == a1


def test_only_landlords_can_use_the_statement_check(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    files = {"file": ("a.csv", statement(row("AAA1111111", "2025-10-03 10:00:00", paid_in="6000")), "text/csv")}
    for headers in (john, tenant, admin):
        assert client.post("/reconcile/preview", files=files, headers=headers).status_code == 403
        assert client.post("/reconcile/analyze", files=files, data={"mapping": "{}"}, headers=headers).status_code == 403
        assert client.post("/reconcile/record", files=files, data={"mapping": "{}", "assignments": "[]"}, headers=headers).status_code == 403
    assert client.post("/reconcile/preview", files=files).status_code == 401