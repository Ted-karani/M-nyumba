# settlement_models.py - a move-out settlement: the deposit, what is deducted, and the refund

# Import the date and time tool
from datetime import datetime
# Import the column types we need for the table
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text

# Import our own files
from database import Base


# This class is the "deposit_settlements" table. Each tenant who moved out has at most one settlement.
class DepositSettlement(Base):
    # The name of the table inside the database
    __tablename__ = "deposit_settlements"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # The tenancy that ended (points to the leases table). Each tenancy has one settlement.
    lease_id = Column(Integer, ForeignKey("leases.id"), unique=True, nullable=False)
    # "draft" (still being worked on) or "final" (the numbers are frozen)
    status = Column(String, nullable=False, default="draft")
    # The deposit the landlord holds
    deposit_held = Column(Integer, nullable=False, default=0)
    # Rent, bills and fees still owing when it was saved
    unpaid_charges = Column(Integer, nullable=False, default=0)
    # Money the tenant paid ahead
    credit = Column(Integer, nullable=False, default=0)
    # The deductions, written as text like [{"label": "Repainting", "amount": 1500}]
    deductions = Column(Text, nullable=False, default="[]")
    # All the deductions added up
    total_deductions = Column(Integer, nullable=False, default=0)
    # What goes back to the tenant, or what they still owe (one of the two is zero)
    refund_due = Column(Integer, nullable=False, default=0)
    tenant_owes = Column(Integer, nullable=False, default=0)
    # A note on the statement
    notes = Column(String, nullable=True)
    # The refund, once it has been paid
    refund_amount = Column(Integer, nullable=True)
    refund_method = Column(String, nullable=True)
    refund_reference = Column(String, nullable=True)
    refunded_on = Column(Date, nullable=True)
    refund_note = Column(String, nullable=True)
    # When the numbers were frozen
    finalized_at = Column(DateTime, nullable=True)
    # When it was made, and last changed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)