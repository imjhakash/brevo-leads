"""
Send a test email using whichever Brevo account has daily quota available.
Checks all 5 accounts and uses the first one with remaining quota.

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

BASE_URL = "https://api.brevo.com/v3"
TEST_EMAIL = "helloatjh@gmail.com"
TEST_FIRSTNAME = "Sarah"
TEST_COMPANY = "Memorial Sloan Kettering"
BREVO_DAILY_LIMIT = 300

# Load template IDs
ids_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template_ids.json")
with open(ids_path) as f:
    template_ids = json.load(f)

# Account configs
ACCOUNTS = [
    {"label": "1", "env": "BREVO_API_KEY", "template_id": template_ids.get("account_1", {}).get("template_id"), "category": "healthcare"},
    {"label": "2", "env": "BREVO_API_KEY_2", "template_id": template_ids.get("account_2", {}).get("template_id"), "category": "building_materials"},
    {"label": "3", "env": "BREVO_API_KEY_3", "template_id": template_ids.get("account_3", {}).get("template_id"), "category": "building_materials"},
    {"label": "4", "env": "BREVO_API_KEY_4", "template_id": template_ids.get("account_4", {}).get("template_id"), "category": "fashion"},
    {"label": "5", "env": "BREVO_API_KEY_5", "template_id": template_ids.get("account_5", {}).get("template_id"), "category": "healthcare"},
]

def get_brevo_sent_today(api_key):
    """Query Brevo API for how many emails were sent today."""
    today_str = date.today().strftime("%Y-%m-%d")
    headers = {"accept": "application/json", "api-key": api_key}
    url = f"{BASE_URL}/smtp/statistics/aggregatedReport?startDate={today_str}&endDate={today_str}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("requests", 0)
    except Exception:
        return 0

print(f"=== Checking all Brevo accounts for available quota ===")
print(f"  Daily limit: {BREVO_DAILY_LIMIT} per account\n")

# Check all accounts and find one with quota
available_account = None
for acct in ACCOUNTS:
    api_key = os.environ.get(acct["env"])
    if not api_key:
        print(f"  Account {acct['label']}: SKIP - {acct['env']} not set")
        continue
    
    sent_today = get_brevo_sent_today(api_key)
    remaining = BREVO_DAILY_LIMIT - sent_today
    status = "✓ AVAILABLE" if remaining > 0 else "✗ EXHAUSTED"
    print(f"  Account {acct['label']}: {sent_today}/{BREVO_DAILY_LIMIT} sent, {remaining} remaining - {status}")
    
    if remaining > 0 and available_account is None:
        available_account = acct

if not available_account:
    print(f"\n  ✗ All accounts exhausted. No quota available today.")
    print(f"  Try again tomorrow when quotas reset.")
    sys.exit(1)

print(f"\n  ✓ Using Account {available_account['label']} ({available_account['category']}) - {BREVO_DAILY_LIMIT - get_brevo_sent_today(os.environ.get(available_account['env']))} remaining")

# Load PDF attachment
PDF_MAP = {
    "healthcare": ("assets/healthcare-report.pdf", "AI-Automation-Report-Healthcare-Wellness.pdf"),
    "building_materials": ("assets/building-materials-report.pdf", "AI-Automation-Report-Building-Materials.pdf"),
    "fashion": ("assets/fashion-report.pdf", "AI-Automation-Report-Apparel-Fashion.pdf"),
}

category = available_account["category"]
pdf_path, pdf_name = PDF_MAP[category]
pdf_b64 = None
if os.path.exists(pdf_path):
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    print(f"  PDF attachment: {pdf_name} ({os.path.getsize(pdf_path)//1024}KB)")
else:
    print(f"  WARNING: PDF not found at {pdf_path}")

# Build email body
body = {
    "templateId": available_account["template_id"],
    "to": [{"email": TEST_EMAIL, "name": TEST_FIRSTNAME}],
    "params": {"FIRSTNAME": TEST_FIRSTNAME, "COMPANY": TEST_COMPANY},
    "tags": ["test", category],
}

if pdf_b64:
    body["attachment"] = [{"content": pdf_b64, "name": pdf_name}]

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "api-key": os.environ.get(available_account["env"]),
}

data = json.dumps(body).encode("utf-8")
req = urllib.request.Request(f"{BASE_URL}/smtp/email", data=data, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        print(f"\n  ✓ SUCCESS! Email sent via Account {available_account['label']}.")
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
