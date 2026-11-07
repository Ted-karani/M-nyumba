# Import the tools we need
import io
from datetime import date

import openpyxl

# Import our own files
import models
import taxrules
from database import SessionLocal

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner
from test_admin import admin_ready
from test_portal import sign_in_tenant


# ---------- the rules on their own ----------

def charge(number, category, amount, day):
    return {"id": number, "category": category, "amount": amount, "due_date": date(2026, 10, day)}


def payment(number, amount, day):
    return {"id": number, "amount": amount, "paid_on": date(2026, 10, day)}


def test_a_payment_pays_the_oldest_charge_first():
    charges = [charge(1, "deposit", 6000, 1), charge(2, "rent", 6000, 5)]
    split = taxrules.allocate(charges, [payment(1, 6000, 2), payment(2, 4000, 10)])
    assert split[1] == {"rent": 0, "arrears": 0, "deposit": 6000, "bills": 0, "advance": 0}
    assert split[2]["rent"] == 4000 and split[2]["deposit"] == 0


def test_one_payment_can_pay_several_charges():
    charges = [charge(1, "deposit", 6000, 1), charge(2, "rent", 6000, 5), charge(3, "bills", 800, 8)]
    split = taxrules.allocate(charges, [payment(1, 13000, 3)])
    assert split[1] == {"rent": 6000, "arrears": 0, "deposit": 6000, "bills": 800, "advance": 200}


def test_old_balances_are_their_own_kind_and_come_first():
    charges = [charge(1, "arrears", 3000, 1), charge(2, "rent", 6000, 5)]
    split = taxrules.allocate(charges, [payment(1, 5000, 4)])
    assert split[1]["arrears"] == 3000 and split[1]["rent"] == 2000


def test_money_paid_before_any_charge_exists_is_an_advance():
    assert taxrules.allocate([], [payment(1, 5000, 4)])[1]["advance"] == 5000
    assert taxrules.allocate([charge(1, "rent", 0, 5)], [payment(1, 700, 4)])[1]["advance"] == 700


def test_payments_are_taken_in_date_order_not_list_order():
    charges = [charge(1, "deposit", 5000, 1), charge(2, "rent", 5000, 2)]
    split = taxrules.allocate(charges, [payment(2, 5000, 20), payment(1, 5000, 10)])
    assert split[1]["deposit"] == 5000 and split[2]["rent"] == 5000


def test_the_charge_kinds():
    assert taxrules.charge_category("rent", None) == "rent"
    assert taxrules.charge_category("deposit", None) == "deposit"
    assert taxrules.charge_category("other", "Balance brought forward") == "arrears"
    assert taxrules.charge_category("other", "Late fee") == "bills"
    for kind in ("water", "wifi", "electricity"):
        assert taxrules.charge_category(kind, None) == "bills"


def test_tax_is_rounded_to_the_nearest_shilling():
    assert taxrules.tax_for(60000, 7.5) == 4500
    assert taxrules.tax_for(1234, 7.5) == 93
    assert taxrules.tax_for(10, 5) == 1
    assert taxrules.tax_for(0, 7.5) == 0
    assert taxrules.tax_for(60000, 10) == 6000


def test_months_and_due_dates():
    assert taxrules.shift_period("2026-01", -1) == "2025-12"
    assert taxrules.shift_period("2026-12", 1) == "2027-01"
    assert taxrules.shift_period("2026-03", -14) == "2025-01"
    assert taxrules.due_date_for("2026-10") == date(2026, 11, 20)
    assert taxrules.due_date_for("2026-12") == date(2027, 1, 20)
    assert taxrules.valid_period("2026-10") and not taxrules.valid_period("2026-13") and not taxrules.valid_period("26-10")


