# Import the date tool
from datetime import datetime
# Import FastAPI tools for building endpoints and errors
from fastapi import APIRouter, Depends, HTTPException, Request
# Import the tool that describes data shapes
from pydantic import BaseModel
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import legal_models
import models
from dependencies import get_db, get_current_user

# Make a group of endpoints that all start with /legal
router = APIRouter(prefix="/legal", tags=["Legal"])


# Where a landlord stands with the Terms and Privacy Policy
class LegalStatus(BaseModel):
    # True if accepting is required right now
    required: bool
    # True if they have accepted the current versions
    accepted: bool
    # The current versions
    terms_version: str
    privacy_version: str
    # When they accepted (empty if they have not)
    accepted_at: datetime | None


# What we ask for when someone accepts
class AcceptIn(BaseModel):
    # They must tick the box
    agree: bool
    # The versions they were shown (so they cannot accept text they did not see)
    terms_version: str
    privacy_version: str


# Find the acceptance of the current versions, if there is one
def current_acceptance(db: Session, user_id: int):
    return (
        db.query(legal_models.TermsAcceptance)
        .filter(
            legal_models.TermsAcceptance.user_id == user_id,
            legal_models.TermsAcceptance.terms_version == legal_models.TERMS_VERSION,
            legal_models.TermsAcceptance.privacy_version == legal_models.PRIVACY_VERSION,
        )
        .order_by(legal_models.TermsAcceptance.accepted_at.desc())
        .first()
    )


# Work out the status for one person (only landlords have to accept)
def status_for(db: Session, user: models.User) -> LegalStatus:
    if user.role != "owner":
        return LegalStatus(
            required=False,
            accepted=True,
            terms_version=legal_models.TERMS_VERSION,
            privacy_version=legal_models.PRIVACY_VERSION,
            accepted_at=None,
        )
    row = current_acceptance(db, user.id)
    return LegalStatus(
        required=legal_models.enforced(),
        accepted=row is not None,
        terms_version=legal_models.TERMS_VERSION,
        privacy_version=legal_models.PRIVACY_VERSION,
        accepted_at=row.accepted_at if row else None,
    )


# Where do I stand?
@router.get("/status", response_model=LegalStatus)
def legal_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return status_for(db, current_user)


# Accept the current Terms and Privacy Policy
@router.post("/accept", response_model=LegalStatus)
def accept_legal(
    data: AcceptIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only landlords accept
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Only landlords accept the Terms")
    if not data.agree:
        raise HTTPException(status_code=400, detail="You need to agree to continue")
    # They must have seen the current versions
    if data.terms_version != legal_models.TERMS_VERSION or data.privacy_version != legal_models.PRIVACY_VERSION:
        raise HTTPException(status_code=409, detail="The documents were updated. Please reload the page and read them again")
    # Accepting twice changes nothing
    if current_acceptance(db, current_user.id) is None:
        db.add(legal_models.TermsAcceptance(
            user_id=current_user.id,
            terms_version=legal_models.TERMS_VERSION,
            privacy_version=legal_models.PRIVACY_VERSION,
            ip=request.client.host if request.client else None,
        ))
        db.commit()
    return status_for(db, current_user)