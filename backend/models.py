# Import the date and time tool so we can record when things happen
from datetime import datetime
# Import the column types we need for the tables (now with UniqueConstraint too)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, UniqueConstraint
# Import "relationship", which lets one table reach into another easily
from sqlalchemy.orm import relationship
# Import the Base class from our database file
from database import Base


# This class is the "users" table. Each user is one row.
class User(Base):
    # The name of the table inside the database
    __tablename__ = "users"

    # A unique number for each user, created automatically (1, 2, 3...)
    id = Column(Integer, primary_key=True, index=True)
    # The person's full name (required)
    full_name = Column(String, nullable=False)
    # Their email, used to log in (required, and no two users can share one)
    email = Column(String, unique=True, index=True, nullable=False)
    # Their phone number (optional)
    phone = Column(String, nullable=True)
    # Their password, stored scrambled (hashed), never as plain text
    password_hash = Column(String, nullable=False)
    # Their role: "owner" or "caretaker" (new users are owners by default)
    role = Column(String, nullable=False, default="owner")
    # Lets us switch an account off without deleting it
    is_active = Column(Boolean, default=True)
    # The date and time the account was created
    created_at = Column(DateTime, default=datetime.utcnow)


# This class is the "properties" table. Each apartment block or plot is one row.
class Property(Base):
    # The name of the table inside the database
    __tablename__ = "properties"

    # A unique number for each property, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The id of the user who owns this property (points to the users table)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The property's name, like "Kinoru Apartments" (required)
    name = Column(String, nullable=False)
    # The county, like "Meru"
    county = Column(String, nullable=True)
    # The town or estate, like "Makutano"
    town = Column(String, nullable=True)
    # A written address or directions to find the place
    address = Column(String, nullable=True)
    # Map position: how far north or south (used later for the map pin)
    latitude = Column(Float, nullable=True)
    # Map position: how far east or west (used later for the map pin)
    longitude = Column(Float, nullable=True)
    # Any extra notes the owner wants to keep
    notes = Column(Text, nullable=True)
    # The date and time the property was added
    created_at = Column(DateTime, default=datetime.utcnow)

    # Lets us write property.owner to get the user who owns it
    owner = relationship("User")
    # Lets us write property.units to get all the units inside this property
    units = relationship("Unit", back_populates="building")


# This class is the "units" table. Each house or room is one row.
class Unit(Base):
    # The name of the table inside the database
    __tablename__ = "units"
    # Rule: the same unit number cannot appear twice inside one property
    __table_args__ = (UniqueConstraint("property_id", "unit_number", name="one_unit_number_per_property"),)

    # A unique number for each unit, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The id of the property this unit is inside (points to the properties table)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=False)
    # The house or door number, like "A12" (required)
    unit_number = Column(String, nullable=False)
    # The kind of unit, like "Bedsitter" or "1 Bedroom"
    unit_type = Column(String, nullable=True)
    # Monthly rent in shillings, like 8000
    rent_amount = Column(Integer, nullable=False, default=0)
    # Deposit amount in shillings
    deposit_amount = Column(Integer, nullable=False, default=0)
    # The unit's status: "vacant", "occupied", or "maintenance"
    status = Column(String, nullable=False, default="vacant")
    # The electricity meter number, so bills match the right house
    electricity_meter_no = Column(String, nullable=True)
    # The water meter number
    water_meter_no = Column(String, nullable=True)
    # Any extra notes about this unit
    notes = Column(Text, nullable=True)
    # The date and time the unit was added
    created_at = Column(DateTime, default=datetime.utcnow)

    # Lets us write unit.building to get the property this unit is inside
    building = relationship("Property", back_populates="units")