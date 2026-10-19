# Import the date and time tool
from datetime import datetime
# Import the column types we need for the tables
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text

# Import the Base class from our database file
from database import Base

# Tenants sign in with their phone number, which we turn into a hidden email-style name ending with this
TENANT_EMAIL_DOMAIN = "tenants.mnyumba.app"


# Turn a phone number like 254711000111 into the hidden login name for a tenant
def tenant_email(phone: str) -> str:
    return f"{phone}@{TENANT_EMAIL_DOMAIN}"


# This class is the "tenant_accounts" table. Each row links a tenant to their portal login.
class TenantAccount(Base):
    # The name of the table inside the database
    __tablename__ = "tenant_accounts"

    # A unique number for each account, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The tenant this login belongs to (points to the tenants table, one login per tenant)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    # The login itself (points to the users table, each login can only be linked once)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # The landlord who gave the access (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # True until the tenant has chosen their own password
    must_change_password = Column(Boolean, nullable=False, default=True)
    # The date and time the access was given
    created_at = Column(DateTime, default=datetime.utcnow)


# This class is the "owner_settings" table. It holds what an owner wants tenants to know about paying.
class OwnerSettings(Base):
    # The name of the table inside the database
    __tablename__ = "owner_settings"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner it is about (each owner has one row)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # The Paybill or Till number
    paybill_number = Column(String, nullable=True)
    # What to type as the account, like "Your unit number"
    account_hint = Column(String, nullable=True)
    # Any other words for tenants about paying
    instructions = Column(Text, nullable=True)
    # When it was last changed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# This class is the "notices" table. Each announcement to tenants is one row.
class Notice(Base):
    # The name of the table inside the database
    __tablename__ = "notices"

    # A unique number for each notice, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner who posted it (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The property it is for (empty means all of the owner's properties)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    # The headline
    title = Column(String, nullable=False)
    # The message
    body = Column(Text, nullable=False)
    # Pinned notices stay at the top
    pinned = Column(Boolean, nullable=False, default=False)
    # The last day it is shown (empty means it never expires)
    expires_on = Column(Date, nullable=True)
    # The date and time it was posted, and last changed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)