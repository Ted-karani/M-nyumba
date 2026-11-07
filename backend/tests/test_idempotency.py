# Import the tools we need
import io
import zipfile
from datetime import datetime, timedelta

import openpyxl
import pytest

# Import our own files
from database import SessionLocal
from idempotency import IdempotencyKey

# Import our test helpers
from helpers import make_business, make_owner
from test_admin import admin_ready, owner_id_for
from test_closing import age_closing

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


# The same headers, plus a secret number
def with_key(headers, key="repair-key-12345"):
    return {**headers, "Idempotency-Key": key}


# A repair report for the test business
def repair(business, title="Leaking tap"):
    return {"property_id": business["property_id"], "title": title}


def count_repairs(client, owner):
    return len(client.get("/maintenance", headers=owner).json()["items"])


def test_the_same_secret_number_creates_a_repair_only_once(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    first = client.post("/maintenance", json=repair(business), headers=with_key(owner))
    second = client.post("/maintenance", json=repair(business), headers=with_key(owner))
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.headers.get("idempotent-replay") == "true" and "idempotent-replay" not in first.headers
    assert count_repairs(client, owner) == 1


def test_different_or_missing_secret_numbers_are_separate_requests(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    client.post("/maintenance", json=repair(business, "One"), headers=with_key(owner, "key-number-000001"))
    client.post("/maintenance", json=repair(business, "Two"), headers=with_key(owner, "key-number-000002"))
    client.post("/maintenance", json=repair(business, "Three"), headers=owner)
    client.post("/maintenance", json=repair(business, "Four"), headers=owner)
    assert count_repairs(client, owner) == 4


def test_a_secret_number_belongs_to_one_person(client):
    first = make_owner(client, "first@example.com")
    second = make_owner(client, "second@example.com")
    business_one = make_business(client, first)
    business_two = make_business(client, second)
    one = client.post("/maintenance", json=repair(business_one), headers=with_key(first, "shared-key-12345"))
    two = client.post("/maintenance", json=repair(business_two), headers=with_key(second, "shared-key-12345"))
    assert one.status_code == 201 and two.status_code == 201
    assert "idempotent-replay" not in two.headers
    assert count_repairs(client, first) == 1 and count_repairs(client, second) == 1


def test_a_secret_number_cannot_be_reused_for_something_else(client, uploads):
    owner = make_owner(client)
    business = make_business(client, owner)
    started = client.post(f"/inspections/lease/{business['lease']['id']}/move_in", json={}, headers=owner).json()
    client.post("/maintenance", json=repair(business), headers=with_key(owner, "reused-key-12345"))
    other = client.post(f"/inspections/{started['id']}/photos", files={"file": ("wall.png", PNG, "image/png")}, headers=with_key(owner, "reused-key-12345"))
    assert other.status_code == 409


def test_a_bad_secret_number_is_refused_and_other_addresses_ignore_it(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    assert client.post("/maintenance", json=repair(business), headers=with_key(owner, "no")).status_code == 400
    # An address that does not use secret numbers behaves as before
    first = client.post("/properties", json={"name": "Twin"}, headers=with_key(owner, "twin-key-123456"))
    second = client.post("/properties", json={"name": "Twin"}, headers=with_key(owner, "twin-key-123456"))
    assert first.status_code == 201 and second.status_code != 500


def test_failures_are_not_remembered(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    bad = client.post("/maintenance", json={"property_id": business["property_id"], "title": "x"}, headers=with_key(owner, "retry-key-12345"))
    assert bad.status_code >= 400
    good = client.post("/maintenance", json=repair(business), headers=with_key(owner, "retry-key-12345"))
    assert good.status_code == 201 and "idempotent-replay" not in good.headers
    assert count_repairs(client, owner) == 1


def test_a_request_that_is_still_running_is_not_started_twice(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    user_id = client.get("/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        db.add(IdempotencyKey(user_id=user_id, key="busy-key-12345", method="POST", path="/maintenance", state="processing", created_at=datetime.utcnow()))
        db.commit()
    busy = client.post("/maintenance", json=repair(business), headers=with_key(owner, "busy-key-12345"))
    assert busy.status_code == 409 and "still being processed" in busy.json()["detail"]
    assert count_repairs(client, owner) == 0
    # Something stuck for ten minutes is allowed to run again
    with SessionLocal() as db:
        db.query(IdempotencyKey).update({"created_at": datetime.utcnow() - timedelta(minutes=10)})
        db.commit()
    assert client.post("/maintenance", json=repair(business), headers=with_key(owner, "busy-key-12345")).status_code == 201
    assert count_repairs(client, owner) == 1


def test_a_photo_sent_twice_is_stored_once(client, uploads):
    owner = make_owner(client)
    business = make_business(client, owner)
    started = client.post(f"/inspections/lease/{business['lease']['id']}/move_in", json={}, headers=owner).json()
    url = f"/inspections/{started['id']}/photos"
    first = client.post(url, files={"file": ("wall.png", PNG, "image/png")}, headers=with_key(owner, "photo-key-12345"))
    second = client.post(url, files={"file": ("wall.png", PNG, "image/png")}, headers=with_key(owner, "photo-key-12345"))
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(list(uploads.iterdir())) == 1


def test_a_repeated_request_is_not_logged_twice(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    client.post("/maintenance", json=repair(business), headers=with_key(owner))
    after_first = len(client.get("/account/activity", headers=owner).json()["items"])
    client.post("/maintenance", json=repair(business), headers=with_key(owner))
    assert len(client.get("/account/activity", headers=owner).json()["items"]) == after_first


def test_saved_secret_numbers_are_not_exported_and_go_with_the_account(client, uploads):
    owner = make_owner(client, "owner@example.com")
    business = make_business(client, owner)
    client.post("/maintenance", json=repair(business), headers=with_key(owner))
    export = client.get("/account/export", headers=owner)
    data = zipfile.ZipFile(io.BytesIO(export.content)).read("data.xlsx")
    assert "idempotency_keys" not in openpyxl.load_workbook(io.BytesIO(data)).sheetnames
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin)
    age_closing(owner_id)
    done = client.post(f"/admin/accounts/{owner_id}/delete", json={"confirm_email": "owner@example.com"}, headers=admin)
    assert done.status_code == 200, done.text
    with SessionLocal() as db:
        assert db.query(IdempotencyKey).count() == 0