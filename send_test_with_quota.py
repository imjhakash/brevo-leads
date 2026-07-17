"""
Send a test email using whichever Brevo account has daily quota available.
Uses inline HTML (no Brevo template) with variables replaced directly in Python.

Environment variables required:
  BREVO_API_KEY through BREVO_API_KEY_5
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date

# Import the email builder from send_daily_batch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_daily_batch import build_html_email, SUBJECTS, PDF_FILENAMES, PDF_PATHS, make_headers, get_brevo_sent_today, CATEGORIES

BASE_URL = "https://api.brevo.com/v3"
TEST_EMAIL = "helloatjh@gmail.com"
TEST_FIRSTNAME = "Sarah"
TEST_COMPANY = "Memorial Sloan Kettering"
BREVO_DAILY_LIMIT = 300

# Account configs (same as send_daily_batch)
ACCOUNTS = [
    {"label": "1", "env": "BREVO_API_KEY", "category": "healthcare", "sender": "admin@codemypixel.com"},
    {"label": "2", "env": "BREVO_API_KEY_2", "category": "building_materials", "sender": "sabbir@team.codemypixel.com"},
    {"label": "3", "env": "BREVO_API_KEY_3", "category": "building_materials", "sender": "akash@codemypixel.com"},
    {"label": "4", "env": "BREVO_API_KEY_4", "category": "fashion", "sender": "neel@connect.codemypixel.com"},
    {"label": "5", "env": "BREVO_API_KEY_5", "category": "healthcare", "sender": "pravas@app.codemypixel.com"},
]

print("=== Checking all Brevo accounts for available quota ===")
print(f"  Daily limit: {BREVO_DAILY_LIMIT} per account\n")

available_account = None
for acct in ACCOUNTS:
    api_key = os.environ.get(acct["env"])
    if not api_key:
        print(f"  Account {acct['label']}: SKIP - {acct['env']} not set")
        continue
    
    sent_today = get_brevo_sent_today(api_key)
    remaining = BREVO_DAILY_LIMIT - sent_today
    status = "AVAILABLE" if remaining > 0 else "EXHAUSTED"
    print(f"  Account {acct['label']}: {sent_today}/{BREVO_DAILY_LIMIT} sent, {remaining} remaining - {status}")
    
    if remaining > 0 and available_account is None:
        available_account = acct

if not available_account:
    print("\n  All accounts exhausted. No quota available today.")
    print("  Try again tomorrow when quotas reset.")
    sys.exit(1)

remaining = BREVO_DAILY_LIMIT - get_brevo_sent_today(os.environ.get(available_account["env"]))
print(f"\n  Using Account {available_account['label']} ({available_account['category']}) - {remaining} remaining")

# Build the test email with mock variables
recipient = {"email": TEST_EMAIL, "firstname": TEST_FIRSTNAME, "company": TEST_COMPANY}
category = available_account["category"]
html_content = build_html_email(recipient, category)

# Verify name and company are in the HTML
if TEST_FIRSTNAME in html_content:
    print(f"  ✓ Name '{TEST_FIRSTNAME}' found in HTML body")
else:
    print(f"  ✗ WARNING: Name '{TEST_FIRSTNAME}' NOT in HTML!")

if TEST_COMPANY in html_content:
    print(f"  ✓ Company '{TEST_COMPANY}' found in HTML body")
else:
    print(f"  ✗ WARNING: Company '{TEST_COMPANY}' NOT in HTML!")

if "codemypixel.com" in html_content:
    print(f"  ✓ CodeMyPixel link found in HTML body")
else:
    print(f"  ✗ WARNING: CodeMyPixel link NOT in HTML!")

# Load PDF attachment
pdf_path = PDF_PATHS[category]
pdf_name = PDF_FILENAMES[category]
pdf_b64 = None
if os.path.exists(pdf_path):
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    print(f"  PDF attachment: {pdf_name} ({os.path.getsize(pdf_path)//1024}KB)")
else:
    print(f"  WARNING: PDF not found at {pdf_path}")

# Build email body (inline HTML, no templateId)
body = {
    "sender": {"name": "Johirul Hoq Akash", "email": available_account["sender"]},
    "subject": SUBJECTS[category],
    "htmlContent": html_content,
    "to": [{"email": TEST_EMAIL, "name": TEST_FIRSTNAME}],
    "tags": ["test", category],
}

if pdf_b64:
    body["attachment"] = [{"content": pdf_b64, "name": pdf_name}]

headers = make_headers(os.environ.get(available_account["env"]))
data = json.dumps(body).encode("utf-8")
req = urllib.request.Request(f"{BASE_URL}/smtp/email", data=data, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"\n  SUCCESS! Email sent via Account {available_account['label']}.")
        print(f"  Full Brevo API response:")
        print(f"  {json.dumps(result, indent=2)}")
        print(f"  Message ID: {result.get('messageId', 'N/A')}")
        print(f"  Check helloatjh@gmail.com inbox (and spam folder).")
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", errors="ignore")
    print(f"\n  FAILED: {e.code} {err}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"\n  FAILED: {e}", file=sys.stderr)
    sys.exit(1)
