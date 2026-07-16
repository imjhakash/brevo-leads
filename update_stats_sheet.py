"""
Hourly stats updater for Google Sheets.

Fetches email activity events from all 5 Brevo accounts and sends them
to a Google Apps Script web app that writes them to a Google Sheet with
three tabs:
  - Summary: daily totals per account (sent, delivered, opens, clicks, bounces)
  - Leads: one row per unique email, color-coded status, no duplicates
  - Detail: per-email events (email, category, event type, timestamp, link)

Categories are identified via email tags (not template IDs):
  - healthcare
  - building_materials
  - fashion

Environment variables required:
  BREVO_API_KEY    - Brevo transactional API key (account 1)
  BREVO_API_KEY_2  - Brevo transactional API key (account 2)
  BREVO_API_KEY_3  - Brevo transactional API key (account 3)
  BREVO_API_KEY_4  - Brevo transactional API key (account 4)
  BREVO_API_KEY_5  - Brevo transactional API key (account 5)
  SHEET_WEBHOOK_URL - Google Apps Script web app URL
  SHEET_AUTH_TOKEN  - Simple auth token to prevent unauthorized POSTs
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timezone, timedelta

BASE_URL = "https://api.brevo.com/v3"

API_KEYS = [
    {"label": "Account 1", "key": os.environ.get("BREVO_API_KEY")},
    {"label": "Account 2", "key": os.environ.get("BREVO_API_KEY_2")},
    {"label": "Account 3", "key": os.environ.get("BREVO_API_KEY_3")},
    {"label": "Account 4", "key": os.environ.get("BREVO_API_KEY_4")},
    {"label": "Account 5", "key": os.environ.get("BREVO_API_KEY_5")},
]

SHEET_WEBHOOK_URL = os.environ.get("SHEET_WEBHOOK_URL")
SHEET_AUTH_TOKEN = os.environ.get("SHEET_AUTH_TOKEN", "cmp-lead-stats-2026")

# Tag to category display name mapping
TAG_TO_CATEGORY = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}


def make_headers(api_key):
    return {
        "accept": "application/json",
        "api-key": api_key,
    }


def api_get(url, api_key, timeout=30):
    headers = make_headers(api_key)
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def get_aggregated_stats(api_key, start_date, end_date):
    """Get aggregated stats for a date range."""
    url = f"{BASE_URL}/smtp/statistics/aggregatedReport?startDate={start_date}&endDate={end_date}"
    try:
        return api_get(url, api_key, timeout=15)
    except Exception as e:
        print(f"  Warning: Could not fetch aggregated stats: {e}")
        return {}


def get_events(api_key, days=1, limit=1000):
    """Get email events (opens, clicks, bounces, etc.) from Brevo."""
    url = f"{BASE_URL}/smtp/statistics/events?limit={limit}&offset=0&days={days}&sort=desc"
    try:
        data = api_get(url, api_key)
        return data.get("events", [])
    except Exception as e:
        print(f"  Warning: Could not fetch events: {e}")
        return []


def get_category_from_tags(tags):
    """Determine category from email tags."""
    if not tags:
        return "Unknown"
    for tag in tags:
        if tag in TAG_TO_CATEGORY:
            return TAG_TO_CATEGORY[tag]
    return "Unknown"


def collect_summary():
    """Collect aggregated stats from all 5 accounts for today and yesterday."""
    today = date.today().strftime("%Y-%m-%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    summaries = []
    for acct in API_KEYS:
        if not acct["key"]:
            continue
        print(f"Fetching aggregated stats for {acct['label']}...")
        stats = get_aggregated_stats(acct["key"], today, today)
        yest_stats = get_aggregated_stats(acct["key"], yesterday, yesterday)

        summaries.append({
            "account": acct["label"],
            "date": today,
            "requests": stats.get("requests", 0),
            "delivered": stats.get("delivered", 0),
            "hardBounces": stats.get("hardBounces", 0),
            "softBounces": stats.get("softBounces", 0),
            "opens": stats.get("opens", 0),
            "uniqueOpens": stats.get("uniqueOpens", 0),
            "clicks": stats.get("clicks", 0),
            "uniqueClicks": stats.get("uniqueClicks", 0),
            "unsubscribed": stats.get("unsubscribed", 0),
            "spamReports": stats.get("spamReports", 0),
            "blocked": stats.get("blocked", 0),
            "deferred": stats.get("deferred", 0),
            "error": stats.get("error", 0),
            "yesterday_requests": yest_stats.get("requests", 0),
            "yesterday_delivered": yest_stats.get("delivered", 0),
            "yesterday_opens": yest_stats.get("opens", 0),
            "yesterday_clicks": yest_stats.get("clicks", 0),
        })
    return summaries


def collect_detail_events():
    """Collect per-email events from all 5 accounts."""
    all_events = []
    for acct in API_KEYS:
        if not acct["key"]:
            continue
        print(f"Fetching email events for {acct['label']}...")
        events = get_events(acct["key"], days=3, limit=1000)
        for ev in events:
            tags = ev.get("tags", [])
            category = get_category_from_tags(tags)
            all_events.append({
                "email": ev.get("email", ""),
                "event": ev.get("event", ""),
                "date": ev.get("date", ""),
                "subject": ev.get("subject", ""),
                "category": category,
                "templateId": ev.get("templateId", ""),
                "tag": ", ".join(tags) if tags else "",
                "link": ev.get("link", ""),
                "from": ev.get("from", ""),
                "messageId": ev.get("messageId", ""),
                "account": acct["label"],
            })
    return all_events


def collect_sent_emails():
    """Collect all sent transactional emails from all 5 accounts."""
    all_sent = []
    for acct in API_KEYS:
        if not acct["key"]:
            continue
        print(f"Fetching sent emails for {acct['label']}...")
        url = f"{BASE_URL}/smtp/emails?limit=1000&offset=0&sort=desc"
        try:
            data = api_get(url, acct["key"])
            for e in data.get("transactionalEmails", []):
                tags = e.get("tags", [])
                category = get_category_from_tags(tags)
                all_sent.append({
                    "email": e.get("email", ""),
                    "date": e.get("date", ""),
                    "subject": e.get("subject", ""),
                    "category": category,
                    "templateId": e.get("templateId", ""),
                    "tag": ", ".join(tags) if tags else "",
                    "from": e.get("from", ""),
                    "messageId": e.get("messageId", ""),
                    "account": acct["label"],
                })
        except Exception as e:
            print(f"  Warning: Could not fetch sent emails: {e}")
    return all_sent


def send_to_sheet(payload):
    """Send data to Google Apps Script web app."""
    if not SHEET_WEBHOOK_URL:
        print("ERROR: SHEET_WEBHOOK_URL not set", file=sys.stderr)
        sys.exit(1)

    payload["auth_token"] = SHEET_AUTH_TOKEN
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        SHEET_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
                print(f"Sheet updated: {result}")
                return True
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")
            print(f"Error sending to sheet (attempt {attempt+1}): {err}")
            if attempt < 2:
                import time
                time.sleep(10)
        except Exception as e:
            print(f"Error sending to sheet (attempt {attempt+1}): {e}")
            if attempt < 2:
                import time
                time.sleep(10)
    return False


def main():
    print(f"=== Hourly Stats Update - {datetime.now(timezone.utc).isoformat()} ===")
    print()

    # Collect data
    summaries = collect_summary()
    events = collect_detail_events()
    sent_emails = collect_sent_emails()

    print()
    print(f"Collected {len(summaries)} account summaries, {len(events)} email events, {len(sent_emails)} sent emails")

    # Send to Google Sheet
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summaries": summaries,
        "events": events,
        "sent_emails": sent_emails,
    }

    print("Sending to Google Sheet...")
    success = send_to_sheet(payload)

    if success:
        print("=== Done ===")
    else:
        print("=== Failed to update sheet ===", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
