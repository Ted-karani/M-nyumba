# Import the tools we need
import pytest

# Import our test helpers
from helpers import make_business, make_owner

# The M-Pesa code used in the tests
CODE = "SJK4L2M9QP"


# A pretend Safaricom: it keeps what we sent, and answers the "what happened?" question however a test says
class FakeSafaricom:
    def __init__(self):
        self.calls = []
        # By default the payment is still being processed
        self.query_answer = {"errorCode": "500.001.1001", "errorMessage": "The transaction is being processed"}

    def post(self, path, body):
        self.calls.append((path, body))
        if path.endswith("/stkpush/v1/processrequest"):
            return {"ResponseCode": "0", "MerchantRequestID": "m-1", "CheckoutRequestID": f"ws_CO_{len(self.calls)}"}
        return self.query_answer


# Switch on the M-Pesa settings for a test, and put the pretend Safaricom in place
@pytest.fixture
def safaricom(monkeypatch):
    from routers import mpesa

    monkeypatch.setattr(mpesa, "CONSUMER_KEY", "key")
    monkeypatch.setattr(mpesa, "CONSUMER_SECRET", "secret")
    monkeypatch.setattr(mpesa, "SHORTCODE", "174379")
    monkeypatch.setattr(mpesa, "PASSKEY", "passkey")
    monkeypatch.setattr(mpesa, "CALLBACK_URL", "https://example.com/payments/callback")
    monkeypatch.setattr(mpesa, "CALLBACK_SECRET", "secret-123")
    monkeypatch.setattr(mpesa, "ALLOWED_OWNERS", {"owner@example.com"})
    monkeypatch.setattr(mpesa, "TRUST_CALLBACK", False)
    monkeypatch.setattr(mpesa, "MIN_POLL_AGE_SECONDS", 0)
    fake = FakeSafaricom()
    monkeypatch.setattr(mpesa, "safaricom_post", fake.post)
    return fake


# Send a prompt, and return Safaricom's id for it
def send_prompt(client, owner, lease_id, amount=1500):
    response = client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": amount}, headers=owner)
    assert response.status_code == 200, response.text
    return response.json()["checkout_request_id"]


# What Safaricom's callback looks like (the amount is deliberately wrong, to prove it is never trusted)
def callback_body(checkout_id, code=0, receipt=CODE, claimed_amount=99999):
    result = {"MerchantRequestID": "m-1", "CheckoutRequestID": checkout_id, "ResultCode": code, "ResultDesc": "done"}
    if code == 0:
        result["CallbackMetadata"] = {"Item": [
            {"Name": "Amount", "Value": claimed_amount},
            {"Name": "MpesaReceiptNumber", "Value": receipt},
        ]}
    return {"Body": {"stkCallback": result}}


# The payments on a lease
def payments_of(client, owner, lease_id):
    return client.get(f"/leases/{lease_id}/payments", headers=owner).json()


def test_only_switched_on_owners_can_send_prompts(client, safaricom, monkeypatch):
    from routers import mpesa

    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    monkeypatch.setattr(mpesa, "ALLOWED_OWNERS", set())
    assert client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 100}, headers=owner).status_code == 403


def test_the_prompt_uses_the_unit_number_and_a_clean_phone(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    reply = client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 1500, "phone": "0712 345 678"}, headers=owner)
    assert reply.status_code == 200
    path, body = safaricom.calls[-1]
    assert path.endswith("/stkpush/v1/processrequest")
    assert body["PhoneNumber"] == "254712345678"
    assert body["AccountReference"] == "A1"
    assert body["Amount"] == 1500
    assert body["CallBackURL"].endswith("/secret-123")


def test_bad_prompts_are_refused(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    assert client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 0}, headers=owner).status_code == 400
    assert client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 300000}, headers=owner).status_code == 400
    assert client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 100, "phone": "12345"}, headers=owner).status_code == 400


