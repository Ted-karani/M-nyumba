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