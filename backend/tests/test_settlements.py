# Import the tools we need
from datetime import date, timedelta

# Import our own files
import models
import settlement_rules as rules
from database import SessionLocal

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner
from test_admin import admin_ready
from test_portal import sign_in_tenant


# ---------- the rules on their own ----------

def charge(number, kind, amount, days_ago, description=None):
    return {"id": number, "charge_type": kind, "amount": amount, "due_date": date.today() - timedelta(days=days_ago), "description": description}


def payment(number, amount, days_ago):
    return {"id": number, "amount": amount, "paid_on": date.today() - timedelta(days=days_ago)}


def test_a_paid_deposit_is_what_the_landlord_holds():
    result = rules.figures([charge(1, "deposit", 6000, 60), charge(2, "rent", 6000, 55)], [payment(1, 12000, 59)], 6000)
    assert result == {"deposit_charged": 6000, "deposit_held": 6000, "deposit_found_from": "paid", "unpaid_charges": 0, "credit": 0}


def test_a_part_paid_deposit_counts_only_what_was_paid():
    result = rules.figures([charge(1, "deposit", 6000, 60), charge(2, "rent", 6000, 55)], [payment(1, 4000, 59)], 6000)
    assert result["deposit_held"] == 4000 and result["unpaid_charges"] == 6000


def test_a_tenant_from_a_notebook_has_the_deposit_on_the_lease():
    result = rules.figures([charge(1, "rent", 6000, 10)], [payment(1, 2000, 5)], 6000)
    assert result["deposit_held"] == 6000 and result["deposit_found_from"] == "recorded" and result["unpaid_charges"] == 4000


def test_bills_and_old_balances_are_unpaid_charges_and_overpayment_is_credit():
    charges = [charge(1, "other", 3000, 40, "Balance brought forward"), charge(2, "rent", 6000, 30), charge(3, "water", 800, 20)]
    assert rules.figures(charges, [payment(1, 6000, 10)], 0)["unpaid_charges"] == 3800
    assert rules.figures([charge(1, "rent", 6000, 30)], [payment(1, 7000, 10)], 0)["credit"] == 1000


def test_the_outcome_is_a_refund_or_what_the_tenant_still_owes():
    assert rules.outcome(6000, 0, 0, []) == {"total_deductions": 0, "refund_due": 6000, "tenant_owes": 0}
    assert rules.outcome(6000, 0, 2000, [{"label": "Paint", "amount": 1500}]) == {"total_deductions": 1500, "refund_due": 2500, "tenant_owes": 0}
    assert rules.outcome(6000, 0, 8000, []) == {"total_deductions": 0, "refund_due": 0, "tenant_owes": 2000}
    assert rules.outcome(6000, 1000, 0, [{"label": "Damage", "amount": 7000}]) == {"total_deductions": 7000, "refund_due": 0, "tenant_owes": 0}


# ---------- the pages ----------

# A tenant who has moved out. The deposit and the rent are charged, and paid as you say
def ended_lease(client, owner, deposit_paid=6000, rent_paid=6000, imported=False, unit_number="A1", phone="254711000001", status="ended"):
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    start = date.today() - timedelta(days=60)
    with SessionLocal() as db:
        prop = db.query(models.Property).filter(models.Property.owner_id == owner_id, models.Property.name == "Block A").first()
        if prop is None:
            prop = models.Property(owner_id=owner_id, name="Block A")
            db.add(prop)
            db.flush()
        unit = models.Unit(property_id=prop.id, unit_number=unit_number, unit_type="Bedsitter", rent_amount=6000, deposit_amount=6000, status="vacant")
        tenant = models.Tenant(owner_id=owner_id, full_name=f"Tenant {unit_number}", phone=phone)
        db.add_all([unit, tenant])
        db.flush()
        lease = models.Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=start, end_date=date.today() - timedelta(days=2), rent_amount=6000, deposit_amount=6000, status=status)
        db.add(lease)
        db.flush()
        if not imported:
            db.add(models.Charge(lease_id=lease.id, charge_type="deposit", amount=6000, period=None, due_date=start, description="Deposit"))
        db.add(models.Charge(lease_id=lease.id, charge_type="rent", amount=6000, period="2026-01", due_date=start + timedelta(days=4), description="Rent"))
        if deposit_paid:
            db.add(models.Payment(lease_id=lease.id, amount=deposit_paid, paid_on=start + timedelta(days=1), method="cash"))
        if rent_paid:
            db.add(models.Payment(lease_id=lease.id, amount=rent_paid, paid_on=start + timedelta(days=6), method="cash"))
        db.commit()
        return lease.id


