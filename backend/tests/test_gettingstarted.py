# Import our own files
from database import SessionLocal
from security_models import UserTotp

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner, make_property, make_tenant, make_unit, pay
from test_admin import admin_ready
from test_portal import sign_in_tenant

IDS = ["add_property", "add_units", "add_tenants", "payment_details", "first_payment", "tenant_portal", "two_step", "caretaker"]


def progress(client, owner):
    response = client.get("/getting-started", headers=owner)
    assert response.status_code == 200, response.text
    return response.json()


def done(data):
    return {step["id"] for step in data["steps"] if step["done"]}


def test_a_new_landlord_starts_with_nothing_done(client):
    owner = make_owner(client)
    data = progress(client, owner)
    assert [step["id"] for step in data["steps"]] == IDS
    assert data["done_count"] == 0 and data["total"] == 8 and data["core_done"] is False
    assert [step["core"] for step in data["steps"]] == [True, True, True, False, False, False, False, False]
    for step in data["steps"]:
        assert step["title"] and step["description"] and step["link"].startswith("/") and step["action"]


def test_a_building_and_then_its_units_tick_off(client):
    owner = make_owner(client)
    property_id = make_property(client, owner)
    assert done(progress(client, owner)) == {"add_property"}
    make_unit(client, owner, property_id, "A1")
    data = progress(client, owner)
    assert done(data) == {"add_property", "add_units"} and data["core_done"] is False


def test_a_tenant_counts_only_once_they_have_a_tenancy(client):
    owner = make_owner(client)
    make_tenant(client, owner)
    assert "add_tenants" not in done(progress(client, owner))
    other = make_owner(client, "second@example.com")
    make_business(client, other)
    data = progress(client, other)
    assert {"add_property", "add_units", "add_tenants"} <= done(data) and data["core_done"] is True


def test_recording_a_payment_ticks_it_off(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    assert "first_payment" not in done(progress(client, owner))
    pay(client, owner, business["lease"]["id"], 3000)
    assert "first_payment" in done(progress(client, owner))


def test_payment_details_count_only_when_a_number_is_saved(client):
    owner = make_owner(client)
    client.put("/portal-access/payment-details", json={"paybill_number": None, "instructions": "Pay on the 5th"}, headers=owner)
    assert "payment_details" not in done(progress(client, owner))
    assert client.put("/portal-access/payment-details", json={"paybill_number": "123456"}, headers=owner).status_code == 200
    assert "payment_details" in done(progress(client, owner))


def test_giving_a_tenant_portal_access_ticks_it_off(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    assert "tenant_portal" not in done(progress(client, owner))
    sign_in_tenant(client, owner, business["tenant_id"])
    assert "tenant_portal" in done(progress(client, owner))


def test_two_step_login_counts_only_when_it_is_switched_on(client):
    owner = make_owner(client)
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        db.add(UserTotp(user_id=owner_id, secret="JBSWY3DPEHPK3PXP", enabled=False))
        db.commit()
    assert "two_step" not in done(progress(client, owner))
    with SessionLocal() as db:
        db.query(UserTotp).filter(UserTotp.user_id == owner_id).update({"enabled": True})
        db.commit()
    assert "two_step" in done(progress(client, owner))


def test_adding_a_caretaker_ticks_it_off(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    assert "caretaker" not in done(progress(client, owner))
    make_caretaker(client, owner, [business["property_id"]])
    assert "caretaker" in done(progress(client, owner))


def test_when_everything_is_done_the_count_is_complete(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    pay(client, owner, business["lease"]["id"], 3000)
    client.put("/portal-access/payment-details", json={"paybill_number": "123456"}, headers=owner)
    sign_in_tenant(client, owner, business["tenant_id"])
    make_caretaker(client, owner, [business["property_id"]])
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        db.add(UserTotp(user_id=owner_id, secret="JBSWY3DPEHPK3PXP", enabled=True))
        db.commit()
    data = progress(client, owner)
    assert done(data) == set(IDS) and data["done_count"] == 8 and data["core_done"] is True


def test_one_landlords_progress_never_counts_anothers_data(client):
    busy = make_owner(client)
    business = make_business(client, busy)
    pay(client, busy, business["lease"]["id"], 3000)
    client.put("/portal-access/payment-details", json={"paybill_number": "123456"}, headers=busy)
    sign_in_tenant(client, busy, business["tenant_id"])
    make_caretaker(client, busy, [business["property_id"]])
    newcomer = make_owner(client, "newcomer@example.com")
    data = progress(client, newcomer)
    assert data["done_count"] == 0 and data["core_done"] is False


def test_only_landlords_have_a_checklist(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    for headers in (john, tenant, admin):
        assert client.get("/getting-started", headers=headers).status_code == 403
    assert client.get("/getting-started").status_code == 401


def test_the_demo_landlord_is_already_past_the_core_steps(client):
    admin = admin_ready(client)
    created = client.post("/admin/demo", headers=admin).json()
    login = client.post("/auth/login", data={"username": "demo.landlord@example.com", "password": created["password"]})
    demo = {"Authorization": f"Bearer {login.json()['access_token']}"}
    data = progress(client, demo)
    assert data["core_done"] is True and {"add_property", "add_units", "add_tenants", "first_payment"} <= done(data)
    assert "caretaker" not in done(data) and "tenant_portal" not in done(data)