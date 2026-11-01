# Import the tools we need
from pathlib import Path

# Import our own files
import legal_models
from admin_models import OwnerAccount
from database import SessionLocal

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner
from test_portal import sign_in_tenant


# The versions the website is showing
def accept_body():
    return {"agree": True, "terms_version": legal_models.TERMS_VERSION, "privacy_version": legal_models.PRIVACY_VERSION}


def test_nothing_is_required_until_enforcement_is_switched_on(client):
    owner = make_owner(client)
    status = client.get("/legal/status", headers=owner).json()
    assert status["required"] is False and status["accepted"] is False
    assert client.get("/properties", headers=owner).status_code == 200


def test_a_landlord_must_accept_before_using_anything_else(client, monkeypatch):
    owner = make_owner(client)
    monkeypatch.setenv("TERMS_ENFORCED", "true")
    blocked = client.get("/properties", headers=owner)
    assert blocked.status_code == 403 and "Terms and Privacy Policy" in blocked.json()["detail"]
    # The few things needed to accept still work
    assert client.get("/auth/me", headers=owner).status_code == 200
    assert client.get("/legal/status", headers=owner).json()["required"] is True
    assert client.get("/setup/status", headers=owner).status_code == 200
    # Not ticking the box, and text they did not see, are refused
    assert client.post("/legal/accept", json={**accept_body(), "agree": False}, headers=owner).status_code == 400
    assert client.post("/legal/accept", json={**accept_body(), "terms_version": "1999-01-01"}, headers=owner).status_code == 409
    assert client.get("/properties", headers=owner).status_code == 403
    # Accepting opens everything, and is only recorded once
    done = client.post("/legal/accept", json=accept_body(), headers=owner)
    assert done.status_code == 200 and done.json()["accepted"] is True and done.json()["accepted_at"]
    assert client.post("/legal/accept", json=accept_body(), headers=owner).status_code == 200
    assert client.get("/properties", headers=owner).status_code == 200
    with SessionLocal() as db:
        assert db.query(legal_models.TermsAcceptance).count() == 1


def test_a_new_version_asks_everyone_again(client, monkeypatch):
    owner = make_owner(client)
    monkeypatch.setenv("TERMS_ENFORCED", "true")
    client.post("/legal/accept", json=accept_body(), headers=owner)
    assert client.get("/properties", headers=owner).status_code == 200
    # The text changes, so the version is bumped
    monkeypatch.setattr(legal_models, "PRIVACY_VERSION", "2099-01-01")
    assert client.get("/legal/status", headers=owner).json()["accepted"] is False
    assert client.get("/properties", headers=owner).status_code == 403
    again = {"agree": True, "terms_version": legal_models.TERMS_VERSION, "privacy_version": "2099-01-01"}
    assert client.post("/legal/accept", json=again, headers=owner).status_code == 200
    assert client.get("/properties", headers=owner).status_code == 200


def test_caretakers_and_tenants_are_not_asked(client, monkeypatch):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    monkeypatch.setenv("TERMS_ENFORCED", "true")
    assert client.get("/work/properties", headers=john).status_code == 200
    assert client.get("/portal/home", headers=tenant).status_code == 200
    assert client.get("/legal/status", headers=john).json() == {
        "required": False,
        "accepted": True,
        "terms_version": legal_models.TERMS_VERSION,
        "privacy_version": legal_models.PRIVACY_VERSION,
        "accepted_at": None,
    }
    # Only landlords can accept
    assert client.post("/legal/accept", json=accept_body(), headers=john).status_code == 403
    # The tenant cannot reach the landlord's legal pages at all
    assert client.get("/legal/status", headers=tenant).status_code == 403


def test_a_read_only_landlord_can_still_accept(client, monkeypatch):
    owner = make_owner(client)
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        db.add(OwnerAccount(owner_id=owner_id, plan="paid", status="read_only"))
        db.commit()
    monkeypatch.setenv("TERMS_ENFORCED", "true")
    assert client.post("/legal/accept", json=accept_body(), headers=owner).status_code == 200


def test_the_acceptance_is_in_the_activity_log(client):
    owner = make_owner(client)
    client.post("/legal/accept", json=accept_body(), headers=owner)
    summaries = [item["summary"] for item in client.get("/account/activity", headers=owner).json()["items"]]
    assert "Accepted the Terms and Privacy Policy" in summaries


def test_the_versions_in_the_website_match_the_server():
    # The text lives in the website, so both places must agree on the version
    config = Path(__file__).resolve().parents[2] / "frontend" / "src" / "legal" / "legalConfig.js"
    text = config.read_text()
    assert f"termsVersion: '{legal_models.TERMS_VERSION}'" in text
    assert f"privacyVersion: '{legal_models.PRIVACY_VERSION}'" in text