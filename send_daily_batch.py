"""
Daily automated outreach sender for CodeMyPixel.

Uses THREE Brevo accounts to send 900 emails per day (300 from each account).
Each day picks THREE consecutive categories from the rotation:
  - Account 1 sends 300 leads from category A
  - Account 2 sends 300 leads from category B
  - Account 3 sends 300 leads from category C

This triples throughput while staying within each account's 300/day limit.

SAFEGUARDS:
  1. Same-day re-run protection: checks progress.json "last_run_date" and exits
     if already run today (prevents multiple sends from manual workflow triggers).
     Use --force to override (for testing only).
  2. Brevo daily quota check: queries each account's actual sent count today
     via Brevo API before sending. Skips accounts that already hit 300/day.

State (which categories are "today", and how far each category's pointer
has progressed) is persisted in progress.json, which this script updates
in place. The GitHub Actions workflow commits that file back to the repo
after every run, so progress carries over correctly day to day.

Environment variables required:
  BREVO_API_KEY    - Brevo transactional API key (account 1)
  BREVO_API_KEY_2  - Brevo transactional API key (account 2)
  BREVO_API_KEY_3  - Brevo transactional API key (account 3)
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
if not API_KEY_1:
    print("ERROR: BREVO_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)
if not API_KEY_2:
    print("ERROR: BREVO_API_KEY_2 environment variable not set", file=sys.stderr)
    sys.exit(1)
if not API_KEY_3:
    print("ERROR: BREVO_API_KEY_3 environment variable not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.brevo.com/v3"
DAILY_BATCH_SIZE = 300
BREVO_DAILY_LIMIT = 300
FORCE = "--force" in sys.argv

# Rotation order: three categories sent per day (one per account), cycling through all 4.
# Subjects are intentionally omitted here so Brevo uses each template's own
# stored subject line (which already contains {{ params.COMPANY }} merge tags).
# template_id = account 1, template_id_2 = account 2, template_id_3 = account 3
CATEGORIES = [
    {"key": "construction", "file": "construction.csv", "template_id": 7, "template_id_2": 20, "template_id_3": 8},
    {"key": "banking", "file": "banking.csv", "template_id": 6, "template_id_2": 23, "template_id_3": 5},
    {"key": "accounting", "file": "accounting.csv", "template_id": 8, "template_id_2": 21, "template_id_3": 6},
    {"key": "automotive", "file": "automotive.csv", "template_id": 9, "template_id_2": 22, "template_id_3": 7},
]

ACCOUNTS = [
    {"label": "1", "api_key": API_KEY_1, "template_field": "template_id"},
    {"label": "2", "api_key": API_KEY_2, "template_field": "template_id_2"},
    {"label": "3", "api_key": API_KEY_3, "template_field": "template_id_3"},
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
    return {"cycle_index": 0, "pointers": {c["key"]: 0 for c in CATEGORIES}, "history": [], "last_run_date": None}


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
    except Exception as e:
        print(f"  WARNING: Could not fetch Brevo stats ({e}). Assuming 0 sent today.")
        return 0


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


def send_category_batch(category, account, progress, max_sends):
    """Send up to max_sends leads for one category using one Brevo account."""
    key = category["key"]
    leads = load_leads(category["file"])
    pointer = progress["pointers"].get(key, 0)
    batch = leads[pointer:pointer + max_sends]

    if not batch:
        print(f"[Account {account['label']}] No more leads left for category '{key}'. Skipping.")
        return {"category": key, "account": account["label"], "attempted": 0, "sent": 0, "failed": 0, "failures": [], "pointer_before": pointer, "pointer_after": pointer, "total_leads": len(leads)}

    sent, failed = 0, 0
    fail_log = []
    for lead in batch:
        ok, result = send_one(category[account["template_field"]], lead, account["api_key"])
        if ok:
            sent += 1
        else:
            failed += 1
            fail_log.append({"email": lead["email"], "error": str(result)})
        time.sleep(0.15)

    # Only advance pointer by the number actually sent (not attempted)
    # This prevents lost leads if Brevo silently drops emails
    progress["pointers"][key] = pointer + sent

    return {
        "category": key,
        "account": account["label"],
        "attempted": len(batch),
        "sent": sent,
        "failed": failed,
        "failures": fail_log,
        "pointer_before": pointer,
        "pointer_after": pointer + sent,
        "total_leads": len(leads),
    }


def main():
    progress = load_progress()
    today = date.today().isoformat()

    # SAFEGUARD 1: Same-day re-run protection
    if progress.get("last_run_date") == today and not FORCE:
        print(f"Already ran today ({today}). Use --force to override. Exiting.")
        return

    idx = progress["cycle_index"] % len(CATEGORIES)

    # Pick three consecutive categories: one for each account.
    categories_today = []
    for i in range(len(ACCOUNTS)):
        categories_today.append(CATEGORIES[(idx + i) % len(CATEGORIES)])

    print(f"=== Daily outreach for {today} ===")

    # SAFEGUARD 2: Check Brevo daily quota for each account
    for i, (account, cat) in enumerate(zip(ACCOUNTS, categories_today)):
        sent_today = get_brevo_sent_today(account["api_key"])
        remaining = BREVO_DAILY_LIMIT - sent_today
        account["remaining"] = max(0, remaining)
        print(f"Account {account['label']} -> category: {cat['key']} (template {cat[account['template_field']]}) | Brevo sent today: {sent_today}/{BREVO_DAILY_LIMIT} | remaining: {account['remaining']}")
        if account["remaining"] == 0:
            print(f"  WARNING: Account {account['label']} has hit daily limit. Will skip this account.")
    print()

    # Send each account's batch (limited by remaining quota)
    results = []
    for account, category in zip(ACCOUNTS, categories_today):
        if account["remaining"] == 0:
            print(f"[Account {account['label']}] SKIPPED - daily limit reached. No sends for category '{category['key']}'.")
            results.append({"category": category["key"], "account": account["label"], "attempted": 0, "sent": 0, "failed": 0, "failures": [], "pointer_before": progress["pointers"].get(category["key"], 0), "pointer_after": progress["pointers"].get(category["key"], 0), "total_leads": len(load_leads(category["file"]))})
            continue
        result = send_category_batch(category, account, progress, account["remaining"])
        results.append(result)
        print(f"[Account {result['account']}] Category={result['category']} attempted={result['attempted']} sent={result['sent']} failed={result['failed']} pointer={result['pointer_after']}/{result['total_leads']}")

    # Advance cycle by number of accounts that actually sent
    accounts_sent = sum(1 for r in results if r["sent"] > 0)
    progress["cycle_index"] += accounts_sent if accounts_sent > 0 else len(ACCOUNTS)
    progress["last_run_date"] = today

    # Record history
    history_entry = {
        "date": today,
        "total_sent": sum(r["sent"] for r in results),
        "total_failed": sum(r["failed"] for r in results),
    }
    for i, result in enumerate(results):
        history_entry[f"account_{result['account']}"] = {
            "category": result["category"],
            "attempted": result["attempted"],
            "sent": result["sent"],
            "failed": result["failed"],
        }
    progress["history"].append(history_entry)
    save_progress(progress)

    # Save logs
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for result in results:
        log_path = os.path.join(LOG_DIR, f"{ts}_{result['category']}_acct{result['account']}.json")
        with open(log_path, "w") as f:
            json.dump(result, f, indent=2)

    total_sent = sum(r["sent"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    print()
    print(f"=== Done. Total sent: {total_sent}, Total failed: {total_failed} ===")


if __name__ == "__main__":
    main()
