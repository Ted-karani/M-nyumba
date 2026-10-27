# Import the file we are testing
import monitoring


def test_error_reports_never_carry_secrets_or_personal_data():
    event = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/payments/callback/SECRETVALUE?x=1",
            "data": {"password": "hunter2"},
            "headers": {"Authorization": "Bearer abc"},
        },
        "user": {"email": "a@b.com"},
        "breadcrumbs": {"values": [{"message": "Paid SJK4L2M9QP"}]},
        "extra": {"phone": "0711"},
        "contexts": {"data": "private"},
    }
    cleaned = monitoring.clean_event(event, {})
    text = str(cleaned)
    for private in ["SECRETVALUE", "hunter2", "Bearer", "a@b.com", "SJK4L2M9QP", "0711", "private"]:
        assert private not in text
    assert cleaned["request"]["method"] == "POST"


def test_secret_web_addresses_are_hidden():
    assert monitoring.hide_secrets("/public/listings/TOKEN123/photos/4?x=1") == "/public/listings/[hidden]/photos/4"
    assert monitoring.hide_secrets("https://api.example.com/share/TOKEN123") == "https://api.example.com/share/[hidden]"
    assert monitoring.hide_secrets("/properties/5") == "/properties/5"