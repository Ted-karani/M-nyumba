# mpesa.py - asks tenants to pay by M-Pesa, and records the payment when Safaricom confirms it
# This file goes inside the "routers" folder (it replaces the earlier mpesa.py)

# Import tool to read values from the environment
import os
# Import tool used to encode the password Safaricom wants
import base64
# Import tool that compares secrets safely
import hmac
# Import the date and time tools
from datetime import datetime, timedelta
# Import tool used to call Safaricom's servers
import requests
# Import tool that reads the .env file on your laptop
from dotenv import load_dotenv
# Import FastAPI tools for endpoints, login checks, request bodies, and errors
from fastapi import APIRouter, Body, Depends, HTTPException
# Import the tool that describes the data we expect
from pydantic import BaseModel
# Import the database session type
from sqlalchemy.orm import Session

# Import our own files
import models
import mpesa_models
from dependencies import get_db, get_current_user
# Reuse the safety helpers we wrote earlier
from routers.properties import require_owner
from routers.leases import get_owned_lease

# Load everything inside the .env file (on Render the settings come from the dashboard instead)
load_dotenv()

# Our app's key from Safaricom
CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
# Our app's secret from Safaricom
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
# The business number (174379 in the sandbox)
SHORTCODE = os.getenv("MPESA_SHORTCODE")
# The passkey used to sign each request
PASSKEY = os.getenv("MPESA_PASSKEY")
# The start of the address where Safaricom sends results (without the secret part)
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")
# A long secret added to the end of the callback address, so nobody can fake a payment
CALLBACK_SECRET = os.getenv("MPESA_CALLBACK_SECRET")
# The sandbox address (this changes when we go live)
BASE_URL = "https://sandbox.safaricom.co.ke"

# Make a group of endpoints for M-Pesa
router = APIRouter(tags=["M-Pesa"])

# The reply Safaricom needs to hear after it sends us a result
ACCEPTED = {"ResultCode": 0, "ResultDesc": "Accepted"}


# The data we expect when someone asks for a payment
class PayRequest(BaseModel):
    # The lease the payment is for
    lease_id: int
    # The amount in shillings
    amount: int
    # The phone to send the prompt to (if empty, we use the tenant's phone)
    phone: str | None = None


# Turn 0712345678 into 254712345678, the format Safaricom needs
def clean_phone(phone):
    # Remove spaces and the plus sign
    phone = phone.strip().replace(" ", "").replace("+", "")
    # If it starts with 0, swap the 0 for 254
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    # Give back the cleaned number
    return phone


# Today's date in Kenya (the server clock is 3 hours behind Kenya)
def today_kenya():
    return (datetime.utcnow() + timedelta(hours=3)).date()


# Ask Safaricom for a temporary access token
def get_token():
    # The address where tokens are issued
    url = BASE_URL + "/oauth/v1/generate?grant_type=client_credentials"
    # Send our key and secret to prove who we are
    response = requests.get(url, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=30)
    # If Safaricom said no, stop with an error
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not get an M-Pesa token")
    # Return just the token
    return response.json()["access_token"]


