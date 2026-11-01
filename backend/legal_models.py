# legal_models.py - remembers who accepted which version of the Terms and Privacy Policy

# Import the tool that reads settings from the environment
import os
# Import the date and time tool
from datetime import datetime
# Import the column types we need for the table
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

# Import the Base class from our database file
from database import Base

# The version of each document (a date). Change BOTH of these, and the same two in
# frontend/src/legal/legalConfig.js, whenever the text changes. Everyone is then asked to accept again.
TERMS_VERSION = "2026-11-01"
PRIVACY_VERSION = "2026-11-01"


# This class is the "terms_acceptances" table. Each time a landlord accepts is one row.
class TermsAcceptance(Base):
    # The name of the table inside the database
    __tablename__ = "terms_acceptances"

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The landlord who accepted (points to the users table)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Which versions they accepted
    terms_version = Column(String, nullable=False)
    privacy_version = Column(String, nullable=False)
    # When they accepted
    accepted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # The address they accepted from
    ip = Column(String, nullable=True)


# Is accepting required right now? (it is switched on with TERMS_ENFORCED=true, once the text is final)
def enforced() -> bool:
    return os.getenv("TERMS_ENFORCED", "false").lower() == "true"


# Has this landlord accepted the CURRENT versions?
def has_accepted_current(db, user_id: int) -> bool:
    row = (
        db.query(TermsAcceptance.id)
        .filter(
            TermsAcceptance.user_id == user_id,
            TermsAcceptance.terms_version == TERMS_VERSION,
            TermsAcceptance.privacy_version == PRIVACY_VERSION,
        )
        .first()
    )
    return row is not None