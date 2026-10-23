# mpesa.py - asks tenants to pay by M-Pesa, and records the payment only after Safaricom confirms it
# This file goes inside the "routers" folder (it replaces the earlier mpesa.py)

# Import the tools we need
import base64
import hmac
import os
import re
# Import the date and time tools
from datetime import datetime, timedelta
# Import tool used to call Safaricom's servers
import requests
# Import tool that reads the .env file on your laptop
from dotenv import load_dotenv
# Import FastAPI tools for endpoints, request bodies, and errors
from fastapi import APIRouter, Body, Depends, HTTPException
# Import the tool that describes the data we expect
from pydantic import BaseModel
# Import the tool that counts rows
from sqlalchemy import func
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import mpesa_models
from dependencies import get_db, get_current_user
from routers.leases import get_owned_lease
from routers.portal import active_leases, lease_totals, ready_context
from routers.properties import require_owner

# Load everything inside the .env file (on Render the settings come from the dashboard instead)
load_dotenv()

# Our app's key and secret from Safaricom
CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
# The business number (174379 in the sandbox) and the passkey used to sign each request
SHORTCODE = os.getenv("MPESA_SHORTCODE")
PASSKEY = os.getenv("MPESA_PASSKEY")
# The start of the address where Safaricom sends results (without the secret part)
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")
# A long secret added to the end of the callback address
CALLBACK_SECRET = os.getenv("MPESA_CALLBACK_SECRET")
# Safaricom's address: the sandbox until we go live (then MPESA_BASE_URL is set to https://api.safaricom.co.ke)
BASE_URL = os.getenv("MPESA_BASE_URL", "https://sandbox.safaricom.co.ke").rstrip("/")
# The owners allowed to use these M-Pesa settings, because they belong to ONE Paybill (emails separated by commas)
ALLOWED_OWNERS = {email.strip().lower() for email in os.getenv("MPESA_OWNER_EMAILS", "").split(",") if email.strip()}
# On the live server this switch is always ignored
IS_PRODUCTION = os.getenv("ENVIRONMENT", "").lower() == "production"
# FOR TESTING ON YOUR LAPTOP ONLY: believe the callback without asking Safaricom
TRUST_CALLBACK = os.getenv("MPESA_TRUST_CALLBACK", "false").lower() == "true" and not IS_PRODUCTION
# How old a pending request must be before the status check asks Safaricom about it
MIN_POLL_AGE_SECONDS = 15
# The most one prompt can ask for (M-Pesa's limit for one payment)
MAX_AMOUNT = 250000
# The most prompts one lease can get in 15 minutes
MAX_PROMPTS_PER_LEASE = 3

# Make a group of endpoints for M-Pesa
router = APIRouter(tags=["M-Pesa"])

# The reply Safaricom needs to hear after it sends us a result
ACCEPTED = {"ResultCode": 0, "ResultDesc": "Accepted"}

# The access token we got from Safaricom (kept for a while so we do not ask every time)
_token_cache = {"value": None, "expires": datetime.min}


# The data we expect when an owner asks for a payment
class PayRequest(BaseModel):
    # The lease the payment is for
    lease_id: int
    # The amount in shillings
    amount: int
    # The phone to send the prompt to (if empty, we use the tenant's phone)
    phone: str | None = None


# The data we expect when a tenant pays
class PortalPay(BaseModel):
    # The amount in shillings
    amount: int
    # Which home it is for (if empty, the newest one)
    lease_id: int | None = None


# Turn 0712345678 into 254712345678, the format Safaricom needs
def clean_phone(phone):
    # Remove spaces and the plus sign
    phone = phone.strip().replace(" ", "").replace("+", "")
    # If it starts with 0, swap the 0 for 254
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    # If it is just the 9 digits, add 254
    elif len(phone) == 9 and phone[0] in "71":
        phone = "254" + phone
    return phone


# Today's date in Kenya (this works the same whatever the server's clock is set to)
def today_kenya():
    return (datetime.utcnow() + timedelta(hours=3)).date()


# Are all the M-Pesa settings filled in?
def settings_ready():
    return all([CONSUMER_KEY, CONSUMER_SECRET, SHORTCODE, PASSKEY, CALLBACK_URL, CALLBACK_SECRET])


