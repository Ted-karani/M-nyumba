# create_admin.py - makes the admin account (run it once, on the computer or server you want it on)

# Import the tools we need
import getpass
import sys

# Import our own files
import models
import security
from database import SessionLocal
from portal_models import TENANT_EMAIL_DOMAIN
from routers.account import validate_new_password

# We need exactly one email after the file name
if len(sys.argv) != 2:
    print("Use it like this: python3 create_admin.py your@email.com")
    sys.exit(1)

# Tidy up the email
email = sys.argv[1].strip().lower()
if "@" not in email or email.endswith("@" + TENANT_EMAIL_DOMAIN):
    print("That does not look like a usable email address.")
    sys.exit(1)

# Open a conversation with the database
db = SessionLocal()
try:
    # Never turn an existing account into an admin by accident
    if db.query(models.User).filter(models.User.email == email).first() is not None:
        print("An account with that email already exists. Use a different email for the admin.")
        sys.exit(1)
    # Ask for the details (the password is not shown while you type)
    name = input("Your full name: ").strip() or "Site Admin"
    password = getpass.getpass("Choose a password (at least 12 characters): ")
    if len(password) < 12:
        print("The password must be at least 12 characters.")
        sys.exit(1)
    if password != getpass.getpass("Type it again: "):
        print("The two passwords are not the same.")
        sys.exit(1)
    # The same checks every password goes through
    try:
        validate_new_password(password, email)
    except Exception as error:
        print(getattr(error, "detail", error))
        sys.exit(1)
    # Make the admin
    db.add(models.User(full_name=name, email=email, password_hash=security.hash_password(password), role="admin", is_active=True))
    db.commit()
    print("Done. Sign in with that email, then turn on 2-step login when the page asks you to.")
finally:
    # Always close the conversation
    db.close()