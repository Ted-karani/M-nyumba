# Import tools to read environment variables
import os
# Import FastAPI tools for building the app and handling errors
from fastapi import FastAPI, Depends, HTTPException, Request
# Import the tool that lets our React app talk to this API
from fastapi.middleware.cors import CORSMiddleware
# Import the tool that handles login forms
from fastapi.security import OAuth2PasswordRequestForm
# Import the tools that describe and check data shapes
from pydantic import BaseModel, Field
# Import the tool that lets us write a plain database command
from sqlalchemy import text
# Import the database session type
from sqlalchemy.orm import Session

# Import our database tools
from database import engine, Base
# Import our own files
import admin_models
import audit
import models
import portal_models
import ratelimit
import schemas
import security
import security_models
import twofactor
from dependencies import get_db, get_current_user
from security_models import UserTotp
# Import all the endpoint groups
from routers import (
    properties, units, tenants, leases, billing, rent, utilities,
    maintenance, staff, caretakers, onboarding, reminders, expenses, reports,
    documents, tasks, inspections, listings, portal, mpesa, admin, account, dashboard,
)

# Create all the tables in the database if they don't exist yet
Base.metadata.create_all(bind=engine)

# A fake password hash, so signing in takes the same time whether or not the email exists
DUMMY_HASH = security.hash_password("not-a-real-password")

# On the live server the automatic /docs pages are hidden (ENVIRONMENT=production)
is_production = os.getenv("ENVIRONMENT", "").lower() == "production"

