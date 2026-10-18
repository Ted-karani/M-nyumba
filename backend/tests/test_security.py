# Import the date tools
from datetime import datetime, timezone

# Import the tools for authenticator codes and for looking at the raw database
import pyotp
import pytest
from sqlalchemy import text

# Import our test helpers
from database import SessionLocal
from helpers import PASSWORD, make_business, make_caretaker, make_owner, make_tenant, register, sign_in


# Try to sign in (the caller checks the answer)
def attempt(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_five_wrong_passwords_lock_the_email(client):
    register(client, "lock@example.com")
    for _ in range(5):
        assert attempt(client, "lock@example.com", "wrong-pass-1").status_code == 401
    # Now even the right password is refused for a while
    locked = attempt(client, "lock@example.com", PASSWORD)
    assert locked.status_code == 429
    assert "Too many failed attempts" in locked.json()["detail"]
    assert "retry-after" in locked.headers


def test_an_email_that_does_not_exist_is_locked_the_same_way(client):
    for _ in range(5):
        assert attempt(client, "ghost@example.com", "wrong-pass-1").status_code == 401
    assert attempt(client, "ghost@example.com", "wrong-pass-1").status_code == 429


def test_a_good_sign_in_clears_the_earlier_mistakes(client):
    register(client, "clear@example.com")
    for _ in range(4):
        assert attempt(client, "clear@example.com", "wrong-pass-1").status_code == 401
    assert attempt(client, "clear@example.com", PASSWORD).status_code == 200
    # Four more mistakes still do not lock it
    for _ in range(4):
        assert attempt(client, "clear@example.com", "wrong-pass-1").status_code == 401


def test_changing_the_password_signs_out_old_sessions(client):
    register(client, "pw@example.com")
    old = sign_in(client, "pw@example.com")
    change = client.post("/account/change-password", json={"current_password": PASSWORD, "new_password": "Brand-New-Pass-5"}, headers=old)
    assert change.status_code == 204
    assert client.get("/auth/me", headers=old).status_code == 401
    assert attempt(client, "pw@example.com", PASSWORD).status_code == 401
    assert client.get("/auth/me", headers=sign_in(client, "pw@example.com", "Brand-New-Pass-5")).status_code == 200


@pytest.mark.parametrize("weak", ["password123", "12345678", "pw@example.com"])
def test_weak_new_passwords_are_refused(client, weak):
    register(client, "pw@example.com")
    headers = sign_in(client, "pw@example.com")
    response = client.post("/account/change-password", json={"current_password": PASSWORD, "new_password": weak}, headers=headers)
    assert response.status_code == 400


def test_the_wrong_current_password_is_refused(client):
    register(client, "pw@example.com")
    headers = sign_in(client, "pw@example.com")
    response = client.post("/account/change-password", json={"current_password": "not-my-password-1", "new_password": "Brand-New-Pass-5"}, headers=headers)
    assert response.status_code == 400


def test_sign_up_can_be_closed(client, monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "false")
    response = client.post("/auth/register", json={"full_name": "Stranger", "email": "stranger@example.com", "password": PASSWORD})
    assert response.status_code == 403


def test_easy_passwords_are_refused_at_sign_up(client):
    response = client.post("/auth/register", json={"full_name": "Easy One", "email": "easy@example.com", "password": "password123"})
    assert response.status_code == 400


def test_id_numbers_are_scrambled_in_the_database(client):
    owner = make_owner(client)
    tenant_id = make_tenant(client, owner, id_number="12345678")
    # The app shows it normally
    assert client.get(f"/tenants/{tenant_id}", headers=owner).json()["id_number"] == "12345678"
    # But the database holds only the scrambled version
    with SessionLocal() as db:
        raw = db.execute(text("SELECT id_number FROM tenants WHERE id = :id"), {"id": tenant_id}).scalar()
    assert raw.startswith("enc1:")
    assert "12345678" not in raw


# Turn on 2-step login for a new account, and return the app's code maker and the recovery codes
def turn_on_two_step(client, email):
    register(client, email)
    headers = sign_in(client, email)
    secret = client.post("/account/2fa/setup", headers=headers).json()["secret"]
    totp = pyotp.TOTP(secret)
    enabled = client.post("/account/2fa/enable", json={"code": totp.now()}, headers=headers)
    assert enabled.status_code == 200, enabled.text
    return headers, totp, enabled.json()["recovery_codes"]


# Do step one of signing in, and return the short-lived pass
def start_login(client, email):
    result = attempt(client, email, PASSWORD).json()
    assert result["requires_otp"] is True
    return result["challenge"]


def test_two_step_login_asks_for_a_code(client):
    register(client, "tf@example.com")
    headers = sign_in(client, "tf@example.com")
    secret = client.post("/account/2fa/setup", headers=headers).json()["secret"]
    totp = pyotp.TOTP(secret)
    # A wrong code does not turn it on
    assert client.post("/account/2fa/enable", json={"code": "000000"}, headers=headers).status_code == 400
    # The right code turns it on, and gives 8 recovery codes
    first_code = totp.now()
    enabled = client.post("/account/2fa/enable", json={"code": first_code}, headers=headers)
    assert enabled.status_code == 200
    assert len(enabled.json()["recovery_codes"]) == 8
    # Now signing in asks for a code instead of giving a token
    login = attempt(client, "tf@example.com", PASSWORD).json()
    assert login["requires_otp"] is True and login["access_token"] is None
    challenge = login["challenge"]
    # The short-lived pass is not a login token
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + challenge}).status_code == 401
    # A wrong code is refused, and so is a code that was already used
    assert client.post("/auth/login/verify", json={"challenge": challenge, "code": "000000"}).status_code == 401
    assert client.post("/auth/login/verify", json={"challenge": challenge, "code": first_code}).status_code == 401
    # The next code works, and the token it gives is a real login
    next_code = totp.at(datetime.now(timezone.utc), counter_offset=1)
    good = client.post("/auth/login/verify", json={"challenge": challenge, "code": next_code})
    assert good.status_code == 200
    token = good.json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 200