def test_nobody_can_prompt_for_someone_elses_lease(client, safaricom, monkeypatch):
    from routers import mpesa

    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    other = make_owner(client, "other@example.com")
    monkeypatch.setattr(mpesa, "ALLOWED_OWNERS", {"owner@example.com", "other@example.com"})
    assert client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 100}, headers=other).status_code == 404


def test_a_callback_with_the_wrong_secret_is_refused(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    checkout_id = send_prompt(client, owner, lease_id)
    assert client.post("/payments/callback/wrong-secret", json=callback_body(checkout_id)).status_code == 404
    assert payments_of(client, owner, lease_id) == []


def test_a_forged_callback_does_not_record_a_payment(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    checkout_id = send_prompt(client, owner, lease_id)
    # The message claims success, but Safaricom says it is still being processed
    reply = client.post("/payments/callback/secret-123", json=callback_body(checkout_id))
    assert reply.status_code == 200
    assert payments_of(client, owner, lease_id) == []
    assert client.get(f"/mpesa/status/{checkout_id}", headers=owner).json()["status"] == "pending"


def test_a_confirmed_payment_is_recorded_once_for_the_amount_asked(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    checkout_id = send_prompt(client, owner, lease_id, amount=1500)
    safaricom.query_answer = {"ResponseCode": "0", "ResultCode": "0", "ResultDesc": "ok"}
    for _ in range(2):
        assert client.post("/payments/callback/secret-123", json=callback_body(checkout_id)).status_code == 200
    payments = payments_of(client, owner, lease_id)
    # One payment, for the 1500 we asked for (not the 99999 the message claimed)
    assert len(payments) == 1
    assert payments[0]["amount"] == 1500 and payments[0]["reference"] == CODE
    status = client.get(f"/mpesa/status/{checkout_id}", headers=owner).json()
    assert status["status"] == "paid" and status["receipt"] == CODE


def test_a_cancelled_prompt_records_nothing(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    checkout_id = send_prompt(client, owner, lease_id)
    safaricom.query_answer = {"ResponseCode": "0", "ResultCode": "1032", "ResultDesc": "Request cancelled by user"}
    client.post("/payments/callback/secret-123", json=callback_body(checkout_id, code=1032))
    assert client.get(f"/mpesa/status/{checkout_id}", headers=owner).json()["status"] == "cancelled"
    assert payments_of(client, owner, lease_id) == []


def test_a_lost_callback_is_found_by_asking_safaricom(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    checkout_id = send_prompt(client, owner, lease_id, amount=2000)
    # No callback ever arrives, but Safaricom says it was paid
    safaricom.query_answer = {"ResponseCode": "0", "ResultCode": "0", "ResultDesc": "ok"}
    assert client.get(f"/mpesa/status/{checkout_id}", headers=owner).json()["status"] == "paid"
    payments = payments_of(client, owner, lease_id)
    assert len(payments) == 1 and payments[0]["amount"] == 2000 and payments[0]["reference"] is None
    # The callback arrives late: it adds the M-Pesa code, and does not record the payment again
    client.post("/payments/callback/secret-123", json=callback_body(checkout_id))
    payments = payments_of(client, owner, lease_id)
    assert len(payments) == 1 and payments[0]["reference"] == CODE


def test_the_status_of_a_request_is_private(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    checkout_id = send_prompt(client, owner, lease_id)
    other = make_owner(client, "other@example.com")
    assert client.get(f"/mpesa/status/{checkout_id}", headers=other).status_code == 404
    assert client.get("/mpesa/status/not-a-real-id", headers=owner).status_code == 404


def test_a_tenant_cannot_be_flooded_with_prompts(client, safaricom):
    owner = make_owner(client)
    lease_id = make_business(client, owner)["lease"]["id"]
    for _ in range(3):
        send_prompt(client, owner, lease_id)
    assert client.post("/mpesa/stk-push", json={"lease_id": lease_id, "amount": 100}, headers=owner).status_code == 429