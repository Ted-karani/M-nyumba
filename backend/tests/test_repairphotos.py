# Import the tools we need
import io
import zipfile
from datetime import date

import pytest

# Import our own files
import models
from database import SessionLocal
from repair_photo_models import RepairPhoto

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner, make_tenant, make_unit
from test_admin import admin_ready, owner_id_for
from test_closing import age_closing
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


def png(name="leak.png"):
    return {"file": (name, PNG, "image/png")}


# A landlord with a tenant who has portal access, and one report from that tenant
def setup(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    repair = client.post("/portal/repairs", json={"title": "Leaking tap"}, headers=tenant).json()["id"]
    return owner, business, tenant, repair


def add(client, headers, repair, tenant=True, **files):
    base = "/portal/repairs" if tenant else "/maintenance"
    return client.post(f"{base}/{repair}/photos", files=files or png(), headers=headers)


def test_a_tenant_adds_a_photo_and_the_landlord_and_caretaker_see_it(client, uploads):
    owner, business, tenant, repair = setup(client)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    added = add(client, tenant, repair)
    assert added.status_code == 201 and added.json()["by_tenant"] is True and added.json()["can_delete"] is True
    for headers in (owner, john):
        photos = client.get(f"/maintenance/{repair}/photos", headers=headers).json()
        assert len(photos) == 1 and photos[0]["by_tenant"] is True and photos[0]["id"] == added.json()["id"]
        file = client.get(f"/maintenance/photos/{photos[0]['id']}/file", headers=headers)
        assert file.status_code == 200 and file.content == PNG and file.headers["content-type"] == "image/png"
        assert "private" in file.headers["cache-control"] and file.headers["x-content-type-options"] == "nosniff"
    # The tenant sees their own photo, and its file
    mine = client.get(f"/portal/repairs/{repair}/photos", headers=tenant).json()
    assert len(mine) == 1 and client.get(f"/portal/repairs/photos/{mine[0]['id']}/file", headers=tenant).content == PNG
    # The list of repairs shows how many photos each has
    assert client.get("/maintenance", headers=owner).json()["items"][0]["photo_count"] == 1
    assert client.get("/maintenance", headers=john).json()["items"][0]["photo_count"] == 1


def test_only_real_pictures_are_accepted(client, uploads):
    owner, business, tenant, repair = setup(client)
    for files in [
        {"file": ("notes.txt", b"hello", "text/plain")},
        {"file": ("fake.png", b"this is not a picture", "image/png")},
        {"file": ("empty.png", b"", "image/png")},
        {"file": ("noending", PNG, "image/png")},
        {"file": ("doc.pdf", b"%PDF-1.4 test", "application/pdf")},
    ]:
        assert add(client, tenant, repair, **files).status_code == 400, files
        assert add(client, owner, repair, tenant=False, **files).status_code == 400, files
    assert list(uploads.iterdir()) == []
    assert client.get("/maintenance", headers=owner).json()["items"][0]["photo_count"] == 0


def test_the_limits_on_photos(client, uploads):
    owner, business, tenant, repair = setup(client)
    for _ in range(4):
        assert add(client, tenant, repair).status_code == 201
    over = add(client, tenant, repair)
    assert over.status_code == 400 and "at most 4" in over.json()["detail"]
    # The landlord can add more, up to 8 in all
    for _ in range(4):
        assert add(client, owner, repair, tenant=False).status_code == 201
    full = add(client, owner, repair, tenant=False)
    assert full.status_code == 400 and "at most 8" in full.json()["detail"]
    assert len(list(uploads.iterdir())) == 8


def test_a_tenant_cannot_add_to_a_fixed_report_but_staff_can(client, uploads):
    owner, business, tenant, repair = setup(client)
    first = add(client, tenant, repair).json()["id"]
    client.put(f"/maintenance/{repair}", json={"status": "fixed"}, headers=owner)
    fixed = add(client, tenant, repair)
    assert fixed.status_code == 400 and "already fixed" in fixed.json()["detail"]
    assert client.delete(f"/portal/repairs/photos/{first}", headers=tenant).status_code == 400
    assert client.get(f"/portal/repairs/{repair}/photos", headers=tenant).json()[0]["can_delete"] is False
    assert add(client, owner, repair, tenant=False).status_code == 201


def test_tenants_only_ever_see_their_own_photos_and_reports(client, uploads):
    owner, business, tenant, repair = setup(client)
    add(client, owner, repair, tenant=False)
    mine = add(client, tenant, repair).json()["id"]
    # The landlord's photo is not in the tenant's list
    assert [photo["id"] for photo in client.get(f"/portal/repairs/{repair}/photos", headers=tenant).json()] == [mine]
    # A second tenant of the same landlord cannot see, add to, or remove them
    second_tenant_id = make_tenant(client, owner, name="Second Tenant", phone="0722 222 222")
    unit = make_unit(client, owner, business["property_id"], "B7")
    with SessionLocal() as db:
        db.add(models.Lease(unit_id=unit, tenant_id=second_tenant_id, start_date=date.today(), rent_amount=5000, status="active"))
        db.commit()
    other = sign_in_tenant(client, owner, second_tenant_id, phone="0722 222 222")
    assert client.get(f"/portal/repairs/{repair}/photos", headers=other).status_code == 404
    assert add(client, other, repair).status_code == 404
    assert client.get(f"/portal/repairs/photos/{mine}/file", headers=other).status_code == 404
    assert client.delete(f"/portal/repairs/photos/{mine}", headers=other).status_code == 404
    # Their own report is separate
    repair_two = client.post("/portal/repairs", json={"title": "Broken window"}, headers=other).json()["id"]
    assert add(client, other, repair_two).status_code == 201
    assert len(client.get(f"/maintenance/{repair_two}/photos", headers=owner).json()) == 1


def test_a_tenant_cannot_remove_the_landlords_photo_and_can_remove_their_own(client, uploads):
    owner, business, tenant, repair = setup(client)
    staff_photo = add(client, owner, repair, tenant=False).json()["id"]
    mine = add(client, tenant, repair).json()["id"]
    assert client.delete(f"/portal/repairs/photos/{staff_photo}", headers=tenant).status_code == 404
    assert client.get(f"/portal/repairs/photos/{staff_photo}/file", headers=tenant).status_code == 404
    assert client.delete(f"/portal/repairs/photos/{mine}", headers=tenant).status_code == 204
    assert len(list(uploads.iterdir())) == 1
    assert client.get(f"/portal/repairs/photos/{mine}/file", headers=tenant).status_code == 404


def test_staff_rules_for_removing_photos(client, uploads):
    owner, business, tenant, repair = setup(client)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenants_photo = add(client, tenant, repair).json()["id"]
    johns_photo = add(client, john, repair, tenant=False).json()["id"]
    assert client.delete(f"/maintenance/photos/{tenants_photo}", headers=john).status_code == 403
    assert client.delete(f"/maintenance/photos/{johns_photo}", headers=john).status_code == 204
    assert client.delete(f"/maintenance/photos/{tenants_photo}", headers=owner).status_code == 204
    assert list(uploads.iterdir()) == []


def test_other_landlords_and_other_caretakers_cannot_reach_the_photos(client, uploads):
    owner, business, tenant, repair = setup(client)
    photo = add(client, tenant, repair).json()["id"]
    stranger = make_owner(client, "stranger@example.com")
    other_business = make_business(client, stranger)
    _, outsider = make_caretaker(client, stranger, [other_business["property_id"]], email="outsider@example.com")
    for headers in (stranger, outsider):
        assert client.get(f"/maintenance/{repair}/photos", headers=headers).status_code == 404
        assert add(client, headers, repair, tenant=False).status_code == 404
        assert client.get(f"/maintenance/photos/{photo}/file", headers=headers).status_code == 404
        assert client.delete(f"/maintenance/photos/{photo}", headers=headers).status_code == 404


def test_each_kind_of_person_uses_only_their_own_endpoints(client, uploads):
    owner, business, tenant, repair = setup(client)
    photo = add(client, tenant, repair).json()["id"]
    # A tenant cannot use the landlord's endpoints, and a landlord cannot use the tenant's
    assert client.get(f"/maintenance/{repair}/photos", headers=tenant).status_code == 403
    assert client.get(f"/maintenance/photos/{photo}/file", headers=tenant).status_code == 403
    assert client.get(f"/portal/repairs/{repair}/photos", headers=owner).status_code == 403
    assert client.get(f"/maintenance/{repair}/photos").status_code == 401
    assert client.post(f"/portal/repairs/{repair}/photos", files=png()).status_code == 401


def test_deleting_a_repair_removes_its_photos_and_files(client, uploads):
    owner, business, tenant, repair = setup(client)
    add(client, tenant, repair)
    add(client, owner, repair, tenant=False)
    assert len(list(uploads.iterdir())) == 2
    assert client.delete(f"/maintenance/{repair}", headers=owner).status_code == 204
    assert list(uploads.iterdir()) == []
    with SessionLocal() as db:
        assert db.query(RepairPhoto).count() == 0


def test_photos_are_in_the_activity_log(client, uploads):
    owner, business, tenant, repair = setup(client)
    add(client, tenant, repair)
    staff_photo = add(client, owner, repair, tenant=False).json()["id"]
    client.delete(f"/maintenance/photos/{staff_photo}", headers=owner)
    summaries = [row["summary"] for row in client.get("/account/activity", headers=owner).json()["items"]]
    for line in ("Added a photo to a repair report", "Added a photo to a repair", "Removed a repair photo"):
        assert line in summaries


def test_photos_are_in_the_data_export_and_leave_with_the_account(client, uploads):
    owner, business, tenant, repair = setup(client)
    add(client, tenant, repair)
    export = client.get("/account/export", headers=owner)
    names = zipfile.ZipFile(io.BytesIO(export.content)).namelist()
    assert any(name.startswith("files/repair_photos/") for name in names)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    client.post(f"/admin/accounts/{owner_id}/start-closing", json={}, headers=admin)
    age_closing(owner_id)
    done = client.post(f"/admin/accounts/{owner_id}/delete", json={"confirm_email": "owner@example.com"}, headers=admin)
    assert done.status_code == 200, done.text
    assert list(uploads.iterdir()) == []
    with SessionLocal() as db:
        assert db.query(RepairPhoto).count() == 0