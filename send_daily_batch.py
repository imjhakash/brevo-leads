"""
Daily automated outreach sender for CodeMyPixel.

Uses FIVE Brevo accounts to send 1500 emails per day.
  - Healthcare & Wellness   → 2 accounts (600/day)
  - Building Materials      → 2 accounts (600/day)
  - Apparel & Fashion       → 1 account  (300/day)

Each email uses a Brevo template (created via create_templates.py) with:
  - Personalized variables ({{params.FIRSTNAME}}, {{params.COMPANY}})
  - Sector-specific AI Automation Report PDF attachment
  - Founder photo inline image (in template)
  - Booking link (cal.com) (in template)

SAFEGUARDS:
  1. Same-day re-run protection: checks progress.json "last_run_date" and exits
     if already run today. Use --force to override.
  2. Brevo daily quota check: queries each account's actual sent count today
     via Brevo API before sending. Skips accounts that already hit 300/day.
  3. Pointer advances by actual sent count, not attempted count.

PREREQUISITE:
  Run the "Create Brevo Templates" workflow ONCE before using this script.
  This creates the email templates in your Brevo accounts and saves the IDs
  to template_ids.json.

Environment variables required:
  BREVO_API_KEY    - Brevo account 1 (Healthcare)
  BREVO_API_KEY_2  - Brevo account 2 (Building Materials)
  BREVO_API_KEY_3  - Brevo account 3 (Building Materials)
  BREVO_API_KEY_4  - Brevo account 4 (Fashion)
  BREVO_API_KEY_5  - Brevo account 5 (Healthcare)
"""
import base64
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEADS_DIR = os.path.join(BASE_DIR, "leads")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
PROGRESS_PATH = os.path.join(BASE_DIR, "progress.json")
TEMPLATE_IDS_PATH = os.path.join(BASE_DIR, "template_ids.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")

API_KEY_1 = os.environ.get("BREVO_API_KEY")
API_KEY_2 = os.environ.get("BREVO_API_KEY_2")
API_KEY_3 = os.environ.get("BREVO_API_KEY_3")
API_KEY_4 = os.environ.get("BREVO_API_KEY_4")
API_KEY_5 = os.environ.get("BREVO_API_KEY_5")
for i, key in enumerate([API_KEY_1, API_KEY_2, API_KEY_3, API_KEY_4, API_KEY_5], 1):
    if not key:
        var_name = f"BREVO_API_KEY_{i}" if i > 1 else "BREVO_API_KEY"
        print(f"ERROR: {var_name} environment variable not set", file=sys.stderr)
        sys.exit(1)

BASE_URL = "https://api.brevo.com/v3"
BREVO_DAILY_LIMIT = 300
FORCE = "--force" in sys.argv

# PDF attachment paths per category
PDF_PATHS = {
    "healthcare": os.path.join(ASSETS_DIR, "healthcare-report.pdf"),
    "building_materials": os.path.join(ASSETS_DIR, "building-materials-report.pdf"),
    "fashion": os.path.join(ASSETS_DIR, "fashion-report.pdf"),
}

# PDF attachment filenames (what the recipient sees)
PDF_FILENAMES = {
    "healthcare": "AI-Automation-Report-Healthcare-Wellness.pdf",
    "building_materials": "AI-Automation-Report-Building-Materials.pdf",
    "fashion": "AI-Automation-Report-Apparel-Fashion.pdf",
}


def load_template_ids():
    """Load template IDs from template_ids.json (created by create_templates.py)."""
    if not os.path.exists(TEMPLATE_IDS_PATH):
        print("ERROR: template_ids.json not found!", file=sys.stderr)
        print("Run the 'Create Brevo Templates' workflow first to create templates.", file=sys.stderr)
        sys.exit(1)
    with open(TEMPLATE_IDS_PATH) as f:
        return json.load(f)