def body(held=6000, deductions=None, notes=None):
    return {"deposit_held": held, "deductions": deductions if deductions is not None else [], "notes": notes}


PAINT = {"label": "Repainting", "amount": 1500}
CLEAN = {"label": "Cleaning", "amount": 500}


def detail(client, owner, lease_id):
    return client.get(f"/settlements/lease/{lease_id}", headers=owner).json()


def test_only_tenants_who_moved_out_can_be_settled(client):
    owner = make_owner(client)
    active = ended_lease(client, owner, status="active", unit_number="A1", phone="254711000001")
    gone = ended_lease(client, owner, unit_number="A2", phone="254711000002")
    assert client.get(f"/settlements/lease/{active}", headers=owner).status_code == 400
    assert client.put(f"/settlements/lease/{active}", json=body(), headers=owner).status_code == 400
    assert client.post(f"/settlements/lease/{active}/finalize", json=body(), headers=owner).status_code == 400
    rows = client.get("/settlements", headers=owner).json()
    assert [row["lease_id"] for row in rows] == [gone] and rows[0]["state"] == "to_settle" and rows[0]["agreed_deposit"] == 6000


def test_the_page_starts_from_what_the_ledger_says(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner, rent_paid=0)
    data = detail(client, owner, lease)
    assert data["suggested"] == {"deposit_held": 6000, "found_from": "paid", "deposit_charged": 6000, "unpaid_charges": 6000, "credit": 0}
    assert data["settlement"] is None and data["state"] == "to_settle"
    assert data["lease"]["tenant_name"] == "Tenant A1" and data["lease"]["unit_number"] == "A1" and data["lease"]["property_name"] == "Block A"


