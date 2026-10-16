# Import the date tools
from datetime import date, datetime, timedelta
# Import the tool that lets us list allowed values
from typing import Literal
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the column types we need for the table
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from database import Base
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.documents import Document
from routers.properties import get_owned_property, require_owner

# Make a group of endpoints that all start with /tasks
router = APIRouter(prefix="/tasks", tags=["Tasks"])

# How many months each kind of repeat moves a task forward
REPEAT_MONTHS = {"monthly": 1, "quarterly": 3, "yearly": 12}
# Tasks due within this many days count as "soon"
SOON_DAYS = 14
# Documents expiring within this many days show up under "coming up"
EXPIRY_DAYS = 30


# This class is the "tasks" table. Each job to remember is one row.
class Task(Base):
    # The name of the table inside the database
    __tablename__ = "tasks"

    # A unique number for each task, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The owner this task belongs to (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The property it is about (optional)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True)
    # What needs doing
    title = Column(String, nullable=False)
    # Extra notes
    notes = Column(Text, nullable=True)
    # The date it is due
    due_date = Column(Date, nullable=False)
    # How often it repeats: "none", "monthly", "quarterly", or "yearly"
    repeat = Column(String, nullable=False, default="none")
    # The last time it was marked done
    last_done_on = Column(Date, nullable=True)
    # True once a task that does not repeat has been done
    is_done = Column(Boolean, nullable=False, default=False)
    # The date and time it was added
    created_at = Column(DateTime, default=datetime.utcnow)


# The data we ask for when adding a task
class TaskCreate(BaseModel):
    # What needs doing
    title: str = Field(min_length=2, max_length=150)
    # The date it is due
    due_date: date
    # How often it repeats
    repeat: Literal["none", "monthly", "quarterly", "yearly"] = "none"
    # The property it is about (optional)
    property_id: int | None = None
    # Extra notes (optional)
    notes: str | None = Field(default=None, max_length=500)


# The data we accept when editing a task (every field is optional, send only what changed)
class TaskUpdate(BaseModel):
    # New title
    title: str | None = Field(default=None, min_length=2, max_length=150)
    # New due date
    due_date: date | None = None
    # New repeat
    repeat: Literal["none", "monthly", "quarterly", "yearly"] | None = None
    # New property (send null to clear it)
    property_id: int | None = None
    # New notes
    notes: str | None = Field(default=None, max_length=500)
    # Reopen a finished task by sending false
    is_done: bool | None = None


# The data we send back about a task
class TaskOut(BaseModel):
    # The task's id
    id: int
    # What needs doing
    title: str
    # Extra notes
    notes: str | None
    # The date it is due
    due_date: date
    # How often it repeats
    repeat: str
    # The property it is about
    property_id: int | None
    property_name: str | None
    # True if a task that does not repeat has been done
    is_done: bool
    # The last time it was marked done
    last_done_on: date | None
    # Days until it is due (negative means it is overdue)
    days_left: int
    # "overdue", "soon", "later", or "done"
    status: str


# One thing coming up (a task or a document that is about to expire)
class UpcomingItem(BaseModel):
    # "task" or "document"
    kind: Literal["task", "document"]
    # The id of the task or the document
    id: int
    # What it is
    title: str
    # The due date or the expiry date
    due_date: date
    # Days left (negative means it has passed)
    days_left: int
    # A short extra line, like the property's name
    detail: str | None
    # Which page to open
    link: str


# Move a date forward by some months (31 Jan plus 1 month is 28 Feb, not a mistake)
def add_months(day: date, months: int) -> date:
    # Count months from year zero, then turn it back into a year and a month
    index = day.year * 12 + (day.month - 1) + months
    year, month = index // 12, index % 12 + 1
    # Find the last day of that month
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


# Turn a task into the shape we send back
def to_out(task, prop, today: date) -> TaskOut:
    # How many days until it is due
    days_left = (task.due_date - today).days
    if task.is_done:
        status = "done"
    elif days_left < 0:
        status = "overdue"
    elif days_left <= SOON_DAYS:
        status = "soon"
    else:
        status = "later"
    return TaskOut(
        id=task.id,
        title=task.title,
        notes=task.notes,
        due_date=task.due_date,
        repeat=task.repeat,
        property_id=task.property_id,
        property_name=prop.name if prop else None,
        is_done=task.is_done,
        last_done_on=task.last_done_on,
        days_left=days_left,
        status=status,
    )


# Find a task, but only if it belongs to this owner
def find_task(db: Session, task_id: int, owner: models.User):
    # Look for a task with this id AND this owner
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == owner.id).first()
    # Say "not found" for missing and for someone else's, so nothing leaks
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # Hand back the task
    return task


