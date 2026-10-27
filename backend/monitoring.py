# monitoring.py - sends us an email when the live app crashes, without sending anyone's private data

# Import the tools we need
import os
import re
# Import the error-reporting tool
import sentry_sdk

# The address Sentry gave us (if it is not set, as on your laptop and in the tests, nothing is sent)
DSN = os.getenv("SENTRY_DSN", "").strip()

# Web addresses that contain a secret: the M-Pesa callback, public listing links, and share links
SECRET_PATHS = re.compile(r"(/payments/callback/|/public/listings/|/share/)[^/?#]+")


# Hide the secret part of a web address, and drop anything after a question mark
def hide_secrets(url: str) -> str:
    return SECRET_PATHS.sub(r"\1[hidden]", (url or "").split("?")[0])


# Clean an error report before it leaves our server: keep only what went wrong and where
def clean_event(event, hint):
    request = event.get("request")
    if request:
        # Keep only the kind of request and the cleaned address (no passwords, no headers, no form data)
        event["request"] = {"method": request.get("method"), "url": hide_secrets(request.get("url"))}
    # Drop everything that could hold names, phone numbers, codes or amounts
    for key in ("user", "breadcrumbs", "extra", "contexts"):
        event.pop(key, None)
    return event


# Start the error reporting, but only when a Sentry address is set
if DSN:
    sentry_sdk.init(
        dsn=DSN,
        # Say whether this is the live server or something else
        environment=os.getenv("ENVIRONMENT", "development"),
        # Render tells us which version of the code is running
        release=os.getenv("RENDER_GIT_COMMIT"),
        # Never send personal data, local variables, or request bodies
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        # We only want crash reports, not speed measurements
        traces_sample_rate=0,
        before_send=clean_event,
    )