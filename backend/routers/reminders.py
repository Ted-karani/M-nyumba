# Import the tool that groups things together
from collections import defaultdict
# Import the date and time tools
from datetime import datetime, timedelta
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints
from fastapi import APIRouter, Depends
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the column types we need for the table
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from database import Base
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.leases import get_owned_lease
from routers.properties import require_owner

# Make a group of endpoints that all start with /reminders
router = APIRouter(prefix="/reminders", tags=["Reminders"])


# This class is the "reminder_logs" table. Each reminder that was sent is one row.
class ReminderLog(Base):
    # The name of the table inside the database
    __tablename__ = "reminder_logs"

    # A unique number for each reminder, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The lease the reminder was about (points to the leases table)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    # The tenant who was reminded (points to the tenants table)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    # How it was sent (for now only "whatsapp")
    channel = Column(String, nullable=False, default="whatsapp")
    # How much was overdue at the time
    amount_overdue = Column(Integer, nullable=False, default=0)
    # The exact message that was sent
    message = Column(Text, nullable=False)
    # The user who sent it (points to the users table)
    sent_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The date and time it was sent
    created_at = Column(DateTime, default=datetime.utcnow)


# The data we ask for when recording a reminder
class ReminderCreate(BaseModel):
    # The lease the reminder is about
    lease_id: int
    # The exact message
    message: str = Field(min_length=1, max_length=2000)
    # How much was overdue
    amount_overdue: int = Field(default=0, ge=0)
    # How it was sent
    channel: Literal["whatsapp"] = "whatsapp"


# The data we send back about a recorded reminder
class ReminderOut(BaseModel):
    # The reminder's id
    id: int
    # The lease it was about
    lease_id: int
    # When it was sent
    created_at: datetime

    # Lets this class read data straight from our database objects
    model_config = {"from_attributes": True}


# When a lease was last reminded, and how often in the last 30 days
class ReminderSummaryItem(BaseModel):
    # The lease's id
    lease_id: int
    # When the latest reminder was sent
    last_sent_at: datetime
    # How many reminders were sent in the last 30 days
    times_30_days: int


# Record that a reminder was sent
@router.post("", response_model=ReminderOut, status_code=201)
def create_reminder(
    data: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can send reminders
    require_owner(current_user)
    # Make sure the lease is theirs
    lease = get_owned_lease(db, data.lease_id, current_user)
    # Build the record, noting who sent it
    log = ReminderLog(
        lease_id=lease.id,
        tenant_id=lease.tenant_id,
        channel=data.channel,
        amount_overdue=data.amount_overdue,
        message=data.message.strip(),
        sent_by_id=current_user.id,
    )
    # Save it to the database
    db.add(log)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(log)
    # Send it back
    return log


# Show, for each lease, when it was last reminded (looking back 90 days)
@router.get("/summary", response_model=list[ReminderSummaryItem])
def reminder_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see reminders
    require_owner(current_user)
    # Look back 90 days
    now = datetime.utcnow()
    since = now - timedelta(days=90)
    # Get this owner's reminders from then
    rows = (
        db.query(ReminderLog.lease_id, ReminderLog.created_at)
        .join(models.Lease, ReminderLog.lease_id == models.Lease.id)
        .join(models.Unit, models.Lease.unit_id == models.Unit.id)
        .join(models.Property, models.Unit.property_id == models.Property.id)
        .filter(models.Property.owner_id == current_user.id, ReminderLog.created_at >= since)
        .all()
    )
    # Find the latest reminder for each lease, and count the ones from the last 30 days
    month_ago = now - timedelta(days=30)
    latest = {}
    counts = defaultdict(int)
    for lease_id, created_at in rows:
        if lease_id not in latest or created_at > latest[lease_id]:
            latest[lease_id] = created_at
        if created_at >= month_ago:
            counts[lease_id] += 1
    # Send it all back
    return [
        ReminderSummaryItem(lease_id=lease_id, last_sent_at=last, times_30_days=counts[lease_id])
        for lease_id, last in latest.items()
    ]