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

# Some hosts give addresses starting with "postgres://", but SQLAlchemy wants "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# Name the PostgreSQL driver we installed (psycopg2), so SQLAlchemy does not pick a different one
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

# Is this the simple file database we use on the laptop?
is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite needs one extra setting so the web server and the tests can share it
connect_args = {"check_same_thread": False} if is_sqlite else {}

# PostgreSQL connections can go stale, so we check them before use and keep the pool small
engine_options = {} if is_sqlite else {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 5, "pool_recycle": 1800}

# Create the engine, which is the actual connection to the database
engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_options)

# Create a factory that gives us a fresh session (a short conversation with the database)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Create the base class that all our tables will copy from
Base = declarative_base()