def test_a_recovery_code_works_only_once(client):
    _, _, codes = turn_on_two_step(client, "rc@example.com")
    first = client.post("/auth/login/verify", json={"challenge": start_login(client, "rc@example.com"), "code": codes[0]})
    assert first.status_code == 200
    second = client.post("/auth/login/verify", json={"challenge": start_login(client, "rc@example.com"), "code": codes[0]})
    assert second.status_code == 401


def test_two_step_login_can_be_turned_off_with_password_and_code(client):
    headers, _, codes = turn_on_two_step(client, "off@example.com")
    # A wrong password does not turn it off
    wrong = client.post("/account/2fa/disable", json={"password": "wrong-pass-9", "code": codes[0]}, headers=headers)
    assert wrong.status_code == 400
    # The right password and a recovery code do
    off = client.post("/account/2fa/disable", json={"password": PASSWORD, "code": codes[0]}, headers=headers)
    assert off.status_code == 204
    plain = attempt(client, "off@example.com", PASSWORD).json()
    assert plain["requires_otp"] is False and plain["access_token"]


def test_documents_refuse_fake_files_and_stay_private(client, tmp_path, monkeypatch):
    from routers import documents, inspections

    # Keep the test files in a throwaway folder
    monkeypatch.setattr(documents, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(inspections, "UPLOAD_DIR", tmp_path)
    owner_a = make_owner(client, "a@example.com")
    owner_b = make_owner(client, "b@example.com")
    details = {"title": "Test", "kind": "other"}
    # A text file pretending to be a picture
    fake = client.post("/documents", data=details, files={"file": ("fake.jpg", b"this is not a picture", "image/jpeg")}, headers=owner_a)
    assert fake.status_code == 400
    # A program
    program = client.post("/documents", data=details, files={"file": ("run.exe", b"MZ program", "application/octet-stream")}, headers=owner_a)
    assert program.status_code == 400
    # A file over 10 MB
    big = client.post("/documents", data=details, files={"file": ("big.pdf", b"%PDF" + b"0" * (10 * 1024 * 1024), "application/pdf")}, headers=owner_a)
    assert big.status_code == 413
    # A real PDF is accepted
    good = client.post("/documents", data=details, files={"file": ("deed.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=owner_a)
    assert good.status_code == 201
    document_id = good.json()["id"]
    # Only its owner can open it, and not without signing in
    assert client.get(f"/documents/{document_id}/file", headers=owner_a).status_code == 200
    assert client.get(f"/documents/{document_id}/file", headers=owner_b).status_code == 404
    assert client.get(f"/documents/{document_id}/file").status_code == 401
    # It is stored under a random name, not "deed.pdf"
    names = [path.name for path in tmp_path.iterdir()]
    assert len(names) == 1 and names[0] != "deed.pdf"


def test_changes_are_logged_with_the_persons_name(client):
    owner = make_owner(client)
    mine = make_business(client, owner)
    _, john = make_caretaker(client, owner, [mine["property_id"]])
    client.post("/maintenance", json={"property_id": mine["property_id"], "title": "Cracked tile"}, headers=john)
    # Just looking at a page is not a change
    client.get("/properties", headers=owner)
    log = client.get("/account/activity", headers=owner).json()
    entries = [(item["actor_name"], item["summary"]) for item in log["items"]]
    assert ("John Mutua", "Reported a repair") in entries
    assert ("Owner One", "Added a property") in entries
    assert not any(summary.startswith("GET") for _, summary in entries)
    # Another owner never sees them
    other = make_owner(client, "other@example.com")
    other_names = [item["actor_name"] for item in client.get("/account/activity", headers=other).json()["items"]]
    assert "John Mutua" not in other_names