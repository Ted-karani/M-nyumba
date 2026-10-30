# Import our own files
import models
from admin_models import OwnerAccount
from database import SessionLocal
from routers.quicksetup import expand_labels

# Import our test helpers
from helpers import make_caretaker, make_owner, make_property, make_unit
from test_portal import sign_in_tenant
from helpers import make_business


# A building with two kinds of units
def two_kinds(name="Kinoru Apartments"):
    return {
        "new_property": {"name": name, "town": "Makutano", "county": "Meru"},
        "groups": [
            {"labels": "A1-A10", "unit_type": "Bedsitter", "rent_amount": 6000, "deposit_amount": 6000},
            {"labels": "B1-B5", "unit_type": "1 Bedroom", "rent_amount": 12000, "deposit_amount": 12000},
        ],
    }


def test_unit_numbers_can_be_typed_as_ranges():
    assert expand_labels("A1-A3, B1") == (["A1", "A2", "A3", "B1"], [])
    assert expand_labels("1-3") == (["1", "2", "3"], [])
    assert expand_labels("Shop 1-2") == (["Shop 1", "Shop 2"], [])
    assert expand_labels("A01-A03") == (["A01", "A02", "A03"], [])
    assert expand_labels("A1-3") == (["A1", "A2", "A3"], [])
    assert expand_labels("A1 to A2") == (["A1", "A2"], [])
    assert expand_labels("Block-A") == (["Block-A"], [])
    assert len(expand_labels("A1-A12\nB1-B12")[0]) == 24


def test_unit_numbers_that_cannot_be_read_are_explained():
    for text in ["A5-A2", "A1-B12", "1-500", "ThisUnitNumberIsFarTooLong1", "A1$"]:
        labels, problems = expand_labels(text)
        assert problems, text
        assert labels == []


def test_a_new_building_is_previewed_then_created_with_all_its_units(client):
    owner = make_owner(client)
    body = two_kinds()
    # The preview saves nothing
    preview = client.post("/quick-setup/preview", json=body, headers=owner).json()
    assert preview["ok"] is True and preview["will_add"] == 15 and preview["created"] == 0
    assert preview["potential_rent"] == 10 * 6000 + 5 * 12000
    assert client.get("/properties", headers=owner).json() == []
    # Now it is created
    made = client.post("/quick-setup/building", json=body, headers=owner).json()
    assert made["ok"] is True and made["created"] == 15 and made["property_id"]
    properties = client.get("/properties", headers=owner).json()
    assert len(properties) == 1 and properties[0]["town"] == "Makutano" and properties[0]["county"] == "Meru"
    units = client.get(f"/properties/{made['property_id']}/units", headers=owner).json()
    assert len(units) == 15 and all(unit["status"] == "vacant" for unit in units)
    one_bedroom = next(unit for unit in units if unit["unit_number"] == "B1")
    assert one_bedroom["rent_amount"] == 12000 and one_bedroom["unit_type"] == "1 Bedroom"


def test_adding_to_an_existing_building_skips_what_is_already_there(client):
    owner = make_owner(client)
    property_id = make_property(client, owner)
    make_unit(client, owner, property_id, "A1")
    body = {"property_id": property_id, "groups": [{"labels": "A1-A3", "rent_amount": 5000}]}
    made = client.post("/quick-setup/building", json=body, headers=owner).json()
    assert made["ok"] is True and made["created"] == 2 and made["skipped"] == 1
    assert len(client.get(f"/properties/{property_id}/units", headers=owner).json()) == 3
    # Without skipping, an existing number is a problem and nothing is saved
    strict = client.post("/quick-setup/building", json={"property_id": property_id, "skip_existing": False, "groups": [{"labels": "A1-A5"}]}, headers=owner).json()
    assert strict["ok"] is False and strict["created"] == 0
    assert len(client.get(f"/properties/{property_id}/units", headers=owner).json()) == 3


def test_mistakes_are_reported_and_nothing_is_saved(client):
    owner = make_owner(client)
    make_property(client, owner, "Kinoru Apartments")
    # A repeated unit number
    repeated = client.post("/quick-setup/building", json={"new_property": {"name": "New Block"}, "groups": [{"labels": "A1-A3, A2"}]}, headers=owner).json()
    assert repeated["ok"] is False and any("A2" in problem for problem in repeated["problems"])
    # A building with a name that is already taken
    taken = client.post("/quick-setup/building", json={"new_property": {"name": "kinoru apartments"}, "groups": [{"labels": "A1-A3"}]}, headers=owner).json()
    assert taken["ok"] is False and any("already have a building" in problem for problem in taken["problems"])
    # A building and a new building at the same time is refused
    both = client.post("/quick-setup/preview", json={"property_id": 1, "new_property": {"name": "Other"}, "groups": [{"labels": "A1"}]}, headers=owner)
    assert both.status_code == 422
    assert len(client.get("/properties", headers=owner).json()) == 1


