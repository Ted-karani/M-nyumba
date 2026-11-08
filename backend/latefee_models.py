# latefee_models.py - a landlord's late fee rule, and a record of every fee that was applied or waived

# Import the date and time tool
from datetime import datetime
# Import the column types we need for the tables
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

# Import our own files
from database import Base


# This class is the "late_fee_settings" table. Each landlord has at most one row.
class LateFeeSettings(Base):
    # The name of the table inside the database
    __tablename__ = "late_fee_settings"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    # Are late fees switched on?
    enabled = Column(Boolean, nullable=False, default=False)
    # How many days after the due date the rent may still be paid without a fee
    grace_days = Column(Integer, nullable=False, default=5)
    # "flat" (a fixed amount) or "percent" (a share of that month's rent)
    kind = Column(String, nullable=False, default="flat")
    # The flat amount in shillings, or the percentage
    amount = Column(Float, nullable=False, default=500)
    # Only rent for this month and later gets fees, like "2026-11" (so old months are never charged by surprise)
    start_period = Column(String, nullable=True)
    # When it was last changed
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# This class is the "late_fee_log" table. Each fee that was applied or waived is one row.
class LateFeeLog(Base):
    # The name of the table inside the database
    __tablename__ = "late_fee_log"
    # Rule: a month's rent can only be decided once for each lease
    __table_args__ = (UniqueConstraint("lease_id", "period", name="one_decision_per_month"),)

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # The tenancy (points to the leases table)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    # The month of rent it is about, like "2026-10"
    period = Column(String, nullable=False)
    # "applied" (a fee was added) or "waived" (the landlord decided no fee)
    action = Column(String, nullable=False)
    # The fee in shillings
    amount = Column(Integer, nullable=False, default=0)
    # The charge that was added (empty once it is waived)
    charge_id = Column(Integer, ForeignKey("charges.id"), nullable=True)
    # When it happened
    created_at = Column(DateTime, default=datetime.utcnow)