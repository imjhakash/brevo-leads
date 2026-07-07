"""
Daily automated outreach sender for CodeMyPixel.

Rotates through 4 lead categories (one category per day) and sends the
next 300 un-contacted leads from that category's CSV file via Brevo's
transactional email API, using the matching Brevo template.

State (which category is "today", and how far each category's pointer
has progressed) is persisted in progress.json, which this script updates
in place. The GitHub Actions workflow commits that file back to the repo
after every run, so progress carries over correctly day to day.

Environment variables required:
  BREVO_API_KEY   - Brevo transactional API key
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

API_KEY = os.environ.get("BREVO_API_KEY")
if not API_KEY:
    print("ERROR: BREVO_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://api.brevo.com/v3"
DAILY_BATCH_SIZE = 300

# Rotation order: one category sent per day, cycling through all 4.
# Subjects are intentionally omitted here so Brevo uses each template's own
# stored subject line (which already contains {{contact.COMPANY}} merge tags).
CATEGORIES = [
    {"key": "construction", "file": "construction.csv", "template_id": 7},
    {"key": "banking", "file": "banking.csv", "template_id": 6},
    {"key": "accounting", "file": "accounting.csv", "template_id": 8},
    {"key": "automotive", "file": "automotive.csv", "template_id": 9},
]

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "api-key": API_KEY,
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


def send_one(template_id, recipient):
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
        except Exception as e:
            time.sleep(2)
    return False, "failed after retries"


def main():
    progress = load_progress()
    idx = progress["cycle_index"] % len(CATEGORIES)
    category = CATEGORIES[idx]
    key = category["key"]

    leads = load_leads(category["file"])
    pointer = progress["pointers"].get(key, 0)
    batch = leads[pointer:pointer + DAILY_BATCH_SIZE]

    if not batch:
        print(f"No more leads left for category '{key}'. Skipping to next category today.")
        progress["cycle_index"] += 1
        save_progress(progress)
        return

    sent, failed = 0, 0
    fail_log = []
    for lead in batch:
        ok, result = send_one(category["template_id"], lead)
        if ok:
            sent += 1
        else:
            failed += 1
            fail_log.append({"email": lead["email"], "error": str(result)})
        time.sleep(0.15)

    progress["pointers"][key] = pointer + len(batch)
    progress["cycle_index"] += 1
    progress["history"].append({
        "date": date.today().isoformat(),
        "category": key,
        "attempted": len(batch),
        "sent": sent,
        "failed": failed,
    })
    save_progress(progress)

    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}_{key}.json")
    with open(log_path, "w") as f:
        json.dump({"category": key, "sent": sent, "failed": failed, "failures": fail_log}, f, indent=2)

    print(f"Category={key} attempted={len(batch)} sent={sent} failed={failed} pointer_now={progress['pointers'][key]}/{len(leads)}")


if __name__ == "__main__":
    main()
