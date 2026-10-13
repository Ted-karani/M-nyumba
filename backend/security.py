# Import tools to read environment variables (like our secret key)
import os
# Import date tools so tokens can expire
from datetime import datetime, timedelta, timezone
# Import bcrypt, the tool that scrambles passwords
import bcrypt
# Import jwt, the tool that makes and checks tokens
import jwt
# Import the tool that reads our .env file
from dotenv import load_dotenv

# Load the secrets from the .env file into memory
load_dotenv()

# Get our secret key (used to sign tokens so nobody can fake them)
SECRET_KEY = os.getenv("SECRET_KEY")
# Stop the app with a clear message if the key is missing
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing. Create the .env file first.")

# The method used to sign tokens
ALGORITHM = "HS256"
# How many minutes a token stays valid
TOKEN_MINUTES = 60


# Turn a normal password into a scrambled hash we can safely store
def hash_password(password: str) -> str:
    # Scramble the password with a random "salt" and return it as text
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Check if a typed password matches the stored hash
def verify_password(password: str, password_hash: str) -> bool:
    # Scramble the typed password the same way and compare
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# Make a token (a temporary pass) for a user
def create_access_token(user_id: int) -> str:
    # Work out when the token should stop working
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    # Put the user's id and the expiry time inside the token, then sign it
    return jwt.encode({"sub": str(user_id), "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)