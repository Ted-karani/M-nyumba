# Import the date tools
from datetime import date, timedelta

# A password that passes all our password rules
PASSWORD = "Kenya-Rent-77"


# Create an owner account
def register(client, email, name="Test Person", password=PASSWORD):
    response = client.post("/auth/register", json={"full_name": name, "email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


# Sign in, and return the header that proves who we are
def sign_in(client, email, password=PASSWORD):
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


# Create an owner account and sign in
def make_owner(client, email="owner@example.com"):
    register(client, email, "Owner One")
    return sign_in(client, email)


# Add a property
def make_property(client, headers, name="Kinoru Apartments"):
    response = client.post("/properties", json={"name": name, "county": "Meru"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# Add a unit
def make_unit(client, headers, property_id, number="A1", rent=8000, deposit=8000):
    response = client.post(
        f"/properties/{property_id}/units",
        json={"unit_number": number, "unit_type": "Bedsitter", "rent_amount": rent, "deposit_amount": deposit},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# Add a tenant
def make_tenant(client, headers, name="Mercy Wambui", phone="0711 000 111", id_number=None):
    body = {"full_name": name, "phone": phone}
    if id_number:
        body["id_number"] = id_number
    response = client.post("/tenants", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# Move a tenant into a unit
def move_in(client, headers, unit_id, tenant_id, start=None):
    body = {"unit_id": unit_id, "tenant_id": tenant_id, "start_date": (start or date.today()).isoformat()}
    response = client.post("/leases", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# Record a payment (the caller checks the answer)
def pay(client, headers, lease_id, amount, method="cash", reference=None, paid_on=None):
    body = {"amount": amount, "paid_on": (paid_on or date.today()).isoformat(), "method": method}
    if reference:
        body["reference"] = reference
    return client.post(f"/leases/{lease_id}/payments", json=body, headers=headers)


# Make a whole little business: a property, a unit, a tenant, and a running lease
def make_business(client, headers, rent=8000, deposit=8000, start=None):
    property_id = make_property(client, headers)
    unit_id = make_unit(client, headers, property_id, rent=rent, deposit=deposit)
    tenant_id = make_tenant(client, headers)
    lease = move_in(client, headers, unit_id, tenant_id, start=start)
    return {"property_id": property_id, "unit_id": unit_id, "tenant_id": tenant_id, "lease": lease}


# Create a caretaker for some properties, and sign them in
def make_caretaker(client, owner_headers, property_ids, email="john@example.com"):
    response = client.post(
        "/caretakers",
        json={"full_name": "John Mutua", "email": email, "password": PASSWORD, "property_ids": property_ids},
        headers=owner_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], sign_in(client, email)


# How many whole months lie between two dates
def months_between(start, end):
    return (end.year * 12 + end.month) - (start.year * 12 + start.month)


# A date some days in the past
def days_ago(days):
    return date.today() - timedelta(days=days)