# Category definitions with account assignments
# Healthcare: Accounts 1 & 5 (600/day)
# Building Materials: Accounts 2 & 3 (600/day)
# Fashion: Account 4 (300/day)
# Template IDs are loaded from template_ids.json at runtime
def build_categories(template_ids):
    """Build CATEGORIES dict with template IDs from template_ids.json."""
    cats = {
        "healthcare": {
            "file": "healthcare.csv",
            "accounts": [
                {"label": "1", "api_key": API_KEY_1, "template_id": template_ids.get("account_1", {}).get("template_id")},
                {"label": "5", "api_key": API_KEY_5, "template_id": template_ids.get("account_5", {}).get("template_id")},
            ],
        },
        "building_materials": {
            "file": "building_materials.csv",
            "accounts": [
                {"label": "2", "api_key": API_KEY_2, "template_id": template_ids.get("account_2", {}).get("template_id")},
                {"label": "3", "api_key": API_KEY_3, "template_id": template_ids.get("account_3", {}).get("template_id")},
            ],
        },
        "fashion": {
            "file": "fashion.csv",
            "accounts": [
                {"label": "4", "api_key": API_KEY_4, "template_id": template_ids.get("account_4", {}).get("template_id")},
            ],
        },
    }
    # Validate all template IDs are present
    for cat_key, cat_config in cats.items():
        for acct in cat_config["accounts"]:
            if not acct["template_id"]:
                print(f"ERROR: Missing template ID for account {acct['label']} (category: {cat_key})", file=sys.stderr)
                print("Run the 'Create Brevo Templates' workflow first.", file=sys.stderr)
                sys.exit(1)
    return cats


def make_headers(api_key):
    return {"accept": "application/json", "content-type": "application/json", "api-key": api_key}


def load_progress(categories):
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return {"pointers": {c: 0 for c in categories}, "history": [], "last_run_date": None}


def save_progress(progress):
    with open(PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=2)


def load_leads(fname):
    path = os.path.join(LEADS_DIR, fname)
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            if len(row) < 3:
                continue
            email = row[0].strip()
            firstname = " ".join(row[1].split()).strip()
            company = " ".join(row[2].split()).strip()
            if not email:
                continue
            rows.append({"email": email, "firstname": firstname or "there", "company": company or "your company"})
    return rows


def get_brevo_sent_today(api_key):
    """Query Brevo API for how many transactional emails were sent today."""
    today_str = date.today().strftime("%Y-%m-%d")
    headers = make_headers(api_key)
    url = f"{BASE_URL}/smtp/statistics/aggregatedReport?startDate={today_str}&endDate={today_str}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("requests", 0)
    except Exception:
        return 0


def load_pdf_attachment(category):
    """Load and base64-encode the PDF for a category."""
    pdf_path = PDF_PATHS.get(category)
    if not pdf_path or not os.path.exists(pdf_path):
        print(f"  WARNING: PDF not found at {pdf_path}")
        return None
    with open(pdf_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    return content


def send_one(template_id, recipient, category, api_key, pdf_b64):
    """Send a single email using a Brevo template with PDF attachment."""
    headers = make_headers(api_key)
    body = {
        "templateId": template_id,
        "to": [{"email": recipient["email"], "name": recipient["firstname"]}],
        "params": {"FIRSTNAME": recipient["firstname"], "COMPANY": recipient["company"]},
        "tags": [category],
    }

    # Add PDF attachment if available
    if pdf_b64:
        filename = PDF_FILENAMES.get(category, "report.pdf")
        body["attachment"] = [{"content": pdf_b64, "name": filename}]

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/smtp/email", data=data, headers=headers, method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return True, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")
            if e.code == 429:
                time.sleep(min(2 ** attempt, 15))
                continue
            return False, err
        except Exception:
            time.sleep(2)
    return False, "failed after retries"


def send_batch(leads, template_id, category, api_key, account_label, max_sends, pdf_b64):
    """Send up to max_sends emails from a batch of leads."""
    sent, failed = 0, 0
    fail_log = []
    for lead in leads[:max_sends]:
        ok, result = send_one(template_id, lead, category, api_key, pdf_b64)
        if ok:
            sent += 1
        else:
            failed += 1
            fail_log.append({"email": lead["email"], "error": str(result)})
        time.sleep(0.15)
    return sent, failed, fail_log


