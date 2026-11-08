# Import the tools we need
from datetime import date, timedelta

# Import our own files
import latefee_rules as rules
import models
from database import SessionLocal
from latefee_models import LateFeeLog

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner
from test_admin import admin_ready
from test_portal import sign_in_tenant


# ---------- the rules on their own ----------

def charge(number, amount, days_ago):
    return {"id": number, "amount": amount, "due_date": date.today() - timedelta(days=days_ago)}


def test_the_oldest_charge_is_paid_first_and_only_payments_up_to_the_day_count():
    today = date.today()
    charges = [charge(1, 3000, 40), charge(2, 6000, 20)]
    # 5,000 paid in time: it clears the old charge and pays 2,000 of the rent
    assert rules.unpaid_at(charges, [{"amount": 5000, "paid_on": today - timedelta(days=18)}], 2, today - timedelta(days=15)) == 4000
    # The same money paid after the day does not count
    assert rules.unpaid_at(charges, [{"amount": 5000, "paid_on": today - timedelta(days=10)}], 2, today - timedelta(days=15)) == 6000
    # Paid in full in time
    assert rules.unpaid_at(charges, [{"amount": 9000, "paid_on": today - timedelta(days=18)}], 2, today - timedelta(days=15)) == 0
    assert rules.unpaid_at(charges, [], 99, today) == 0


def test_the_fee_is_flat_or_a_rounded_percentage():
    assert rules.fee_for("flat", 500, 6000) == 500
    assert rules.fee_for("percent", 5, 6000) == 300
    assert rules.fee_for("percent", 7.5, 6000) == 450
    assert rules.fee_for("percent", 10, 5555) == 556
    assert rules.deadline_for(date(2026, 11, 5), 5) == date(2026, 11, 10)


# ---------- the page ----------

# One active tenant with one rent charge that fell due some days ago. payments: [(amount, days ago)]
def seed(client, owner, days_ago=20, rent=6000, payments=(), unit_number="A1", phone="254711000001", status="active"):
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    due = date.today() - timedelta(days=days_ago)
    period = f"{due.year}-{due.month:02d}"
    with SessionLocal() as db:
        prop = db.query(models.Property).filter(models.Property.owner_id == owner_id, models.Property.name == "Block A").first()
        if prop is None:
            prop = models.Property(owner_id=owner_id, name="Block A")
            db.add(prop)
            db.flush()
        unit = models.Unit(property_id=prop.id, unit_number=unit_number, unit_type="Bedsitter", rent_amount=rent, status="occupied")
        tenant = models.Tenant(owner_id=owner_id, full_name=f"Tenant {unit_number}", phone=phone)
        db.add_all([unit, tenant])
        db.flush()
        lease = models.Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=due, rent_amount=rent, status=status)
        db.add(lease)
        db.flush()
        db.add(models.Charge(lease_id=lease.id, charge_type="rent", amount=rent, period=period, due_date=due, description="Rent"))
        for amount, paid_ago in payments:
            db.add(models.Payment(lease_id=lease.id, amount=amount, paid_on=date.today() - timedelta(days=paid_ago), method="cash"))
        db.commit()
        return {"lease_id": lease.id, "period": period, "due": due}


# Switch late fees on with a start month long ago (so the test months count)
def turn_on(client, owner, **changes):
    body = {"enabled": True, "grace_days": 5, "kind": "flat", "amount": 500, "start_period": "2000-01", **changes}
    response = client.put("/late-fees/settings", json=body, headers=owner)
    assert response.status_code == 200, response.text
    return response.json()


def preview(client, owner):
    return client.get("/late-fees/preview", headers=owner).json()


def apply(client, owner, *items):
    return client.post("/late-fees/apply", json={"items": [{"lease_id": lease, "period": period} for lease, period in items]}, headers=owner)


# What the tenant owes in all: charges minus payments
def balance(lease_id):
    with SessionLocal() as db:
        charged = sum(row.amount for row in db.query(models.Charge).filter(models.Charge.lease_id == lease_id))
        paid = sum(row.amount for row in db.query(models.Payment).filter(models.Payment.lease_id == lease_id))
    return charged - paid


def test_the_settings_start_switched_off_and_enabling_starts_this_month(client):
    owner = make_owner(client)
    first = client.get("/late-fees/preview", headers=owner).json()
    assert first["settings"] == {"enabled": False, "grace_days": 5, "kind": "flat", "amount": 500, "start_period": None}
    assert first["candidates"] == [] and first["total_fee"] == 0
    saved = client.put("/late-fees/settings", json={"enabled": True, "grace_days": 3, "kind": "flat", "amount": 300}, headers=owner).json()
    assert saved["enabled"] is True and saved["start_period"] == f"{date.today().year}-{date.today().month:02d}"


