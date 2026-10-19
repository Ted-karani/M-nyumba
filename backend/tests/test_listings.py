# Import the pieces we need
from helpers import make_business, make_caretaker, make_owner, make_property, make_tenant, make_unit, move_in

# A tiny file that starts like a real PNG picture
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


# Make an empty unit with a listing, and return what we need
def make_listing(client, owner, **extra):
    property_id = make_property(client, owner)
    unit_id = make_unit(client, owner, property_id, "B1", rent=7000, deposit=7000)
    body = {"unit_id": unit_id, "title": "Bedsitter near the stage", "contact_phone": "0711 000 111", **extra}
    response = client.post("/listings", json=body, headers=owner)
    assert response.status_code == 201, response.text
    return response.json(), unit_id, property_id


def test_only_empty_units_can_be_listed_and_only_once(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    # The unit with a tenant cannot be listed
    taken = client.post("/listings", json={"unit_id": business["unit_id"]}, headers=owner)
    assert taken.status_code == 400
    # An empty one can, but only once
    empty = make_unit(client, owner, business["property_id"], "A2")
    assert client.post("/listings", json={"unit_id": empty}, headers=owner).status_code == 201
    assert client.post("/listings", json={"unit_id": empty}, headers=owner).status_code == 400


def test_a_headline_is_written_when_none_is_given(client):
    owner = make_owner(client)
    property_id = make_property(client, owner)
    unit_id = make_unit(client, owner, property_id, "B1")
    made = client.post("/listings", json={"unit_id": unit_id}, headers=owner).json()
    assert "for rent in" in made["title"]


def test_the_public_page_shows_no_private_details(client):
    owner = make_owner(client)
    business = make_business(client, owner)
    tenant_name = "Mercy Wambui"
    empty = make_unit(client, owner, business["property_id"], "A2")
    listing = client.post("/listings", json={"unit_id": empty, "title": "Bedsitter A2", "contact_phone": "0711 000 111"}, headers=owner).json()
    # No login needed
    page = client.get(f"/public/listings/{listing['token']}")
    assert page.status_code == 200
    data = page.json()
    assert data["rent_amount"] == 8000 and data["available"] is True
    assert data["contact_phone"] == "254711000111"
    # The tenant's name and the building's name are not there
    assert tenant_name not in page.text
    assert data["property_name"] is None
    # The owner can choose to show the building
    assert client.put(f"/listings/{listing['id']}", json={"show_exact_address": True}, headers=owner).status_code == 200
    assert client.get(f"/public/listings/{listing['token']}").json()["property_name"] == "Kinoru Apartments"


def test_a_hidden_listing_is_not_available_and_can_come_back(client):
    owner = make_owner(client)
    listing, _, _ = make_listing(client, owner)
    assert client.put(f"/listings/{listing['id']}", json={"is_active": False}, headers=owner).json()["state"] == "hidden"
    assert client.get(f"/public/listings/{listing['token']}").status_code == 404
    assert client.put(f"/listings/{listing['id']}", json={"is_active": True}, headers=owner).status_code == 200
    assert client.get(f"/public/listings/{listing['token']}").status_code == 200


def test_the_page_says_taken_once_a_tenant_moves_in(client):
    owner = make_owner(client)
    listing, unit_id, _ = make_listing(client, owner)
    tenant_id = make_tenant(client, owner)
    move_in(client, owner, unit_id, tenant_id)
    assert client.get(f"/public/listings/{listing['token']}").json()["available"] is False
    overview = client.get("/listings", headers=owner).json()
    assert overview["listings"][0]["state"] == "taken"


def test_a_new_link_kills_the_old_one(client):
    owner = make_owner(client)
    listing, _, _ = make_listing(client, owner)
    fresh = client.post(f"/listings/{listing['id']}/regenerate-link", headers=owner).json()
    assert fresh["token"] != listing["token"]
    assert client.get(f"/public/listings/{listing['token']}").status_code == 404
    assert client.get(f"/public/listings/{fresh['token']}").status_code == 200


def test_other_owners_and_caretakers_cannot_touch_listings(client):
    owner = make_owner(client)
    other = make_owner(client, "other@example.com")
    listing, _, property_id = make_listing(client, owner)
    assert client.put(f"/listings/{listing['id']}", json={"title": "Hijacked"}, headers=other).status_code == 404
    assert client.delete(f"/listings/{listing['id']}", headers=other).status_code == 404
    assert client.post(f"/listings/{listing['id']}/regenerate-link", headers=other).status_code == 404
    assert client.get("/listings", headers=other).json()["listings"] == []
    # Another owner cannot make a listing for a unit that is not theirs
    some_unit = client.get(f"/properties/{property_id}/units", headers=owner).json()[0]["id"]
    assert client.post("/listings", json={"unit_id": some_unit}, headers=other).status_code == 404
    # Caretakers are refused
    _, john = make_caretaker(client, owner, [property_id])
    assert client.get("/listings", headers=john).status_code == 403


def test_the_share_page_is_safe_and_has_a_preview_card(client):
    owner = make_owner(client)
    listing, _, _ = make_listing(client, owner, title="<script>alert(1)</script> Bedsitter")
    share = client.get(f"/share/{listing['token']}")
    assert share.status_code == 200
    # What people typed is made safe, and the preview card tags are there
    assert "<script>alert(1)" not in share.text
    assert "&lt;script&gt;" in share.text
    assert 'property="og:title"' in share.text
    # A link that does not exist
    assert client.get("/share/not-a-real-code").status_code == 404


def test_listing_photos_are_checked_and_limited(client, tmp_path, monkeypatch):
    from routers import listings

    # Keep the test files in a throwaway folder
    monkeypatch.setattr(listings, "UPLOAD_DIR", tmp_path)
    owner = make_owner(client)
    listing, _, _ = make_listing(client, owner)
    url = f"/listings/{listing['id']}/photos"
    # A text file pretending to be a picture, and a document
    assert client.post(url, files={"file": ("fake.jpg", b"this is not a picture", "image/jpeg")}, headers=owner).status_code == 400
    assert client.post(url, files={"file": ("deed.pdf", b"%PDF-1.4 test", "application/pdf")}, headers=owner).status_code == 400
    # A real picture is accepted, and anyone with the link can see it
    good = client.post(url, files={"file": ("one.png", PNG, "image/png")}, headers=owner)
    assert good.status_code == 201
    photo_id = good.json()["id"]
    shown = client.get(f"/public/listings/{listing['token']}/photos/{photo_id}")
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/png"
    # But not with a wrong code, or for a photo that does not exist
    assert client.get(f"/public/listings/wrong-code/photos/{photo_id}").status_code == 404
    assert client.get(f"/public/listings/{listing['token']}/photos/9999").status_code == 404
    # The 11th photo is refused
    for _ in range(9):
        assert client.post(url, files={"file": ("more.png", PNG, "image/png")}, headers=owner).status_code == 201
    assert client.post(url, files={"file": ("last.png", PNG, "image/png")}, headers=owner).status_code == 400
    # Files are stored under random names
    assert all(path.name != "one.png" for path in tmp_path.iterdir())


def test_views_are_counted(client):
    owner = make_owner(client)
    listing, _, _ = make_listing(client, owner)
    client.get(f"/public/listings/{listing['token']}")
    client.get(f"/public/listings/{listing['token']}")
    assert client.get("/listings", headers=owner).json()["listings"][0]["views"] == 2