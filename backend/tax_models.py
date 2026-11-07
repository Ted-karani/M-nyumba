# tax_models.py - a landlord's tax settings, and a record of the months they have filed with KRA

# Import the date and time tool
from datetime import datetime
# Import the column types we need for the tables
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

# Import our own files
from database import Base
from taxrules import DEFAULT_RATE


# This class is the "tax_settings" table. Each landlord has at most one row.
class TaxSettings(Base):
    # The name of the table inside the database
    __tablename__ = "tax_settings"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # Is the landlord a Kenyan tax resident? (this simple tax is only for residents)
    resident = Column(Boolean, nullable=False, default=True)
    # The tax rate in percent
    rate_percent = Column(Float, nullable=False, default=DEFAULT_RATE)
    # How each building is treated, written as text like {"12": "commercial"}
    property_treatments = Column(Text, nullable=False, default="{}")
    # When it was last changed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# This class is the "tax_filings" table. Each month a landlord has filed and paid is one row.
class TaxFiling(Base):
    # The name of the table inside the database
    __tablename__ = "tax_filings"
    # Rule: a month can only be filed once
    __table_args__ = (UniqueConstraint("owner_id", "period", name="one_filing_per_month"),)

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The month of rent it covers, like "2026-10"
    period = Column(String, nullable=False)
    # The tax we calculated when it was marked as filed
    tax_due = Column(Integer, nullable=False, default=0)
    # What the landlord actually paid KRA
    amount_paid = Column(Integer, nullable=False)
    # The day they paid
    paid_on = Column(Date, nullable=False)
    # The reference or receipt number from KRA
    reference = Column(String, nullable=True)
    # A short note
    note = Column(String, nullable=True)
    # When it was recorded
    created_at = Column(DateTime, default=datetime.utcnow)