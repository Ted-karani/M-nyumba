# Import the date tools
from datetime import date

# Import our test helpers
from helpers import days_ago, make_business, make_owner, make_property, make_tenant, make_unit, months_between, move_in, pay


def test_move_in_charges_the_deposit_and_first_rent(client):
    headers = make_owner(client)
    business = make_business(client, headers)
    lease = business["lease"]
    # Deposit 8000 plus first rent 8000
    assert lease["total_charged"] == 16000
    assert lease["balance"] == 16000
    # The unit is now occupied
    unit = client.get(f"/units/{business['unit_id']}", headers=headers).json()
    assert unit["status"] == "occupied"


def test_partial_payments_change_the_balance(client):
    headers = make_owner(client)
    lease_id = make_business(client, headers)["lease"]["id"]
    first = pay(client, headers, lease_id, 5000, method="mpesa", reference="SJK4L2M9QP")
    assert first.status_code == 201
    assert first.json()["lease_balance"] == 11000
    second = pay(client, headers, lease_id, 11000)
    assert second.json()["lease_balance"] == 0
    # Paying too much leaves the tenant in credit
    extra = pay(client, headers, lease_id, 1000)
    assert extra.json()["lease_balance"] == -1000


def test_the_same_mpesa_code_cannot_be_recorded_twice(client):
    headers = make_owner(client)
    lease_id = make_business(client, headers)["lease"]["id"]
    assert pay(client, headers, lease_id, 1000, method="mpesa", reference="SJK4L2M9QP").status_code == 201
    again = pay(client, headers, lease_id, 1000, method="mpesa", reference="SJK4L2M9QP")
    assert again.status_code == 400
    assert "already been recorded" in again.json()["detail"]


def test_bad_payments_are_refused(client):
    headers = make_owner(client)
    lease_id = make_business(client, headers)["lease"]["id"]
    # A payment of nothing
    assert pay(client, headers, lease_id, 0).status_code == 422
    # An M-Pesa payment without a proper code
    assert pay(client, headers, lease_id, 500, method="mpesa", reference="123").status_code == 422
    assert pay(client, headers, lease_id, 500, method="mpesa").status_code == 422


def test_deleting_a_payment_brings_the_balance_back(client):
    headers = make_owner(client)
    lease_id = make_business(client, headers)["lease"]["id"]
    payment = pay(client, headers, lease_id, 4000).json()
    assert client.get(f"/leases/{lease_id}", headers=headers).json()["balance"] == 12000
    assert client.delete(f"/payments/{payment['id']}", headers=headers).status_code == 204
    assert client.get(f"/leases/{lease_id}", headers=headers).json()["balance"] == 16000


def test_monthly_rent_catches_up_and_never_doubles(client):
    headers = make_owner(client)
    start = days_ago(75)
    lease_id = make_business(client, headers, start=start)["lease"]["id"]
    expected = months_between(start, date.today())
    first = client.post("/billing/generate-rent", headers=headers)
    assert first.status_code == 200
    assert first.json()["created_count"] == expected
    # Pressing it again changes nothing
    assert client.post("/billing/generate-rent", headers=headers).json()["created_count"] == 0
    charges = client.get(f"/leases/{lease_id}/charges", headers=headers).json()
    periods = [charge["period"] for charge in charges if charge["charge_type"] == "rent"]
    assert len(periods) == len(set(periods)) == expected + 1


def test_overdue_respects_the_grace_period_and_payments(client):
    headers = make_owner(client)
    # Rent of 8000 that was due 20 days ago (no deposit)
    lease_id = make_business(client, headers, deposit=0, start=days_ago(20))["lease"]["id"]
    board = client.get("/dashboard", headers=headers).json()
    assert board["overdue_count"] == 1
    assert board["total_overdue"] == 8000
    # With a 30 day grace period nobody is overdue yet
    assert client.get("/dashboard?grace_days=30", headers=headers).json()["overdue_count"] == 0
    # Paying clears it
    pay(client, headers, lease_id, 8000)
    assert client.get("/dashboard", headers=headers).json()["overdue_count"] == 0