# Ask a tenant's phone for a payment (only the owner of the lease can do this)
@router.post("/mpesa/stk-push")
def stk_push(
    data: PayRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Only owners can ask for payments
    require_owner(current_user)
    # Make sure the lease belongs to this owner
    lease = get_owned_lease(db, data.lease_id, current_user)
    # Make sure all the M-Pesa settings are filled in
    if not all([CONSUMER_KEY, CONSUMER_SECRET, SHORTCODE, PASSKEY, CALLBACK_URL, CALLBACK_SECRET]):
        raise HTTPException(status_code=500, detail="M-Pesa settings are missing")
    # The amount must be at least 1 shilling
    if data.amount < 1:
        raise HTTPException(status_code=400, detail="Amount must be at least 1")
    # Use the phone we were given, or the tenant's own phone
    phone = clean_phone(data.phone or lease.tenant.phone)

    # First get a fresh token
    token = get_token()
    # The current time, like 20261021143000
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    # Join shortcode + passkey + timestamp
    raw = SHORTCODE + PASSKEY + timestamp
    # Encode it, which is what Safaricom expects as the password
    password = base64.b64encode(raw.encode()).decode()

    # The payment request
    body = {
        # Who is receiving the money
        "BusinessShortCode": SHORTCODE,
        # The encoded password
        "Password": password,
        # The same timestamp used in the password
        "Timestamp": timestamp,
        # A Paybill payment
        "TransactionType": "CustomerPayBillOnline",
        # How much to pay
        "Amount": data.amount,
        # Who is paying
        "PartyA": phone,
        # Who is receiving
        "PartyB": SHORTCODE,
        # The phone that gets the PIN prompt
        "PhoneNumber": phone,
        # Where the result is sent (our address plus the secret)
        "CallBackURL": CALLBACK_URL.rstrip("/") + "/" + CALLBACK_SECRET,
        # Shown to the tenant
        "AccountReference": "EstateLoom",
        # Short description
        "TransactionDesc": "Rent payment",
    }

    # Send the request to Safaricom
    response = requests.post(
        # The STK push address
        BASE_URL + "/mpesa/stkpush/v1/processrequest",
        # Send our data as JSON
        json=body,
        # Prove who we are with the token
        headers={"Authorization": "Bearer " + token},
        # Give up after 30 seconds
        timeout=30,
    )
    # Read Safaricom's answer
    answer = response.json()
    # If Safaricom did not accept it, tell the user why
    if answer.get("ResponseCode") != "0":
        message = answer.get("errorMessage") or answer.get("ResponseDescription") or "M-Pesa refused the request"
        raise HTTPException(status_code=400, detail=message)

    # Remember this request as "pending" until the result comes back
    row = mpesa_models.MpesaRequest(
        lease_id=lease.id,
        phone=phone,
        amount=data.amount,
        checkout_request_id=answer["CheckoutRequestID"],
        merchant_request_id=answer.get("MerchantRequestID"),
        status="pending",
        requested_by_id=current_user.id,
    )
    # Save it to the database
    db.add(row)
    db.commit()
    # Tell the frontend what to look out for
    return {
        "message": "Prompt sent. Ask the tenant to enter their M-Pesa PIN.",
        "checkout_request_id": row.checkout_request_id,
        "status": row.status,
    }


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
    # Try to read the result out of what Safaricom sent
    try:
        # The part of the message that holds the result
        result = payload["Body"]["stkCallback"]
        # Which request this result belongs to
        checkout_id = result["CheckoutRequestID"]
        # 0 means paid, anything else means it did not work
        result_code = int(result["ResultCode"])
    except (KeyError, TypeError, ValueError):
        # A message we cannot read: say thanks and ignore it
        return ACCEPTED
    # Find the request we saved earlier
    row = db.query(mpesa_models.MpesaRequest).filter(mpesa_models.MpesaRequest.checkout_request_id == checkout_id).first()
    # Unknown request, or one we already handled: say thanks and do nothing (this also stops double payments)
    if row is None or row.status != "pending":
        return ACCEPTED
    # Save the message and the time the result came back
    row.result_desc = result.get("ResultDesc")
    row.completed_at = datetime.utcnow()

    # If it was not paid
    if result_code != 0:
        # 1032 means the tenant cancelled the prompt
        row.status = "cancelled" if result_code == 1032 else "failed"
        db.commit()
        return ACCEPTED

    # It was paid: read the details Safaricom sent
    items = (result.get("CallbackMetadata") or {}).get("Item", [])
    # Turn the list of items into a simple lookup, like {"Amount": 1, "MpesaReceiptNumber": "ABC123"}
    values = {item.get("Name"): item.get("Value") for item in items}
    # The M-Pesa code
    receipt = values.get("MpesaReceiptNumber")
    # The amount that was really paid (if missing, use what we asked for)
    amount = int(float(values.get("Amount", row.amount)))
    # Check we have not already recorded this M-Pesa code
    already = None
    if receipt:
        already = db.query(models.Payment).filter(models.Payment.reference == receipt).first()
    # Record the payment in the normal payments table, so balances and "Who owes me" update by themselves
    if already is None:
        db.add(models.Payment(
            lease_id=row.lease_id,
            amount=amount,
            paid_on=today_kenya(),
            method="mpesa",
            reference=receipt,
            recorded_by_id=None,
            notes="Paid by M-Pesa prompt",
        ))
    # Mark the request as paid and keep the code
    row.status = "paid"
    row.receipt = receipt
    # Save everything
    db.commit()
    # Tell Safaricom we got it
    return ACCEPTED


# Check what happened to a payment request (the frontend uses this to show "paid" or "failed")
@router.get("/mpesa/status/{checkout_request_id}")
def mpesa_status(
    checkout_request_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Find the request
    row = db.query(mpesa_models.MpesaRequest).filter(mpesa_models.MpesaRequest.checkout_request_id == checkout_request_id).first()
    # Not found
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    # Make sure its lease belongs to this user (says "not found" if it does not)
    get_owned_lease(db, row.lease_id, current_user)
    # Send back where it stands
    return {"status": row.status, "message": row.result_desc, "receipt": row.receipt}