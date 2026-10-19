# Import the date tools
from datetime import date, timedelta

# Import our test helpers
from helpers import PASSWORD, make_business, make_caretaker, make_owner, make_property, make_tenant, make_unit, move_in, pay, register

# The tenant's phone number in the helpers
PHONE = "0711 000 111"


# Give a tenant portal access, and return the answer
def give_access(client, owner, tenant_id):
    response = client.post(f"/portal-access/{tenant_id}", headers=owner)
    assert response.status_code == 200, response.text
    return response.json()


# Try to sign in with a phone number (the caller checks the answer)
def tenant_login(client, phone, password):
    return client.post("/auth/login", data={"username": phone, "password": password})


# Give access, sign in with the temporary password, choose a new password, and return the header of the new login
def sign_in_tenant(client, owner, tenant_id, phone=PHONE, new_password="My-Own-Pass-42"):
    temporary = give_access(client, owner, tenant_id)["temporary_password"]
    first = tenant_login(client, phone, temporary)
    assert first.status_code == 200, first.text
    first_headers = {"Authorization": "Bearer " + first.json()["access_token"]}
    changed = client.post("/portal/change-password", json={"current_password": temporary, "new_password": new_password}, headers=first_headers)
    assert changed.status_code == 200, changed.text
    return {"Authorization": "Bearer " + changed.json()["access_token"]}


