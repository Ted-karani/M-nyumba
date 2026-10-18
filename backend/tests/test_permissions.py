# Import our test helpers
from helpers import PASSWORD, make_business, make_caretaker, make_owner, make_property, make_unit, pay, sign_in


def test_owners_cannot_see_each_others_data(client):
    owner_a = make_owner(client, "a@example.com")
    owner_b = make_owner(client, "b@example.com")
    business = make_business(client, owner_a)
    lease_id = business["lease"]["id"]
    pay(client, owner_a, lease_id, 3000)
    # Everything of owner A is "not found" for owner B
    for path in [
        f"/properties/{business['property_id']}",
        f"/units/{business['unit_id']}",
        f"/tenants/{business['tenant_id']}",
        f"/leases/{lease_id}",
        f"/leases/{lease_id}/payments",
        f"/leases/{lease_id}/charges",
    ]:
        assert client.get(path, headers=owner_b).status_code == 404, path
    # Owner B cannot add payments to owner A's lease
    assert pay(client, owner_b, lease_id, 100).status_code == 404
    # Owner B's own screens are empty
    assert client.get("/properties", headers=owner_b).json() == []
    assert client.get("/payments", headers=owner_b).json()["total"] == 0
    assert client.get("/dashboard", headers=owner_b).json()["units"]["total"] == 0
    assert client.get(f"/reports/monthly?month=2026-10&property_id={business['property_id']}", headers=owner_b).status_code == 404


def test_nobody_can_get_in_without_signing_in(client):
    for path in ["/properties", "/dashboard", "/payments", "/tenants", "/work/properties", "/account/activity", "/documents", "/tasks", "/expenses"]:
        assert client.get(path).status_code == 401, path


def test_a_caretaker_sees_only_their_properties_and_no_money(client):
    owner = make_owner(client)
    mine = make_business(client, owner)
    other_property = make_property(client, owner, "Test Block")
    make_unit(client, owner, other_property, "T1")
    _, john = make_caretaker(client, owner, [mine["property_id"]])
    # Their home screen shows only their property, with no rent or deposit
    work = client.get("/work/properties", headers=john).json()
    assert [prop["property_id"] for prop in work] == [mine["property_id"]]
    for unit in work[0]["units"]:
        assert "rent_amount" not in unit and "deposit_amount" not in unit
    # The owner's screens are empty for them
    assert client.get("/properties", headers=john).json() == []
    board = client.get("/dashboard", headers=john).json()
    assert board["collected_this_month"] == 0 and board["overdue_count"] == 0
    assert client.get("/payments", headers=john).json()["total"] == 0
    # And they cannot change anything of the owner's
    assert client.post("/properties", json={"name": "Hack"}, headers=john).status_code == 403
    assert client.get("/account/activity", headers=john).status_code == 403
    assert client.get("/expenses", headers=john).status_code == 403


def test_caretaker_repairs_are_scoped_and_cost_free(client):
    owner = make_owner(client)
    mine = make_business(client, owner)
    other_property = make_property(client, owner, "Test Block")
    _, john = make_caretaker(client, owner, [mine["property_id"]])
    created = client.post(
        "/maintenance",
        json={"property_id": mine["property_id"], "unit_id": mine["unit_id"], "title": "Leaking tap", "priority": "urgent"},
        headers=john,
    )
    assert created.status_code == 201
    assert created.json()["reported_by_name"] == "John Mutua"
    repair_id = created.json()["id"]
    # A property that is not theirs
    assert client.post("/maintenance", json={"property_id": other_property, "title": "Not allowed"}, headers=john).status_code == 404
    # They can move it along, but cannot enter costs or delete it
    assert client.put(f"/maintenance/{repair_id}", json={"status": "in_progress"}, headers=john).status_code == 200
    assert client.put(f"/maintenance/{repair_id}", json={"cost": 500}, headers=john).status_code == 403
    assert client.delete(f"/maintenance/{repair_id}", headers=john).status_code == 403
    # The owner enters the cost, and the caretaker still cannot see it
    assert client.put(f"/maintenance/{repair_id}", json={"cost": 500}, headers=owner).status_code == 200
    assert client.get("/maintenance", headers=john).json()["items"][0]["cost"] is None
    # The owner's repair in the other property is invisible to the caretaker
    hidden = client.post("/maintenance", json={"property_id": other_property, "title": "Broken gate"}, headers=owner).json()["id"]
    assert client.get(f"/maintenance/{hidden}", headers=john).status_code == 404


def test_a_caretaker_cannot_change_an_occupied_unit(client):
    owner = make_owner(client)
    mine = make_business(client, owner)
    empty_unit = make_unit(client, owner, mine["property_id"], "A2")
    _, john = make_caretaker(client, owner, [mine["property_id"]])
    assert client.put(f"/work/units/{mine['unit_id']}/status", json={"status": "maintenance"}, headers=john).status_code == 400
    assert client.put(f"/work/units/{empty_unit}/status", json={"status": "maintenance"}, headers=john).status_code == 200


def test_a_switched_off_caretaker_is_locked_out_at_once(client):
    owner = make_owner(client)
    mine = make_business(client, owner)
    caretaker_id, john = make_caretaker(client, owner, [mine["property_id"]])
    assert client.get("/work/properties", headers=john).status_code == 200
    assert client.put(f"/caretakers/{caretaker_id}", json={"is_active": False}, headers=owner).status_code == 200
    assert client.get("/work/properties", headers=john).status_code == 401


def test_resetting_a_caretakers_password_signs_them_out(client):
    owner = make_owner(client)
    mine = make_business(client, owner)
    caretaker_id, john = make_caretaker(client, owner, [mine["property_id"]])
    reset = client.put(f"/caretakers/{caretaker_id}", json={"password": "Another-Pass-9"}, headers=owner)
    assert reset.status_code == 200
    # The old login stops working straight away, and the new password works
    assert client.get("/work/properties", headers=john).status_code == 401
    assert client.post("/auth/login", data={"username": "john@example.com", "password": PASSWORD}).status_code == 401
    assert client.get("/work/properties", headers=sign_in(client, "john@example.com", "Another-Pass-9")).status_code == 200