"""
Daily automated outreach sender for CodeMyPixel.

Uses TWO Brevo accounts to send 600 emails per day (300 from each account).
Each day picks TWO consecutive categories from the rotation:
  - Account 1 sends 300 leads from category A
  - Account 2 sends 300 leads from category B (the next in rotation)

This doubles throughput while staying within each account's 300/day limit.

State (which categories are "today", and how far each category's pointer
has progressed) is persisted in progress.json, which this script updates
in place. The GitHub Actions workflow commits that file back to the repo
after every run, so progress carries over correctly day to day.

Environment variables required:
  BREVO_API_KEY    - Brevo transactional API key (account 1)
  BREVO_API_KEY_2  - Brevo transactional API key (account 2)
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
if not API_KEY_1:
    print("ERROR: BREVO_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)
if not API_KEY_2:
    print("ERROR: BREVO_API_KEY_2 environment variable not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.brevo.com/v3"
DAILY_BATCH_SIZE = 300

# Rotation order: two categories sent per day (one per account), cycling through all 4.
# Subjects are intentionally omitted here so Brevo uses each template's own
# stored subject line (which already contains {{contact.COMPANY}} merge tags).
# template_id = account 1 template, template_id_2 = account 2 template (copy in second account)
CATEGORIES = [
    {"key": "construction", "file": "construction.csv", "template_id": 7, "template_id_2": 20},
    {"key": "banking", "file": "banking.csv", "template_id": 6, "template_id_2": 23},
    {"key": "accounting", "file": "accounting.csv", "template_id": 8, "template_id_2": 21},
    {"key": "automotive", "file": "automotive.csv", "template_id": 9, "template_id_2": 22},
]


def make_headers(api_key):
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }


def load_progress():
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return {"cycle_index": 0, "pointers": {c["key"]: 0 for c in CATEGORIES}, "history": []}


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


def send_one(template_id, recipient, api_key):
    headers = make_headers(api_key)
    body = {
        "templateId": template_id,
        "to": [{"email": recipient["email"], "name": recipient["firstname"]}],
        "params": {
            "FIRSTNAME": recipient["firstname"],
            "COMPANY": recipient["company"],
        },
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


def send_category_batch(category, api_key, template_id_field, progress, account_label):
    """Send DAILY_BATCH_SIZE leads for one category using one Brevo account."""
    key = category["key"]
    leads = load_leads(category["file"])
    pointer = progress["pointers"].get(key, 0)
    batch = leads[pointer:pointer + DAILY_BATCH_SIZE]

    if not batch:
        print(f"[Account {account_label}] No more leads left for category '{key}'. Skipping.")
        return {"category": key, "account": account_label, "attempted": 0, "sent": 0, "failed": 0, "failures": [], "pointer_before": pointer, "pointer_after": pointer, "total_leads": len(leads)}

    sent, failed = 0, 0
    fail_log = []
    for lead in batch:
        ok, result = send_one(category[template_id_field], lead, api_key)
        if ok:
            sent += 1
        else:
            failed += 1
            fail_log.append({"email": lead["email"], "error": str(result)})
        time.sleep(0.15)

    progress["pointers"][key] = pointer + len(batch)

    return {
        "category": key,
        "account": account_label,
        "attempted": len(batch),
        "sent": sent,
        "failed": failed,
        "failures": fail_log,
        "pointer_before": pointer,
        "pointer_after": pointer + len(batch),
        "total_leads": len(leads),
    }


def main():
    progress = load_progress()
    idx = progress["cycle_index"] % len(CATEGORIES)

    # Pick two consecutive categories: one for each account.
    cat_a = CATEGORIES[idx]
    cat_b = CATEGORIES[(idx + 1) % len(CATEGORIES)]

    today = date.today().isoformat()
    print(f"=== Daily outreach for {today} ===")
    print(f"Account 1 -> category: {cat_a['key']} (template {cat_a['template_id']})")
    print(f"Account 2 -> category: {cat_b['key']} (template {cat_b['template_id_2']})")
    print()

    # Account 1 sends category A
    result_a = send_category_batch(cat_a, API_KEY_1, "template_id", progress, "1")
    print(f"[Account 1] Category={result_a['category']} attempted={result_a['attempted']} sent={result_a['sent']} failed={result_a['failed']} pointer={result_a['pointer_after']}/{result_a['total_leads']}")

    # Account 2 sends category B
    result_b = send_category_batch(cat_b, API_KEY_2, "template_id_2", progress, "2")
    print(f"[Account 2] Category={result_b['category']} attempted={result_b['attempted']} sent={result_b['sent']} failed={result_b['failed']} pointer={result_b['pointer_after']}/{result_b['total_leads']}")

    # Advance cycle by 2 (we covered 2 categories today)
    progress["cycle_index"] += 2

    # Record history
    progress["history"].append({
        "date": today,
        "account_1": {"category": result_a["category"], "attempted": result_a["attempted"], "sent": result_a["sent"], "failed": result_a["failed"]},
        "account_2": {"category": result_b["category"], "attempted": result_b["attempted"], "sent": result_b["sent"], "failed": result_b["failed"]},
        "total_sent": result_a["sent"] + result_b["sent"],
        "total_failed": result_a["failed"] + result_b["failed"],
    })
    save_progress(progress)

    # Save logs
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for result, suffix in [(result_a, cat_a["key"]), (result_b, cat_b["key"])]:
        log_path = os.path.join(LOG_DIR, f"{ts}_{suffix}_acct{result['account']}.json")
        with open(log_path, "w") as f:
            json.dump(result, f, indent=2)

    print()
    print(f"=== Done. Total sent: {result_a['sent'] + result_b['sent']}, Total failed: {result_a['failed'] + result_b['failed']} ===")


if __name__ == "__main__":
    main()
