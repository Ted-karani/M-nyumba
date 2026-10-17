# Import tools to read environment variables
import os
# Import FastAPI tools for building the app and handling errors
from fastapi import FastAPI, Depends, HTTPException, Request
# Import the tool that lets our React app talk to this API
from fastapi.middleware.cors import CORSMiddleware
# Import the tool that handles login forms
from fastapi.security import OAuth2PasswordRequestForm
# Import the database session type
from sqlalchemy.orm import Session

# Import our database tools
from database import engine, Base
# Import our own files
import audit
import models
import ratelimit
import schemas
import security
import security_models
from dependencies import get_db, get_current_user
# Import all the endpoint groups
from routers import (
    properties, units, tenants, leases, billing, rent, utilities,
    maintenance, staff, caretakers, onboarding, reminders, expenses, reports,
    documents, tasks, inspections, account, dashboard,
)

# Create all the tables in the database if they don't exist yet
Base.metadata.create_all(bind=engine)

# A fake password hash, so signing in takes the same time whether or not the email exists
DUMMY_HASH = security.hash_password("not-a-real-password")

# Create the app and give it a name
app = FastAPI(title="M-nyumba")

# Record every change somebody makes (this is added first, so it sits inside the CORS layer below)
app.add_middleware(audit.AuditMiddleware)

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
# Plug in the existing-tenant setup endpoint
app.include_router(onboarding.router)
# Plug in the reminder endpoints
app.include_router(reminders.router)
# Plug in the expense endpoints
app.include_router(expenses.router)
# Plug in the report endpoints
app.include_router(reports.router)
# Plug in the document endpoints
app.include_router(documents.router)
# Plug in the task endpoints
app.include_router(tasks.router)
# Plug in the move-in and move-out checklist endpoints
app.include_router(inspections.router)
# Plug in the account endpoints (change password, activity log)
app.include_router(account.router)
# Plug in the dashboard endpoint
app.include_router(dashboard.router)


# When someone visits the home address "/", send a simple message
@app.get("/")
def home():
    # Prove the server works
    return {"message": "M-nyumba is running"}


# Create a new account (anyone who registers here becomes an owner, unless sign-ups are closed)
@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Sign-ups can be closed by setting ALLOW_REGISTRATION=false in the .env file
    if os.getenv("ALLOW_REGISTRATION", "true").lower() == "false":
        raise HTTPException(status_code=403, detail="Sign-ups are closed")
    # Store emails in lowercase so "A@x.com" and "a@x.com" are the same
    email = data.email.lower()
    # The password must not be too easy to guess
    account.validate_new_password(data.password, email)
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
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # The login form calls the email field "username"
    email = form.username.lower()
    # The address the request came from
    ip = request.client.host if request.client else None
    # Too many wrong passwords? Make the person wait
    wait = ratelimit.seconds_locked(db, email, ip)
    if wait > 0:
        minutes = (wait + 59) // 60
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )
    # Look for the user by email
    user = db.query(models.User).filter(models.User.email == email).first()
    # Always check a password hash, so the time taken does not reveal whether the email exists
    password_ok = security.verify_password(form.password, user.password_hash if user else DUMMY_HASH)
    # Same error for a wrong email or a wrong password, so attackers learn nothing
    if user is None or not password_ok or not user.is_active:
        ratelimit.record(db, email, ip, success=False)
        raise HTTPException(status_code=401, detail="Wrong email or password")
    # Remember the good sign-in, and add it to the activity log
    ratelimit.record(db, email, ip, success=True)
    audit.log_signin(db, user, ip)
    # Make a token for this user
    token = security.create_access_token(user.id)
    # Send the token back
    return {"access_token": token, "token_type": "bearer"}


# Show the details of whoever is logged in (needs a valid token)
@app.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    # Return the logged-in user
    return current_user