def test_shops_and_offices_are_commercial():
    for kind in ("Shop", "shop front", "Office", "Store", "Warehouse"):
        assert taxrules.unit_is_commercial(kind), kind
    for kind in (None, "", "Bedsitter", "1 Bedroom", "Single room"):
        assert not taxrules.unit_is_commercial(kind), kind
    assert taxrules.treatment_of({"5": "residential"}, 5, "Shop") == "residential"
    assert taxrules.treatment_of({"5": "commercial"}, 5, "Bedsitter") == "commercial"
    assert taxrules.treatment_of({}, 5, "Shop") == "commercial"
    assert taxrules.treatment_of({}, 5, "Bedsitter") == "residential"


def test_the_yearly_lines():
    assert taxrules.annual_status(287_999) == "below"
    assert taxrules.annual_status(288_000) == "in_band"
    assert taxrules.annual_status(15_000_000) == "in_band"
    assert taxrules.annual_status(15_000_001) == "above"


# ---------- the page ----------

# Put a small, known business in the database: two bedsitters and a shop, with rent paid last month
def seed(client, owner):
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    period = taxrules.shift_period(taxrules.period_of(date.today()), -1)
    year, month = int(period[:4]), int(period[5:7])
    day = lambda number: date(year, month, number)
    with SessionLocal() as db:
        prop = models.Property(owner_id=owner_id, name="Block A")
        db.add(prop)
        db.flush()
        units = [
            models.Unit(property_id=prop.id, unit_number="A1", unit_type="Bedsitter", rent_amount=6000, deposit_amount=6000, status="occupied"),
            models.Unit(property_id=prop.id, unit_number="A2", unit_type="Bedsitter", rent_amount=6000, deposit_amount=0, status="occupied"),
            models.Unit(property_id=prop.id, unit_number="S1", unit_type="Shop", rent_amount=20000, deposit_amount=0, status="occupied"),
        ]
        db.add_all(units)
        db.flush()
        tenants = [models.Tenant(owner_id=owner_id, full_name=name, phone=phone) for name, phone in [("Tenant One", "254711000001"), ("Tenant Two", "254711000002"), ("Shop Tenant", "254711000003")]]
        db.add_all(tenants)
        db.flush()
        leases = [models.Lease(unit_id=unit.id, tenant_id=tenant.id, start_date=day(1), rent_amount=unit.rent_amount, deposit_amount=unit.deposit_amount, status="active") for unit, tenant in zip(units, tenants)]
        db.add_all(leases)
        db.flush()
        one, two, shop = leases
        db.add(models.Charge(lease_id=one.id, charge_type="deposit", amount=6000, period=None, due_date=day(1), description="Deposit"))
        db.add(models.Charge(lease_id=one.id, charge_type="rent", amount=6000, period=period, due_date=day(5), description="Rent"))
        db.add(models.Charge(lease_id=two.id, charge_type="other", amount=3000, period=None, due_date=day(1), description="Balance brought forward"))
        db.add(models.Charge(lease_id=two.id, charge_type="rent", amount=6000, period=period, due_date=day(5), description="Rent"))
        db.add(models.Charge(lease_id=shop.id, charge_type="rent", amount=20000, period=period, due_date=day(5), description="Rent"))
        db.add(models.Payment(lease_id=one.id, amount=6000, paid_on=day(2), method="cash"))
        db.add(models.Payment(lease_id=one.id, amount=4000, paid_on=day(10), method="cash"))
        db.add(models.Payment(lease_id=two.id, amount=5000, paid_on=day(4), method="cash"))
        db.add(models.Payment(lease_id=shop.id, amount=20000, paid_on=day(6), method="cash"))
        db.commit()
        return {"owner_id": owner_id, "property_id": prop.id, "period": period, "lease_ids": [lease.id for lease in leases]}


def overview(client, owner, period=None):
    url = "/tax/overview" + (f"?period={period}" if period else "")
    return client.get(url, headers=owner).json()


