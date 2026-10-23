# Import our test helpers
from helpers import make_business, make_owner, make_tenant, make_unit, move_in, pay
# Reuse the pretend Safaricom and helpers from the other M-Pesa tests
from test_mpesa import CODE, callback_body, payments_of, safaricom  # noqa: F401
# Reuse the tenant sign-in helper
from test_portal import sign_in_tenant


def test_a_tenant_can_ask_for_a_prompt_for_what_they_owe(client, safaricom):
    owner = make_owner(client)
    # The tenant owes 16000 (deposit plus first rent)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    assert client.get("/portal/mpesa/enabled", headers=tenant).json()["enabled"] is True
    reply = client.post("/portal/mpesa/pay", json={"amount": 5000}, headers=tenant)
    assert reply.status_code == 200, reply.text
    path, body = safaricom.calls[-1]
    # The prompt goes to the tenant's OWN phone, for the unit's account number
    assert body["PhoneNumber"] == "254711000111"
    assert body["AccountReference"] == "A1"
    assert body["Amount"] == 5000


def test_a_tenant_cannot_pay_more_than_they_owe_or_nothing(client, safaricom):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    assert client.post("/portal/mpesa/pay", json={"amount": 0}, headers=tenant).status_code == 400
    assert client.post("/portal/mpesa/pay", json={"amount": 16001}, headers=tenant).status_code == 400
    # A phone number sent by the tenant is ignored (it is not even accepted)
    reply = client.post("/portal/mpesa/pay", json={"amount": 100, "phone": "0799000000"}, headers=tenant)
    assert reply.status_code == 200
    assert safaricom.calls[-1][1]["PhoneNumber"] == "254711000111"


def test_nothing_owed_means_nothing_to_pay(client, safaricom):
    owner = make_owner(client)
    business = make_business(client, owner)
    pay(client, owner, business["lease"]["id"], 16000)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    assert client.post("/portal/mpesa/pay", json={"amount": 100}, headers=tenant).status_code == 400


def test_a_paid_prompt_lowers_the_tenants_balance(client, safaricom):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    checkout_id = client.post("/portal/mpesa/pay", json={"amount": 5000}, headers=tenant).json()["checkout_request_id"]
    # Still waiting
    assert client.get(f"/portal/mpesa/status/{checkout_id}", headers=tenant).json()["status"] == "pending"
    # Safaricom confirms it
    safaricom.query_answer = {"ResponseCode": "0", "ResultCode": "0", "ResultDesc": "ok"}
    assert client.get(f"/portal/mpesa/status/{checkout_id}", headers=tenant).json()["status"] == "paid"
    assert client.get("/portal/home", headers=tenant).json()["tenancies"][0]["balance"] == 11000
    assert len(payments_of(client, owner, business["lease"]["id"])) == 1


def test_only_one_prompt_can_wait_at_a_time(client, safaricom):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    assert client.post("/portal/mpesa/pay", json={"amount": 1000}, headers=tenant).status_code == 200
    assert client.post("/portal/mpesa/pay", json={"amount": 1000}, headers=tenant).status_code == 409


def test_a_tenant_cannot_see_another_tenants_request(client, safaricom):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    checkout_id = client.post("/portal/mpesa/pay", json={"amount": 1000}, headers=tenant).json()["checkout_request_id"]
    # A second tenant in another unit
    second_unit = make_unit(client, owner, business["property_id"], "B1", rent=9000, deposit=0)
    second_tenant = make_tenant(client, owner, name="Joseph Kamau", phone="0722 111 222")
    move_in(client, owner, second_unit, second_tenant)
    other = sign_in_tenant(client, owner, second_tenant, phone="0722 111 222")
    assert client.get(f"/portal/mpesa/status/{checkout_id}", headers=other).status_code == 404


def test_pay_now_is_off_when_the_landlord_is_not_switched_on(client, safaricom, monkeypatch):
    from routers import mpesa

    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    monkeypatch.setattr(mpesa, "ALLOWED_OWNERS", set())
    assert client.get("/portal/mpesa/enabled", headers=tenant).json()["enabled"] is False
    assert client.post("/portal/mpesa/pay", json={"amount": 100}, headers=tenant).status_code == 403


def test_owners_and_tenants_use_their_own_routes(client, safaricom):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    # A tenant cannot use the owner's prompt route
    assert client.post("/mpesa/stk-push", json={"lease_id": business["lease"]["id"], "amount": 100}, headers=tenant).status_code == 403
    assert client.get("/mpesa/enabled", headers=tenant).status_code == 403
    # An owner cannot use the tenant's routes
    assert client.post("/portal/mpesa/pay", json={"amount": 100}, headers=owner).status_code == 403
    # The owner's button is on for the allowed owner, and off for anyone else
    assert client.get("/mpesa/enabled", headers=owner).json()["enabled"] is True
    other = make_owner(client, "other@example.com")
    assert client.get("/mpesa/enabled", headers=other).json()["enabled"] is False