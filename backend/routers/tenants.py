# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Query
# Import the tool that lets us search with "or"
from sqlalchemy import or_
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import schemas
from dependencies import get_db, get_current_user
# Reuse the owner check we wrote for properties
from routers.properties import require_owner

# Make a group of endpoints that all start with /tenants
router = APIRouter(prefix="/tenants", tags=["Tenants"])

# Fields that must always have a value (they cannot be emptied out)
REQUIRED_FIELDS = {"full_name", "phone"}


# Find a tenant, but only if it belongs to this user
def get_owned_tenant(db: Session, tenant_id: int, user: models.User):
    # Look for a tenant with this id AND this owner
    tenant = (
        db.query(models.Tenant)
        .filter(models.Tenant.id == tenant_id, models.Tenant.owner_id == user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # Hand back the tenant
    return tenant


# Check that this owner has no other tenant with the same phone number
def check_phone_free(db: Session, owner_id: int, phone: str, ignore_tenant_id: int | None = None):
    # Look for another tenant of this owner with the same phone
    query = db.query(models.Tenant).filter(
        models.Tenant.owner_id == owner_id,
        models.Tenant.phone == phone,
    )
    # When editing, do not count the tenant we are editing
    if ignore_tenant_id is not None:
        query = query.filter(models.Tenant.id != ignore_tenant_id)
    # If one exists, refuse with a clear message
    if query.first():
        raise HTTPException(status_code=400, detail="A tenant with this phone number already exists")


# Add a new tenant
@router.post("", response_model=schemas.TenantOut, status_code=201)
def create_tenant(
    data: schemas.TenantCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add tenants
    require_owner(current_user)
    # Make sure this phone number is not already used by another tenant
    check_phone_free(db, current_user.id, data.phone)
    # Build the tenant and attach it to the logged-in owner
    values = data.model_dump()
    values["full_name"] = values["full_name"].strip()
    tenant = models.Tenant(owner_id=current_user.id, **values)
    # Save it to the database
    db.add(tenant)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(tenant)
    # Send it back
    return tenant


# List this owner's tenants (optionally search by name or phone)
@router.get("", response_model=list[schemas.TenantOut])
def list_tenants(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Start with only this owner's tenants
    query = db.query(models.Tenant).filter(models.Tenant.owner_id == current_user.id)
    # If a search word was given, match it against the name or the phone
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(models.Tenant.full_name.ilike(pattern), models.Tenant.phone.like(pattern))
        )
    # Return them in alphabetical order
    return query.order_by(models.Tenant.full_name).all()


# Get one tenant by their id
@router.get("/{tenant_id}", response_model=schemas.TenantOut)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find them, but only if they are this owner's
    return get_owned_tenant(db, tenant_id, current_user)


# Edit a tenant (send only the fields that changed)
@router.put("/{tenant_id}", response_model=schemas.TenantOut)
def update_tenant(
    tenant_id: int,
    data: schemas.TenantUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit tenants
    require_owner(current_user)
    # Find them, but only if they are this owner's
    tenant = get_owned_tenant(db, tenant_id, current_user)
    # Get only the fields that were actually sent
    changes = data.model_dump(exclude_unset=True)
    # If the phone is changing, make sure the new one is free
    if "phone" in changes and changes["phone"] is not None:
        check_phone_free(db, current_user.id, changes["phone"], ignore_tenant_id=tenant.id)
    # Clean up spaces around the name
    if "full_name" in changes and changes["full_name"] is not None:
        changes["full_name"] = changes["full_name"].strip()
    # Apply each change
    for field, value in changes.items():
        # Required fields cannot be emptied out
        if field in REQUIRED_FIELDS and value is None:
            continue
        # Save the new value on the tenant
        setattr(tenant, field, value)
    # Save the changes
    db.commit()
    # Reload them with the changes
    db.refresh(tenant)
    # Send them back
    return tenant


# Delete a tenant (only if they have never had a lease)
@router.delete("/{tenant_id}", status_code=204)
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete tenants
    require_owner(current_user)
    # Find them, but only if they are this owner's
    tenant = get_owned_tenant(db, tenant_id, current_user)
    # Refuse if they have lease history, so we never lose rent records by accident
    if tenant.leases:
        raise HTTPException(status_code=400, detail="This tenant has lease history and cannot be deleted")
    # Delete them
    db.delete(tenant)
    db.commit()