# Ask Safaricom for a temporary access token (and keep it for about 50 minutes)
def get_token():
    # Use the saved one if it is still good
    if _token_cache["value"] and datetime.utcnow() < _token_cache["expires"]:
        return _token_cache["value"]
    try:
        # Send our key and secret to prove who we are
        response = requests.get(
            BASE_URL + "/oauth/v1/generate?grant_type=client_credentials",
            auth=(CONSUMER_KEY, CONSUMER_SECRET),
            timeout=30,
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach M-Pesa. Please try again")
    # If Safaricom said no, stop with an error
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not get an M-Pesa token")
    # Keep the token for a while
    _token_cache["value"] = response.json()["access_token"]
    _token_cache["expires"] = datetime.utcnow() + timedelta(seconds=3000)
    return _token_cache["value"]


# Send a request to Safaricom and give back its answer (failed or unreadable answers become a friendly error)
def safaricom_post(path, body):
    token = get_token()
    try:
        response = requests.post(BASE_URL + path, json=body, headers={"Authorization": "Bearer " + token}, timeout=30)
        return response.json()
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach M-Pesa. Please try again")
    except ValueError:
        raise HTTPException(status_code=502, detail="M-Pesa sent an answer we could not read")


# Make the password and timestamp Safaricom wants with every request
def stk_password():
    # The current time in Kenya, like 20261021143000
    timestamp = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
    # Join shortcode + passkey + timestamp, and encode it
    raw = SHORTCODE + PASSKEY + timestamp
    return base64.b64encode(raw.encode()).decode(), timestamp


# Ask Safaricom what really happened to a request: "paid", "cancelled", "failed", or "pending" (not finished or unknown)
def ask_safaricom(row):
    password, timestamp = stk_password()
    answer = safaricom_post(
        "/mpesa/stkpushquery/v1/query",
        {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": row.checkout_request_id,
        },
    )
    # While the payment is still being processed Safaricom answers with an error instead of a result
    if "ResultCode" not in answer:
        return "pending", answer.get("errorMessage") or answer.get("ResponseDescription")
    code = str(answer["ResultCode"])
    message = answer.get("ResultDesc")
    # 0 means paid, 1032 means the tenant cancelled, anything else means it did not work
    if code == "0":
        return "paid", message
    if code == "1032":
        return "cancelled", message
    return "failed", message


# Update a request with what Safaricom said, and record the payment when it was paid
def apply_outcome(db, row, outcome, message, receipt):
    # Only a request that is still waiting can be finished (this also stops double payments)
    if row.status != "pending" or outcome == "pending":
        return
    row.status = outcome
    row.result_desc = message
    row.completed_at = datetime.utcnow()
    if outcome != "paid":
        return
    # A note that links the payment to this request, so it is only ever recorded once
    note = f"Paid by M-Pesa prompt (request #{row.id})"
    if db.query(models.Payment).filter(models.Payment.notes == note).first() is not None:
        return
    # An M-Pesa code can only be used once
    code = receipt
    if code and db.query(models.Payment).filter(models.Payment.reference == code).first() is not None:
        code = None
    # Record the payment for the amount we ASKED for (never the amount a message claims)
    db.add(models.Payment(
        lease_id=row.lease_id,
        amount=row.amount,
        paid_on=today_kenya(),
        method="mpesa",
        reference=code,
        recorded_by_id=None,
        notes=note,
    ))
    row.receipt = code


# If the payment was recorded without its M-Pesa code (the callback was late), add the code when it arrives
def add_late_receipt(db, row, receipt):
    if not receipt or row.receipt:
        return
    if db.query(models.Payment).filter(models.Payment.reference == receipt).first() is not None:
        return
    note = f"Paid by M-Pesa prompt (request #{row.id})"
    payment = db.query(models.Payment).filter(models.Payment.notes == note).first()
    if payment is not None and payment.reference is None:
        payment.reference = receipt
        row.receipt = receipt


# If a request is still waiting, ask Safaricom directly (this finds payments whose callback never arrived)
def check_with_safaricom(db, row):
    age = (datetime.utcnow() - row.created_at).total_seconds()
    if row.status == "pending" and settings_ready() and age >= MIN_POLL_AGE_SECONDS:
        try:
            outcome, message = ask_safaricom(row)
            apply_outcome(db, row, outcome, message, None)
            db.commit()
        except HTTPException:
            # Could not ask right now: keep showing "pending"
            db.rollback()


# Send the payment prompt to a phone and remember it as "pending" (used by both owners and tenants)
def send_prompt(db, lease, amount, phone, requested_by):
    # Make sure all the M-Pesa settings are filled in
    if not settings_ready():
        raise HTTPException(status_code=500, detail="M-Pesa settings are missing")
    # The amount must be sensible
    if amount < 1 or amount > MAX_AMOUNT:
        raise HTTPException(status_code=400, detail=f"The amount must be between 1 and {MAX_AMOUNT:,} shillings")
    # Clean the phone and check it looks right
    phone = clean_phone(phone)
    if not re.fullmatch(r"254[17]\d{8}", phone):
        raise HTTPException(status_code=400, detail="That phone number does not look right")
    # Stop prompts from being sent again and again to the same tenant
    recent = (
        db.query(func.count(mpesa_models.MpesaRequest.id))
        .filter(
            mpesa_models.MpesaRequest.lease_id == lease.id,
            mpesa_models.MpesaRequest.created_at >= datetime.utcnow() - timedelta(minutes=15),
        )
        .scalar()
    )
    if recent >= MAX_PROMPTS_PER_LEASE:
        raise HTTPException(status_code=429, detail="Too many prompts for this tenant. Please wait a few minutes")

    # The password and timestamp for this request
    password, timestamp = stk_password()
    # The payment request
    body = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        # A Paybill payment
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        # Who is paying, and which phone gets the PIN prompt
        "PartyA": phone,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone,
        # Where the result is sent (our address plus the secret)
        "CallBackURL": CALLBACK_URL.rstrip("/") + "/" + CALLBACK_SECRET,
        # The account number the payment is credited to: the unit number, so statements match
        "AccountReference": str(lease.unit.unit_number)[:12],
        "TransactionDesc": "Rent payment",
    }
    # Send the request to Safaricom
    answer = safaricom_post("/mpesa/stkpush/v1/processrequest", body)
    # If Safaricom did not accept it, tell the user why
    if answer.get("ResponseCode") != "0":
        message = answer.get("errorMessage") or answer.get("ResponseDescription") or "M-Pesa refused the request"
        raise HTTPException(status_code=400, detail=message)

    # Remember this request as "pending" until the result is confirmed
    row = mpesa_models.MpesaRequest(
        lease_id=lease.id,
        phone=phone,
        amount=amount,
        checkout_request_id=answer["CheckoutRequestID"],
        merchant_request_id=answer.get("MerchantRequestID"),
        status="pending",
        requested_by_id=requested_by.id,
    )
    db.add(row)
    db.commit()
    # Tell the screen what to look out for
    return {
        "message": "Prompt sent. Enter your M-Pesa PIN on the phone.",
        "checkout_request_id": row.checkout_request_id,
        "status": row.status,
    }


