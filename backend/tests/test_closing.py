# Import the tools we need
import io
import zipfile
from datetime import date, datetime, timedelta

import openpyxl
import pytest
from sqlalchemy import func, select

# Import our own files
import legal_models
import models
import mpesa_models
from admin_models import OwnerAccount, SubscriptionPayment
from database import Base, SessionLocal
from ownership import KEEP_TABLES, collect
from security_models import LoginAttempt, UserSecurity, UserTotp

# Import our test helpers
from helpers import PASSWORD, make_business, make_caretaker, make_owner, make_tenant, make_unit, pay
from test_admin import admin_ready, owner_id_for
from test_legal import accept_body
from test_portal import sign_in_tenant

# A tiny file that starts like a real PNG picture
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


# Keep test files in a throwaway folder, and forget earlier downloads
@pytest.fixture
def uploads(tmp_path, monkeypatch):
    from routers import dataexport, documents, inspections, listings

    for module in (documents, inspections, listings):
        monkeypatch.setattr(module, "UPLOAD_DIR", tmp_path)
    dataexport.LAST_EXPORT.clear()
    return tmp_path


# A landlord with a bit of everything, including 3 uploaded files (a document, a listing photo, a checklist photo)
def rich_business(client, owner):
    business = make_business(client, owner)
    lease_id = business["lease"]["id"]
    make_tenant(client, owner, name="Joseph Kamau", phone="0722 111 222", id_number="87654321")
    pay(client, owner, lease_id, 3000)
    client.post("/expenses", json={"category": "supplies", "amount": 1200, "spent_on": date.today().isoformat(), "property_id": business["property_id"]}, headers=owner)
    client.post("/maintenance", json={"property_id": business["property_id"], "title": "Cracked tile"}, headers=owner)
    client.post("/notices", json={"title": "Water shutdown", "body": "Off on Tuesday"}, headers=owner)
    document = client.post("/documents", data={"title": "Title deed", "kind": "other"}, files={"file": ("deed.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=owner)
    assert document.status_code == 201, document.text
    empty = make_unit(client, owner, business["property_id"], "B1")
    listing = client.post("/listings", json={"unit_id": empty, "title": "Bedsitter B1"}, headers=owner).json()
    assert client.post(f"/listings/{listing['id']}/photos", files={"file": ("room.png", PNG, "image/png")}, headers=owner).status_code == 201
    started = client.post(f"/inspections/lease/{lease_id}/move_in", json={}, headers=owner).json()
    assert client.post(f"/inspections/{started['id']}/photos", files={"file": ("wall.png", PNG, "image/png")}, headers=owner).status_code == 201
    business["caretaker"] = make_caretaker(client, owner, [business["property_id"]])[1]
    business["tenant"] = sign_in_tenant(client, owner, business["tenant_id"])
    client.post("/portal/repairs", json={"title": "Leaking tap"}, headers=business["tenant"])
    client.post("/legal/accept", json=accept_body(), headers=owner)
    return business


# Pretend 31 days have passed since closing started
def age_closing(owner_id, days=31):
    with SessionLocal() as db:
        db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).update({"closing_started_at": datetime.utcnow() - timedelta(days=days)})
        db.commit()


def test_a_landlord_can_download_a_copy_of_all_their_data(client, uploads):
    owner = make_owner(client, "owner@example.com")
    rich_business(client, owner)
    other = make_owner(client, "other@example.com")
    make_tenant(client, other, name="Zainab Hassan", phone="0733 222 333")
    response = client.get("/account/export", headers=owner)
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "data.xlsx" in names and "README.txt" in names
    # The uploaded files are inside, under their own names
    assert any(name.startswith("files/documents/") and name.endswith("deed.pdf") for name in names)
    assert sum(1 for name in names if name.startswith("files/")) == 3
    workbook = openpyxl.load_workbook(io.BytesIO(archive.read("data.xlsx")))
    sheets = set(workbook.sheetnames)
    assert {"README", "people", "properties", "units", "tenants", "leases", "payments", "expenses"} <= sheets
    # Sign-in secrets and our own admin log are never in it
    assert not ({"user_totp", "user_security", "login_attempts", "admin_events", "users"} & sheets)
    everything = " ".join(str(cell.value) for sheet in workbook for row in sheet.iter_rows() for cell in row if cell.value is not None)
    # The ID number is readable (it is scrambled only inside the database), and nothing of the other landlord is there
    assert "Mercy Wambui" in everything and "87654321" in everything
    assert "Zainab" not in everything
    assert "$2b$" not in everything
    # A second download straight away is asked to wait
    assert client.get("/account/export", headers=owner).status_code == 429
    # The download is written in the activity log
    summaries = [item["summary"] for item in client.get("/account/activity", headers=owner).json()["items"]]
    assert "Downloaded a full copy of their data" in summaries


def test_only_landlords_can_download_a_copy(client, uploads):
    owner = make_owner(client)
    business = rich_business(client, owner)
    admin = admin_ready(client)
    for headers in (business["caretaker"], business["tenant"], admin):
        assert client.get("/account/export", headers=headers).status_code == 403
    assert client.get("/account/export").status_code == 401


def test_closing_keeps_the_account_readable_and_downloadable(client, uploads):
    owner = make_owner(client)
    make_business(client, owner)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    started = client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin)
    assert started.status_code == 200
    state = started.json()
    assert state["closing"] is True and state["can_delete"] is False and state["days_left"] in (29, 30, 31)
    # The landlord can still look and download, but not change anything
    assert client.get("/properties", headers=owner).status_code == 200
    assert client.get("/account/export", headers=owner).status_code == 200
    blocked = client.post("/properties", json={"name": "New place"}, headers=owner)
    assert blocked.status_code == 403 and "closing" in blocked.json()["detail"].lower()
    # Starting twice is refused, and cancelling brings everything back
    assert client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin).status_code == 400
    assert client.post(f"/admin/accounts/{owner_id}/cancel-closing", headers=admin).status_code == 200
    assert client.post("/properties", json={"name": "New place"}, headers=owner).status_code == 201


