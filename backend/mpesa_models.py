# mpesa_models.py - the table that remembers every M-Pesa payment request

# Import the date and time tool so we can record when things happen
from datetime import datetime
# Import the column types we need for the table
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
# Import the Base class from our database file
from database import Base


# This class is the "mpesa_requests" table. Each payment prompt we send is one row.
class MpesaRequest(Base):
    # The name of the table inside the database
    __tablename__ = "mpesa_requests"

    # A unique number for each request, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The lease this payment is for (points to the leases table)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    # The phone number that got the prompt, like 254712345678
    phone = Column(String, nullable=False)
    # The amount we asked for, in shillings
    amount = Column(Integer, nullable=False)
    # Safaricom's id for this request (this is how we match the result when it comes back)
    checkout_request_id = Column(String, unique=True, index=True, nullable=False)
    # Safaricom's second id for this request
    merchant_request_id = Column(String, nullable=True)
    # Where it stands: "pending", "paid", "cancelled", or "failed"
    status = Column(String, nullable=False, default="pending")
    # The message Safaricom sent with the result
    result_desc = Column(String, nullable=True)
    # The M-Pesa code (like SJK4L2M9QP), filled in once it is paid
    receipt = Column(String, nullable=True)
    # The user who asked for the payment (points to the users table)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The date and time the request was sent
    created_at = Column(DateTime, default=datetime.utcnow)
    # The date and time the result came back
    completed_at = Column(DateTime, nullable=True)