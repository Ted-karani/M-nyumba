# Import the date tools
from datetime import timezone
# Import FastAPI tools for errors and shared helpers
from fastapi import Depends, HTTPException
# Import the tool that reads login tokens
from fastapi.security import OAuth2PasswordBearer
# Import the database session type
from sqlalchemy.orm import Session
# Import jwt so we can read tokens
import jwt

# Import our database session factory
from database import SessionLocal
# Import our own files
import models
import security
from security_models import UserSecurity

# Tell FastAPI where users log in to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# Give each request its own database session, and close it when done
def get_db():
    # Open a new session
    db = SessionLocal()
    try:
        # Hand it to the endpoint that needs it
        yield db
    finally:
        # Always close it afterwards
        db.close()


# Work out which user is making the request by reading their token
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # The error we send if anything is wrong with the token
    error = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Open the token and read what is inside
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        # Get the user id stored inside the token
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        # The token is fake, expired, or damaged
        raise error
    # The short-lived "enter your code" pass is not a login token
    if payload.get("purpose"):
        raise error
    # Find that user in the database
    user = db.get(models.User, user_id)
    # Reject the request if the user is missing or switched off
    if user is None or not user.is_active:
        raise error
    # Reject tokens made before the person's password was last changed
    changed = db.query(UserSecurity.password_changed_at).filter(UserSecurity.user_id == user.id).scalar()
    if changed is not None:
        issued = float(payload.get("iat", 0))
        if issued < changed.replace(tzinfo=timezone.utc).timestamp():
            raise error
    # Return the user so the endpoint knows who is asking
    return user