def test_a_tenant_signs_in_with_their_phone_number(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    access = give_access(client, owner, business["tenant_id"])
    assert access["phone"] == "254711000111"
    assert len(access["temporary_password"]) == 8
    # Different ways of typing the same number all work
    for typed in [PHONE, "0711000111", "+254 711 000 111"]:
        assert tenant_login(client, typed, access["temporary_password"]).status_code == 200, typed
    assert tenant_login(client, PHONE, "wrong-pass-1").status_code == 401
    token = tenant_login(client, PHONE, access["temporary_password"]).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": "Bearer " + token}).json()
    assert me["role"] == "tenant"


def test_the_first_login_forces_a_new_password(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    temporary = give_access(client, owner, business["tenant_id"])["temporary_password"]
    first = {"Authorization": "Bearer " + tenant_login(client, PHONE, temporary).json()["access_token"]}
    assert client.get("/portal/status", headers=first).json()["must_change_password"] is True
    # Nothing else works until the password is changed
    assert client.get("/portal/home", headers=first).status_code == 403
    # Weak and wrong passwords are refused
    assert client.post("/portal/change-password", json={"current_password": temporary, "new_password": "password123"}, headers=first).status_code == 400
    assert client.post("/portal/change-password", json={"current_password": "not-it-1234", "new_password": "My-Own-Pass-42"}, headers=first).status_code == 400
    # A good password gives a fresh login, and the old one stops working
    good = client.post("/portal/change-password", json={"current_password": temporary, "new_password": "My-Own-Pass-42"}, headers=first)
    assert good.status_code == 200
    fresh = {"Authorization": "Bearer " + good.json()["access_token"]}
    assert client.get("/portal/status", headers=first).status_code == 401
    assert client.get("/portal/status", headers=fresh).json()["must_change_password"] is False
    assert client.get("/portal/home", headers=fresh).status_code == 200
    # The temporary password no longer signs in
    assert tenant_login(client, PHONE, temporary).status_code == 401


def test_a_tenant_is_fenced_off_everything_but_the_portal(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    for path in [
        "/properties", "/tenants", "/dashboard", "/payments", "/expenses", "/maintenance", "/documents",
        "/tasks", "/tasks/upcoming", "/listings", "/notices", "/portal-access", "/account/activity",
        "/work/properties", "/caretakers", "/reminders/summary", "/billing/rent-preview",
    ]:
        assert client.get(path, headers=tenant).status_code == 403, path
    lease_id = business["lease"]["id"]
    assert pay(client, tenant, lease_id, 100).status_code == 403
    assert client.post("/maintenance", json={"property_id": business["property_id"], "title": "Nope"}, headers=tenant).status_code == 403
    assert client.post("/notices", json={"title": "Fake notice", "body": "x"}, headers=tenant).status_code == 403
    assert client.post(f"/portal-access/{business['tenant_id']}", headers=tenant).status_code == 403


def test_owners_and_caretakers_cannot_use_the_tenant_portal(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    assert client.get("/portal/home", headers=owner).status_code == 403
    assert client.get("/portal/home", headers=john).status_code == 403
    assert client.get("/portal/status", headers=owner).status_code == 403


def test_a_tenant_sees_only_their_own_home_and_statement(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    # A second tenant in another unit
    other_unit = make_unit(client, owner, business["property_id"], "B1", rent=9000, deposit=0)
    other_tenant = make_tenant(client, owner, name="Joseph Kamau", phone="0722 111 222")
    other_lease = move_in(client, owner, other_unit, other_tenant)
    pay(client, owner, business["lease"]["id"], 5000, method="mpesa", reference="SJK4L2M9QP")
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    page = client.get("/portal/home", headers=tenant)
    assert page.status_code == 200
    home = page.json()
    assert len(home["tenancies"]) == 1
    assert home["tenancies"][0]["unit_number"] == "A1"
    assert home["tenancies"][0]["balance"] == 11000
    assert home["tenancies"][0]["total_paid"] == 5000
    # Nothing of the other tenant leaks
    assert "Joseph" not in page.text and "B1" not in page.text
    # The statement shows the newest line first, with the balance after it
    statement = client.get(f"/portal/statement/{business['lease']['id']}", headers=tenant).json()
    assert statement[0]["kind"] == "payment"
    assert statement[0]["reference"] == "SJK4L2M9QP"
    assert statement[0]["balance_after"] == 11000
    assert statement[-1]["balance_after"] in (8000, 16000)
    # Someone else's statement is "not found"
    assert client.get(f"/portal/statement/{other_lease['id']}", headers=tenant).status_code == 404


def test_the_payment_details_reach_the_tenant(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    # A bad number is refused
    assert client.put("/portal-access/payment-details", json={"paybill_number": "12ab"}, headers=owner).status_code == 422
    saved = client.put(
        "/portal-access/payment-details",
        json={"paybill_number": "247 247", "account_hint": "Your unit number", "instructions": "Please pay by the 5th."},
        headers=owner,
    )
    assert saved.status_code == 200 and saved.json()["paybill_number"] == "247247"
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    info = client.get("/portal/home", headers=tenant).json()["payment_info"]
    assert info["paybill_number"] == "247247"
    assert info["account_hint"] == "Your unit number"
    assert info["contact_name"] == "Owner One"


def test_tenants_report_problems_the_owner_can_see(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    created = client.post("/portal/repairs", json={"title": "Leaking tap", "description": "In the kitchen", "priority": "urgent"}, headers=tenant)
    assert created.status_code == 201
    assert created.json()["unit_number"] == "A1" and created.json()["status"] == "open"
    # The owner sees it, with the tenant's name
    items = client.get("/maintenance", headers=owner).json()["items"]
    assert any(item["title"] == "Leaking tap" and item["reported_by_name"] == "Mercy Wambui" for item in items)
    # The owner's own repair is not shown to the tenant
    client.post("/maintenance", json={"property_id": business["property_id"], "title": "Paint the gate"}, headers=owner)
    mine = client.get("/portal/repairs", headers=tenant).json()
    assert [item["title"] for item in mine] == ["Leaking tap"]
    # A tenant cannot have more than 5 open problems
    for number in range(4):
        assert client.post("/portal/repairs", json={"title": f"Problem {number + 2}"}, headers=tenant).status_code == 201
    assert client.post("/portal/repairs", json={"title": "One too many"}, headers=tenant).status_code == 400


def test_notices_reach_the_right_tenants(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    other_property = make_property(client, owner, "Other Block")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    for body in [
        {"title": "Water shutdown", "body": "Tuesday 8am to 2pm"},
        {"title": "Gate repair", "body": "Gate closed Friday", "property_id": business["property_id"]},
        {"title": "Other block only", "body": "Not for you", "property_id": other_property},
        {"title": "Old news", "body": "Expired", "expires_on": yesterday},
        {"title": "Rent due date", "body": "Pay by the 5th", "pinned": True},
    ]:
        assert client.post("/notices", json=body, headers=owner).status_code == 201
    # Another landlord's notice is not shown either
    stranger = make_owner(client, "stranger@example.com")
    assert client.post("/notices", json={"title": "From someone else", "body": "x"}, headers=stranger).status_code == 201
    # A landlord cannot post to a property that is not theirs
    assert client.post("/notices", json={"title": "Hijack", "body": "x", "property_id": business["property_id"]}, headers=stranger).status_code == 404
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    titles = [notice["title"] for notice in client.get("/portal/notices", headers=tenant).json()]
    assert set(titles) == {"Water shutdown", "Gate repair", "Rent due date"}
    # Pinned ones come first
    assert titles[0] == "Rent due date"


def test_access_can_be_switched_off_and_reset(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    assert client.get("/portal/home", headers=tenant).status_code == 200
    # Switching off locks them out at once
    assert client.put(f"/portal-access/{business['tenant_id']}", json={"is_active": False}, headers=owner).status_code == 200
    assert client.get("/portal/home", headers=tenant).status_code == 401
    assert tenant_login(client, PHONE, "My-Own-Pass-42").status_code == 401
    # Switching back on brings the same password back
    assert client.put(f"/portal-access/{business['tenant_id']}", json={"is_active": True}, headers=owner).status_code == 200
    assert tenant_login(client, PHONE, "My-Own-Pass-42").status_code == 200
    # A new password kills the old one and forces another change
    fresh = give_access(client, owner, business["tenant_id"])["temporary_password"]
    assert tenant_login(client, PHONE, "My-Own-Pass-42").status_code == 401
    login = tenant_login(client, PHONE, fresh)
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/portal/status", headers=headers).json()["must_change_password"] is True


def test_access_belongs_to_one_landlord_and_one_phone(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    other = make_owner(client, "other@example.com")
    # Another landlord cannot give access to this tenant
    assert client.post(f"/portal-access/{business['tenant_id']}", headers=other).status_code == 404
    give_access(client, owner, business["tenant_id"])
    # And cannot take the same phone number for their own tenant
    their_tenant = make_tenant(client, other)
    clash = client.post(f"/portal-access/{their_tenant}", headers=other)
    assert clash.status_code == 400
    assert "already" in clash.json()["detail"]
    # The list of who has access is private to each owner
    names = [row["tenant_name"] for row in client.get("/portal-access", headers=other).json()]
    assert names == []


def test_the_hidden_tenant_login_name_cannot_be_registered(client):
    response = client.post("/auth/register", json={"full_name": "Sneaky Person", "email": "254711000111@tenants.mnyumba.app", "password": PASSWORD})
    assert response.status_code == 400


def test_tenant_actions_are_logged_but_sign_ins_are_not(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    client.post("/portal/repairs", json={"title": "Broken window"}, headers=tenant)
    log = client.get("/account/activity", headers=owner).json()
    entries = [(item["actor_name"], item["summary"]) for item in log["items"]]
    assert ("Mercy Wambui", "Reported a repair from the tenant portal") in entries
    assert not any(name == "Mercy Wambui" and summary == "Signed in" for name, summary in entries)


def test_a_tenant_with_no_active_lease_sees_no_home(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    assert client.post(f"/leases/{business['lease']['id']}/end", json={}, headers=owner).status_code == 200
    home = client.get("/portal/home", headers=tenant).json()
    assert home["tenancies"] == []
    # They cannot report problems without a home
    assert client.post("/portal/repairs", json={"title": "Leaking roof"}, headers=tenant).status_code == 400