def test_the_month_adds_up_to_the_right_tax(client):
    owner = make_owner(client)
    info = seed(client, owner)
    data = overview(client, owner)
    month = data["month"]
    assert month["period"] == info["period"]
    # Rent 4000 + 2000, old balance 3000, nothing in advance
    assert (month["rent"], month["arrears"], month["advance"]) == (6000, 3000, 0)
    assert month["gross_rent"] == 9000 and month["tax_due"] == 675 and month["rate_percent"] == 7.5
    # Left out: the deposit, and the shop
    assert (month["deposits"], month["bills"], month["commercial"]) == (6000, 0, 20000)
    # What was billed that month for the homes (the shop is not counted)
    assert month["rent_billed"] == 12000
    assert month["state"] in ("due", "overdue") and month["filing"] is None
    line = month["properties"][0]
    assert line["name"] == "Block A" and line["gross_rent"] == 9000 and line["commercial_excluded"] == 20000
    assert line["residential_units"] == 2 and line["commercial_units"] == 1 and line["setting"] == "auto"


def test_the_year_strip_and_the_yearly_line(client):
    owner = make_owner(client)
    info = seed(client, owner)
    year = overview(client, owner)["year"]
    assert len(year["months"]) == 12 and year["months"][-1]["period"] == info["period"]
    assert year["months"][-1]["gross_rent"] == 9000 and year["months"][-1]["tax_due"] == 675
    assert year["total"] == 9000 and year["status"] == "below"
    # A big advance payment takes the year over the lower line
    with SessionLocal() as db:
        lease = info["lease_ids"][0]
        db.add(models.Payment(lease_id=lease, amount=300000, paid_on=date(int(info["period"][:4]), int(info["period"][5:7]), 15), method="bank"))
        db.commit()
    year = overview(client, owner)["year"]
    assert year["total"] == 309000 and year["status"] == "in_band"


def test_the_current_month_is_not_over_yet(client):
    owner = make_owner(client)
    seed(client, owner)
    current = taxrules.period_of(date.today())
    assert overview(client, owner, current)["month"]["state"] == "upcoming"


def test_settings_change_what_counts(client):
    owner = make_owner(client)
    info = seed(client, owner)
    pid = str(info["property_id"])
    # Treat the whole building as homes: the shop's rent now counts
    client.put("/tax/settings", json={"resident": True, "rate_percent": 7.5, "treatments": {pid: "residential"}}, headers=owner)
    month = overview(client, owner)["month"]
    assert month["gross_rent"] == 29000 and month["tax_due"] == 2175 and month["commercial"] == 0
    # Treat it all as commercial: nothing counts
    client.put("/tax/settings", json={"resident": True, "rate_percent": 7.5, "treatments": {pid: "commercial"}}, headers=owner)
    month = overview(client, owner)["month"]
    assert month["gross_rent"] == 0 and month["state"] == "nil"
    # Back to automatic, with a different rate
    client.put("/tax/settings", json={"resident": True, "rate_percent": 10, "treatments": {pid: "auto"}}, headers=owner)
    month = overview(client, owner)["month"]
    assert month["gross_rent"] == 9000 and month["tax_due"] == 900 and month["rate_percent"] == 10
    # Someone who is not a Kenyan resident does not use this tax
    client.put("/tax/settings", json={"resident": False, "rate_percent": 7.5, "treatments": {}}, headers=owner)
    month = overview(client, owner)["month"]
    assert month["state"] == "not_applicable" and month["tax_due"] == 0 and month["gross_rent"] == 9000


def test_bad_settings_are_refused(client):
    owner = make_owner(client)
    info = seed(client, owner)
    other = make_owner(client, "other@example.com")
    good = {"resident": True, "rate_percent": 7.5, "treatments": {}}
    assert client.put("/tax/settings", json={**good, "rate_percent": 0}, headers=owner).status_code == 422
    assert client.put("/tax/settings", json={**good, "rate_percent": 31}, headers=owner).status_code == 422
    assert client.put("/tax/settings", json={**good, "treatments": {"99999": "commercial"}}, headers=owner).status_code == 400
    assert client.put("/tax/settings", json={**good, "treatments": {str(info["property_id"]): "weird"}}, headers=owner).status_code == 400
    # Another landlord's building cannot be touched
    assert client.put("/tax/settings", json={**good, "treatments": {str(info["property_id"]): "commercial"}}, headers=other).status_code == 400


