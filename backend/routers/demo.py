# Import the tools we need
from datetime import datetime

# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Response
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import demo_data
import models
from admin_models import log_admin
from dependencies import get_db
from routers.admin import require_admin

# Make a group of endpoints that all start with /admin/demo (only for the admin)
router = APIRouter(prefix="/admin/demo", tags=["Admin: demo landlord"])


# Where the demo stands
class DemoStatus(BaseModel):
    exists: bool
    # True if an account with the demo email exists that is NOT a demo (we never touch it)
    blocked: bool
    email: str
    created_at: datetime | None
    counts: dict[str, int]
    message: str | None


# What we send back after the demo is built
class DemoCreated(BaseModel):
    email: str
    # Shown only now: it is stored scrambled, so it cannot be shown again
    password: str
    counts: dict[str, int]


# Look at the demo account
@router.get("", response_model=DemoStatus)
def demo_status(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, is_demo = demo_data.find_demo(db)
    if owner is None:
        return DemoStatus(exists=False, blocked=False, email=demo_data.DEMO_EMAIL, created_at=None, counts={}, message=None)
    if not is_demo:
        return DemoStatus(exists=False, blocked=True, email=demo_data.DEMO_EMAIL, created_at=None, counts={}, message="An account with the demo email already exists and is not a demo account. Nothing was touched.")
    return DemoStatus(exists=True, blocked=False, email=owner.email, created_at=owner.created_at, counts=demo_data.demo_counts(db, owner.id), message=None)


# Build the demo landlord
def create(db: Session, admin: models.User, action: str) -> DemoCreated:
    try:
        built = demo_data.build_demo(db)
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"The demo could not be built: {error}")
    log_admin(db, admin, None, action, None)
    db.commit()
    return DemoCreated(email=demo_data.DEMO_EMAIL, password=built["password"], counts=built["counts"])


# Make the demo (only once)
@router.post("", response_model=DemoCreated, status_code=201)
def create_demo(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, is_demo = demo_data.find_demo(db)
    if owner is not None:
        raise HTTPException(status_code=409, detail="The demo already exists. Use Reset to rebuild it" if is_demo else "An account with the demo email exists and is not a demo account")
    return create(db, admin, "Created the demo landlord")


# Wipe the demo and build it again with fresh dates (and a new password)
@router.post("/reset", response_model=DemoCreated, status_code=201)
def reset_demo(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, is_demo = demo_data.find_demo(db)
    if owner is not None:
        if not is_demo:
            raise HTTPException(status_code=409, detail="An account with the demo email exists and is not a demo account")
        demo_data.wipe_demo(db, owner)
    return create(db, admin, "Reset the demo landlord")


# Remove the demo completely
@router.delete("", status_code=204)
def delete_demo(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    owner, is_demo = demo_data.find_demo(db)
    if owner is None:
        raise HTTPException(status_code=404, detail="There is no demo to delete")
    if not is_demo:
        raise HTTPException(status_code=409, detail="An account with the demo email exists and is not a demo account. Nothing was deleted")
    demo_data.wipe_demo(db, owner)
    log_admin(db, admin, None, "Deleted the demo landlord", None)
    db.commit()
    return Response(status_code=204)