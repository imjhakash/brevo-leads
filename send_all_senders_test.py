"""
Send a test email from ALL 5 Brevo accounts to akash@codemypixel.com.
Each email is labeled by account number so you can see which sender lands in inbox vs spam.

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

# Import email builder from send_daily_batch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_daily_batch import build_html_email, SUBJECTS, PDF_FILENAMES, PDF_PATHS, make_headers, get_brevo_sent_today

BASE_URL = "https://api.brevo.com/v3"
TEST_EMAIL = "akash@codemypixel.com"
TEST_FIRSTNAME = "Akash"
TEST_COMPANY = "Test Company Ltd"
BREVO_DAILY_LIMIT = 300

ACCOUNTS = [
    {"label": "1", "env": "BREVO_API_KEY", "category": "healthcare", "sender": "admin@codemypixel.com"},
    {"label": "2", "env": "BREVO_API_KEY_2", "category": "building_materials", "sender": "sabbir@team.codemypixel.com"},
    {"label": "3", "env": "BREVO_API_KEY_3", "category": "building_materials", "sender": "akash@codemypixel.com"},
    {"label": "4", "env": "BREVO_API_KEY_4", "category": "fashion", "sender": "neel@connect.codemypixel.com"},
    {"label": "5", "env": "BREVO_API_KEY_5", "category": "healthcare", "sender": "pravas@app.codemypixel.com"},
]

print("=== Spam/Deliverability Test: Send from all 5 accounts ===")
print(f"  Recipient: {TEST_EMAIL}")
print(f"  Each email is labeled with its account number in the subject\n")

# Test recipient (one row)
recipient = {"email": TEST_EMAIL, "firstname": TEST_FIRSTNAME, "company": TEST_COMPANY}

results = []
for acct in ACCOUNTS:
    api_key = os.environ.get(acct["env"])
    if not api_key:
        print(f"  Account {acct['label']}: SKIP - {acct['env']} not set")
        results.append({"account": acct["label"], "status": "skip", "reason": f"{acct['env']} not set"})
        continue

    sent_today = get_brevo_sent_today(api_key)
    remaining = BREVO_DAILY_LIMIT - sent_today
    print(f"  Account {acct['label']} ({acct['sender']}): {sent_today}/{BREVO_DAILY_LIMIT} sent, {remaining} remaining")

    if remaining == 0:
        print(f"    -> Quota exhausted, cannot send test")
        results.append({"account": acct["label"], "status": "quota_exhausted", "remaining": 0})
        continue

    category = acct["category"]
    html_content = build_html_email(recipient, category)

    # Add a visible label in the email body and subject
    html_label = f'<div style="background:#ffeb3b;color:#000;padding:10px 14px;font-size:13px;font-weight:700;text-align:center;border-radius:8px;margin:14px 0;">THIS IS A DELIVERABILITY TEST - Account {acct["label"]} - Sender: {acct["sender"]}</div>'
    html_content = html_content.replace(
        '<h1 style="margin:0 0 14px 0;color:#0f172a;font-size:24px;font-weight:800;letter-spacing:-0.5px;line-height:1.3;">',
        html_label + '<h1 style="margin:0 0 14px 0;color:#0f172a;font-size:24px;font-weight:800;letter-spacing:-0.5px;line-height:1.3;">'
    )

    # Change subject to include account label
    subject = f"[TEST Account {acct['label']}] {SUBJECTS[category]}"

    # Load PDF for this account's category
    pdf_path = PDF_PATHS[category]
    pdf_name = PDF_FILENAMES[category]
    pdf_b64 = None
    if os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

    body = {
        "sender": {"name": "Johirul Hoq Akash", "email": acct["sender"]},
        "subject": subject,
        "htmlContent": html_content,
        "to": [{"email": TEST_EMAIL, "name": TEST_FIRSTNAME}],
        "tags": ["spam-test", category, f"account-{acct['label']}"],
    }

    if pdf_b64:
        body["attachment"] = [{"content": pdf_b64, "name": pdf_name}]

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/smtp/email", data=data, headers=make_headers(api_key), method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"    -> SENT (messageId: {result.get('messageId', 'N/A')})")
            results.append({"account": acct["label"], "status": "sent", "sender": acct["sender"], "remaining": remaining - 1, "messageId": result.get("messageId", "N/A")})
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"    -> FAILED ({e.code}: {err})")
        results.append({"account": acct["label"], "status": "failed", "error": f"{e.code} {err}"})
    except Exception as e:
        print(f"    -> FAILED ({e})")
        results.append({"account": acct["label"], "status": "failed", "error": str(e)})

print("\n=== Results ===")
for r in results:
    print(f"  Account {r['account']:>2}: {r['status'].upper()}")
    if r['status'] == 'sent':
        print(f"             Sender: {r.get('sender')}")
        print(f"             Message ID: {r.get('messageId')}")
        print(f"             Remaining quota today: {r.get('remaining')}")
    elif r['status'] == 'failed':
        print(f"             Error: {r.get('error')}")
    elif r['status'] == 'quota_exhausted':
        print(f"             Daily quota exhausted")

print("\nCheck akash@codemypixel.com inbox + spam folder for all 5 test emails.")
print("Each email subject starts with [TEST Account N] so you can identify senders.")