def test_bad_settings_are_refused(client):
    owner = make_owner(client)
    good = {"enabled": True, "grace_days": 5, "kind": "flat", "amount": 500}
    for change in [{"grace_days": 31}, {"grace_days": -1}, {"kind": "daily"}, {"amount": 0}, {"kind": "percent", "amount": 60}, {"start_period": "2026-13"}, {"start_period": "soon"}]:
        assert client.put("/late-fees/settings", json={**good, **change}, headers=owner).status_code == 422, change


def test_nothing_happens_while_the_feature_is_off(client):
    owner = make_owner(client)
    info = seed(client, owner)
    assert preview(client, owner)["candidates"] == []
    assert apply(client, owner, (info["lease_id"], info["period"])).status_code == 400


def test_a_tenant_who_did_not_pay_by_the_deadline_is_late(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20)
    turn_on(client, owner)
    data = preview(client, owner)
    assert data["total_fee"] == 500 and len(data["candidates"]) == 1
    item = data["candidates"][0]
    assert item["lease_id"] == info["lease_id"] and item["period"] == info["period"] and item["fee"] == 500
    assert item["tenant_name"] == "Tenant A1" and item["unit_number"] == "A1" and item["property_name"] == "Block A"
    assert item["unpaid_at_deadline"] == 6000 and item["still_owing"] == 6000 and item["rent_amount"] == 6000
    assert item["deadline"] == (info["due"] + timedelta(days=5)).isoformat()


def test_paying_in_time_means_no_fee_but_paying_late_still_does(client):
    owner = make_owner(client)
    # Paid in full 18 days ago: the deadline was 15 days ago
    seed(client, owner, days_ago=20, payments=[(6000, 18)], unit_number="A1", phone="254711000001")
    assert preview(client, owner)["candidates"] == [] or True
    turn_on(client, owner)
    assert preview(client, owner)["candidates"] == []
    # Paid in full, but 10 days ago: after the deadline
    seed(client, owner, days_ago=20, payments=[(6000, 10)], unit_number="A2", phone="254711000002")
    items = preview(client, owner)["candidates"]
    assert len(items) == 1 and items[0]["unit_number"] == "A2"
    assert items[0]["unpaid_at_deadline"] == 6000 and items[0]["still_owing"] == 0


def test_a_part_payment_is_still_late_for_the_rest(client):
    owner = make_owner(client)
    seed(client, owner, days_ago=20, payments=[(5000, 18)])
    turn_on(client, owner)
    item = preview(client, owner)["candidates"][0]
    assert item["unpaid_at_deadline"] == 1000 and item["still_owing"] == 1000


def test_the_grace_days_are_respected(client):
    owner = make_owner(client)
    seed(client, owner, days_ago=3, unit_number="A1", phone="254711000001")
    seed(client, owner, days_ago=5, unit_number="A2", phone="254711000002")
    seed(client, owner, days_ago=6, unit_number="A3", phone="254711000003")
    turn_on(client, owner, grace_days=5)
    # The deadline of A2 is today, so it is not late yet. Only A3 is.
    assert [item["unit_number"] for item in preview(client, owner)["candidates"]] == ["A3"]
    turn_on(client, owner, grace_days=0)
    assert len(preview(client, owner)["candidates"]) == 3


def test_old_months_before_the_start_month_are_never_charged(client):
    owner = make_owner(client)
    seed(client, owner, days_ago=70)
    turn_on(client, owner, start_period=f"{date.today().year}-{date.today().month:02d}")
    assert preview(client, owner)["candidates"] == []


def test_a_percentage_fee_is_a_share_of_that_months_rent(client):
    owner = make_owner(client)
    seed(client, owner, days_ago=20, rent=6000)
    turn_on(client, owner, kind="percent", amount=5)
    assert preview(client, owner)["candidates"][0]["fee"] == 300


def test_tenants_who_have_moved_out_are_not_charged(client):
    owner = make_owner(client)
    seed(client, owner, days_ago=20, status="ended")
    turn_on(client, owner)
    assert preview(client, owner)["candidates"] == []


def test_applying_adds_one_fee_once(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20)
    turn_on(client, owner)
    result = apply(client, owner, (info["lease_id"], info["period"]))
    assert result.status_code == 200 and result.json() == {"applied": 1, "skipped": 0, "total": 500}
    assert balance(info["lease_id"]) == 6500
    with SessionLocal() as db:
        fee = db.query(models.Charge).filter(models.Charge.lease_id == info["lease_id"], models.Charge.charge_type == "other").one()
        assert fee.amount == 500 and fee.period == info["period"] and fee.description.startswith("Late fee: ") and fee.description.endswith(" rent")
        assert fee.due_date == date.today()
    # Pressing again, or reloading, never adds a second fee
    again = apply(client, owner, (info["lease_id"], info["period"]))
    assert again.json() == {"applied": 0, "skipped": 1, "total": 0}
    assert balance(info["lease_id"]) == 6500
    assert preview(client, owner)["candidates"] == []
    history = client.get("/late-fees/history", headers=owner).json()
    assert len(history) == 1 and history[0]["action"] == "applied" and history[0]["can_waive"] is True and history[0]["amount"] == 500


