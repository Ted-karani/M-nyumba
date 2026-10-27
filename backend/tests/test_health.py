def test_the_health_addresses_answer_both_kinds_of_visit(client):
    # A normal visit, and the lighter "are you alive?" visit that monitors often use
    assert client.get("/health").status_code == 200
    assert client.head("/health").status_code == 200
    assert client.get("/health/db").status_code == 200
    assert client.head("/health/db").status_code == 200