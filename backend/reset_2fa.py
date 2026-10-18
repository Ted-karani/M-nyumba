# Import the tool that reads what was typed after the file name
import sys

# Import our own files
from database import SessionLocal
import models
from security_models import UserTotp

# We need exactly one email
if len(sys.argv) != 2:
    print("Use it like this: python3 reset_2fa.py their@email.com")
    sys.exit(1)

# Open a conversation with the database
db = SessionLocal()
try:
    # Find the person
    user = db.query(models.User).filter(models.User.email == sys.argv[1].lower()).first()
    if user is None:
        print("No account has that email.")
        sys.exit(1)
    # Remove their 2-step login settings
    removed = db.query(UserTotp).filter(UserTotp.user_id == user.id).delete()
    db.commit()
    print("2-step login was turned off for that account." if removed else "That account did not have 2-step login on.")
finally:
    # Always close the conversation
    db.close()