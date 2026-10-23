# Import the date tools
from datetime import date, timedelta

# Import the tool for authenticator codes
import pyotp

# Import our own files
import models
import security
from admin_models import add_months
from database import SessionLocal
from security_models import UserTotp

# Import our test helpers
from helpers import PASSWORD, make_business, make_caretaker, make_owner, make_property, make_unit
from test_portal import sign_in_tenant
from test_security import turn_on_two_step

# The admin's password in the tests
ADMIN_PASSWORD = "Admin-Pass-2026-xyz"


# Make an admin account straight in the database (this is how it is made for real too, by a command on the server)
def make_admin(two_step=True, email="admin@example.com"):
    secret = None
    with SessionLocal() as db:
        user = models.User(full_name="Site Admin", email=email, password_hash=security.hash_password(ADMIN_PASSWORD), role="admin", is_active=True)
        db.add(user)
        db.flush()
        if two_step:
            secret = pyotp.random_base32()
            db.add(UserTotp(user_id=user.id, secret=secret, enabled=True))
        db.commit()
    return secret


# Sign the admin in (with a code from the pretend authenticator app, when 2-step login is on)
def sign_in_admin(client, secret, email="admin@example.com"):
    if secret:
        # Forget the last used code, so the same 30-second code can be used again in a test
        with SessionLocal() as db:
            user = db.query(models.User).filter(models.User.email == email).first()
            db.query(UserTotp).filter(UserTotp.user_id == user.id).update({"last_counter": 0})
            db.commit()
    first = client.post("/auth/login", data={"username": email, "password": ADMIN_PASSWORD}).json()
    if first.get("requires_otp"):
        second = client.post("/auth/login/verify", json={"challenge": first["challenge"], "code": pyotp.TOTP(secret).now()}).json()
        return {"Authorization": "Bearer " + second["access_token"]}
    return {"Authorization": "Bearer " + first["access_token"]}


# A ready admin
def admin_ready(client):
    return sign_in_admin(client, make_admin())


# Find a landlord's number in the admin's list, by their email
def owner_id_for(client, admin, email):
    rows = client.get("/admin/accounts", headers=admin).json()
    return next(row["owner_id"] for row in rows if row["email"] == email)