# Is the "Request M-Pesa" button available to this person?
@router.get("/mpesa/enabled")
def mpesa_enabled(current_user: models.User = Depends(get_current_user)):
    allowed = current_user.role == "owner" and settings_ready() and current_user.email.lower() in ALLOWED_OWNERS
    return {"enabled": allowed}


# Ask a tenant's phone for a payment (only an allowed owner of the lease can do this)
@router.post("/mpesa/stk-push")
def stk_push(
    data: PayRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can ask for payments
    require_owner(current_user)
    # The M-Pesa settings belong to one Paybill, so only the owners on the allowed list can use them
    if current_user.email.lower() not in ALLOWED_OWNERS:
        raise HTTPException(status_code=403, detail="M-Pesa prompts are not switched on for your account yet")
    # Make sure the lease belongs to this owner
    lease = get_owned_lease(db, data.lease_id, current_user)
    # Send the prompt (to the phone we were given, or the tenant's own phone)
    return send_prompt(db, lease, data.amount, data.phone or lease.tenant.phone, current_user)


# Safaricom calls this address when the tenant has paid, cancelled, or failed (no login: Safaricom is the caller)
@router.post("/payments/callback/{secret}")
def mpesa_callback(
    secret: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    # If the secret in the address is wrong, pretend this address does not exist
    if not CALLBACK_SECRET or not hmac.compare_digest(secret, CALLBACK_SECRET):
        raise HTTPException(status_code=404, detail="Not found")
    # Try to read the message out of what Safaricom sent
    try:
        result = payload["Body"]["stkCallback"]
        checkout_id = result["CheckoutRequestID"]
        result_code = int(result["ResultCode"])
    except (KeyError, TypeError, ValueError):
        # A message we cannot read: say thanks and ignore it
        return ACCEPTED
    # Find the request we saved earlier, and lock it while we work on it (so two callbacks cannot record twice)
    row = (
        db.query(mpesa_models.MpesaRequest)
        .filter(mpesa_models.MpesaRequest.checkout_request_id == checkout_id)
        .with_for_update()
        .first()
    )
    # Unknown request: say thanks and do nothing
    if row is None:
        return ACCEPTED
    # The M-Pesa code, if the message has one
    items = (result.get("CallbackMetadata") or {}).get("Item", [])
    receipt = {item.get("Name"): item.get("Value") for item in items if isinstance(item, dict)}.get("MpesaReceiptNumber")
    # Already paid, but without its code: add the code now
    if row.status == "paid":
        add_late_receipt(db, row, receipt)
        db.commit()
        return ACCEPTED
    # Already finished some other way: nothing to do
    if row.status != "pending":
        return ACCEPTED

    if TRUST_CALLBACK:
        # Testing on a laptop only: believe the message
        outcome = "paid" if result_code == 0 else ("cancelled" if result_code == 1032 else "failed")
        message = result.get("ResultDesc")
    else:
        # The message is only a nudge: ask Safaricom what really happened
        if not settings_ready():
            return ACCEPTED
        try:
            outcome, message = ask_safaricom(row)
        except HTTPException:
            # Could not ask right now: leave it pending, the status check will try again
            return ACCEPTED
    apply_outcome(db, row, outcome, message, receipt if result_code == 0 else None)
    db.commit()
    return ACCEPTED


# Check what happened to a payment request (the owner's screen uses this to show "paid" or "failed")
@router.get("/mpesa/status/{checkout_request_id}")
def mpesa_status(
    checkout_request_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find the request, and lock it while we work on it
    row = (
        db.query(mpesa_models.MpesaRequest)
        .filter(mpesa_models.MpesaRequest.checkout_request_id == checkout_request_id)
        .with_for_update()
        .first()
    )
    # Not found
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    # Make sure its lease belongs to this user (says "not found" if it does not)
    get_owned_lease(db, row.lease_id, current_user)
    # Still waiting? Ask Safaricom directly
    check_with_safaricom(db, row)
    # Send back where it stands
    return {"status": row.status, "message": row.result_desc, "receipt": row.receipt}


# Is the "Pay now" button available to this tenant? (it needs their landlord to be switched on)
@router.get("/portal/mpesa/enabled")
def portal_pay_enabled(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    landlord = db.get(models.User, account.owner_id)
    allowed = landlord is not None and settings_ready() and landlord.email.lower() in ALLOWED_OWNERS
    return {"enabled": allowed}


# A tenant pays their own rent: the prompt goes to their own phone, for no more than they owe
@router.post("/portal/mpesa/pay")
def portal_pay(
    data: PortalPay,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    # The landlord must be switched on
    landlord = db.get(models.User, account.owner_id)
    if landlord is None or landlord.email.lower() not in ALLOWED_OWNERS:
        raise HTTPException(status_code=403, detail="Pay now is not switched on yet. Please use the Paybill details to pay")
    # Pick the home: the one asked for, or the newest
    homes = active_leases(db, tenant.id)
    if not homes:
        raise HTTPException(status_code=400, detail="You have no active tenancy")
    chosen = homes[0]
    if data.lease_id is not None:
        matches = [row for row in homes if row[0].id == data.lease_id]
        if not matches:
            raise HTTPException(status_code=404, detail="Lease not found")
        chosen = matches[0]
    lease = chosen[0]
    # They can only pay what they owe
    charged, paid = lease_totals(db, lease.id)
    balance = charged - paid
    if balance <= 0:
        raise HTTPException(status_code=400, detail="You do not owe anything right now")
    if data.amount < 1 or data.amount > balance:
        raise HTTPException(status_code=400, detail=f"You can pay between 1 and {balance:,} shillings")
    # Only one prompt can wait at a time
    waiting = (
        db.query(mpesa_models.MpesaRequest)
        .filter(
            mpesa_models.MpesaRequest.lease_id == lease.id,
            mpesa_models.MpesaRequest.status == "pending",
            mpesa_models.MpesaRequest.created_at >= datetime.utcnow() - timedelta(minutes=2),
        )
        .first()
    )
    if waiting is not None:
        raise HTTPException(status_code=409, detail="A prompt is already waiting on your phone. Please finish it first")
    # Send the prompt to the tenant's OWN phone, never to a number they type
    return send_prompt(db, lease, data.amount, tenant.phone, current_user)


# Check what happened to a tenant's own payment request
@router.get("/portal/mpesa/status/{checkout_request_id}")
def portal_pay_status(
    checkout_request_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    account, tenant = ready_context(db, current_user)
    # Find the request, and lock it while we work on it
    row = (
        db.query(mpesa_models.MpesaRequest)
        .filter(mpesa_models.MpesaRequest.checkout_request_id == checkout_request_id)
        .with_for_update()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    # It must be for one of this tenant's own leases (says "not found" otherwise)
    lease = db.query(models.Lease).filter(models.Lease.id == row.lease_id, models.Lease.tenant_id == tenant.id).first()
    if lease is None:
        raise HTTPException(status_code=404, detail="Request not found")
    # Still waiting? Ask Safaricom directly
    check_with_safaricom(db, row)
    return {"status": row.status, "message": row.result_desc, "receipt": row.receipt}