# Import the date and time tool
from datetime import datetime
# Import the column types we need for the tables
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

# Import the Base class from our database file
from database import Base
# Import the column type that scrambles text before it is stored
from encryption import EncryptedText


# This class is the "user_security" table. It remembers when each person last changed their password.
class UserSecurity(Base):
    # The name of the table inside the database
    __tablename__ = "user_security"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The user it is about (each user has one row)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # When their password was last changed (older logins stop working)
    password_changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# This class is the "user_totp" table. It holds the settings for each person's 2-step login.
class UserTotp(Base):
    # The name of the table inside the database
    __tablename__ = "user_totp"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The user it is about (each user has one row)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # The secret shared with their authenticator app (scrambled in the database)
    secret = Column(EncryptedText, nullable=False)
    # True once they have proved the app works and turned 2-step login on
    enabled = Column(Boolean, nullable=False, default=False)
    # The newest code we accepted (so the same code cannot be used twice)
    last_counter = Column(Integer, nullable=False, default=0)
    # The recovery codes, kept as scrambled hashes (a list written as text)
    recovery_hashes = Column(Text, nullable=True)
    # When the row was made
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # When 2-step login was turned on
    enabled_at = Column(DateTime, nullable=True)


# This class is the "login_attempts" table. Each time someone tries to sign in is one row.
class LoginAttempt(Base):
    # The name of the table inside the database
    __tablename__ = "login_attempts"

    # A unique number for each attempt, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The email that was typed (in lowercase)
    email = Column(String, nullable=False, index=True)
    # The address the attempt came from
    ip = Column(String, nullable=True, index=True)
    # True if the password was right
    success = Column(Boolean, nullable=False, default=False)
    # When it happened
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


# This class is the "audit_logs" table. Each change somebody made is one row.
class AuditLog(Base):
    # The name of the table inside the database
    __tablename__ = "audit_logs"

    # A unique number for each entry, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner whose business this change belongs to (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # The person who made the change (points to the users table)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Their name at that time (kept here so it never changes)
    actor_name = Column(String, nullable=False)
    # Their role at that time: "owner" or "caretaker"
    actor_role = Column(String, nullable=False)
    # What they did, in words
    summary = Column(String, nullable=False)
    # The kind of request, like "POST"
    method = Column(String, nullable=True)
    # The address of the request, like "/leases/4/payments"
    path = Column(String, nullable=True)
    # The address the request came from
    ip = Column(String, nullable=True)
    # When it happened
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


# Remember that a person's password changed just now (the caller saves the change to the database)
def mark_password_changed(db, user_id: int):
    # Find their row, if they have one
    row = db.query(UserSecurity).filter(UserSecurity.user_id == user_id).first()
    if row is None:
        # First time: make a row
        db.add(UserSecurity(user_id=user_id, password_changed_at=datetime.utcnow()))
    else:
        # Otherwise update the time
        row.password_changed_at = datetime.utcnow()