def test_existing_tenants_have_no_history_charged(client):
    headers = make_owner(client)
    make_property(client, headers, "Kinoru Apartments")
    row = {
        "property_name": "Kinoru Apartments",
        "unit_number": "E1",
        "tenant_name": "Samuel Otieno",
        "phone": "0722 111 222",
        "rent_amount": "6,000",
        "deposit_amount": "6000",
        "balance": "1500",
    }
    # Only checking saves nothing
    check = client.post("/onboarding/existing-tenants", json={"rows": [row], "dry_run": True}, headers=headers).json()
    assert check["ok"] is True and check["imported"] == 0
    assert client.get("/tenants", headers=headers).json() == []
    # Importing for real
    done = client.post("/onboarding/existing-tenants", json={"rows": [row], "dry_run": False}, headers=headers).json()
    assert done["imported"] == 1
    lease = client.get("/leases", headers=headers).json()[0]
    # Only the balance brought forward is charged: no deposit and no past rent
    assert lease["total_charged"] == 1500
    assert lease["balance"] == 1500
    charges = client.get(f"/leases/{lease['id']}/charges", headers=headers).json()
    assert [charge["charge_type"] for charge in charges] == ["other"]


def test_one_bad_row_saves_nothing(client):
    headers = make_owner(client)
    make_property(client, headers, "Kinoru Apartments")
    good = {"property_name": "Kinoru Apartments", "unit_number": "E1", "tenant_name": "Samuel Otieno", "phone": "0722 111 222", "rent_amount": "6000"}
    bad = {"property_name": "Wrong Place", "unit_number": "E2", "tenant_name": "Lucy Achieng", "phone": "0733 222 333", "rent_amount": "6000"}
    result = client.post("/onboarding/existing-tenants", json={"rows": [good, bad], "dry_run": False}, headers=headers).json()
    assert result["ok"] is False
    assert result["imported"] == 0
    assert result["error_count"] == 1
    assert client.get("/tenants", headers=headers).json() == []


def test_meter_bills_use_the_difference_between_readings(client):
    headers = make_owner(client)
    business = make_business(client, headers)

    def bill(period, reading):
        return client.post(
            "/utilities/bill",
            json={
                "property_id": business["property_id"],
                "utility": "water",
                "period": period,
                "rate_per_unit": 150,
                "due_date": date.today().isoformat(),
                "readings": [{"unit_id": business["unit_id"], "reading": reading}],
            },
            headers=headers,
        )

    # The first reading is only a starting point
    first = bill("2026-09", 100)
    assert first.status_code == 201
    assert first.json()["baselines"] == 1 and first.json()["charged"] == 0
    # 12 units at 150 each
    second = bill("2026-10", 112).json()
    assert second["charged"] == 1 and second["total_amount"] == 1800
    assert client.get(f"/leases/{business['lease']['id']}", headers=headers).json()["balance"] == 16000 + 1800
    # A meter cannot go backwards
    lower = bill("2026-11", 100)
    assert lower.status_code == 400 and "lower" in lower.json()["detail"]
    # The same month cannot be billed twice
    assert bill("2026-10", 120).status_code == 400


def test_the_report_net_is_collected_minus_spent(client):
    headers = make_owner(client)
    business = make_business(client, headers)
    pay(client, headers, business["lease"]["id"], 5000)
    spent = client.post(
        "/expenses",
        json={"category": "supplies", "amount": 1200, "spent_on": date.today().isoformat(), "property_id": business["property_id"]},
        headers=headers,
    )
    assert spent.status_code == 201
    month = date.today().strftime("%Y-%m")
    report = client.get(f"/reports/monthly?month={month}", headers=headers).json()
    assert report["collected"] == 5000
    assert report["expenses_total"] == 1200
    assert report["net"] == 3800


def test_an_expense_of_nothing_is_refused(client):
    headers = make_owner(client)
    response = client.post("/expenses", json={"category": "supplies", "amount": 0, "spent_on": date.today().isoformat()}, headers=headers)
    assert response.status_code == 422