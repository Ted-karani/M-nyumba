# Import FastAPI tools for building the app and handling errors
from fastapi import FastAPI, Depends, HTTPException
# Import the tool that lets our React app talk to this API
from fastapi.middleware.cors import CORSMiddleware
# Import the tool that handles login forms
from fastapi.security import OAuth2PasswordRequestForm
# Import the database session type
from sqlalchemy.orm import Session

# Import our database tools
from database import engine, Base
# Import our own files
import models
import schemas
import security
from dependencies import get_db, get_current_user
# Import all the endpoint groups
from routers import properties, units, tenants, leases, billing, rent, utilities, maintenance, staff, caretakers, dashboard

# Create all the tables in the database if they don't exist yet
Base.metadata.create_all(bind=engine)

# Create the app and give it a name
app = FastAPI(title="M-nyumba")

# Allow our React app (running on port 5173) to call this API
app.add_middleware(
    CORSMiddleware,
    # The websites allowed to talk to us
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    # We use tokens in headers, not cookies, so this stays off
    allow_credentials=False,
    # Allow all request types (GET, POST, PUT, DELETE)
    allow_methods=["*"],
    # Allow all headers, including the Authorization header
    allow_headers=["*"],
)

# Plug in the properties endpoints
app.include_router(properties.router)
# Plug in the units endpoints
app.include_router(units.router)
# Plug in the tenants endpoints
app.include_router(tenants.router)
# Plug in the leases endpoints
app.include_router(leases.router)
# Plug in the charges and payments endpoints
app.include_router(billing.router)
# Plug in the monthly rent endpoints
app.include_router(rent.router)
# Plug in the water, electricity, and Wi-Fi endpoints
app.include_router(utilities.router)
# Plug in the repairs endpoints
app.include_router(maintenance.router)
# Plug in the caretaker's own endpoints
app.include_router(staff.router)
# Plug in the endpoints owners use to manage caretakers
app.include_router(caretakers.router)
# Plug in the dashboard endpoint
app.include_router(dashboard.router)


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