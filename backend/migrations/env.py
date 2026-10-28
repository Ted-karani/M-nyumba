# env.py - tells Alembic how to find our database and our tables

# Import the tools we need
import os
from logging.config import fileConfig

# Migrations must never create tables behind our back, so the automatic table creation is switched off BEFORE the app is imported
os.environ["AUTO_CREATE_TABLES"] = "false"

from alembic import context  # noqa: E402

# Import our database, and the app (importing the app makes sure every table is known)
from database import Base, engine  # noqa: E402
import main  # noqa: E402,F401

# Alembic's settings from alembic.ini
config = context.config
# Set up the messages Alembic prints
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# The tables our code describes (Alembic compares the database with this)
target_metadata = Base.metadata


# Run the migrations against the real database
def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Notice changes to a column's type too
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


# We only run migrations against a real database (not by writing SQL files)
if context.is_offline_mode():
    raise RuntimeError("Offline mode is not used in this project.")
run_migrations_online()