# List this owner's tasks (open ones, finished ones, or all)
@router.get("", response_model=list[TaskOut])
def list_tasks(
    show: Literal["open", "done", "all"] = Query(default="open"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see tasks
    require_owner(current_user)
    # Always start with only this owner's tasks
    conditions = [Task.owner_id == current_user.id]
    if show == "open":
        conditions.append(Task.is_done.is_(False))
    elif show == "done":
        conditions.append(Task.is_done.is_(True))
    # Get them with their properties, the ones due first coming first
    rows = (
        db.query(Task, models.Property)
        .outerjoin(models.Property, Task.property_id == models.Property.id)
        .filter(*conditions)
        .order_by(Task.due_date, Task.id)
        .limit(500)
        .all()
    )
    today = date.today()
    return [to_out(task, prop, today) for task, prop in rows]


# Show what is coming up: tasks due soon (or overdue) and documents about to expire (or expired)
@router.get("/upcoming", response_model=list[UpcomingItem])
def upcoming(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can see this
    require_owner(current_user)
    today = date.today()
    items = []
    # Tasks that are not done and due within the next two weeks (or already overdue)
    task_rows = (
        db.query(Task, models.Property)
        .outerjoin(models.Property, Task.property_id == models.Property.id)
        .filter(
            Task.owner_id == current_user.id,
            Task.is_done.is_(False),
            Task.due_date <= today + timedelta(days=SOON_DAYS),
        )
        .all()
    )
    for task, prop in task_rows:
        items.append(UpcomingItem(
            kind="task",
            id=task.id,
            title=task.title,
            due_date=task.due_date,
            days_left=(task.due_date - today).days,
            detail=prop.name if prop else None,
            link="/tasks",
        ))
    # Documents expiring within a month (or already expired)
    document_rows = (
        db.query(Document, models.Property, models.Tenant)
        .outerjoin(models.Property, Document.property_id == models.Property.id)
        .outerjoin(models.Tenant, Document.tenant_id == models.Tenant.id)
        .filter(
            Document.owner_id == current_user.id,
            Document.expires_on.isnot(None),
            Document.expires_on <= today + timedelta(days=EXPIRY_DAYS),
        )
        .all()
    )
    for document, prop, tenant in document_rows:
        items.append(UpcomingItem(
            kind="document",
            id=document.id,
            title=document.title,
            due_date=document.expires_on,
            days_left=(document.expires_on - today).days,
            detail=(prop.name if prop else None) or (tenant.full_name if tenant else None),
            link="/documents",
        ))
    # The most urgent first
    items.sort(key=lambda item: item.due_date)
    return items[:20]


# Add a task
@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add tasks
    require_owner(current_user)
    # If a property was given, make sure it is theirs
    prop = get_owned_property(db, data.property_id, current_user) if data.property_id is not None else None
    # Build the task
    task = Task(
        owner_id=current_user.id,
        property_id=prop.id if prop else None,
        title=data.title.strip(),
        notes=(data.notes or "").strip() or None,
        due_date=data.due_date,
        repeat=data.repeat,
    )
    # Save it to the database
    db.add(task)
    db.commit()
    db.refresh(task)
    # Send it back
    return to_out(task, prop, date.today())


# Edit a task (send only the fields that changed)
@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit tasks
    require_owner(current_user)
    # Find it, but only if it is theirs
    task = find_task(db, task_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # If a new property was given, make sure it is theirs
    if changes.get("property_id") is not None:
        get_owned_property(db, changes["property_id"], current_user)
    # Apply each change
    for field, value in changes.items():
        # These fields cannot be emptied out
        if field in ("title", "due_date", "repeat", "is_done") and value is None:
            continue
        # Tidy up text (empty text becomes "nothing")
        if isinstance(value, str):
            value = value.strip() or None
            if field == "title" and value is None:
                raise HTTPException(status_code=400, detail="The title cannot be empty")
        # Save the new value
        setattr(task, field, value)
    # Save the changes
    db.commit()
    db.refresh(task)
    # Send it back
    prop = db.get(models.Property, task.property_id) if task.property_id else None
    return to_out(task, prop, date.today())


# Delete a task
@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete tasks
    require_owner(current_user)
    # Find it, but only if it is theirs
    task = find_task(db, task_id, current_user)
    # Delete it
    db.delete(task)
    db.commit()


# Mark a task done (a repeating task moves on to its next due date)
@router.post("/{task_id}/done", response_model=TaskOut)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can finish tasks
    require_owner(current_user)
    # Find it, but only if it is theirs
    task = find_task(db, task_id, current_user)
    today = date.today()
    task.last_done_on = today
    if task.repeat == "none":
        # A one-off task is simply finished
        task.is_done = True
    else:
        # A repeating task moves forward, and never lands on a date that has already passed
        step = REPEAT_MONTHS[task.repeat]
        next_due = add_months(task.due_date, step)
        guard = 0
        while next_due < today and guard < 120:
            next_due = add_months(next_due, step)
            guard += 1
        task.due_date = next_due
    # Save the changes
    db.commit()
    db.refresh(task)
    # Send it back
    prop = db.get(models.Property, task.property_id) if task.property_id else None
    return to_out(task, prop, today)