# Import FastAPI tools for building endpoints
from fastapi import APIRouter, Depends
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the tool that counts rows
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
from dependencies import get_db, get_current_user
from portal_models import OwnerSettings, TenantAccount
from routers.properties import require_owner
from security_models import UserTotp

# Make a group of endpoints that all start with /getting-started
router = APIRouter(prefix="/getting-started", tags=["Getting started"])


# One step of the checklist
class Step(BaseModel):
    id: str
    title: str
    description: str
    # True once it is done (worked out from the landlord's own data)
    done: bool
    # True for the three steps that make an account usable
    core: bool
    # Where to go to do it, and what the button says
    link: str
    action: str


# The whole checklist
class Progress(BaseModel):
    steps: list[Step]
    done_count: int
    total: int
    # True once the building, its units and a tenant are in
    core_done: bool


# Count the rows of a landlord in a table that is reached through the building
def owned_count(db: Session, model, owner_id: int) -> int:
    query = db.query(func.count(model.id))
    if model is models.Unit:
        query = query.join(models.Property, models.Unit.property_id == models.Property.id)
    elif model is models.Lease:
        query = query.join(models.Unit, models.Lease.unit_id == models.Unit.id).join(models.Property, models.Unit.property_id == models.Property.id)
    elif model is models.Payment:
        query = (
            query.join(models.Lease, models.Payment.lease_id == models.Lease.id)
            .join(models.Unit, models.Lease.unit_id == models.Unit.id)
            .join(models.Property, models.Unit.property_id == models.Property.id)
        )
    return query.filter(models.Property.owner_id == owner_id).scalar() if model is not models.Property else query.filter(models.Property.owner_id == owner_id).scalar()


# The checklist, with each step worked out from the landlord's own data
@router.get("", response_model=Progress)
def getting_started(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_owner(current_user)
    owner_id = current_user.id
    settings = db.query(OwnerSettings).filter(OwnerSettings.owner_id == owner_id).first()
    facts = {
        "add_property": owned_count(db, models.Property, owner_id) > 0,
        "add_units": owned_count(db, models.Unit, owner_id) > 0,
        "add_tenants": owned_count(db, models.Lease, owner_id) > 0,
        "payment_details": bool(settings and (settings.paybill_number or "").strip()),
        "first_payment": owned_count(db, models.Payment, owner_id) > 0,
        "tenant_portal": db.query(TenantAccount).filter(TenantAccount.owner_id == owner_id).count() > 0,
        "two_step": db.query(UserTotp).filter(UserTotp.user_id == owner_id, UserTotp.enabled.is_(True)).count() > 0,
        "caretaker": db.query(models.CaretakerAccount).filter(models.CaretakerAccount.owner_id == owner_id).count() > 0,
    }
    # id, title, description, core, link, button
    plan = [
        ("add_property", "Add your first building", "Give it a name and say where it is. Quick setup adds the building and all its units together.", True, "/quick-setup", "Open Quick setup"),
        ("add_units", "Add its units", "The houses, rooms or shops that people rent. You can type them as ranges, like A1-A12.", True, "/quick-setup", "Add units"),
        ("add_tenants", "Add the people who live there", "Paste your notebook, or add them one by one. Their balance starts from what they owe today.", True, "/setup", "Add tenants"),
        ("payment_details", "Set how tenants pay you", "Your Paybill or Till number, so your tenants see it in their portal.", False, "/portal-access", "Set payment details"),
        ("first_payment", "Record a payment", "Open a tenant and record a rent payment. Balances, reports and the tax page all follow from this.", False, "/tenants", "Open your tenants"),
        ("tenant_portal", "Give a tenant portal access", "They see their balance on their phone, and can report problems with photos.", False, "/portal-access", "Give access"),
        ("two_step", "Turn on 2-step login", "A code from your phone each time you sign in, so only you can open your account.", False, "/account", "Open My account"),
        ("caretaker", "Add a caretaker (if you have one)", "They see only the buildings you choose, and never any money.", False, "/team", "Open Team"),
    ]
    steps = [Step(id=key, title=title, description=text, done=facts[key], core=core, link=link, action=action) for key, title, text, core, link, action in plan]
    return Progress(
        steps=steps,
        done_count=sum(1 for step in steps if step.done),
        total=len(steps),
        core_done=all(step.done for step in steps if step.core),
    )