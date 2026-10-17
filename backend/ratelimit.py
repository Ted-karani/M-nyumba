# Import the date and time tools
from datetime import datetime, timedelta
# Import the tool that finds the biggest value
from sqlalchemy import func

# Import our own files
from security_models import LoginAttempt

# We look at the last 15 minutes
WINDOW = timedelta(minutes=15)
# This many wrong passwords for one email lock it
MAX_PER_EMAIL = 5
# This many wrong passwords from one address (across all emails) lock that address
MAX_PER_IP = 20


# Work out how many seconds someone must still wait before trying again (0 means they may try now)
def seconds_locked(db, email: str, ip: str | None) -> int:
    now = datetime.utcnow()
    since = now - WINDOW
    wait = 0

    # A successful sign-in clears the earlier wrong passwords for that email
    last_ok = (
        db.query(func.max(LoginAttempt.created_at))
        .filter(LoginAttempt.email == email, LoginAttempt.success.is_(True))
        .scalar()
    )
    start = max(since, last_ok) if last_ok else since

    # The wrong passwords for this email, oldest first
    email_failures = [
        created
        for (created,) in db.query(LoginAttempt.created_at)
        .filter(LoginAttempt.email == email, LoginAttempt.success.is_(False), LoginAttempt.created_at > start)
        .order_by(LoginAttempt.created_at)
        .all()
    ]
    if len(email_failures) >= MAX_PER_EMAIL:
        # The lock lifts when enough old attempts have aged out of the 15 minutes
        release = email_failures[len(email_failures) - MAX_PER_EMAIL] + WINDOW
        wait = max(wait, int((release - now).total_seconds()) + 1)

    # The wrong passwords from this address, oldest first
    if ip:
        ip_failures = [
            created
            for (created,) in db.query(LoginAttempt.created_at)
            .filter(LoginAttempt.ip == ip, LoginAttempt.success.is_(False), LoginAttempt.created_at > since)
            .order_by(LoginAttempt.created_at)
            .all()
        ]
        if len(ip_failures) >= MAX_PER_IP:
            release = ip_failures[len(ip_failures) - MAX_PER_IP] + WINDOW
            wait = max(wait, int((release - now).total_seconds()) + 1)

    return max(0, wait)


# Remember a sign-in attempt (this saves to the database right away)
def record(db, email: str, ip: str | None, success: bool):
    db.add(LoginAttempt(email=email, ip=ip, success=success))
    # After a good sign-in, tidy away attempts older than 30 days
    if success:
        db.query(LoginAttempt).filter(LoginAttempt.created_at < datetime.utcnow() - timedelta(days=30)).delete()
    db.commit()