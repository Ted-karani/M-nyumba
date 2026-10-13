# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import schemas
from dependencies import get_db, get_current_user

# Make a group of endpoints that all start with /properties
router = APIRouter(prefix="/properties", tags=["Properties"])


# Stop anyone who is not an owner (like a caretaker) from changing things
def require_owner(user: models.User):
    # Only owners may continue
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can do this")


# Find a property, but only if it belongs to this user
def get_owned_property(db: Session, property_id: int, user: models.User):
    # Look for a property with this id AND this owner
    prop = (
        db.query(models.Property)
        .filter(models.Property.id == property_id, models.Property.owner_id == user.id)
        .first()
    )
    # Say "not found" for missing and for someone else's, so nothing leaks
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    # Hand back the property
    return prop


# Add a new property
@router.post("", response_model=schemas.PropertyOut, status_code=201)
def create_property(
    data: schemas.PropertyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can add properties
    require_owner(current_user)
    # Build the property and attach it to the logged-in owner
    prop = models.Property(owner_id=current_user.id, **data.model_dump())
    # Save it to the database
    db.add(prop)
    db.commit()
    # Reload it so it includes its new id
    db.refresh(prop)
    # Send it back
    return prop


# List all of this owner's properties, newest first
@router.get("", response_model=list[schemas.PropertyOut])
def list_properties(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only fetch properties that belong to the logged-in user
    return (
        db.query(models.Property)
        .filter(models.Property.owner_id == current_user.id)
        .order_by(models.Property.created_at.desc())
        .all()
    )


# Get one property by its id
@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find it, but only if it is theirs
    return get_owned_property(db, property_id, current_user)


# Edit a property (send only the fields that changed)
@router.put("/{property_id}", response_model=schemas.PropertyOut)
def update_property(
    property_id: int,
    data: schemas.PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can edit properties
    require_owner(current_user)
    # Find it, but only if it is theirs
    prop = get_owned_property(db, property_id, current_user)
    # Go through only the fields that were actually sent
    for field, value in data.model_dump(exclude_unset=True).items():
        # A name cannot be emptied out
        if field == "name" and value is None:
            continue
        # Save the new value on the property
        setattr(prop, field, value)
    # Save the changes
    db.commit()
    # Reload it with the changes
    db.refresh(prop)
    # Send it back
    return prop


# Delete a property (only if it has no units inside)
@router.delete("/{property_id}", status_code=204)
def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can delete properties
    require_owner(current_user)
    # Find it, but only if it is theirs
    prop = get_owned_property(db, property_id, current_user)
    # Refuse if it still has units, so we never lose rent records by accident
    if prop.units:
        raise HTTPException(status_code=400, detail="Remove the units in this property first")
    # Delete it
    db.delete(prop)
    db.commit()