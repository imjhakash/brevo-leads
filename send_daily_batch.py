"""
Daily automated outreach sender for CodeMyPixel.

Uses FIVE Brevo accounts to send 1500 emails per day.
  - Healthcare & Wellness   -> 2 accounts (600/day)
  - Building Materials      -> 2 accounts (600/day)
  - Apparel & Fashion       -> 1 account  (300/day)

Each email is sent as plain, human-written text — no images, no links,
no attachments. Just a personal note from Johirul asking if they'd like
to hear an idea.

SAFEGUARDS:
  1. Same-day re-run protection: checks progress.json "last_run_date" and exits
     if already run today. Use --force to override.
  2. Brevo daily quota check: queries each account's actual sent count today
     via Brevo API before sending. Skips accounts that already hit 300/day.
  3. Pointer advances by actual sent count, not attempted count.

Environment variables required:
  BREVO_API_KEY    - Brevo account 1 (Healthcare)
  BREVO_API_KEY_2  - Brevo account 2 (Building Materials)
  BREVO_API_KEY_3  - Brevo account 3 (Building Materials)
  BREVO_API_KEY_4  - Brevo account 4 (Fashion)
  BREVO_API_KEY_5  - Brevo account 5 (Healthcare)
"""
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
PROGRESS_PATH = os.path.join(BASE_DIR, "progress.json")
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

CATEGORY_NAMES = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}

CATEGORIES = {
    "healthcare": {
        "file": "healthcare.csv",
        "accounts": [
            {"label": "1", "api_key": API_KEY_1, "sender": "admin@codemypixel.com"},
            {"label": "5", "api_key": API_KEY_5, "sender": "pravas@app.codemypixel.com"},
        ],
    },
    "building_materials": {
        "file": "building_materials.csv",
        "accounts": [
            {"label": "2", "api_key": API_KEY_2, "sender": "sabbir@team.codemypixel.com"},
            {"label": "3", "api_key": API_KEY_3, "sender": "akash@codemypixel.com"},
        ],
    },
    "fashion": {
        "file": "fashion.csv",
        "accounts": [
            {"label": "4", "api_key": API_KEY_4, "sender": "neel@connect.codemypixel.com"},
        ],
    },
}


def make_headers(api_key):
    return {"accept": "application/json", "content-type": "application/json", "api-key": api_key}


def load_progress():
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return {"pointers": {c: 0 for c in CATEGORIES}, "history": [], "last_run_date": None}


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


def build_html_email(recipient, category):
    """Build a plain, human-written email — no links, no images, no styling."""
    name = recipient["firstname"]
    company = recipient["company"]
    industry = CATEGORY_NAMES.get(category, category)

    html = (
        f"Hi {name},<br><br>"
        f"Hope you're doing well.<br><br>"
        f"I'm Johirul Hoq Akash. I came across {company} recently and spent some time looking at what you do in the {industry} space.<br><br>"
        f"While going through your website and services, an idea came to mind that I honestly think could help your business. I'm not trying to sell you anything in this email. I'm just genuinely curious to know what you think about the idea.<br><br>"
        f"If this email ended up in your promotions or spam folder, I'd really appreciate it if you gave it a quick look. I'm a real person. You can search Johirul Hoq Akash on Google and you'll find me and my company, CodeMyPixel.<br><br>"
        f"If the idea sounds interesting, just reply with \"sure\" and I'll send it over. If it isn't something you're looking for right now, no worries at all. You can simply ignore this email.<br><br>"
        f"Thanks for reading, and I hope you have a great week.<br><br>"
        f"Best,<br><br>"
        f"Johirul Hoq Akash<br>"
        f"Founder, CodeMyPixel"
    )
    return html


def build_subject(recipient):
    return f"An idea for {recipient['company']}"


def send_one(recipient, category, api_key, sender_email):
    """Send a single personalized plain-text email."""
    headers = make_headers(api_key)
    subject = build_subject(recipient)
    html_content = build_html_email(recipient, category)

    body = {
        "sender": {"name": "Johirul Hoq Akash", "email": sender_email},
        "subject": subject,
        "htmlContent": html_content,
        "to": [{"email": recipient["email"], "name": recipient["firstname"]}],
        "tags": [category],
    }

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


def send_batch(leads, category, api_key, sender_email, account_label, max_sends):
    sent, failed = 0, 0
    fail_log = []
    for lead in leads[:max_sends]:
        ok, result = send_one(lead, category, api_key, sender_email)
        if ok:
            sent += 1
        else:
            failed += 1
            fail_log.append({"email": lead["email"], "error": str(result)})
        time.sleep(0.15)
    return sent, failed, fail_log


def main():
    progress = load_progress()
    today = date.today().isoformat()

    if progress.get("last_run_date") == today and not FORCE:
        print(f"Already ran today ({today}). Use --force to override. Exiting.")
        return

    print(f"=== Daily outreach for {today} ===")
    print(f"Healthcare: 2 accounts (600/day) | Building Materials: 2 (600) | Fashion: 1 (300)")
    print(f"Total target: 1500 emails/day")
    print(f"Mode: Plain text human-written email (no links, no images, no attachments)")
    print()

    all_results = []

    for cat_key, cat_config in CATEGORIES.items():
        leads = load_leads(cat_config["file"])
        pointer = progress["pointers"].get(cat_key, 0)
        accounts = cat_config["accounts"]

        print(f"--- Category: {cat_key} ({len(accounts)} account(s), pointer at {pointer}/{len(leads)}) ---")

        current_offset = pointer
        category_sent = 0
        category_failed = 0

        for acct in accounts:
            sent_today = get_brevo_sent_today(acct["api_key"])
            remaining = BREVO_DAILY_LIMIT - sent_today
            acct["remaining"] = max(0, remaining)

            if acct["remaining"] == 0:
                print(f"  [Account {acct['label']}] SKIPPED - daily limit reached ({sent_today}/{BREVO_DAILY_LIMIT})")
                all_results.append({"category": cat_key, "account": acct["label"], "attempted": 0, "sent": 0, "failed": 0, "failures": [], "pointer_before": current_offset, "pointer_after": current_offset})
                continue

            batch = leads[current_offset:current_offset + acct["remaining"]]
            if not batch:
                print(f"  [Account {acct['label']}] No more leads for '{cat_key}'. Skipping.")
                all_results.append({"category": cat_key, "account": acct["label"], "attempted": 0, "sent": 0, "failed": 0, "failures": [], "pointer_before": current_offset, "pointer_after": current_offset})
                continue

            print(f"  [Account {acct['label']}] Sending {len(batch)} leads (sender: {acct['sender']}, Brevo used: {sent_today}/{BREVO_DAILY_LIMIT})")

            sent, failed, fail_log = send_batch(batch, cat_key, acct["api_key"], acct["sender"], acct["label"], acct["remaining"])

            current_offset += sent
            category_sent += sent
            category_failed += failed

            print(f"  [Account {acct['label']}] sent={sent} failed={failed}")

            all_results.append({"category": cat_key, "account": acct["label"], "attempted": len(batch), "sent": sent, "failed": failed, "failures": fail_log, "pointer_before": current_offset - sent, "pointer_after": current_offset})

        progress["pointers"][cat_key] = current_offset
        print(f"  Category {cat_key}: total sent={category_sent}, failed={category_failed}")

    progress["last_run_date"] = today
    progress["history"].append({"date": today, "results": all_results, "total_sent": sum(r["sent"] for r in all_results), "total_failed": sum(r["failed"] for r in all_results)})
    save_progress(progress)

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
