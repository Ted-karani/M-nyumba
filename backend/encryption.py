# Import the tool that reads settings from the environment
import os
# Import the tools that lock and unlock text
from cryptography.fernet import Fernet, InvalidToken
# Import the tool that reads our .env file
from dotenv import load_dotenv
# Import the tools that let us make our own kind of database column
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

# Load the secrets from the .env file into memory
load_dotenv()

# Get the secret key used to scramble text
KEY = os.getenv("ENCRYPTION_KEY")
# Stop the app with a clear message if the key is missing
if not KEY:
    raise RuntimeError("ENCRYPTION_KEY is missing. Add it to the .env file first.")
# Make the lock-and-unlock tool from the key
try:
    fernet = Fernet(KEY.encode("utf-8"))
except ValueError:
    raise RuntimeError("ENCRYPTION_KEY in the .env file is not a valid key. Make a new one with the command in the instructions.")

# Scrambled values start with this, so we can tell them apart from old plain ones
PREFIX = "enc1:"


# Scramble some text so it can be stored safely
def encrypt_text(plain: str) -> str:
    # Lock the text and put our marker in front of it
    return PREFIX + fernet.encrypt(plain.encode("utf-8")).decode("utf-8")


# Unscramble some stored text (old plain values are handed back as they are)
def decrypt_text(stored: str):
    # Values without our marker were saved before we started scrambling
    if not stored.startswith(PREFIX):
        return stored
    try:
        # Unlock the text
        return fernet.decrypt(stored[len(PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # The key does not match, so the text cannot be read
        return None


# A database column that scrambles text on the way in and unscrambles it on the way out
class EncryptedText(TypeDecorator):
    # It is stored as ordinary text underneath
    impl = String
    # This tells SQLAlchemy the column is safe to reuse in its caches
    cache_ok = True

    # Runs when a value is being saved
    def process_bind_param(self, value, dialect):
        # Empty values stay empty
        if value is None or value == "":
            return value
        return encrypt_text(value)

    # Runs when a value is being read
    def process_result_value(self, value, dialect):
        # Empty values stay empty
        if value is None or value == "":
            return value
        return decrypt_text(value)