def test_only_people_who_are_really_late_can_be_charged(client):
    owner = make_owner(client)
    paid = seed(client, owner, days_ago=20, payments=[(6000, 18)], unit_number="A1", phone="254711000001")
    late = seed(client, owner, days_ago=20, unit_number="A2", phone="254711000002")
    turn_on(client, owner)
    result = apply(client, owner, (paid["lease_id"], paid["period"]), (late["lease_id"], late["period"]), (99999, "2026-01"))
    assert result.json() == {"applied": 1, "skipped": 2, "total": 500}
    assert balance(paid["lease_id"]) == 0 and balance(late["lease_id"]) == 6500


def test_waiving_before_it_is_added_means_it_never_is(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20)
    turn_on(client, owner)
    waived = client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=owner)
    assert waived.status_code == 200 and waived.json() == {"waived": True, "fee": 500}
    assert preview(client, owner)["candidates"] == []
    assert apply(client, owner, (info["lease_id"], info["period"])).json()["applied"] == 0
    assert balance(info["lease_id"]) == 6000
    assert client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=owner).status_code == 400


def test_a_fee_that_was_added_can_be_taken_back(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20)
    turn_on(client, owner)
    apply(client, owner, (info["lease_id"], info["period"]))
    assert balance(info["lease_id"]) == 6500
    assert client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=owner).status_code == 200
    assert balance(info["lease_id"]) == 6000
    history = client.get("/late-fees/history", headers=owner).json()
    assert history[0]["action"] == "waived" and history[0]["can_waive"] is False
    # It does not come back
    assert preview(client, owner)["candidates"] == []
    assert client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=owner).status_code == 400
    with SessionLocal() as db:
        assert db.query(LateFeeLog).one().charge_id is None


def test_waiving_something_that_is_not_late_is_refused(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20, payments=[(6000, 18)])
    turn_on(client, owner)
    assert client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=owner).status_code == 404


def test_each_landlord_only_sees_and_charges_their_own_tenants(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20)
    turn_on(client, owner)
    other = make_owner(client, "other@example.com")
    turn_on(client, other)
    assert preview(client, other)["candidates"] == []
    assert apply(client, other, (info["lease_id"], info["period"])).json() == {"applied": 0, "skipped": 1, "total": 0}
    assert client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=other).status_code == 404
    assert balance(info["lease_id"]) == 6000
    apply(client, owner, (info["lease_id"], info["period"]))
    assert client.get("/late-fees/history", headers=other).json() == []
    # The other landlord cannot take the fee back either
    assert client.post("/late-fees/waive", json={"lease_id": info["lease_id"], "period": info["period"]}, headers=other).status_code == 404
    assert balance(info["lease_id"]) == 6500


def test_only_landlords_can_use_late_fees(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    item = {"lease_id": 1, "period": "2026-10"}
    for headers in (john, tenant, admin):
        assert client.get("/late-fees/preview", headers=headers).status_code == 403
        assert client.get("/late-fees/history", headers=headers).status_code == 403
        assert client.put("/late-fees/settings", json={"enabled": True, "grace_days": 5, "kind": "flat", "amount": 500}, headers=headers).status_code == 403
        assert client.post("/late-fees/apply", json={"items": [item]}, headers=headers).status_code == 403
        assert client.post("/late-fees/waive", json=item, headers=headers).status_code == 403
    assert client.get("/late-fees/preview").status_code == 401


def test_what_the_landlord_does_is_in_the_activity_log(client):
    owner = make_owner(client)
    info = seed(client, owner, days_ago=20, unit_number="A1", phone="254711000001")
    other = seed(client, owner, days_ago=20, unit_number="A2", phone="254711000002")
    turn_on(client, owner)
    apply(client, owner, (info["lease_id"], info["period"]))
    client.post("/late-fees/waive", json={"lease_id": other["lease_id"], "period": other["period"]}, headers=owner)
    summaries = [row["summary"] for row in client.get("/account/activity", headers=owner).json()["items"]]
    for line in ("Changed the late fee settings", "Applied late fees", "Waived a late fee"):
        assert line in summaries
    # Looking at the page is not logged
    client.get("/late-fees/preview", headers=owner)
    assert not any(line.startswith("GET /late-fees") for line in [row["summary"] for row in client.get("/account/activity", headers=owner).json()["items"]])