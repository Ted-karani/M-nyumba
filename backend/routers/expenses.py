# Import the date and time tools
from datetime import date, datetime
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the column types and the tool that adds up numbers
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from database import Base
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.properties import get_owned_property, require_owner

# Make a group of endpoints that all start with /expenses
router = APIRouter(prefix="/expenses", tags=["Expenses"])

# The shape a month must have, like "2026-10"
PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
# The kinds of expense we know about
CATEGORIES = Literal["caretaker", "security", "cleaning", "taxes", "insurance", "licences", "utilities", "supplies", "other"]


# This class is the "expenses" table. Each amount spent is one row.
class Expense(Base):
    # The name of the table inside the database
    __tablename__ = "expenses"

    # A unique number for each expense, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner this expense belongs to (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The property it was spent on (empty means "general", for all properties)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    # What kind of expense it is
    category = Column(String, nullable=False)
    # The amount in shillings
    amount = Column(Integer, nullable=False)
    # The date the money was spent
    spent_on = Column(Date, nullable=False)
    # A short note
    description = Column(Text, nullable=True)
    # Who was paid
    paid_to = Column(String, nullable=True)
    # The user who recorded it (points to the users table)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # The date and time it was recorded
    created_at = Column(DateTime, default=datetime.utcnow)


# The data we ask for when recording an expense
class ExpenseCreate(BaseModel):
    # The property it was spent on (leave empty for "general")
    property_id: int | None = None
    # What kind of expense it is
    category: CATEGORIES
    # The amount in shillings (must be more than zero)
    amount: int = Field(gt=0, le=100000000)
    # The date the money was spent
    spent_on: date
    # A short note (optional)
    description: str | None = Field(default=None, max_length=300)
    # Who was paid (optional)
    paid_to: str | None = Field(default=None, max_length=120)


# The data we accept when editing an expense (every field is optional, send only what changed)
class ExpenseUpdate(BaseModel):
    # The property (send null to make it "general")
    property_id: int | None = None
    # New kind
    category: CATEGORIES | None = None
    # New amount
    amount: int | None = Field(default=None, gt=0, le=100000000)
    # New date
    spent_on: date | None = None
    # New note
    description: str | None = Field(default=None, max_length=300)
    # New "paid to"
    paid_to: str | None = Field(default=None, max_length=120)


# The data we send back about an expense
class ExpenseOut(BaseModel):
    # The expense's id
    id: int
    # The property's id (empty for "general")
    property_id: int | None
    # The property's name (empty for "general")
    property_name: str | None
    # What kind of expense it is
    category: str
    # The amount
    amount: int
    # The date it was spent
    spent_on: date
    # The note
    description: str | None
    # Who was paid
    paid_to: str | None
    # The name of the person who recorded it
    recorded_by_name: str | None


# A total for one kind of expense
class CategoryTotal(BaseModel):
    # The kind
    category: str
    # The total for that kind
    total: int


# Everything the expenses page needs
class ExpenseList(BaseModel):
    # The total of all matching expenses
    total: int
    # How many match
    count: int
    # The total for each kind, biggest first
    by_category: list[CategoryTotal]
    # The expenses themselves, newest first (up to 500)
    items: list[ExpenseOut]


# Work out the first day of a month and the first day of the next month
def month_range(month: str):
    # Split "2026-10" into the year and the month number
    year, number = int(month[:4]), int(month[5:7])
    start = date(year, number, 1)
    end = date(year + 1, 1, 1) if number == 12 else date(year, number + 1, 1)
    return start, end


# Turn an expense and its related rows into the shape we send back
def to_out(expense, prop, creator) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        property_id=expense.property_id,
        property_name=prop.name if prop else None,
        category=expense.category,
        amount=expense.amount,
        spent_on=expense.spent_on,
        description=expense.description,
        paid_to=expense.paid_to,
        recorded_by_name=creator.full_name if creator else None,
    )


# Find an expense, but only if it belongs to this owner
def find_expense(db: Session, expense_id: int, owner: models.User):
    # Look for an expense with this id AND this owner
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.owner_id == owner.id).first()
    # Say "not found" for missing and for someone else's, so nothing leaks
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    # Hand back the expense
    return expense


# List this owner's expenses (optionally one month, one property, or one kind)
@router.get("", response_model=ExpenseList)
def list_expenses(
    month: str | None = Query(default=None, pattern=PERIOD_PATTERN),
    property_id: int | None = Query(default=None),
    category: CATEGORIES | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see expenses
    require_owner(current_user)
    # Always start with only this owner's expenses
    conditions = [Expense.owner_id == current_user.id]
    # Only one month
    if month:
        start, end = month_range(month)
        conditions.append(Expense.spent_on >= start)
        conditions.append(Expense.spent_on < end)
    # Only one property
    if property_id:
        conditions.append(Expense.property_id == property_id)
    # Only one kind
    if category:
        conditions.append(Expense.category == category)
    # Add up everything that matches
    total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(*conditions).scalar()
    count = db.query(func.count(Expense.id)).filter(*conditions).scalar()
    category_rows = (
        db.query(Expense.category, func.sum(Expense.amount)).filter(*conditions).group_by(Expense.category).all()
    )
    by_category = sorted(
        [CategoryTotal(category=name, total=int(amount)) for name, amount in category_rows],
        key=lambda item: item.total,
        reverse=True,
    )
    # Get the expenses themselves, newest first
    rows = (
        db.query(Expense, models.Property, models.User)
        .outerjoin(models.Property, Expense.property_id == models.Property.id)
        .outerjoin(models.User, Expense.created_by_id == models.User.id)
        .filter(*conditions)
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
        .limit(500)
        .all()
    )
    # Send everything back
    return ExpenseList(
        total=int(total),
        count=count,
        by_category=by_category,
        items=[to_out(expense, prop, creator) for expense, prop, creator in rows],
    )


# Record an expense
@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can record expenses
    require_owner(current_user)
    # If a property was given, make sure it is theirs
    prop = None
    if data.property_id is not None:
        prop = get_owned_property(db, data.property_id, current_user)
    # Build the expense
    expense = Expense(
        owner_id=current_user.id,
        property_id=prop.id if prop else None,
        category=data.category,
        amount=data.amount,
        spent_on=data.spent_on,
        description=(data.description or "").strip() or None,
        paid_to=(data.paid_to or "").strip() or None,
        created_by_id=current_user.id,
    )
    # Save it to the database
    db.add(expense)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(expense)
    # Send it back
    return to_out(expense, prop, current_user)


# Edit an expense (send only the fields that changed)
@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit expenses
    require_owner(current_user)
    # Find it, but only if it is theirs
    expense = find_expense(db, expense_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # If a new property was given, make sure it is theirs
    if changes.get("property_id") is not None:
        get_owned_property(db, changes["property_id"], current_user)
    # Apply each change
    for field, value in changes.items():
        # These fields cannot be emptied out
        if field in ("category", "amount", "spent_on") and value is None:
            continue
        # Tidy up text (empty text becomes "nothing")
        if isinstance(value, str):
            value = value.strip() or None
        # Save the new value on the expense
        setattr(expense, field, value)
    # Save the changes
    db.commit()
    db.refresh(expense)
    # Send it back
    prop = db.get(models.Property, expense.property_id) if expense.property_id else None
    creator = db.get(models.User, expense.created_by_id) if expense.created_by_id else None
    return to_out(expense, prop, creator)


# Delete an expense (for fixing a mistake)
@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete expenses
    require_owner(current_user)
    # Find it, but only if it is theirs
    expense = find_expense(db, expense_id, current_user)
    # Delete it
    db.delete(expense)
    db.commit()