def test_only_the_admin_can_use_the_admin_pages(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    for headers in (owner, john, tenant):
        assert client.get("/admin/overview", headers=headers).status_code == 403
        assert client.get("/admin/accounts", headers=headers).status_code == 403
    assert client.get("/admin/overview").status_code == 401


def test_the_admin_must_turn_on_two_step_login_first(client):
    make_admin(two_step=False)
    admin = sign_in_admin(client, None)
    reply = client.get("/admin/overview", headers=admin)
    assert reply.status_code == 403
    assert "2-step" in reply.json()["detail"]


def test_the_admin_is_fenced_off_the_landlord_pages(client):
    admin = admin_ready(client)
    for path in ["/properties", "/tenants", "/dashboard", "/payments", "/documents", "/listings", "/work/properties", "/portal/home"]:
        assert client.get(path, headers=admin).status_code == 403, path
    assert client.get("/admin/overview", headers=admin).status_code == 200
    assert client.get("/account/2fa", headers=admin).status_code == 200


def test_the_admin_sees_counts_but_never_tenant_details(client):
    owner = make_owner(client)
    make_business(client, owner)
    admin = admin_ready(client)
    reply = client.get("/admin/accounts", headers=admin)
    row = next(item for item in reply.json() if item["email"] == "owner@example.com")
    assert row["units"] == 1 and row["occupied_units"] == 1 and row["tenants"] == 1
    assert "Mercy" not in reply.text and "0711" not in reply.text


def test_a_new_landlord_must_choose_their_own_password(client):
    admin = admin_ready(client)
    created = client.post("/admin/accounts", json={"full_name": "Grace Njeri", "email": "grace@example.com", "plan": "pilot", "unit_limit": 5}, headers=admin)
    assert created.status_code == 201
    temporary = created.json()["temporary_password"]
    login = client.post("/auth/login", data={"username": "grace@example.com", "password": temporary}).json()
    first = {"Authorization": "Bearer " + login["access_token"]}
    assert client.get("/setup/status", headers=first).json()["must_change_password"] is True
    # Nothing else works until the password is changed
    assert client.get("/properties", headers=first).status_code == 403
    changed = client.post("/setup/change-password", json={"current_password": temporary, "new_password": "My-Own-Pass-42"}, headers=first)
    assert changed.status_code == 200
    fresh = {"Authorization": "Bearer " + changed.json()["access_token"]}
    assert client.get("/properties", headers=fresh).status_code == 200
    assert client.get("/setup/status", headers=fresh).json()["must_change_password"] is False
    # The temporary password no longer works, and the same email cannot be added twice
    assert client.post("/auth/login", data={"username": "grace@example.com", "password": temporary}).status_code == 401
    again = client.post("/admin/accounts", json={"full_name": "Grace Again", "email": "grace@example.com"}, headers=admin)
    assert again.status_code == 400


def test_a_suspended_business_is_shut_out_and_can_come_back(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    suspended = client.put(f"/admin/accounts/{owner_id}", json={"status": "suspended", "status_note": "Please contact support about your payment."}, headers=admin)
    assert suspended.status_code == 200 and suspended.json()["state"] == "suspended"
    # Existing sessions stop working, for the landlord, their caretaker, and their tenant
    for headers in (owner, john, tenant):
        assert client.get("/auth/me", headers=headers).status_code == 403
    # New sign-ins are refused with the message
    for username, password in [("owner@example.com", PASSWORD), ("john@example.com", PASSWORD), ("0711 000 111", "My-Own-Pass-42")]:
        reply = client.post("/auth/login", data={"username": username, "password": password})
        assert reply.status_code == 403, username
        assert "contact support" in reply.json()["detail"]
    # Reactivating brings everything back
    assert client.put(f"/admin/accounts/{owner_id}", json={"status": "active"}, headers=admin).json()["state"] == "active"
    assert client.get("/properties", headers=owner).status_code == 200
    assert client.get("/portal/home", headers=tenant).status_code == 200


def test_a_read_only_business_can_look_but_not_change(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    client.put(f"/admin/accounts/{owner_id}", json={"status": "read_only", "status_note": "Payment overdue."}, headers=admin)
    assert client.get("/properties", headers=owner).status_code == 200
    blocked = client.post("/properties", json={"name": "New place"}, headers=owner)
    assert blocked.status_code == 403 and "look at everything" in blocked.json()["detail"]
    # Their tenants can look, but not report problems
    assert client.get("/portal/home", headers=tenant).status_code == 200
    assert client.post("/portal/repairs", json={"title": "Leaking tap"}, headers=tenant).status_code == 403
    # But everyone can still change their own password
    assert client.post("/account/change-password", json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-5"}, headers=owner).status_code == 204


def test_access_ends_by_itself_after_the_grace_days(client):
    owner = make_owner(client)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    today = date.today()
    # Ended 30 days ago: read-only
    client.put(f"/admin/accounts/{owner_id}", json={"plan": "paid", "paid_until": (today - timedelta(days=30)).isoformat()}, headers=admin)
    assert client.get("/admin/accounts", headers=admin).json()[0]["state"] == "read_only"
    assert client.post("/properties", json={"name": "Blocked"}, headers=owner).status_code == 403
    # Ended 3 days ago: still inside the grace days
    client.put(f"/admin/accounts/{owner_id}", json={"paid_until": (today - timedelta(days=3)).isoformat()}, headers=admin)
    assert client.post("/properties", json={"name": "Allowed"}, headers=owner).status_code == 201


def test_a_payment_extends_access_and_is_recorded(client):
    owner = make_owner(client)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    today = date.today()
    client.put(f"/admin/accounts/{owner_id}", json={"plan": "paid", "paid_until": (today - timedelta(days=30)).isoformat()}, headers=admin)
    assert client.post("/properties", json={"name": "Blocked"}, headers=owner).status_code == 403
    payment = client.post(f"/admin/accounts/{owner_id}/payments", json={"amount": 3000, "months": 3, "method": "mpesa", "reference": "sjk4l2m9qp"}, headers=admin)
    assert payment.status_code == 201
    assert payment.json()["covers_until"] == add_months(today, 3).isoformat()
    assert payment.json()["reference"] == "SJK4L2M9QP"
    # Access is back, and the same reference cannot be used twice
    assert client.post("/properties", json={"name": "Allowed"}, headers=owner).status_code == 201
    again = client.post(f"/admin/accounts/{owner_id}/payments", json={"amount": 3000, "months": 3, "reference": "SJK4L2M9QP"}, headers=admin)
    assert again.status_code == 400
    # A payment made in the future is refused
    future = (today + timedelta(days=2)).isoformat()
    assert client.post(f"/admin/accounts/{owner_id}/payments", json={"amount": 100, "months": 1, "paid_on": future}, headers=admin).status_code == 400
    # The totals add up
    overview = client.get("/admin/overview", headers=admin).json()
    assert overview["revenue_this_month"] == 3000 and overview["revenue_total"] == 3000
    assert len(client.get(f"/admin/accounts/{owner_id}/payments", headers=admin).json()) == 1
    assert len(client.get("/admin/payments", headers=admin).json()) == 1


def test_the_unit_limit_stops_new_units(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    client.put(f"/admin/accounts/{owner_id}", json={"unit_limit": 1}, headers=admin)
    blocked = client.post(f"/properties/{business['property_id']}/units", json={"unit_number": "A2", "rent_amount": 5000, "deposit_amount": 0}, headers=owner)
    assert blocked.status_code == 403 and "plan allows 1 units" in blocked.json()["detail"]
    client.put(f"/admin/accounts/{owner_id}", json={"unit_limit": 5}, headers=admin)
    allowed = client.post(f"/properties/{business['property_id']}/units", json={"unit_number": "A2", "rent_amount": 5000, "deposit_amount": 0}, headers=owner)
    assert allowed.status_code == 201


def test_a_new_password_and_signing_out_end_old_sessions(client):
    owner = make_owner(client)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    # Sign out everywhere
    assert client.post(f"/admin/accounts/{owner_id}/sign-out", headers=admin).status_code == 204
    assert client.get("/properties", headers=owner).status_code == 401
    # A new password: the old one stops working, and the new one must be changed
    owner = {"Authorization": "Bearer " + client.post("/auth/login", data={"username": "owner@example.com", "password": PASSWORD}).json()["access_token"]}
    reset = client.post(f"/admin/accounts/{owner_id}/reset-password", headers=admin)
    assert reset.status_code == 200
    assert client.get("/properties", headers=owner).status_code == 401
    assert client.post("/auth/login", data={"username": "owner@example.com", "password": PASSWORD}).status_code == 401
    login = client.post("/auth/login", data={"username": "owner@example.com", "password": reset.json()["temporary_password"]})
    assert login.status_code == 200
    first = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/setup/status", headers=first).json()["must_change_password"] is True


def test_the_admin_can_reset_a_landlords_two_step_login(client):
    turn_on_two_step(client, "owner@example.com")
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    assert client.post("/auth/login", data={"username": "owner@example.com", "password": PASSWORD}).json()["requires_otp"] is True
    assert client.post(f"/admin/accounts/{owner_id}/reset-2fa", headers=admin).status_code == 204
    again = client.post("/auth/login", data={"username": "owner@example.com", "password": PASSWORD}).json()
    assert again["requires_otp"] is False and again["access_token"]


def test_what_the_admin_does_is_logged(client):
    make_owner(client)
    admin = admin_ready(client)
    owner_id = owner_id_for(client, admin, "owner@example.com")
    client.put(f"/admin/accounts/{owner_id}", json={"status": "suspended"}, headers=admin)
    events = client.get("/admin/events", headers=admin).json()
    assert any(event["action"] == "Changed an account" and "suspended" in event["detail"] for event in events)


def test_the_admin_can_only_manage_landlords(client):
    admin = admin_ready(client)
    # Nobody with the admin's own number, or a number that does not exist, can be changed
    assert client.put("/admin/accounts/1", json={"status": "suspended"}, headers=admin).status_code == 404
    assert client.put("/admin/accounts/9999", json={"status": "suspended"}, headers=admin).status_code == 404
    assert client.post("/admin/accounts/9999/reset-password", headers=admin).status_code == 404