def test_a_draft_is_saved_and_replaced(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    saved = client.put(f"/settlements/lease/{lease}", json=body(deductions=[PAINT, CLEAN], notes="Keys returned"), headers=owner)
    assert saved.status_code == 200
    settlement = saved.json()["settlement"]
    assert settlement["status"] == "draft" and settlement["total_deductions"] == 2000
    assert settlement["refund_due"] == 4000 and settlement["tenant_owes"] == 0 and settlement["notes"] == "Keys returned"
    assert [item["label"] for item in settlement["deductions"]] == ["Repainting", "Cleaning"]
    assert saved.json()["state"] == "draft"
    # Saving again replaces it: no second settlement
    again = client.put(f"/settlements/lease/{lease}", json=body(deductions=[CLEAN]), headers=owner).json()["settlement"]
    assert again["refund_due"] == 5500 and len(again["deductions"]) == 1
    assert len(client.get("/settlements", headers=owner).json()) == 1


def test_unpaid_rent_comes_off_the_deposit_and_can_leave_the_tenant_owing(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner, rent_paid=0)
    result = client.put(f"/settlements/lease/{lease}", json=body(), headers=owner).json()["settlement"]
    assert result["unpaid_charges"] == 6000 and result["refund_due"] == 0 and result["tenant_owes"] == 0
    result = client.put(f"/settlements/lease/{lease}", json=body(deductions=[PAINT]), headers=owner).json()["settlement"]
    assert result["refund_due"] == 0 and result["tenant_owes"] == 1500


def test_the_landlord_can_correct_the_deposit_held(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    result = client.put(f"/settlements/lease/{lease}", json=body(held=4000), headers=owner).json()["settlement"]
    assert result["deposit_held"] == 4000 and result["refund_due"] == 4000


def test_a_tenant_from_a_notebook_uses_the_deposit_on_the_lease(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner, imported=True, deposit_paid=0)
    data = detail(client, owner, lease)
    assert data["suggested"]["deposit_held"] == 6000 and data["suggested"]["found_from"] == "recorded" and data["suggested"]["unpaid_charges"] == 0


def test_a_final_settlement_is_frozen_until_it_is_reopened(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    final = client.post(f"/settlements/lease/{lease}/finalize", json=body(deductions=[PAINT]), headers=owner)
    assert final.status_code == 200 and final.json()["settlement"]["status"] == "final" and final.json()["settlement"]["finalized_at"]
    assert final.json()["settlement"]["refund_due"] == 4500
    # It cannot be edited or finalised again
    assert client.put(f"/settlements/lease/{lease}", json=body(), headers=owner).status_code == 400
    assert client.post(f"/settlements/lease/{lease}/finalize", json=body(), headers=owner).status_code == 400
    # Money that arrives afterwards does not change the signed numbers, but shows in what the ledger says now
    with SessionLocal() as db:
        db.add(models.Payment(lease_id=lease, amount=1000, paid_on=date.today(), method="cash"))
        db.commit()
    after = detail(client, owner, lease)
    assert after["settlement"]["refund_due"] == 4500 and after["suggested"]["credit"] == 1000
    # Reopening and finalising again uses the new figures
    assert client.post(f"/settlements/lease/{lease}/reopen", headers=owner).json()["settlement"]["status"] == "draft"
    final = client.post(f"/settlements/lease/{lease}/finalize", json=body(deductions=[PAINT]), headers=owner)
    assert final.json()["settlement"]["credit"] == 1000 and final.json()["settlement"]["refund_due"] == 5500
    assert client.post(f"/settlements/lease/{lease}/reopen", headers=owner).status_code == 200
    assert client.post(f"/settlements/lease/{lease}/reopen", headers=owner).status_code == 400


def test_the_refund_is_recorded_once_with_checks(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    refund = {"amount": 4500, "paid_on": date.today().isoformat(), "method": "mpesa", "reference": "SJK4L2M9QP"}
    # Not final yet
    assert client.post(f"/settlements/lease/{lease}/refund", json=refund, headers=owner).status_code == 400
    client.post(f"/settlements/lease/{lease}/finalize", json=body(deductions=[PAINT]), headers=owner)
    assert client.post(f"/settlements/lease/{lease}/refund", json={**refund, "amount": 4501}, headers=owner).status_code == 400
    assert client.post(f"/settlements/lease/{lease}/refund", json={**refund, "paid_on": "2999-01-01"}, headers=owner).status_code == 400
    assert client.post(f"/settlements/lease/{lease}/refund", json={**refund, "method": "cheque"}, headers=owner).status_code == 422
    assert client.post(f"/settlements/lease/{lease}/refund", json={**refund, "amount": 0}, headers=owner).status_code == 422
    assert detail(client, owner, lease)["state"] == "refund_pending"
    done = client.post(f"/settlements/lease/{lease}/refund", json=refund, headers=owner)
    assert done.status_code == 200 and done.json()["state"] == "refunded"
    assert done.json()["settlement"]["refund"]["reference"] == "SJK4L2M9QP" and done.json()["settlement"]["refund"]["amount"] == 4500
    # Only once, and it cannot be reopened while a refund is on record
    assert client.post(f"/settlements/lease/{lease}/refund", json=refund, headers=owner).status_code == 400
    assert client.post(f"/settlements/lease/{lease}/reopen", headers=owner).status_code == 400
    # Taking the record back
    assert client.delete(f"/settlements/lease/{lease}/refund", headers=owner).json()["state"] == "refund_pending"
    assert client.delete(f"/settlements/lease/{lease}/refund", headers=owner).status_code == 404
    # A smaller refund is a part refund
    part = client.post(f"/settlements/lease/{lease}/refund", json={**refund, "amount": 1000}, headers=owner)
    assert part.json()["state"] == "part_refunded"


def test_there_is_nothing_to_refund_when_the_tenant_owes(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner, rent_paid=0)
    final = client.post(f"/settlements/lease/{lease}/finalize", json=body(deductions=[PAINT]), headers=owner).json()
    assert final["state"] == "tenant_owes" and final["settlement"]["tenant_owes"] == 1500
    refund = {"amount": 100, "paid_on": date.today().isoformat(), "method": "cash"}
    assert client.post(f"/settlements/lease/{lease}/refund", json=refund, headers=owner).status_code == 400


def test_the_list_puts_what_needs_doing_first(client):
    owner = make_owner(client)
    pending = ended_lease(client, owner, unit_number="A1", phone="254711000001")
    unsettled = ended_lease(client, owner, unit_number="A2", phone="254711000002")
    refunded = ended_lease(client, owner, unit_number="A3", phone="254711000003")
    client.post(f"/settlements/lease/{pending}/finalize", json=body(), headers=owner)
    client.post(f"/settlements/lease/{refunded}/finalize", json=body(), headers=owner)
    client.post(f"/settlements/lease/{refunded}/refund", json={"amount": 6000, "paid_on": date.today().isoformat(), "method": "bank"}, headers=owner)
    rows = client.get("/settlements", headers=owner).json()
    assert [(row["lease_id"], row["state"]) for row in rows] == [(pending, "refund_pending"), (unsettled, "to_settle"), (refunded, "refunded")]
    assert rows[0]["refund_due"] == 6000


def test_bad_deductions_are_refused(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    url = f"/settlements/lease/{lease}"
    for bad in [
        body(deductions=[{"label": "", "amount": 100}]),
        body(deductions=[{"label": "   ", "amount": 100}]),
        body(deductions=[{"label": "Paint", "amount": 0}]),
        body(deductions=[{"label": "Paint", "amount": -5}]),
        body(deductions=[{"label": "Paint", "amount": 100}] * 21),
        body(held=-1),
        {"deposit_held": 100, "deductions": [], "notes": "x" * 301},
    ]:
        assert client.put(url, json=bad, headers=owner).status_code == 422
    assert client.get(url, headers=owner).json()["settlement"] is None


def test_each_landlord_only_sees_their_own_settlements(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    client.post(f"/settlements/lease/{lease}/finalize", json=body(), headers=owner)
    other = make_owner(client, "other@example.com")
    assert client.get("/settlements", headers=other).json() == []
    url = f"/settlements/lease/{lease}"
    assert client.get(url, headers=other).status_code == 404
    assert client.put(url, json=body(), headers=other).status_code == 404
    assert client.post(f"{url}/finalize", json=body(), headers=other).status_code == 404
    assert client.post(f"{url}/reopen", headers=other).status_code == 404
    refund = {"amount": 100, "paid_on": date.today().isoformat(), "method": "cash"}
    assert client.post(f"{url}/refund", json=refund, headers=other).status_code == 404
    assert client.delete(f"{url}/refund", headers=other).status_code == 404


def test_only_landlords_can_use_settlements(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    for headers in (john, tenant, admin):
        assert client.get("/settlements", headers=headers).status_code == 403
        assert client.get("/settlements/lease/1", headers=headers).status_code == 403
        assert client.put("/settlements/lease/1", json=body(), headers=headers).status_code == 403
        assert client.post("/settlements/lease/1/finalize", json=body(), headers=headers).status_code == 403
        assert client.post("/settlements/lease/1/reopen", headers=headers).status_code == 403
        assert client.delete("/settlements/lease/1/refund", headers=headers).status_code == 403
    assert client.get("/settlements").status_code == 401


def test_what_the_landlord_does_is_in_the_activity_log(client):
    owner = make_owner(client)
    lease = ended_lease(client, owner)
    url = f"/settlements/lease/{lease}"
    client.put(url, json=body(), headers=owner)
    client.post(f"{url}/finalize", json=body(), headers=owner)
    client.post(f"{url}/refund", json={"amount": 6000, "paid_on": date.today().isoformat(), "method": "cash"}, headers=owner)
    client.delete(f"{url}/refund", headers=owner)
    client.post(f"{url}/reopen", headers=owner)
    summaries = [row["summary"] for row in client.get("/account/activity", headers=owner).json()["items"]]
    for line in ("Saved a move-out settlement", "Finalised a move-out settlement", "Recorded a deposit refund", "Removed a deposit refund record", "Reopened a move-out settlement"):
        assert line in summaries
    # Looking is not logged
    client.get(url, headers=owner)
    assert not any(row["summary"].startswith("GET /settlements") for row in client.get("/account/activity", headers=owner).json()["items"])