# Create the app and give it a name
app = FastAPI(
    title="M-nyumba",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# The websites allowed to talk to us: the laptop, plus the real website address when it is set
allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if frontend_url:
    allowed_origins.append(frontend_url)
# More website addresses can be added, separated by commas, in EXTRA_ORIGINS
for extra in os.getenv("EXTRA_ORIGINS", "").split(","):
    if extra.strip():
        allowed_origins.append(extra.strip().rstrip("/"))

# Record every change somebody makes (this is added first, so it sits inside the CORS layer below)
app.add_middleware(audit.AuditMiddleware)

# Allow our React app to call this API
app.add_middleware(
    CORSMiddleware,
    # The websites allowed to talk to us
    allow_origins=allowed_origins,
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
# Plug in the endpoints owners use to manage vacancy listings
app.include_router(listings.router)
# Plug in the public listing endpoints (these need no login)
app.include_router(listings.public_router)
# Plug in the endpoints tenants use
app.include_router(portal.tenant_router)
# Plug in the endpoints owners use to give tenants access and set the payment details
app.include_router(portal.access_router)
# Plug in the notice board endpoints
app.include_router(portal.notices_router)
# Plug in the M-Pesa endpoints
app.include_router(mpesa.router)
# Plug in the admin endpoints
app.include_router(admin.admin_router)
# Plug in the first-time setup and account status endpoints
app.include_router(admin.setup_router)
# Plug in the account endpoints (change password, 2-step login, activity log)
app.include_router(account.router)
# Plug in the dashboard endpoint
app.include_router(dashboard.router)


# What we send back after a sign-in step: either a login token, or a request for the 6-digit code
class LoginResult(BaseModel):
    # The login token (empty while a code is still needed)
    access_token: str | None = None
    # The kind of token (always "bearer")
    token_type: str = "bearer"
    # True if the person must now enter a code
    requires_otp: bool = False
    # The short-lived pass to send back together with the code
    challenge: str | None = None


# The data we ask for in the second step of signing in
class OtpRequest(BaseModel):
    # The short-lived pass from the first step
    challenge: str
    # The 6-digit code, or a recovery code
    code: str = Field(min_length=4, max_length=20)


# Work out the login name from what was typed: an email stays as it is, a phone number becomes a tenant's hidden login name
def login_name(typed: str) -> str:
    text_typed = typed.strip().lower()
    # Anything with an @ is an email
    if "@" in text_typed:
        return text_typed
    # Otherwise try it as a phone number
    try:
        phone = schemas.clean_phone(text_typed)
    except ValueError:
        return text_typed
    return portal_models.tenant_email(phone)


# When someone visits the home address "/", send a simple message
@app.get("/")
def home():
    # Prove the server works
    return {"message": "M-nyumba is running"}


# A quick check that the server is alive (the host uses this to know the app started)
@app.get("/health")
def health():
    return {"status": "ok"}


# A deeper check that also talks to the database (an uptime monitor can use this one)
@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database not reachable")
    return {"status": "ok"}


# Create a new account (anyone who registers here becomes an owner, unless sign-ups are closed)
@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Sign-ups can be closed by setting ALLOW_REGISTRATION=false in the settings
    if os.getenv("ALLOW_REGISTRATION", "true").lower() == "false":
        raise HTTPException(status_code=403, detail="Sign-ups are closed")
    # Store emails in lowercase so "A@x.com" and "a@x.com" are the same
    email = data.email.lower()
    # The hidden login names used for tenants cannot be registered by hand
    if email.endswith("@" + portal_models.TENANT_EMAIL_DOMAIN):
        raise HTTPException(status_code=400, detail="This email address cannot be used")
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


# Log in with an email (or, for tenants, a phone number) and a password (step one: this gives a login token, or asks for a code)
@app.post("/auth/login", response_model=LoginResult)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # The login form calls the email field "username"
    email = login_name(form.username)
    # The address the request came from
    ip = request.client.host if request.client else None
    # Too many wrong passwords? Make the person wait
    account.refuse_if_locked(db, email, ip)
    # Look for the user by email
    user = db.query(models.User).filter(models.User.email == email).first()
    # Always check a password hash, so the time taken does not reveal whether the email exists
    password_ok = security.verify_password(form.password, user.password_hash if user else DUMMY_HASH)
    # Same error for a wrong email or a wrong password, so attackers learn nothing
    if user is None or not password_ok or not user.is_active:
        ratelimit.record(db, email, ip, success=False)
        raise HTTPException(status_code=401, detail="Wrong email or password")
    # A suspended or closed business cannot sign in (we say why, now that the password was right)
    blocked = admin_models.login_block_message(db, user)
    if blocked:
        raise HTTPException(status_code=403, detail=blocked)
    # If this person has 2-step login on, ask for the code before giving a token
    totp = db.query(UserTotp).filter(UserTotp.user_id == user.id, UserTotp.enabled.is_(True)).first()
    if totp is not None:
        return LoginResult(requires_otp=True, challenge=security.create_challenge_token(user.id))
    # Remember the good sign-in, and add it to the activity log
    ratelimit.record(db, email, ip, success=True)
    audit.log_signin(db, user, ip)
    # Make a token for this user and send it back
    return LoginResult(access_token=security.create_access_token(user.id))


# Finish signing in with the 6-digit code (or a recovery code)
@app.post("/auth/login/verify", response_model=LoginResult)
def login_verify(request: Request, data: OtpRequest, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    # Read the short-lived pass from step one
    user_id = security.read_challenge_token(data.challenge)
    if user_id is None:
        raise HTTPException(status_code=401, detail="This sign-in took too long. Please start again")
    user = db.get(models.User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="This sign-in took too long. Please start again")
    # A business that was suspended while the person was typing the code is shut out here too
    blocked = admin_models.login_block_message(db, user)
    if blocked:
        raise HTTPException(status_code=403, detail=blocked)
    email = user.email.lower()
    # Guessing codes is limited like guessing passwords
    account.refuse_if_locked(db, email, ip)
    row = db.query(UserTotp).filter(UserTotp.user_id == user.id, UserTotp.enabled.is_(True)).first()
    if row is None:
        raise HTTPException(status_code=401, detail="This sign-in took too long. Please start again")
    # The code must be right (a recovery code works too, once)
    if not (twofactor.check_code(row, data.code) or twofactor.use_recovery_code(row, data.code)):
        ratelimit.record(db, email, ip, success=False)
        raise HTTPException(status_code=401, detail="That code is not right")
    # Remember the good sign-in (this also saves the used code), and add it to the activity log
    ratelimit.record(db, email, ip, success=True)
    audit.log_signin(db, user, ip)
    return LoginResult(access_token=security.create_access_token(user.id))


# Show the details of whoever is logged in (needs a valid token)
@app.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    # Return the logged-in user
    return current_user