def test_deleting_needs_the_closing_period_the_typed_email_and_an_off_switch(client, uploads):
    owner = make_owner(client)
    make_business(client, owner)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    url = f"/admin/accounts/{owner_id}/delete"
    # An account in use can never be deleted
    assert client.post(url, json={"confirm_email": "owner@example.com", "force": True}, headers=admin).status_code == 400
    client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin)
    # The wrong email, and too early
    assert client.post(url, json={"confirm_email": "wrong@example.com"}, headers=admin).status_code == 400
    early = client.post(url, json={"confirm_email": "owner@example.com"}, headers=admin)
    assert early.status_code == 400 and "30 days" in early.json()["detail"]
    # Nothing was deleted
    assert client.get("/properties", headers=owner).status_code == 200
    assert len(client.get("/properties", headers=owner).json()) == 1


def test_only_the_admin_can_use_closing(client, uploads):
    owner = make_owner(client)
    business = make_business(client, owner)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    for headers in (owner, business and make_caretaker(client, owner, [business["property_id"]])[1]):
        assert client.get(f"/admin/accounts/{owner_id}/closing", headers=headers).status_code == 403
        assert client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=headers).status_code == 403
        assert client.post(f"/admin/accounts/{owner_id}/delete", json={"confirm_email": "owner@example.com"}, headers=headers).status_code == 403


def test_the_preview_shows_counts_but_no_personal_details(client, uploads):
    owner = make_owner(client)
    rich_business(client, owner)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    reply = client.get(f"/admin/accounts/{owner_id}/closing", headers=admin)
    state = reply.json()
    assert state["counts"]["properties"] == 1 and state["counts"]["tenants"] == 2 and state["files"] == 3
    assert "Mercy" not in reply.text and "Joseph" not in reply.text and "87654321" not in reply.text


