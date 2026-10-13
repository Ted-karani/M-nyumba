# Import FastAPI tools for building the app and handling errors
from fastapi import FastAPI, Depends, HTTPException
# Import the tools that handle login forms and tokens
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# Import the database session type
from sqlalchemy.orm import Session
# Import jwt so we can read tokens
import jwt

# Import our database tools
from database import engine, Base, SessionLocal
# Import our own files
import models
import schemas
import security

# Create all the tables in the database if they don't exist yet
Base.metadata.create_all(bind=engine)

# Create the app and give it a name
app = FastAPI(title="M-nyumba")

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
    # Find that user in the database
    user = db.get(models.User, user_id)
    # Reject the request if the user is missing or switched off
    if user is None or not user.is_active:
        raise error
    # Return the user so the endpoint knows who is asking
    return user


# When someone visits the home address "/", send a simple message
@app.get("/")
def home():
    # Prove the server works
    return {"message": "M-nyumba is running"}


# Create a new account (anyone who registers here becomes an owner)
@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Store emails in lowercase so "A@x.com" and "a@x.com" are the same
    email = data.email.lower()
    # Check if this email already has an account
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        # Refuse to create a duplicate
        raise HTTPException(status_code=400, detail="This email is already registered")
    # Build the new user, saving only the scrambled password
    user = models.User(
        full_name=data.full_name,
        email=email,
        phone=data.phone,
        password_hash=security.hash_password(data.password),
        role="owner",
    )
    # Save the user to the database
    db.add(user)
    db.commit()
    # Reload the user so it includes its new id
    db.refresh(user)
    # Send back the user's details (no password)
    return user


# Log in with email and password, and get a token back
@app.post("/auth/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # The login form calls the email field "username"
    email = form.username.lower()
    # Look for the user by email
    user = db.query(models.User).filter(models.User.email == email).first()
    # Same error for a wrong email or a wrong password, so attackers learn nothing
    if user is None or not security.verify_password(form.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Wrong email or password")
    # Make a token for this user
    token = security.create_access_token(user.id)
    # Send the token back
    return {"access_token": token, "token_type": "bearer"}


# Show the details of whoever is logged in (needs a valid token)
@app.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    # Return the logged-in user
    return current_user