def test_a_month_can_be_marked_filed_changed_and_taken_back(client):
    owner = make_owner(client)
    info = seed(client, owner)
    period = info["period"]
    body = {"amount_paid": 675, "paid_on": date.today().isoformat(), "reference": "KRA123", "note": "Paid by M-Pesa"}
    saved = client.put(f"/tax/filings/{period}", json=body, headers=owner)
    assert saved.status_code == 200 and saved.json()["tax_due"] == 675 and saved.json()["reference"] == "KRA123"
    month = overview(client, owner)["month"]
    assert month["state"] == "filed" and month["filing"]["amount_paid"] == 675
    assert overview(client, owner)["year"]["months"][-1]["state"] == "filed"
    # Changing it does not make a second record
    assert client.put(f"/tax/filings/{period}", json={**body, "amount_paid": 700}, headers=owner).status_code == 200
    assert overview(client, owner)["month"]["filing"]["amount_paid"] == 700
    summaries = [item["summary"] for item in client.get("/account/activity", headers=owner).json()["items"]]
    assert "Marked a month of rental income tax as filed" in summaries
    assert client.delete(f"/tax/filings/{period}", headers=owner).status_code == 204
    assert overview(client, owner)["month"]["filing"] is None
    assert client.delete(f"/tax/filings/{period}", headers=owner).status_code == 404


def test_filing_rules(client):
    owner = make_owner(client)
    seed(client, owner)
    today = date.today().isoformat()
    body = {"amount_paid": 100, "paid_on": today}
    current = taxrules.period_of(date.today())
    assert client.put(f"/tax/filings/{current}", json=body, headers=owner).status_code == 400
    assert client.put("/tax/filings/2026-13", json=body, headers=owner).status_code == 422
    last = taxrules.shift_period(current, -1)
    assert client.put(f"/tax/filings/{last}", json={**body, "amount_paid": -5}, headers=owner).status_code == 422
    assert client.put(f"/tax/filings/{last}", json={**body, "paid_on": "2999-01-01"}, headers=owner).status_code == 400
    assert client.get("/tax/overview?period=nonsense", headers=owner).status_code == 422


def test_each_landlord_sees_only_their_own_money(client):
    owner = make_owner(client)
    seed(client, owner)
    other = make_owner(client, "other@example.com")
    month = overview(client, other)["month"]
    assert month["gross_rent"] == 0 and month["properties"] == [] and month["state"] == "nil"
    # And their filings are separate too
    last = taxrules.shift_period(taxrules.period_of(date.today()), -1)
    client.put(f"/tax/filings/{last}", json={"amount_paid": 1, "paid_on": date.today().isoformat()}, headers=owner)
    assert overview(client, other)["month"]["filing"] is None


def test_only_landlords_can_use_the_tax_pages(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    admin = admin_ready(client)
    for headers in (john, tenant, admin):
        assert client.get("/tax/overview", headers=headers).status_code == 403
        assert client.get("/tax/export", headers=headers).status_code == 403
        assert client.put("/tax/settings", json={"resident": True, "rate_percent": 7.5, "treatments": {}}, headers=headers).status_code == 403
    assert client.get("/tax/overview").status_code == 401


def test_the_excel_schedule_has_the_numbers_but_no_phone_numbers(client):
    owner = make_owner(client)
    info = seed(client, owner)
    response = client.get(f"/tax/export?period={info['period']}", headers=owner)
    assert response.status_code == 200 and "spreadsheetml" in response.headers["content-type"]
    workbook = openpyxl.load_workbook(io.BytesIO(response.content))
    assert workbook.sheetnames == ["Summary", "By unit"]
    text = " ".join(str(cell.value) for sheet in workbook for row in sheet.iter_rows() for cell in row if cell.value is not None)
    assert "9000" in text and "675" in text and "Tenant One" in text and "A1" in text
    assert "not tax advice" in text and "254711000001" not in text