def test_nobody_can_add_units_to_someone_elses_building(client):
    owner = make_owner(client)
    property_id = make_property(client, owner)
    other = make_owner(client, "other@example.com")
    body = {"property_id": property_id, "groups": [{"labels": "Z1-Z3"}]}
    assert client.post("/quick-setup/preview", json=body, headers=other).status_code == 404
    assert client.post("/quick-setup/building", json=body, headers=other).status_code == 404
    assert client.post("/quick-setup/building", json={"property_id": 9999, "groups": [{"labels": "A1"}]}, headers=other).status_code == 404


def test_the_unit_limit_set_by_the_admin_is_respected(client):
    owner = make_owner(client)
    owner_id = client.get("/auth/me", headers=owner).json()["id"]
    with SessionLocal() as db:
        db.add(OwnerAccount(owner_id=owner_id, plan="paid", status="active", unit_limit=5))
        db.commit()
    too_many = client.post("/quick-setup/building", json={"new_property": {"name": "Big Block"}, "groups": [{"labels": "A1-A6"}]}, headers=owner).json()
    assert too_many["ok"] is False and any("plan allows 5" in problem for problem in too_many["problems"])
    assert client.get("/properties", headers=owner).json() == []
    just_right = client.post("/quick-setup/building", json={"new_property": {"name": "Big Block"}, "groups": [{"labels": "A1-A5"}]}, headers=owner).json()
    assert just_right["ok"] is True and just_right["created"] == 5


def test_only_landlords_can_use_quick_setup(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    _, john = make_caretaker(client, owner, [business["property_id"]])
    tenant = sign_in_tenant(client, owner, business["tenant_id"])
    body = {"new_property": {"name": "Sneaky Block"}, "groups": [{"labels": "A1-A3"}]}
    for headers in (john, tenant):
        assert client.post("/quick-setup/preview", json=body, headers=headers).status_code == 403
        assert client.post("/quick-setup/building", json=body, headers=headers).status_code == 403
    assert client.post("/quick-setup/preview", json=body).status_code == 401


def test_setting_up_a_building_is_logged_but_previews_are_not(client):
    owner = make_owner(client)
    body = two_kinds()
    client.post("/quick-setup/preview", json=body, headers=owner)
    client.post("/quick-setup/building", json=body, headers=owner)
    summaries = [item["summary"] for item in client.get("/account/activity", headers=owner).json()["items"]]
    assert "Set up a building with its units" in summaries
    assert not any(summary.startswith("POST /quick-setup") for summary in summaries)


def test_tenant_rows_can_leave_the_rent_empty_when_the_unit_has_one(client):
    owner = make_owner(client)
    client.post("/quick-setup/building", json={"new_property": {"name": "Kinoru Apartments"}, "groups": [{"labels": "A1-A2", "rent_amount": 7000}]}, headers=owner)
    row = {"property_name": "Kinoru Apartments", "unit_number": "A1", "tenant_name": "Samuel Otieno", "phone": "0722 111 222"}
    check = client.post("/onboarding/existing-tenants", json={"rows": [row], "dry_run": True}, headers=owner).json()
    assert check["ok"] is True and check["results"][0]["new_unit"] is False
    done = client.post("/onboarding/existing-tenants", json={"rows": [row], "dry_run": False}, headers=owner).json()
    assert done["imported"] == 1
    lease = client.get("/leases", headers=owner).json()[0]
    assert lease["rent_amount"] == 7000
    # A brand new unit still needs a rent
    new_unit = {"property_name": "Kinoru Apartments", "unit_number": "Z9", "tenant_name": "Lucy Achieng", "phone": "0733 222 333"}
    result = client.post("/onboarding/existing-tenants", json={"rows": [new_unit], "dry_run": True}, headers=owner).json()
    assert result["ok"] is False and "Rent amount is needed" in result["results"][0]["message"]


def test_a_unit_with_no_rent_set_needs_the_rent_in_the_list(client):
    owner = make_owner(client)
    client.post("/quick-setup/building", json={"new_property": {"name": "Kinoru Apartments"}, "groups": [{"labels": "A1"}]}, headers=owner)
    row = {"property_name": "Kinoru Apartments", "unit_number": "A1", "tenant_name": "Samuel Otieno", "phone": "0722 111 222"}
    result = client.post("/onboarding/existing-tenants", json={"rows": [row], "dry_run": True}, headers=owner).json()
    assert result["ok"] is False and "No rent is set" in result["results"][0]["message"]


def test_a_misspelled_building_name_gets_a_hint(client):
    owner = make_owner(client)
    make_property(client, owner, "Kinoru Apartments")
    row = {"property_name": "Kinoru Apartment", "unit_number": "A1", "tenant_name": "Samuel Otieno", "phone": "0722 111 222", "rent_amount": "6000"}
    result = client.post("/onboarding/existing-tenants", json={"rows": [row], "dry_run": True}, headers=owner).json()
    assert result["ok"] is False
    assert "Did you mean 'Kinoru Apartments'" in result["results"][0]["message"]