# Import the date and time tool
from datetime import datetime
# Import tools to describe and check data shapes
from pydantic import BaseModel, EmailStr, Field


# The data we ask for when someone registers
class UserCreate(BaseModel):
    # Full name, at least 2 characters
    full_name: str = Field(min_length=2)
    # Email, must look like a real email
    email: EmailStr
    # Phone number (optional)
    phone: str | None = None
    # Password, between 8 and 64 characters
    password: str = Field(min_length=8, max_length=64)


# The data we send back about a user (notice: no password in here)
class UserOut(BaseModel):
    # The user's id
    id: int
    # The user's full name
    full_name: str
    # The user's email
    email: EmailStr
    # The user's phone number
    phone: str | None
    # The user's role
    role: str

    # Lets this class read data straight from our database objects
    model_config = {"from_attributes": True}


# The data we send back after a successful login
class Token(BaseModel):
    # The token itself
    access_token: str
    # The kind of token (always "bearer")
    token_type: str


# The data we ask for when adding a property
class PropertyCreate(BaseModel):
    # The property's name, at least 2 characters
    name: str = Field(min_length=2)
    # The county, like "Meru" (optional)
    county: str | None = None
    # The town or estate (optional)
    town: str | None = None
    # A written address or directions (optional)
    address: str | None = None
    # Map position north or south, must be between -90 and 90 (optional)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    # Map position east or west, must be between -180 and 180 (optional)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    # Extra notes (optional)
    notes: str | None = None


# The data we accept when editing a property (every field is optional, send only what changed)
class PropertyUpdate(BaseModel):
    # New name (optional)
    name: str | None = Field(default=None, min_length=2)
    # New county (optional)
    county: str | None = None
    # New town (optional)
    town: str | None = None
    # New address (optional)
    address: str | None = None
    # New latitude (optional)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    # New longitude (optional)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    # New notes (optional)
    notes: str | None = None


# The data we send back about a property
class PropertyOut(BaseModel):
    # The property's id
    id: int
    # The id of the owner
    owner_id: int
    # The property's name
    name: str
    # The county
    county: str | None
    # The town or estate
    town: str | None
    # The address or directions
    address: str | None
    # Map position north or south
    latitude: float | None
    # Map position east or west
    longitude: float | None
    # Extra notes
    notes: str | None
    # When it was added
    created_at: datetime

    # Lets this class read data straight from our database objects
    model_config = {"from_attributes": True}