def test_deleting_removes_everything_of_theirs_and_nothing_else(client, uploads):
    owner = make_owner(client, "owner@example.com")
    business = rich_business(client, owner)
    other = make_owner(client, "other@example.com")
    other_business = make_business(client, other)
    pay(client, other, other_business["lease"]["id"], 500)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    # What they paid us is kept for our accounts
    client.post(f"/admin/accounts/{owner_id}/payments", json={"amount": 2000, "months": 2, "reference": "ABC1234567"}, headers=admin)
    client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin)
    age_closing(owner_id)
    assert client.get(f"/admin/accounts/{owner_id}/closing", headers=admin).json()["can_delete"] is True
    done = client.post(f"/admin/accounts/{owner_id}/delete", json={"confirm_email": "OWNER@example.com"}, headers=admin)
    assert done.status_code == 200, done.text
    assert done.json()["files_deleted"] == 3 and done.json()["rows_deleted"] > 10
    # The files are gone from the disk
    assert list(uploads.iterdir()) == []
    # Nobody of theirs can sign in any more: the landlord, the caretaker, or the tenant
    for username, password in [("owner@example.com", PASSWORD), ("john@example.com", PASSWORD), ("0711 000 111", "My-Own-Pass-42")]:
        assert client.post("/auth/login", data={"username": username, "password": password}).status_code == 401
    # The other landlord is untouched
    assert len(client.get("/properties", headers=other).json()) == 1
    assert client.get("/payments", headers=other).json()["total"] == 500
    with SessionLocal() as db:
        assert collect(db, owner_id) == {}
        gone = db.get(models.User, owner_id)
        assert gone.role == "deleted" and gone.is_active is False and gone.email == f"deleted-{owner_id}@deleted.invalid"
        assert gone.full_name == "Deleted account" and gone.phone is None
        assert db.query(SubscriptionPayment).filter(SubscriptionPayment.owner_id == owner_id).count() == 1
    # The admin side: the log has it (with the email masked), the list no longer shows them, and the revenue stays
    events = client.get("/admin/events", headers=admin).json()
    deleted = [event for event in events if event["action"] == "Deleted an account"]
    assert len(deleted) == 1 and "o***@example.com" in deleted[0]["detail"] and "owner@example.com" not in str(events)
    assert "owner@example.com" not in [row["email"] for row in client.get("/admin/accounts", headers=admin).json()]
    assert client.get("/admin/overview", headers=admin).json()["revenue_total"] == 2000


def test_after_deleting_the_only_landlord_every_table_is_empty(client, uploads):
    owner = make_owner(client, "owner@example.com")
    business = rich_business(client, owner)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    # A few more kinds of rows: an M-Pesa request, a 2-step login, and a recorded sign-in
    with SessionLocal() as db:
        db.add(mpesa_models.MpesaRequest(lease_id=business["lease"]["id"], phone="254711000111", amount=100, checkout_request_id="ws_CO_1", status="pending"))
        db.add(UserTotp(user_id=owner_id, secret="JBSWY3DPEHPK3PXP", enabled=True))
        db.commit()
    client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin)
    age_closing(owner_id)
    done = client.post(f"/admin/accounts/{owner_id}/delete", json={"confirm_email": "owner@example.com"}, headers=admin)
    assert done.status_code == 200, done.text
    skip = KEEP_TABLES | {"login_attempts", "user_security", "user_totp"}
    with SessionLocal() as db:
        for table in Base.metadata.sorted_tables:
            if table.name in skip:
                continue
            assert db.execute(select(func.count()).select_from(table)).scalar() == 0, f"The table {table.name} still has rows"
        # The admin's own sign-in secrets stay, theirs do not
        assert db.query(UserTotp).filter(UserTotp.user_id == owner_id).count() == 0
        assert db.query(UserSecurity).filter(UserSecurity.user_id == owner_id).count() == 0
        assert db.query(LoginAttempt).filter(LoginAttempt.email.in_(["owner@example.com", "john@example.com"])).count() == 0
        assert db.query(models.User).filter(models.User.role.in_(["caretaker", "tenant", "owner"])).count() == 0