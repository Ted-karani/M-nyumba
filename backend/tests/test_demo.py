# Import the tools we need
from datetime import date

import pytest

# Import our own files
import legal_models
import models
import taxrules
from admin_models import AdminEvent, OwnerAccount
from database import Base, SessionLocal
from demo_data import DEMO_EMAIL, build_demo, wipe_demo
from ownership import KEEP_TABLES, collect
from portal_models import Notice
from routers.expenses import Expense
from routers.latefees import find_candidates, read_settings
from routers.listings import Listing
from routers.tasks import Task
from settlement_models import DepositSettlement
from sqlalchemy import func, select
from tax_models import TaxFiling

# Import our test helpers
from helpers import make_business, make_caretaker, make_owner
from test_admin import admin_ready
from test_portal import sign_in_tenant


def create_demo(client, admin):
    response = client.post("/admin/demo", headers=admin)
    assert response.status_code == 201, response.text
    return response.json()


def sign_in_demo(client, password):
    response = client.post("/auth/login", data={"username": DEMO_EMAIL, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def demo_id():
    with SessionLocal() as db:
        return db.query(models.User).filter(models.User.email == DEMO_EMAIL).one().id


def test_only_the_admin_can_use_the_demo_pages(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    for headers in (owner, john, tenant):
        assert client.get("/admin/demo", headers=headers).status_code == 403
        assert client.post("/admin/demo", headers=headers).status_code == 403
        assert client.post("/admin/demo/reset", headers=headers).status_code == 403
        assert client.delete("/admin/demo", headers=headers).status_code == 403
    assert client.get("/admin/demo").status_code == 401


def test_the_demo_is_built_and_the_password_works(client):
    admin = admin_ready(client)
    assert client.get("/admin/demo", headers=admin).json()["exists"] is False
    created = create_demo(client, admin)
    assert created["email"] == DEMO_EMAIL and created["password"].startswith("Demo-")
    assert created["counts"]["properties"] == 3 and created["counts"]["units"] == 60 and created["counts"]["occupied_units"] == 52
    assert created["counts"]["tenants"] == 53 and created["counts"]["listings"] == 4 and created["counts"]["repairs"] == 8
    status = client.get("/admin/demo", headers=admin).json()
    assert status["exists"] is True and status["blocked"] is False and status["counts"]["units"] == 60
    demo = sign_in_demo(client, created["password"])
    assert len(client.get("/properties", headers=demo).json()) == 3
    # Making it twice is refused
    assert client.post("/admin/demo", headers=admin).status_code == 409


def test_the_demo_has_the_shape_we_promised(client):
    admin = admin_ready(client)
    create_demo(client, admin)
    owner_id = demo_id()
    today = date.today()
    with SessionLocal() as db:
        units = db.query(models.Unit).join(models.Property, models.Unit.property_id == models.Property.id).filter(models.Property.owner_id == owner_id).all()
        assert sorted([(unit.status) for unit in units]).count("occupied") == 52
        assert [unit.status for unit in units].count("vacant") == 7 and [unit.status for unit in units].count("maintenance") == 1
        assert len([unit for unit in units if unit.unit_type == "Shop"]) == 4
        leases = db.query(models.Lease).join(models.Unit, models.Lease.unit_id == models.Unit.id).join(models.Property, models.Unit.property_id == models.Property.id).filter(models.Property.owner_id == owner_id).all()
        assert [lease.status for lease in leases].count("active") == 52 and [lease.status for lease in leases].count("ended") == 1
        payments = db.query(models.Payment).filter(models.Payment.lease_id.in_([lease.id for lease in leases])).all()
        assert payments and all(payment.paid_on <= today for payment in payments)
        references = [payment.reference for payment in payments if payment.reference]
        assert len(references) == len(set(references)) and all(reference.startswith("DEMO-") for reference in references)
        repair_states = [row.status for row in db.query(models.MaintenanceRequest).all()]
        assert (repair_states.count("open"), repair_states.count("in_progress"), repair_states.count("fixed")) == (3, 2, 3)
        assert db.query(func.count(Notice.id)).scalar() == 3 and db.query(func.count(Task.id)).scalar() == 4 and db.query(func.count(Listing.id)).scalar() == 4
        assert db.query(func.count(Expense.id)).scalar() in (19, 23)
        assert db.query(func.count(DepositSettlement.id)).scalar() == 1 and db.query(func.count(TaxFiling.id)).scalar() == 1
        account = db.query(OwnerAccount).filter(OwnerAccount.owner_id == owner_id).one()
        assert account.plan == "paid" and account.paid_until > today and account.notes.startswith("DEMO ACCOUNT")


def test_the_demo_fills_the_money_screens(client):
    admin = admin_ready(client)
    demo = sign_in_demo(client, create_demo(client, admin)["password"])
    late = client.get("/late-fees/preview", headers=demo).json()
    assert late["settings"]["enabled"] is True and len(late["candidates"]) >= 4
    tax = client.get("/tax/overview", headers=demo).json()["month"]
    assert tax["gross_rent"] > 0 and tax["commercial"] > 0 and tax["tax_due"] > 0
    settlements = client.get("/settlements", headers=demo).json()
    assert len(settlements) == 1 and settlements[0]["state"] == "draft" and settlements[0]["refund_due"] == 4500
    year = client.get("/tax/overview", headers=demo).json()["year"]
    assert any(month["state"] == "filed" for month in year["months"])


def test_the_demo_works_even_when_the_terms_are_required(client, monkeypatch):
    admin = admin_ready(client)
    demo = sign_in_demo(client, create_demo(client, admin)["password"])
    monkeypatch.setenv("TERMS_ENFORCED", "true")
    assert client.get("/properties", headers=demo).status_code == 200


def test_reset_rebuilds_with_a_new_password_and_no_duplicates(client):
    admin = admin_ready(client)
    first = create_demo(client, admin)
    reset = client.post("/admin/demo/reset", headers=admin)
    assert reset.status_code == 201
    second = reset.json()
    assert second["password"] != first["password"] and second["counts"] == first["counts"]
    assert client.post("/auth/login", data={"username": DEMO_EMAIL, "password": first["password"]}).status_code == 401
    demo = sign_in_demo(client, second["password"])
    assert len(client.get("/properties", headers=demo).json()) == 3
    with SessionLocal() as db:
        assert db.query(func.count(models.Tenant.id)).scalar() == 53 and db.query(func.count(models.User.id)).filter(models.User.email == DEMO_EMAIL).scalar() == 1
    # Resetting when there is no demo just builds it
    client.delete("/admin/demo", headers=admin)
    assert client.post("/admin/demo/reset", headers=admin).status_code == 201


def test_deleting_the_demo_leaves_nothing_behind(client):
    admin = admin_ready(client)
    created = create_demo(client, admin)
    demo = sign_in_demo(client, created["password"])
    client.post("/late-fees/apply", json={"items": [{"lease_id": row["lease_id"], "period": row["period"]} for row in client.get("/late-fees/preview", headers=demo).json()["candidates"][:2]]}, headers=demo)
    owner_id = demo_id()
    assert client.delete("/admin/demo", headers=admin).status_code == 204
    assert client.get("/admin/demo", headers=admin).json()["exists"] is False
    assert client.post("/auth/login", data={"username": DEMO_EMAIL, "password": created["password"]}).status_code == 401
    assert client.delete("/admin/demo", headers=admin).status_code == 404
    skip = KEEP_TABLES | {"login_attempts", "user_security", "user_totp"}
    with SessionLocal() as db:
        assert collect(db, owner_id) == {}
        assert db.query(func.count(OwnerAccount.id)).filter(OwnerAccount.owner_id == owner_id).scalar() == 0
        assert db.query(func.count(models.User.id)).filter(models.User.email == DEMO_EMAIL).scalar() == 0
        for table in Base.metadata.sorted_tables:
            if table.name in skip:
                continue
            assert db.execute(select(func.count()).select_from(table)).scalar() == 0, f"The table {table.name} still has rows"
        assert db.query(func.count(AdminEvent.id)).filter(AdminEvent.owner_id == owner_id).scalar() == 0
    actions = [event["action"] for event in client.get("/admin/events", headers=admin).json()]
    assert "Created the demo landlord" in actions and "Deleted the demo landlord" in actions


def test_a_real_landlords_data_is_never_touched(client):
    real = make_owner(client, "real@example.com")
    business = make_business(client, real)
    admin = admin_ready(client)
    before = (len(client.get("/properties", headers=real).json()), client.get("/payments", headers=real).json()["total"])
    created = create_demo(client, admin)
    client.post("/admin/demo/reset", headers=admin)
    client.delete("/admin/demo", headers=admin)
    after = (len(client.get("/properties", headers=real).json()), client.get("/payments", headers=real).json()["total"])
    assert before == after and business["property_id"]
    assert created["password"]


def test_an_account_with_the_demo_email_that_is_not_a_demo_is_left_alone(client):
    real = make_owner(client, DEMO_EMAIL)
    make_business(client, real)
    admin = admin_ready(client)
    status = client.get("/admin/demo", headers=admin).json()
    assert status["exists"] is False and status["blocked"] is True and "not a demo" in status["message"]
    assert client.post("/admin/demo", headers=admin).status_code == 409
    assert client.post("/admin/demo/reset", headers=admin).status_code == 409
    assert client.delete("/admin/demo", headers=admin).status_code == 409
    assert len(client.get("/properties", headers=real).json()) == 1


@pytest.mark.parametrize("today", [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 31), date(2026, 1, 1), date(2026, 12, 31)])
def test_the_demo_makes_sense_on_any_day_of_the_month(client, today):
    with SessionLocal() as db:
        built = build_demo(db, today)
        owner = built["owner"]
        assert built["counts"]["units"] == 60 and built["counts"]["occupied_units"] == 52
        payments = db.query(models.Payment).all()
        assert payments and all(payment.paid_on <= today for payment in payments)
        assert all(expense.spent_on <= today for expense in db.query(Expense).all())
        # Someone is always late, so the late fee page always has something to show
        assert len(find_candidates(db, owner.id, read_settings(db, owner.id), today)) >= 4
        assert db.query(TaxFiling).one().period == taxrules.shift_period(taxrules.period_of(today), -2)
        wipe_demo(db, owner)
        assert db.query(func.count(models.Tenant.id)).scalar() == 0 and db.query(func.count(models.Payment.id)).scalar() == 0