# Import the tools we need
import hmac
import json
import secrets
from datetime import datetime, timezone
# Import the tool that makes and checks the 6-digit codes
import pyotp

# Import our own files
import security

# The name shown in the authenticator app
ISSUER = "M-nyumba"
# How many recovery codes we give
RECOVERY_CODE_COUNT = 8


# Make a new secret to share with an authenticator app
def new_secret() -> str:
    return pyotp.random_base32()


# Make the address that the QR code holds (an authenticator app reads it)
def otpauth_url(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


# Check a 6-digit code: it must be right, and newer than the last code we accepted
def check_code(row, code: str) -> bool:
    # Tidy up the code: no spaces, and exactly 6 digits
    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return False
    totp = pyotp.TOTP(row.secret)
    now = datetime.now(timezone.utc)
    # The number of the current 30-second window
    base = totp.timecode(now)
    # Allow the window just before and just after, in case the phone's clock is a little off
    for offset in (-1, 0, 1):
        if hmac.compare_digest(totp.at(now, counter_offset=offset), code):
            counter = base + offset
            # A code from a window we already used is a replay
            if counter <= (row.last_counter or 0):
                return False
            row.last_counter = counter
            return True
    return False


# Make a fresh set of recovery codes, like "a1b2c3-d4e5f6"
def make_recovery_codes() -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(RECOVERY_CODE_COUNT)]


# Scramble the recovery codes so only the scrambled versions are stored
def hash_codes(codes: list[str]) -> str:
    return json.dumps([security.hash_password(code) for code in codes])


# Check a recovery code, and use it up if it is right (the caller saves the change to the database)
def use_recovery_code(row, code: str) -> bool:
    code = code.strip().lower()
    hashes = json.loads(row.recovery_hashes or "[]")
    for index, stored in enumerate(hashes):
        if security.verify_password(code, stored):
            # Remove it so it cannot be used again
            del hashes[index]
            row.recovery_hashes = json.dumps(hashes)
            return True
    return False