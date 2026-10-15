# Import the database session type
from sqlalchemy.orm import Session

# Import our tables
import models


# Work out which properties a user is allowed to work with
def property_scope(db: Session, user: models.User) -> list[int]:
    # An owner works with every property they own
    if user.role == "owner":
        rows = db.query(models.Property.id).filter(models.Property.owner_id == user.id).all()
        return [property_id for (property_id,) in rows]
    # A caretaker works only with the properties they were assigned
    if user.role == "caretaker":
        rows = (
            db.query(models.PropertyCaretaker.property_id)
            .join(models.Property, models.PropertyCaretaker.property_id == models.Property.id)
            .join(models.CaretakerAccount, models.CaretakerAccount.user_id == models.PropertyCaretaker.caretaker_id)
            .filter(
                models.PropertyCaretaker.caretaker_id == user.id,
                # The property must also belong to the owner who created this caretaker
                models.Property.owner_id == models.CaretakerAccount.owner_id,
            )
            .all()
        )
        return [property_id for (property_id,) in rows]
    # Anyone else gets nothing
    return []