def main():
    # Load template IDs
    template_ids = load_template_ids()
    print(f"Loaded template IDs: {json.dumps({k: v.get('template_id') for k, v in template_ids.items()})}")

    # Build categories with template IDs
    categories = build_categories(template_ids)

    progress = load_progress(categories)
    today = date.today().isoformat()

    # SAFEGUARD 1: Same-day re-run protection
    if progress.get("last_run_date") == today and not FORCE:
        print(f"Already ran today ({today}). Use --force to override. Exiting.")
        return

    print(f"=== Daily outreach for {today} ===")
    print(f"Healthcare: 2 accounts (600/day) | Building Materials: 2 (600) | Fashion: 1 (300)")
    print(f"Total target: 1500 emails/day")
    print()

    all_results = []

    for cat_key, cat_config in categories.items():
        leads = load_leads(cat_config["file"])
        pointer = progress["pointers"].get(cat_key, 0)
        accounts = cat_config["accounts"]

        print(f"--- Category: {cat_key} ({len(accounts)} account(s), pointer at {pointer}/{len(leads)}) ---")

        # Load PDF attachment once per category
        pdf_b64 = load_pdf_attachment(cat_key)
        if pdf_b64:
            print(f"  PDF attachment loaded ({PDF_FILENAMES[cat_key]})")

        current_offset = pointer
        category_sent = 0
        category_failed = 0

        for acct in accounts:
            # Check Brevo daily quota
            sent_today = get_brevo_sent_today(acct["api_key"])
            remaining = BREVO_DAILY_LIMIT - sent_today
            acct["remaining"] = max(0, remaining)

            if acct["remaining"] == 0:
                print(f"  [Account {acct['label']}] SKIPPED - daily limit reached ({sent_today}/{BREVO_DAILY_LIMIT})")
                all_results.append({
                    "category": cat_key, "account": acct["label"],
                    "attempted": 0, "sent": 0, "failed": 0, "failures": [],
                    "pointer_before": current_offset, "pointer_after": current_offset,
                })
                continue

            batch = leads[current_offset:current_offset + acct["remaining"]]
            if not batch:
                print(f"  [Account {acct['label']}] No more leads for '{cat_key}'. Skipping.")
                all_results.append({
                    "category": cat_key, "account": acct["label"],
                    "attempted": 0, "sent": 0, "failed": 0, "failures": [],
                    "pointer_before": current_offset, "pointer_after": current_offset,
                })
                continue

            print(f"  [Account {acct['label']}] Sending {len(batch)} leads (template {acct['template_id']}, Brevo used: {sent_today}/{BREVO_DAILY_LIMIT})")

            sent, failed, fail_log = send_batch(
                batch, acct["template_id"], cat_key, acct["api_key"], acct["label"], acct["remaining"], pdf_b64
            )

            current_offset += sent
            category_sent += sent
            category_failed += failed

            print(f"  [Account {acct['label']}] sent={sent} failed={failed}")

            all_results.append({
                "category": cat_key, "account": acct["label"],
                "attempted": len(batch), "sent": sent, "failed": failed,
                "failures": fail_log,
                "pointer_before": current_offset - sent, "pointer_after": current_offset,
            })

        progress["pointers"][cat_key] = current_offset
        print(f"  Category {cat_key}: total sent={category_sent}, failed={category_failed}")

    # Update progress
    progress["last_run_date"] = today
    progress["history"].append({
        "date": today,
        "results": all_results,
        "total_sent": sum(r["sent"] for r in all_results),
        "total_failed": sum(r["failed"] for r in all_results),
    })
    save_progress(progress)

    # Write log file
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"{today}.json")
    with open(log_path, "w") as f:
        json.dump({"date": today, "results": all_results}, f, indent=2)

    total_sent = sum(r["sent"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    print()
    print(f"=== DONE: sent={total_sent} failed={total_failed} ===")


if __name__ == "__main__":
    main()
