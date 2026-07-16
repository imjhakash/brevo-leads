"""
Send a test email to Helloatjh@gmail.com using Account 1 (Healthcare template).
Uses mock variable values for FIRSTNAME and COMPANY.

Environment variables required:
  BREVO_API_KEY - Brevo account 1
"""
import base64
import json
import os
import sys
import urllib.request
import urllib.error

BASE_URL = "https://api.brevo.com/v3"
TEST_EMAIL = "helloatjh@gmail.com"
TEST_FIRSTNAME = "Sarah"
TEST_COMPANY = "Memorial Sloan Kettering"

# Load template IDs
ids_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template_ids.json")
with open(ids_path) as f:
    template_ids = json.load(f)

TEMPLATE_ID = template_ids["account_1"]["template_id"]
CATEGORY = template_ids["account_1"]["category"]

# PDF attachment
PDF_MAP = {
    "healthcare": ("assets/healthcare-report.pdf", "AI-Automation-Report-Healthcare-Wellness.pdf"),
    "building_materials": ("assets/building-materials-report.pdf", "AI-Automation-Report-Building-Materials.pdf"),
    "fashion": ("assets/fashion-report.pdf", "AI-Automation-Report-Apparel-Fashion.pdf"),
}

API_KEY = os.environ.get("BREVO_API_KEY")
if not API_KEY:
    print("ERROR: BREVO_API_KEY not set", file=sys.stderr)
    sys.exit(1)

print(f"=== Sending test email ===")
print(f"  To: {TEST_EMAIL}")
print(f"  Template ID: {TEMPLATE_ID} (category: {CATEGORY})")
print(f"  Mock FIRSTNAME: {TEST_FIRSTNAME}")
print(f"  Mock COMPANY: {TEST_COMPANY}")

# Load PDF attachment
pdf_path, pdf_name = PDF_MAP[CATEGORY]
pdf_b64 = None
if os.path.exists(pdf_path):
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    print(f"  PDF attachment: {pdf_name} ({os.path.getsize(pdf_path)//1024}KB)")
else:
    print(f"  WARNING: PDF not found at {pdf_path}")

# Build email body
body = {
    "templateId": TEMPLATE_ID,
    "to": [{"email": TEST_EMAIL, "name": TEST_FIRSTNAME}],
    "params": {"FIRSTNAME": TEST_FIRSTNAME, "COMPANY": TEST_COMPANY},
    "tags": ["test", CATEGORY],
}

if pdf_b64:
    body["attachment"] = [{"content": pdf_b64, "name": pdf_name}]

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
        print(f"\n  ✓ SUCCESS! Email sent.")
        print(f"  Full Brevo API response:")
        print(f"  {json.dumps(result, indent=2)}")
        print(f"  Message ID: {result.get('messageId', 'N/A')}")
        print(f"  Check Helloatjh@gmail.com inbox (and spam folder).")
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", errors="ignore")
    print(f"\n  ✗ FAILED: {e.code} {err}", file=sys.stderr)
    print(f"  Full error response: {err}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"\n  ✗ FAILED: {e}", file=sys.stderr)
    sys.exit(1)
