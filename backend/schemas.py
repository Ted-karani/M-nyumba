# Import the date and time tool
from datetime import datetime
# Import the tool that lets us list allowed values
from typing import Literal
# Import tools to describe and check data shapes
from pydantic import BaseModel, EmailStr, Field, field_validator


# Turn any Kenyan phone number into the 254712345678 format
def clean_phone(value: str) -> str:
    # Keep only the digits (this removes spaces, dashes, and the + sign)
    digits = "".join(ch for ch in value if ch.isdigit())
    # Already starts with 254 and has 12 digits, like 254712345678
    if digits.startswith("254") and len(digits) == 12:
        pass
    # Starts with 0 and has 10 digits, like 0712345678
    elif digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    # Has 9 digits starting with 7 or 1, like 712345678
    elif len(digits) == 9 and digits[0] in "17":
        digits = "254" + digits
    # Anything else is not a valid number
    else:
        raise ValueError("Enter a valid Kenyan phone number, like 0712345678")
    # The digit after 254 must be 7 or 1 (Safaricom, Airtel, and so on)
    if digits[3] not in "17":
        raise ValueError("Enter a valid Kenyan phone number, like 0712345678")
    # Send back the cleaned number
    return digits


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


# The data we ask for when adding a unit
class UnitCreate(BaseModel):
    # The house or door number, like "A12"
    unit_number: str = Field(min_length=1, max_length=20)
    # The kind of unit, like "Bedsitter" (optional)
    unit_type: str | None = None
    # Monthly rent in shillings (cannot be negative)
    rent_amount: int = Field(default=0, ge=0)
    # Deposit in shillings (cannot be negative)
    deposit_amount: int = Field(default=0, ge=0)
    # Status you may set by hand ("occupied" is set automatically by leases)
    status: Literal["vacant", "maintenance"] = "vacant"
    # The electricity meter number (optional)
    electricity_meter_no: str | None = None
    # The water meter number (optional)
    water_meter_no: str | None = None
    # Extra notes (optional)
    notes: str | None = None


# The data we accept when editing a unit (every field is optional, send only what changed)
class UnitUpdate(BaseModel):
    # New unit number (optional)
    unit_number: str | None = Field(default=None, min_length=1, max_length=20)
    # New unit type (optional)
    unit_type: str | None = None
    # New rent (optional)
    rent_amount: int | None = Field(default=None, ge=0)
    # New deposit (optional)
    deposit_amount: int | None = Field(default=None, ge=0)
    # New status (optional, only these two can be set by hand)
    status: Literal["vacant", "maintenance"] | None = None
    # New electricity meter number (optional)
    electricity_meter_no: str | None = None
    # New water meter number (optional)
    water_meter_no: str | None = None
    # New notes (optional)
    notes: str | None = None


# The data we send back about a unit
class UnitOut(BaseModel):
    # The unit's id
    id: int
    # The id of the property it is inside
    property_id: int
    # The house or door number
    unit_number: str
    # The kind of unit
    unit_type: str | None
    # Monthly rent in shillings
    rent_amount: int
    # Deposit in shillings
    deposit_amount: int
    # The status: "vacant", "occupied", or "maintenance"
    status: str
    # The electricity meter number
    electricity_meter_no: str | None
    # The water meter number
    water_meter_no: str | None
    # Extra notes
    notes: str | None
    # When it was added
    created_at: datetime

    # Lets this class read data straight from our database objects
    model_config = {"from_attributes": True}


# The data we ask for when adding a tenant
class TenantCreate(BaseModel):
    # The tenant's full name, at least 2 characters
    full_name: str = Field(min_length=2)
    # The tenant's phone number (we clean it to 254... format)
    phone: str
    # The tenant's email (optional)
    email: EmailStr | None = None
    # The tenant's national ID number (optional)
    id_number: str | None = None
    # Name of someone to call in an emergency (optional)
    emergency_contact_name: str | None = None
    # That person's phone number (optional, cleaned too)
    emergency_contact_phone: str | None = None
    # Extra notes (optional)
    notes: str | None = None

    # Clean both phone fields before saving
    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def check_phone(cls, value):
        # Skip empty optional values
        if value is None:
            return value
        # Clean the number, or raise an error if it is not valid
        return clean_phone(value)


# The data we accept when editing a tenant (every field is optional, send only what changed)
class TenantUpdate(BaseModel):
    # New full name (optional)
    full_name: str | None = Field(default=None, min_length=2)
    # New phone number (optional)
    phone: str | None = None
    # New email (optional)
    email: EmailStr | None = None
    # New ID number (optional)
    id_number: str | None = None
    # New emergency contact name (optional)
    emergency_contact_name: str | None = None
    # New emergency contact phone (optional)
    emergency_contact_phone: str | None = None
    # New notes (optional)
    notes: str | None = None

    # Clean both phone fields before saving
    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def check_phone(cls, value):
        # Skip empty optional values
        if value is None:
            return value
        # Clean the number, or raise an error if it is not valid
        return clean_phone(value)


# The data we send back about a tenant
class TenantOut(BaseModel):
    # The tenant's id
    id: int
    # The id of the owner
    owner_id: int
    # The tenant's full name
    full_name: str
    # The tenant's phone number
    phone: str
    # The tenant's email
    email: str | None
    # The tenant's ID number
    id_number: str | None
    # The emergency contact's name
    emergency_contact_name: str | None
    # The emergency contact's phone
    emergency_contact_phone: str | None
    # Extra notes
    notes: str | None
    # When it was added
    created_at: datetime

    # Lets this class read data straight from our database objects
    model_config = {"from_attributes": True}