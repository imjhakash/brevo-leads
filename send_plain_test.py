"""
Send a simple plain text test email (no template) to verify Brevo API works.
This bypasses templates to test if the API key and sender are valid.

Environment variables required:
  BREVO_API_KEY - Brevo account 1
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE_URL = "https://api.brevo.com/v3"
TEST_EMAIL = "helloatjh@gmail.com"
SENDER_EMAIL = "admin@codemypixel.com"
SENDER_NAME = "Johirul Hoq Akash"

API_KEY = os.environ.get("BREVO_API_KEY")
if not API_KEY:
    print("ERROR: BREVO_API_KEY not set", file=sys.stderr)
    sys.exit(1)

print(f"=== Sending simple test email (no template) ===")
print(f"  From: {SENDER_NAME} <{SENDER_EMAIL}>")
print(f"  To: {TEST_EMAIL}")

body = {
    "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
    "to": [{"email": TEST_EMAIL}],
    "subject": "Brevo API Test - Plain Email",
    "htmlContent": """
      <h2>Test Email</h2>
      <p>This is a plain test email sent via Brevo API (no template).</p>
      <p>If you receive this, the API key and sender email are working.</p>
      <p>From: Johirul Hoq Akash<br>CodeMyPixel</p>
    """,
    "tags": ["test", "plain-email"],
}

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "api-key": API_KEY,
}

data = json.dumps(body).encode("utf-8")
req = urllib.request.Request(f"{BASE_URL}/smtp/email", data=data, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"\n  ✓ SUCCESS! Plain email sent.")
        print(f"  Full Brevo API response:")
        print(f"  {json.dumps(result, indent=2)}")
        print(f"  Message ID: {result.get('messageId', 'N/A')}")
        print(f"  Check helloatjh@gmail.com inbox (and spam folder).")
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", errors="ignore")
    print(f"\n  ✗ FAILED: {e.code} {err}", file=sys.stderr)
    print(f"  Full error response: {err}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"\n  ✗ FAILED: {e}", file=sys.stderr)
    sys.exit(1)
