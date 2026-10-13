# Import the tools that connect Python to a database
from sqlalchemy import create_engine
# Import tools to make database sessions and the base class for tables
from sqlalchemy.orm import sessionmaker, declarative_base

# Say where the database lives (a file called mnyumba.db, for now)
DATABASE_URL = "sqlite:///./mnyumba.db"

# Create the engine, which is the actual connection to the database
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a factory that gives us a fresh session (a short conversation with the database)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Create the base class that all our tables will copy from
Base = declarative_base()