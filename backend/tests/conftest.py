# Import the tools we need
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# If TEST_DATABASE_URL is set, the tests run on that database (like a local PostgreSQL). Otherwise they use a throwaway SQLite file.
_folder = tempfile.mkdtemp(prefix="mnyumba-tests-")
_test_url = os.environ.get("TEST_DATABASE_URL")
if _test_url:
    # Safety: the tests erase everything in the database, so its name must contain the word "test"
    _name = _test_url.rsplit("/", 1)[-1].split("?")[0].lower()
    if "test" not in _name:
        raise RuntimeError("TEST_DATABASE_URL must point to a database whose name contains 'test'. The tests erase everything in it.")

# Use throwaway settings, so the tests never touch your real data.
# These settings must be made BEFORE the app is imported below.
os.environ["DATABASE_URL"] = _test_url or f"sqlite:///{Path(_folder) / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-real-use"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
# Scrambling passwords is slow on purpose, so the tests use a small number to run fast
os.environ["BCRYPT_ROUNDS"] = "4"

# Pin every setting that could change how the tests behave, so a value in your .env file can never leak into them
os.environ["ALLOW_REGISTRATION"] = "true"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["ENVIRONMENT"] = "test"
os.environ["IP_LIMIT"] = "on"
os.environ["TERMS_ENFORCED"] = "false"
os.environ["MPESA_TRUST_CALLBACK"] = "false"
os.environ["SENTRY_DSN"] = ""
# The tests must never be able to reach Safaricom with your real keys (the M-Pesa tests set their own pretend ones)
for _name in [
    "MPESA_CONSUMER_KEY",
    "MPESA_CONSUMER_SECRET",
    "MPESA_SHORTCODE",
    "MPESA_PASSKEY",
    "MPESA_CALLBACK_URL",
    "MPESA_CALLBACK_SECRET",
    "MPESA_OWNER_EMAILS",
]:
    os.environ[_name] = ""

from fastapi.testclient import TestClient  # noqa: E402

from database import Base, engine  # noqa: E402
from main import app  # noqa: E402


# Before every test, start with a completely empty database
@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


# A pretend web browser that talks to the app
@pytest.fixture
def client():
    return TestClient(app)