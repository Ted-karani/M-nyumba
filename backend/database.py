# Import the tool that reads settings from the environment
import os
# Import the tool that reads our .env file
from dotenv import load_dotenv
# Import the tool that connects Python to a database
from sqlalchemy import create_engine
# Import tools to make database sessions and the base class for tables
from sqlalchemy.orm import sessionmaker, declarative_base

# Load the settings from the .env file into memory
load_dotenv()

# Say where the database lives (a file called mnyumba.db, unless a different address is set)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mnyumba.db")

# SQLite needs one extra setting so the web server and the tests can share it
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Create the engine, which is the actual connection to the database
engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Create a factory that gives us a fresh session (a short conversation with the database)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Create the base class that all our tables will copy from
Base = declarative_base()