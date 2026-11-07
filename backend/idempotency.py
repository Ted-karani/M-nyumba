# idempotency.py - makes sure a request that is sent twice (a bad signal makes the phone try again) only happens once

# Import the tools we need
import base64
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timedelta
# Import the tool that runs normal (slow) code without blocking the server
from fastapi.concurrency import run_in_threadpool
# Import the column types we need for the table
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError
# Import the tools for middleware (code that sees every request)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

# Import our own files
from database import Base, SessionLocal

# Only these addresses honour the secret number (a repair report, and a checklist photo)
PROTECTED = [re.compile(r"^/maintenance$"), re.compile(r"^/inspections/\d+/photos$")]
# What a valid secret number looks like
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,80}$")
# A request that has been "running" for longer than this is considered stuck, and may be run again
STALE_AFTER = timedelta(minutes=2)
# How long we remember a secret number
KEEP_FOR = timedelta(days=7)
# We only remember answers up to this size
MAX_BODY = 256 * 1024


# This class is the "idempotency_keys" table. Each secret number a phone sent is one row.
class IdempotencyKey(Base):
    # The name of the table inside the database
    __tablename__ = "idempotency_keys"
    # One secret number can only be used once per person
    __table_args__ = (UniqueConstraint("user_id", "key", name="one_key_per_user"),)

    # A unique number for each row, created automatically
    id = Column(Integer, primary_key=True, index=True)
    # Who sent it (points to the users table)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # The secret number the phone made up
    key = Column(String, nullable=False)
    # What the request was
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    # "processing" while we work on it, "done" once we have the answer
    state = Column(String, nullable=False, default="processing")
    # The answer we gave (so we can give the same answer again)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    # When it started
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# Work out who is asking from the sign-in token (this checks the token's signature and its expiry, nothing else)
def user_id_from_token(token: str):
    try:
        header, payload, signature = token.split(".")
        secret = os.getenv("SECRET_KEY", "").encode()
        expected = base64.urlsafe_b64encode(hmac.new(secret, f"{header}.{payload}".encode(), hashlib.sha256).digest()).rstrip(b"=")
        if not hmac.compare_digest(expected, signature.encode()):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data.get("exp") is not None and float(data["exp"]) < time.time():
            return None
        return int(data["sub"])
    except Exception:
        return None


# Claim a secret number. The answer is one of: run it, replay the earlier answer, it is busy, or the key was used for something else
def claim(user_id: int, key: str, path: str):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Forget old secret numbers
        db.query(IdempotencyKey).filter(IdempotencyKey.created_at < now - KEEP_FOR).delete()
        db.add(IdempotencyKey(user_id=user_id, key=key, method="POST", path=path, state="processing", created_at=now))
        try:
            db.commit()
            return ("run", None)
        except IntegrityError:
            db.rollback()
        existing = db.query(IdempotencyKey).filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key).first()
        if existing is None:
            return ("run", None)
        if existing.path != path:
            return ("conflict", None)
        if existing.state == "done" and existing.status_code is not None:
            return ("replay", (existing.status_code, existing.response_body or ""))
        if now - existing.created_at > STALE_AFTER:
            existing.created_at = now
            db.commit()
            return ("run", None)
        return ("busy", None)
    finally:
        db.close()


# Remember the answer (only for successes; anything else is forgotten, so a retry really runs again)
def finish(user_id: int, key: str, status: int, body: bytes):
    db = SessionLocal()
    try:
        row = db.query(IdempotencyKey).filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key).first()
        if row is None:
            return
        if 200 <= status < 300 and len(body) <= MAX_BODY:
            row.state = "done"
            row.status_code = status
            row.response_body = body.decode("utf-8", "replace")
        else:
            db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# This watches every request: if the phone sent a secret number we have seen before, we repeat the old answer
class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        key = request.headers.get("idempotency-key")
        # Only repair reports and checklist photos, and only when a secret number was sent
        if request.method != "POST" or not key or not any(pattern.match(request.url.path) for pattern in PROTECTED):
            return await call_next(request)
        if not KEY_PATTERN.match(key):
            return JSONResponse({"detail": "The Idempotency-Key is not valid"}, status_code=400)
        header = request.headers.get("authorization", "")
        user_id = user_id_from_token(header[7:]) if header.lower().startswith("bearer ") else None
        # Not signed in: the normal checks will refuse it
        if user_id is None:
            return await call_next(request)
        outcome, stored = await run_in_threadpool(claim, user_id, key, request.url.path)
        if outcome == "replay":
            status, text = stored
            return Response(content=text, status_code=status, media_type="application/json", headers={"Idempotent-Replay": "true"})
        if outcome == "busy":
            return JSONResponse({"detail": "This request is still being processed. Please wait a moment and try again"}, status_code=409)
        if outcome == "conflict":
            return JSONResponse({"detail": "This request key was already used for something else"}, status_code=409)
        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        await run_in_threadpool(finish, user_id, key, response.status_code, body)
        headers = {name: value for name, value in response.headers.items() if name.lower() != "content-length"}
        return Response(content=body, status_code=response.status_code, headers=headers)