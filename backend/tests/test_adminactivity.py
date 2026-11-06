# Import our test helpers
from helpers import PASSWORD, make_business, make_caretaker, make_owner
from test_admin import admin_ready, make_admin, owner_id_for, sign_in_admin
from test_portal import sign_in_tenant


# Try to sign in (the caller checks the answer)
def attempt(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_only_the_admin_can_see_sign_in_history(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    for path in ["/admin/signups", "/admin/signins", "/admin/security"]:
        for headers in (owner, john, tenant):
            assert client.get(path, headers=headers).status_code == 403, path
        assert client.get(path).status_code == 401, path


def test_signups_show_how_each_landlord_joined_and_whether_they_came_back(client):
    make_owner(client, "self@example.com")
    admin = admin_ready(client)
    created = client.post("/admin/accounts", json={"full_name": "Grace Njeri", "email": "grace@example.com"}, headers=admin)
    assert created.status_code == 201
    rows = {row["email"]: row for row in client.get("/admin/signups", headers=admin).json()}
    assert rows["self@example.com"]["source"] == "self"
    assert rows["self@example.com"]["never_signed_in"] is False and rows["self@example.com"]["sign_ins_30d"] >= 1
    assert rows["self@example.com"]["first_sign_in"] is not None
    # A landlord you added, who has not opened the app yet
    assert rows["grace@example.com"]["source"] == "admin"
    assert rows["grace@example.com"]["never_signed_in"] is True and rows["grace@example.com"]["sign_ins_30d"] == 0
    assert rows["grace@example.com"]["state"] == "active"
    # After her first sign-in she is no longer "never signed in"
    assert attempt(client, "grace@example.com", created.json()["temporary_password"]).status_code == 200
    after = {row["email"]: row for row in client.get("/admin/signups", headers=admin).json()}
    assert after["grace@example.com"]["never_signed_in"] is False


def test_the_sign_in_feed_shows_landlords_and_caretakers_but_never_tenants_or_names(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    make_caretaker(client, owner, [business["property_id"]])
    sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    feed = client.get("/admin/signins", headers=admin)
    data = feed.json()
    assert {row["who"] for row in data["items"]} == {"landlord", "caretaker"}
    assert all(row["landlord_name"] == "Owner One" for row in data["items"])
    assert data["caretaker_total"] == 1 and data["landlord_total"] >= 1
    # No tenant, no caretaker name, no phone number, and no internet address
    assert "Mercy" not in feed.text and "John" not in feed.text and "0711" not in feed.text
    assert all("ip" not in row for row in data["items"])
    # The admin's own sign-in is not in this feed
    assert not any(row["landlord_name"] == "Site Admin" for row in data["items"])


def test_the_sign_in_feed_can_be_filtered_and_has_limits(client):
    first = make_owner(client, "first@example.com")
    make_owner(client, "second@example.com")
    admin = admin_ready(client)
    first_id = owner_id_for(client, admin, "first@example.com")
    filtered = client.get(f"/admin/signins?owner_id={first_id}", headers=admin).json()
    assert filtered["items"] and all(row["owner_id"] == first_id for row in filtered["items"])
    everyone = client.get("/admin/signins", headers=admin).json()
    assert {person["name"] for person in everyone["people"]} == {"Owner One"}
    assert len(everyone["people"]) == 2
    assert client.get("/admin/signins?days=0", headers=admin).status_code == 422
    assert client.get("/admin/signins?days=31", headers=admin).status_code == 422


def test_failed_sign_ins_and_locks_show_in_the_security_view(client):
    make_owner(client)
    secret = make_admin()
    # Five wrong passwords lock the landlord, three on an email that does not exist, two on the admin
    for _ in range(5):
        assert attempt(client, "owner@example.com", "wrong-pass-1").status_code in (401, 429)
    for _ in range(3):
        attempt(client, "ghost@example.com", "wrong-pass-1")
    for _ in range(2):
        attempt(client, "admin@example.com", "wrong-pass-1")
    admin = sign_in_admin(client, secret)
    response = client.get("/admin/security", headers=admin)
    security = response.json()
    owner_row = next(row for row in security["accounts"] if row["email"] == "owner@example.com")
    assert owner_row["failed_24h"] == 5 and owner_row["failed_7d"] == 5
    assert owner_row["locked_minutes"] >= 1 and security["locked_now"] == 1
    # An email that belongs to nobody is only counted, never shown
    assert security["unknown_failed_24h"] == 3 and security["unknown_failed_7d"] == 3
    assert "ghost" not in response.text
    # The admin account sees its own attempts and sign-ins
    assert security["admin_failed_24h"] == 2 and security["admin_failed_7d"] == 2
    assert security["admin_sign_ins_7d"] == 1 and security["admin_last_sign_in"] is not None


def test_nobody_is_listed_when_nothing_went_wrong(client):
    make_owner(client)
    admin = admin_ready(client)
    security = client.get("/admin/security", headers=admin).json()
    assert security["accounts"] == [] and security["locked_now"] == 0
    assert security["unknown_failed_7d"] == 0 and security["admin_failed_7d"] == 0


def test_the_admins_own_sign_ins_are_in_the_admin_log(client):
    admin = admin_ready(client)
    events = client.get("/admin/events", headers=admin).json()
    assert any(event["action"] == "Admin signed in" for event in events)