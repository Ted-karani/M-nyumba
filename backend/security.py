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
# How many minutes a login token stays valid
TOKEN_MINUTES = 60
# How many minutes the "now enter your code" pass stays valid
CHALLENGE_MINUTES = 5
# How hard passwords are to scramble (12 is slow on purpose, which protects them; the tests use a small number to run fast)
ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))


# Turn a normal password into a scrambled hash we can safely store
def hash_password(password: str) -> str:
    # Scramble the password with a random "salt" and return it as text
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=ROUNDS)).decode("utf-8")


# Check if a typed password matches the stored hash
def verify_password(password: str, password_hash: str) -> bool:
    # Scramble the typed password the same way and compare
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# Make a token (a temporary pass) for a user
def create_access_token(user_id: int) -> str:
    # The current time, and when the token should stop working
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=TOKEN_MINUTES)
    # Put the user's id, the exact time it was made, and the expiry time inside the token, then sign it
    return jwt.encode(
        {"sub": str(user_id), "iat": now.timestamp(), "exp": expires},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# Make the short-lived pass given after a correct password, when the person still has to enter a code
def create_challenge_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=CHALLENGE_MINUTES)
    # The "purpose" marks it as NOT a login token
    return jwt.encode({"sub": str(user_id), "purpose": "2fa", "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


# Read that pass, and return the user's id (or nothing if it is fake, expired, or the wrong kind)
def read_challenge_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    # Only passes made for this purpose count
    if payload.get("purpose") != "2fa":
        return None
    try:
        return int(payload["sub"])
    except (KeyError, ValueError):
        return None