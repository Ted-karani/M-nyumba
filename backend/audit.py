# Import the tool that checks text patterns
import re
# Import the tool that runs slow work without freezing the app
from fastapi.concurrency import run_in_threadpool
# Import the tool that reads login tokens
import jwt
# Import the tool that lets us watch every request
from starlette.middleware.base import BaseHTTPMiddleware

# Import our own files
import models
import security
from database import SessionLocal
from security_models import AuditLog

# Only requests that change things are recorded (just looking at a page is not)
MUTATING = {"POST", "PUT", "DELETE"}


# Make one rule: a request kind, an address pattern, and the words to record (None means "do not record this one")
def rule(method, pattern, text):
    return (method, re.compile(pattern), text)


# The words we record for each kind of change
RULES = [
    rule("POST", r"^/properties$", "Added a property"),
    rule("PUT", r"^/properties/(\d+)$", "Edited property #{0}"),
    rule("DELETE", r"^/properties/(\d+)$", "Deleted property #{0}"),
    rule("POST", r"^/properties/(\d+)/units$", "Added a unit to property #{0}"),
    rule("PUT", r"^/units/(\d+)$", "Edited unit #{0}"),
    rule("DELETE", r"^/units/(\d+)$", "Deleted unit #{0}"),
    rule("POST", r"^/tenants$", "Added a tenant"),
    rule("PUT", r"^/tenants/(\d+)$", "Edited tenant #{0}"),
    rule("DELETE", r"^/tenants/(\d+)$", "Deleted tenant #{0}"),
    rule("POST", r"^/leases$", "Moved a tenant into a unit"),
    rule("PUT", r"^/leases/(\d+)$", "Edited lease #{0}"),
    rule("POST", r"^/leases/(\d+)/end$", "Ended lease #{0}"),
    rule("POST", r"^/leases/(\d+)/charges$", "Added a charge to lease #{0}"),
    rule("DELETE", r"^/charges/(\d+)$", "Deleted charge #{0}"),
    rule("POST", r"^/leases/(\d+)/payments$", "Recorded a payment on lease #{0}"),
    rule("DELETE", r"^/payments/(\d+)$", "Deleted payment #{0}"),
    rule("POST", r"^/billing/generate-rent$", "Added the monthly rent charges"),
    rule("POST", r"^/utilities/bill$", "Saved meter readings and billed tenants"),
    rule("POST", r"^/utilities/bill-wifi$", "Charged Wi-Fi"),
    rule("DELETE", r"^/utilities/readings/(\d+)$", "Undid meter reading #{0}"),
    rule("POST", r"^/maintenance$", "Reported a repair"),
    rule("PUT", r"^/maintenance/(\d+)$", "Updated repair #{0}"),
    rule("DELETE", r"^/maintenance/(\d+)$", "Deleted repair #{0}"),
    rule("PUT", r"^/work/units/(\d+)/status$", "Changed the status of unit #{0}"),
    rule("POST", r"^/caretakers$", "Added a caretaker"),
    rule("PUT", r"^/caretakers/(\d+)$", "Changed caretaker #{0} (access, properties or password)"),
    rule("POST", r"^/onboarding/existing-tenants$", "Checked or imported a list of existing tenants"),
    rule("POST", r"^/reminders$", "Opened a payment reminder"),
    rule("POST", r"^/expenses$", "Recorded an expense"),
    rule("PUT", r"^/expenses/(\d+)$", "Edited expense #{0}"),
    rule("DELETE", r"^/expenses/(\d+)$", "Deleted expense #{0}"),
    rule("POST", r"^/documents$", "Uploaded a document"),
    rule("PUT", r"^/documents/(\d+)$", "Edited document #{0}"),
    rule("DELETE", r"^/documents/(\d+)$", "Deleted document #{0}"),
    rule("POST", r"^/tasks$", "Added a task"),
    rule("PUT", r"^/tasks/(\d+)$", "Edited task #{0}"),
    rule("DELETE", r"^/tasks/(\d+)$", "Deleted task #{0}"),
    rule("POST", r"^/tasks/(\d+)/done$", "Marked task #{0} done"),
    rule("POST", r"^/inspections/lease/(\d+)/(move_in|move_out)$", "Started the {1} checklist for lease #{0}"),
    rule("POST", r"^/inspections/(\d+)/finalize$", "Locked checklist #{0}"),
    rule("POST", r"^/inspections/(\d+)/unlock$", "Unlocked checklist #{0}"),
    rule("DELETE", r"^/inspections/(\d+)$", "Deleted checklist #{0}"),
    rule("POST", r"^/inspections/(\d+)/photos$", "Added a photo to checklist #{0}"),
    rule("DELETE", r"^/inspections/photos/(\d+)$", "Deleted a checklist photo"),
    rule("POST", r"^/inspections/(\d+)/items$", "Added an area to checklist #{0}"),
    rule("PUT", r"^/inspections/items/(\d+)$", None),
    rule("DELETE", r"^/inspections/items/(\d+)$", "Removed an area from a checklist"),
    rule("PUT", r"^/inspections/(\d+)$", "Edited the details of checklist #{0}"),
    rule("POST", r"^/account/change-password$", "Changed their password"),
]


# Turn a request into words (None means "do not record it")
def describe(method: str, path: str):
    for rule_method, pattern, text in RULES:
        if rule_method != method:
            continue
        match = pattern.match(path)
        if match:
            # Some rules are marked as "too chatty to record"
            if text is None:
                return None
            # Fill in the numbers from the address, and write move_in as move-in
            return text.format(*match.groups()).replace("move_in", "move-in").replace("move_out", "move-out")
    # If we have no words for it, record the plain request
    return f"{method} {path}"


# Find which owner's business a person works for
def owner_id_for(db, user):
    # Owners work for themselves
    if user.role == "owner":
        return user.id
    # Caretakers work for the owner who created them
    account = db.query(models.CaretakerAccount).filter(models.CaretakerAccount.user_id == user.id).first()
    return account.owner_id if account else None


# Save one entry in the activity log
def write_entry(token: str, method: str, path: str, ip):
    db = SessionLocal()
    try:
        # Find out who the token belongs to
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        user = db.get(models.User, int(payload["sub"]))
        if user is None:
            return
        # Work out the words, and skip the ones we do not record
        summary = describe(method, path)
        owner_id = owner_id_for(db, user)
        if summary is None or owner_id is None:
            return
        # Save the entry
        db.add(AuditLog(
            owner_id=owner_id,
            actor_id=user.id,
            actor_name=user.full_name,
            actor_role=user.role,
            summary=summary,
            method=method,
            path=path,
            ip=ip,
        ))
        db.commit()
    except Exception:
        # The log must never break the real request
        db.rollback()
    finally:
        db.close()


# Record that someone signed in
def log_signin(db, user, ip):
    owner_id = owner_id_for(db, user)
    if owner_id is None:
        return
    db.add(AuditLog(
        owner_id=owner_id,
        actor_id=user.id,
        actor_name=user.full_name,
        actor_role=user.role,
        summary="Signed in",
        method="POST",
        path="/auth/login",
        ip=ip,
    ))
    db.commit()


# This watches every request, and records the ones that changed something and worked
class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Let the request run first
        response = await call_next(request)
        # Record it only if it changes things and it worked
        if request.method in MUTATING and 200 <= response.status_code < 400:
            header = request.headers.get("authorization", "")
            if header.lower().startswith("bearer "):
                ip = request.client.host if request.client else None
                await run_in_threadpool(write_entry, header[7:], request.method, request.url.path, ip)
        return response