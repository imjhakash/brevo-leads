"""
Daily automated outreach sender for CodeMyPixel.

Uses FIVE Brevo accounts to send 1500 emails per day (300 from each account).
Construction gets 2 accounts (600/day), other categories get 1 account each
(300/day). All 4 categories are sent every day — no rotation needed.

  - Account 1 → Construction (300/day)
  - Account 2 → Banking (300/day)
  - Account 3 → Accounting (300/day)
  - Account 4 → Automotive (300/day)
  - Account 5 → Construction (300/day, second batch)

SAFEGUARDS:
  1. Same-day re-run protection: checks progress.json "last_run_date" and exits
     if already run today. Use --force to override.
  2. Brevo daily quota check: queries each account's actual sent count today
     via Brevo API before sending. Skips accounts that already hit 300/day.
  3. Pointer advances by actual sent count, not attempted count.

Environment variables required:
  BREVO_API_KEY    - Brevo account 1
  BREVO_API_KEY_2  - Brevo account 2
  BREVO_API_KEY_3  - Brevo account 3
  BREVO_API_KEY_4  - Brevo account 4
  BREVO_API_KEY_5  - Brevo account 5
"""
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timezone
from collections import defaultdict

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
        print(f"ERROR: BREVO_API_KEY_{i if i > 1 else ''} environment variable not set", file=sys.stderr)
        sys.exit(1)

BASE_URL = "https://api.brevo.com/v3"
DAILY_BATCH_SIZE = 300
BREVO_DAILY_LIMIT = 300
FORCE = "--force" in sys.argv

# Category definitions with template IDs per account
CATEGORIES = {
    "construction": {
        "file": "construction.csv",
        "accounts": [
            {"label": "1", "api_key": API_KEY_1, "template_id": 7},
            {"label": "5", "api_key": API_KEY_5, "template_id": 2},
        ],
    },
    "banking": {
        "file": "banking.csv",
        "accounts": [
            {"label": "2", "api_key": API_KEY_2, "template_id": 23},
        ],
    },
    "accounting": {
        "file": "accounting.csv",
        "accounts": [
            {"label": "3", "api_key": API_KEY_3, "template_id": 6},
        ],
    },
    "automotive": {
        "file": "automotive.csv",
        "accounts": [
            {"label": "4", "api_key": API_KEY_4, "template_id": 4},
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


def send_one(template_id, recipient, api_key):
    headers = make_headers(api_key)
    body = {
        "templateId": template_id,
        "to": [{"email": recipient["email"], "name": recipient["firstname"]}],
        "params": {"FIRSTNAME": recipient["firstname"], "COMPANY": recipient["company"]},
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


def send_batch(leads, template_id, api_key, account_label, max_sends):
    """Send up to max_sends emails from a batch of leads."""
    sent, failed = 0, 0
    fail_log = []
    for lead in leads[:max_sends]:
        ok, result = send_one(template_id, lead, api_key)
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

    # SAFEGUARD 1: Same-day re-run protection
    if progress.get("last_run_date") == today and not FORCE:
        print(f"Already ran today ({today}). Use --force to override. Exiting.")
        return

    print(f"=== Daily outreach for {today} ===")
    print(f"Construction: 2 accounts (600/day) | Banking: 1 (300) | Accounting: 1 (300) | Automotive: 1 (300)")
    print(f"Total target: 1500 emails/day")
    print()

    all_results = []

    for cat_key, cat_config in CATEGORIES.items():
        leads = load_leads(cat_config["file"])
        pointer = progress["pointers"].get(cat_key, 0)
        accounts = cat_config["accounts"]

        print(f"--- Category: {cat_key} ({len(accounts)} account(s), pointer at {pointer}/{len(leads)}) ---")

        # For each account assigned to this category, send a consecutive slice
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

            # Get the slice for this account
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
                batch, acct["template_id"], acct["api_key"], acct["label"], acct["remaining"]
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

        # Advance pointer by total actually sent for this category
        progress["pointers"][cat_key] = current_offset
        print(f"  Category {cat_key}: total sent={category_sent}, failed={category_failed}, pointer now={current_offset}/{len(leads)}")
        print()

    progress["last_run_date"] = today

    # Record history
    total_sent = sum(r["sent"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    history_entry = {
        "date": today,
        "total_sent": total_sent,
        "total_failed": total_failed,
    }
    for r in all_results:
        key = f"account_{r['account']}"
        history_entry[key] = {
            "category": r["category"],
            "attempted": r["attempted"],
            "sent": r["sent"],
            "failed": r["failed"],
        }
    progress["history"].append(history_entry)
    save_progress(progress)

    # Save logs
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for r in all_results:
        log_path = os.path.join(LOG_DIR, f"{ts}_{r['category']}_acct{r['account']}.json")
        with open(log_path, "w") as f:
            json.dump(r, f, indent=2)

    print(f"=== Done. Total sent: {total_sent}, Total failed: {total_failed} ===")


if __name__ == "__main__":
    main()
