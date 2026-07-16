"""
Daily automated outreach sender for CodeMyPixel.

Uses FIVE Brevo accounts to send 1500 emails per day.
  - Healthcare & Wellness   → 2 accounts (600/day)
  - Building Materials      → 2 accounts (600/day)
  - Apparel & Fashion       → 1 account  (300/day)

Each email includes:
  - Personalized HTML body (name + company)
  - Sector-specific AI Automation Report PDF attachment
  - Founder photo inline image
  - Booking link (cal.com)

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
BOOKING_URL = "https://cal.com/team-cmp-tk2uvf/from-website"

# Founder image hosted in public repo (raw GitHub URL)
FOUNDER_IMAGE_URL = "https://raw.githubusercontent.com/imjhakash/brevo-leads/main/assets/founder.png"

# PDF attachment paths per category
PDF_PATHS = {
    "healthcare": os.path.join(ASSETS_DIR, "healthcare-report.pdf"),
    "building_materials": os.path.join(ASSETS_DIR, "building-materials-report.pdf"),
    "fashion": os.path.join(ASSETS_DIR, "fashion-report.pdf"),
}

# Category display names for email content
CATEGORY_NAMES = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}

# Subject lines per category
SUBJECTS = {
    "healthcare": "We researched the Healthcare & Wellness market and found something interesting",
    "building_materials": "We researched the Building Materials market and found something interesting",
    "fashion": "We researched the Apparel & Fashion market and found something interesting",
}

# PDF attachment filenames (what the recipient sees)
PDF_FILENAMES = {
    "healthcare": "AI-Automation-Report-Healthcare-Wellness.pdf",
    "building_materials": "AI-Automation-Report-Building-Materials.pdf",
    "fashion": "AI-Automation-Report-Apparel-Fashion.pdf",
}

# Category definitions with account assignments
# Healthcare: Accounts 1 & 5 (600/day)
# Building Materials: Accounts 2 & 3 (600/day)
# Fashion: Account 4 (300/day)
CATEGORIES = {
    "healthcare": {
        "file": "healthcare.csv",
        "accounts": [
            {"label": "1", "api_key": API_KEY_1},
            {"label": "5", "api_key": API_KEY_5},
        ],
    },
    "building_materials": {
        "file": "building_materials.csv",
        "accounts": [
            {"label": "2", "api_key": API_KEY_2},
            {"label": "3", "api_key": API_KEY_3},
        ],
    },
    "fashion": {
        "file": "fashion.csv",
        "accounts": [
            {"label": "4", "api_key": API_KEY_4},
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


def load_pdf_attachment(category):
    """Load and base64-encode the PDF for a category."""
    pdf_path = PDF_PATHS.get(category)
    if not pdf_path or not os.path.exists(pdf_path):
        print(f"  WARNING: PDF not found at {pdf_path}")
        return None
    with open(pdf_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    return content


def build_html_email(recipient, category):
    """Build personalized HTML email body for a recipient."""
    name = recipient["firstname"]
    company = recipient["company"]
    cat_name = CATEGORY_NAMES.get(category, category)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:24px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- Founder image header -->
          <tr>
            <td align="center" style="padding:32px 40px 16px 40px;background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);">
              <img src="{FOUNDER_IMAGE_URL}" alt="Johirul Hoq Akash" width="100" height="100"
                style="border-radius:50%;border:3px solid #3b82f6;object-fit:cover;display:block;margin-bottom:16px;" />
              <p style="margin:0;color:#94a3b8;font-size:13px;letter-spacing:0.5px;text-transform:uppercase;">Johirul Hoq Akash</p>
              <p style="margin:4px 0 0 0;color:#e2e8f0;font-size:15px;">Founder, CodeMyPixel</p>
            </td>
          </tr>

          <!-- Email body -->
          <tr>
            <td style="padding:36px 40px 8px 40px;">
              <h2 style="margin:0 0 8px 0;color:#0f172a;font-size:22px;font-weight:700;">
                Hi {name},
              </h2>
              <p style="margin:0 0 16px 0;color:#475569;font-size:15px;line-height:1.7;">
                I know you're busy, so I'll keep this short &mdash; just 2 minutes, I promise.
              </p>
              <p style="margin:0 0 16px 0;color:#475569;font-size:15px;line-height:1.7;">
                I'm <strong style="color:#0f172a;">Johirul Hoq Akash</strong>, founder of
                <strong style="color:#0f172a;">CodeMyPixel</strong>. My team and I researched the
                <strong style="color:#2563eb;">{cat_name}</strong> market and found some interesting gaps
                that companies like <strong style="color:#0f172a;">{company}</strong> are likely facing right now.
              </p>
              <p style="margin:0 0 16px 0;color:#475569;font-size:15px;line-height:1.7;">
                We put together a short <strong style="color:#0f172a;">4-page report</strong> &mdash; attached to this
                email as a PDF. It's concise, easy to understand, and directly relevant to your industry.
              </p>

              <!-- Report highlight box -->
              <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f9ff;border-left:4px solid #2563eb;border-radius:8px;margin:20px 0;">
                <tr>
                  <td style="padding:20px 24px;">
                    <p style="margin:0 0 6px 0;color:#1e40af;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">
                      &#128206; Attached: AI Automation Report
                    </p>
                    <p style="margin:0;color:#475569;font-size:14px;line-height:1.6;">
                      {cat_name} &mdash; 4 pages covering the biggest automation gaps we found,
                      what they cost businesses, and how to close them.
                    </p>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 16px 0;color:#475569;font-size:15px;line-height:1.7;">
                As an automation developer team, we can help you close those gaps &mdash; saving time,
                reducing manual work, and letting your team focus on what matters.
              </p>
              <p style="margin:0 0 24px 0;color:#475569;font-size:15px;line-height:1.7;">
                No pressure at all. If it's interesting, grab a time that works for you:
              </p>
            </td>
          </tr>

          <!-- CTA button -->
          <tr>
            <td style="padding:0 40px 32px 40px;" align="center">
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
                href="{BOOKING_URL}" style="height:52px;v-text-anchor:middle;width:280px;" arcsize="12%"
                strokecolor="#2563eb" fillcolor="#2563eb">
                <w:anchorlock/>
                <center style="color:#ffffff;font-family:sans-serif;font-size:16px;font-weight:bold;">
                  Book Your Preferred Time
                </center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <a href="{BOOKING_URL}"
                style="display:inline-block;padding:15px 36px;background-color:#2563eb;color:#ffffff;
                       text-decoration:none;font-size:16px;font-weight:600;border-radius:10px;
                       box-shadow:0 2px 4px rgba(37,99,235,0.3);">
                Book Your Preferred Time
              </a>
              <!--<![endif]-->
            </td>
          </tr>

          <!-- Signature -->
          <tr>
            <td style="padding:0 40px 36px 40px;border-top:1px solid #e2e8f0;">
              <p style="margin:20px 0 4px 0;color:#475569;font-size:14px;line-height:1.6;">
                Best regards,
              </p>
              <p style="margin:0 0 2px 0;color:#0f172a;font-size:15px;font-weight:600;">
                Johirul Hoq Akash
              </p>
              <p style="margin:0 0 2px 0;color:#64748b;font-size:13px;">
                Founder, CodeMyPixel
              </p>
              <p style="margin:0;color:#64748b;font-size:13px;">
                <a href="{BOOKING_URL}" style="color:#2563eb;text-decoration:none;">cal.com/team-cmp-tk2uvf/from-website</a>
              </p>
            </td>
          </tr>

        </table>

        <!-- Footer -->
        <table width="600" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center" style="padding:20px 40px;">
              <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.5;">
                CodeMyPixel &middot; AI Automation for Growing Businesses<br>
                This email was sent to you because we believe our research is relevant to {company}.
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""
    return html


def send_one(recipient, category, api_key, pdf_b64):
    """Send a single personalized email with PDF attachment."""
    headers = make_headers(api_key)
    subject = SUBJECTS.get(category, "We researched your market and found something interesting")
    html_content = build_html_email(recipient, category)

    body = {
        "subject": subject,
        "htmlContent": html_content,
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


def send_batch(leads, category, api_key, account_label, max_sends, pdf_b64):
    """Send up to max_sends emails from a batch of leads."""
    sent, failed = 0, 0
    fail_log = []
    for lead in leads[:max_sends]:
        ok, result = send_one(lead, category, api_key, pdf_b64)
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
    print(f"Healthcare: 2 accounts (600/day) | Building Materials: 2 (600) | Fashion: 1 (300)")
    print(f"Total target: 1500 emails/day")
    print()

    all_results = []

    for cat_key, cat_config in CATEGORIES.items():
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

            print(f"  [Account {acct['label']}] Sending {len(batch)} leads (Brevo used: {sent_today}/{BREVO_DAILY_LIMIT})")

            sent, failed, fail_log = send_batch(
                batch, cat_key, acct["api_key"], acct["label"], acct["remaining"], pdf_b64
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
