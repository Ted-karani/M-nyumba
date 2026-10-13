# Import the date and time tools so we can record when things happen
from datetime import datetime
# Import the column types we need for the tables (now with Date too)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Float, Text, ForeignKey, UniqueConstraint
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
    # Lets us write unit.leases to get every stay this unit has ever had
    leases = relationship("Lease", back_populates="unit")


# This class is the "tenants" table. Each person who rents is one row.
class Tenant(Base):
    # The name of the table inside the database
    __tablename__ = "tenants"

    # A unique number for each tenant, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The id of the owner this tenant belongs to (so landlords only see their own tenants)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # The tenant's full name (required)
    full_name = Column(String, nullable=False)
    # The tenant's phone number, used for reminders and M-Pesa matching later (required)
    phone = Column(String, nullable=False)
    # The tenant's email (optional)
    email = Column(String, nullable=True)
    # The tenant's national ID number (we will encrypt this later in Phase 4)
    id_number = Column(String, nullable=True)
    # The name of someone to call in an emergency
    emergency_contact_name = Column(String, nullable=True)
    # That person's phone number
    emergency_contact_phone = Column(String, nullable=True)
    # Any extra notes about the tenant
    notes = Column(Text, nullable=True)
    # The date and time the tenant was added
    created_at = Column(DateTime, default=datetime.utcnow)

    # Lets us write tenant.leases to get every stay this tenant has had
    leases = relationship("Lease", back_populates="tenant")


# This class is the "leases" table. Each stay (one tenant in one unit) is one row.
class Lease(Base):
    # The name of the table inside the database
    __tablename__ = "leases"

    # A unique number for each lease, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # The unit being rented (points to the units table)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False)
    # The person renting it (points to the tenants table)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    # The day the tenant moves in
    start_date = Column(Date, nullable=False)
    # The day the tenant is leaving (empty if they have not given a date)
    end_date = Column(Date, nullable=True)
    # The monthly rent agreed for this stay (copied from the unit, so later rent changes do not affect it)
    rent_amount = Column(Integer, nullable=False)
    # The deposit agreed for this stay
    deposit_amount = Column(Integer, nullable=False, default=0)
    # The lease status: "active" or "ended"
    status = Column(String, nullable=False, default="active")
    # Any extra notes about this lease
    notes = Column(Text, nullable=True)
    # The date and time the lease was created
    created_at = Column(DateTime, default=datetime.utcnow)

    # Lets us write lease.unit to get the unit being rented
    unit = relationship("Unit", back_populates="leases")
    # Lets us write lease.tenant to get the person renting it
    tenant = relationship("Tenant", back_populates="leases")