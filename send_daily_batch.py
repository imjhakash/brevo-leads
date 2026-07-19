"""
Daily automated outreach sender for CodeMyPixel.

Uses FIVE Brevo accounts to send 1500 emails per day.
  - Healthcare & Wellness   -> 2 accounts (600/day)
  - Building Materials      -> 2 accounts (600/day)
  - Apparel & Fashion       -> 1 account  (300/day)

Each email is sent as inline HTML (no Brevo template needed) with:
  - Personalized name + company (replaced directly in Python)
  - Sector-specific AI Automation Report PDF attachment
  - Founder photo inline image
  - Booking link (cal.com)
  - Mobile-responsive design

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

# Founder image hosted in public repo (raw GitHub URL)
FOUNDER_IMAGE_URL = "https://raw.githubusercontent.com/imjhakash/brevo-leads/main/assets/founder.png"
BOOKING_URL = "https://cal.com/team-cmp-tk2uvf/from-website"
COMPANY_URL = "https://www.codemypixel.com"

# Google Drive PDF links per category
PDF_LINKS = {
    "healthcare": "https://drive.google.com/file/d/1YacIAJuoxoE3zZWdpmta9-A2fZArOLnp/view?usp=sharing",
    "building_materials": "https://drive.google.com/file/d/1q3V2x7u-PMXHxR4XZumvHT5EvJYufO5O/view?usp=sharing",
    "fashion": "https://drive.google.com/file/d/1A_bGfA_DO-mUeTrx40DcKWazGIg7vihr/view?usp=sharing",
}

# PDF attachment paths per category (for attaching to email)
PDF_PATHS = {
    "healthcare": os.path.join(ASSETS_DIR, "healthcare-report.pdf"),
    "building_materials": os.path.join(ASSETS_DIR, "building-materials-report.pdf"),
    "fashion": os.path.join(ASSETS_DIR, "fashion-report.pdf"),
}

PDF_FILENAMES = {
    "healthcare": "AI-Automation-Report-Healthcare-Wellness.pdf",
    "building_materials": "AI-Automation-Report-Building-Materials.pdf",
    "fashion": "AI-Automation-Report-Apparel-Fashion.pdf",
}

CATEGORY_NAMES = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}

SUBJECTS = {
    "healthcare": "We researched the Healthcare & Wellness market and found something interesting",
    "building_materials": "We researched the Building Materials market and found something interesting",
    "fashion": "We researched the Apparel & Fashion market and found something interesting",
}

# Category definitions with account assignments
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


def load_pdf_attachment(category):
    pdf_path = PDF_PATHS.get(category)
    if not pdf_path or not os.path.exists(pdf_path):
        print(f"  WARNING: PDF not found at {pdf_path}")
        return None
    with open(pdf_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    return content


def build_html_email(recipient, category):
    """Build personalized HTML email with name and company replaced directly."""
    name = recipient["firstname"]
    company = recipient["company"]
    cat_name = CATEGORY_NAMES.get(category, category)
    pdf_link = PDF_LINKS.get(category, "")

    # Category-specific content
    if category == "healthcare":
        stats = [("40%", "of clinician hours consumed by admin", "#ef4444"),
                 ("5.3 hrs", "recovered daily with AI scribes", "#10b981"),
                 ("$31B", "spent yearly on prior-auth paperwork", "#f59e0b")]
        hook = 'Your clinicians spend <strong style="color:#0f172a;">2 hours on paperwork for every 1 hour with a patient</strong>. We found a way to flip that ratio.'
        findings = [
            ("Ambient AI scribes", "Cut patient encounter time from 41 minutes to 16 minutes &mdash; recovering 5+ hours of clinical capacity every day."),
            ("Prior-authorization automation", "Turnaround from 5&ndash;7 days down to 24&ndash;48 hours, automating up to 75% of manual admin tasks."),
            ("Predictive scheduling & RCM", "30&ndash;45% reduction in no-show rates and 98%+ coding accuracy with automated billing verification."),
        ]
        report_title = "AI Automation Briefing: Healthcare &amp; Wellness"
        report_subtitle = "How ambient AI is recovering 5+ hours per day for clinics like yours"
    elif category == "building_materials":
        stats = [("36%", "of workweek lost to manual admin", "#ef4444"),
                 ("60%", "faster order processing with AI", "#10b981"),
                 ("99%+", "order accuracy after automation", "#2563eb")]
        hook = 'Your sales reps spend <strong style="color:#0f172a;">only 1/3 of their day actually selling</strong>. The rest is eaten by manual order entry and invoice reconciliation.'
        findings = [
            ("Intelligent Document Processing", "Turns a 5-minute manual order entry into a 100-millisecond automated extraction &mdash; reclaiming ~5 hours of daily labor."),
            ("Automated 3-way AP matching", "Cuts accounts payable from 6&ndash;7 hours daily to under 1 hour, protecting early-payment discounts."),
            ("Predictive demand forecasting", "40% labor reduction in sourcing and 95% forecast accuracy &mdash; no more spreadsheet guessing."),
        ]
        report_title = "AI Automation Briefing: Building Materials Distribution"
        report_subtitle = "How AI-powered order processing cuts cycle times by 60%"
    else:  # fashion
        stats = [("68%", "of workweek on operations, not growth", "#ef4444"),
                 ("91%", "less time on visual production with AI", "#10b981"),
                 ("98%+", "cost reduction per finished image", "#2563eb")]
        hook = 'You spend <strong style="color:#0f172a;">68% of your week running the business. Only 32% grows it.</strong> We found where the time goes and how to get it back.'
        findings = [
            ("Generative AI visual production", "Turns a 3-week photoshoot into a 1-hour render &mdash; cutting cost per image from $84 to ~$1."),
            ("AI catalog enrichment", "Auto-generates SEO descriptions, tags, and sizing data 5x faster than manual entry."),
            ("Conversational commerce AI", "Resolves 70% of routine customer questions autonomously, cutting support costs by 39%."),
        ]
        report_title = "AI Automation Briefing: Apparel &amp; Fashion E-Commerce"
        report_subtitle = "How generative AI cuts visual production costs by 98%"

    # Build stat cards
    stat_cards = ""
    for number, label, accent in stats:
        stat_cards += (
            '<td class="stat-card" style="padding:0 6px;width:33.33%;">'
            '<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">'
            '<tr><td align="center" style="padding:18px 8px;">'
            f'<p style="margin:0;font-size:26px;font-weight:800;color:{accent};line-height:1.1;letter-spacing:-1px;">{number}</p>'
            f'<p style="margin:8px 0 0 0;font-size:11px;color:#64748b;line-height:1.4;font-weight:500;">{label}</p>'
            '</td></tr></table></td>'
        )

    # Build numbered findings
    findings_html = ""
    for i, (title, desc) in enumerate(findings, 1):
        findings_html += (
            '<tr><td style="padding:0 0 18px 0;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            '<td valign="top" style="width:40px;padding-right:14px;">'
            f'<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#7c3fc8);color:#ffffff;font-size:14px;font-weight:700;text-align:center;line-height:32px;">{i}</div>'
            '</td><td valign="top">'
            f'<p style="margin:0 0 5px 0;font-size:15px;font-weight:700;color:#0f172a;line-height:1.3;">{title}</p>'
            f'<p style="margin:0;font-size:13px;color:#64748b;line-height:1.65;">{desc}</p>'
            '</td></tr></table></td></tr>'
        )

    # HTML template with variables replaced directly (no Brevo variables)
    # Using string concatenation to avoid f-string brace issues
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">\n'
        '<title>CodeMyPixel Research Report</title>\n'
        '<style>\n'
        '  @media only screen and (max-width: 620px) {\n'
        '    .email-container { width: 100% !important; border-radius: 0 !important; }\n'
        '    .email-padding { padding: 24px 20px !important; }\n'
        '    .hero-padding { padding: 32px 20px 24px 20px !important; }\n'
        '    .stat-card { width: 100% !important; display: block !important; padding: 0 0 10px 0 !important; }\n'
        '    .stat-card table { width: 100% !important; }\n'
        '    .cta-button { width: 100% !important; box-sizing: border-box !important; text-align: center !important; }\n'
        '    .footer-text { font-size: 10px !important; }\n'
        '    h1 { font-size: 20px !important; }\n'
        '    h2 { font-size: 16px !important; }\n'
        '    .body-text { font-size: 14px !important; line-height: 1.7 !important; }\n'
        '    .pdf-box { padding: 18px 16px !important; }\n'
        '  }\n'
        '  @media only screen and (max-width: 480px) {\n'
        '    .stat-card { padding: 0 0 8px 0 !important; }\n'
        '    .stat-card p:first-child { font-size: 22px !important; }\n'
        '    .email-padding { padding: 20px 16px !important; }\n'
        '    .hero-padding { padding: 28px 16px 20px 16px !important; }\n'
        '  }\n'
        '</style>\n'
        '</head>\n'
        '<body style="margin:0;padding:0;background-color:#eef2f6;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">\n'
        '\n'
        '  <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">\n'
        f'    We researched the {cat_name} market and found gaps that companies like {company} are facing right now. 2-minute read + 4-page report inside.\n'
        '  </div>\n'
        '\n'
        '  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#eef2f6;padding:28px 12px;">\n'
        '    <tr><td align="center">\n'
        '\n'
        '      <table class="email-container" width="620" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(15,23,42,0.08);max-width:620px;">\n'
        '\n'
        '        <tr>\n'
        '          <td class="hero-padding" style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#2563eb 100%);padding:40px 40px 32px 40px;" align="center">\n'
        f'            <img src="{FOUNDER_IMAGE_URL}" alt="Johirul Hoq Akash" width="88" height="88" style="border-radius:50%;border:3px solid rgba(255,255,255,0.25);object-fit:cover;display:block;margin-bottom:14px;" />\n'
        '            <p style="margin:0;color:#94a3b8;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">CodeMyPixel Research</p>\n'
        '            <p style="margin:6px 0 0 0;color:#f8fafc;font-size:18px;font-weight:600;">Johirul Hoq Akash &middot; Founder</p>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:36px 40px 0 40px;">\n'
        f'            <h1 style="margin:0 0 14px 0;color:#0f172a;font-size:24px;font-weight:800;letter-spacing:-0.5px;line-height:1.3;">Hi {name},</h1>\n'
        f'            <p class="body-text" style="margin:0 0 20px 0;color:#334155;font-size:15px;line-height:1.75;">{hook}</p>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:0 40px 28px 40px;">\n'
        '            <table width="100%" cellpadding="0" cellspacing="0"><tr>' + stat_cards + '</tr></table>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr><td style="padding:0 40px;"><div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div></td></tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:28px 40px 8px 40px;">\n'
        '            <p style="margin:0 0 6px 0;color:#2563eb;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;">The Report</p>\n'
        f'            <h2 style="margin:0 0 8px 0;color:#0f172a;font-size:18px;font-weight:700;line-height:1.4;">{report_title}</h2>\n'
        f'            <p style="margin:0 0 20px 0;color:#64748b;font-size:13px;font-style:italic;">{report_subtitle}</p>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:0 40px 24px 40px;">\n'
        '            <table width="100%" cellpadding="0" cellspacing="0">' + findings_html + '</table>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:0 40px 28px 40px;">\n'
        '            <table class="pdf-box" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border:1px solid #bae6fd;border-radius:12px;">\n'
        '              <tr><td class="pdf-box" style="padding:22px 24px;">\n'
        f'                <p style="margin:0 0 4px 0;color:#0c4a6e;font-size:14px;font-weight:700;">&#128206; Read the full 4-page report</p>\n'
        f'                <p style="margin:0 0 14px 0;color:#0369a1;font-size:12px;line-height:1.5;">Open the PDF to see the complete data, sources, and real-world impact numbers for the {cat_name} sector.</p>\n'
        f'                <a href="{pdf_link}" style="display:inline-block;padding:11px 26px;background-color:#2563eb;color:#ffffff;text-decoration:none;font-size:13px;font-weight:600;border-radius:8px;">Open Report PDF &rarr;</a>\n'
        '              </td></tr>\n'
        '            </table>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr><td style="padding:0 40px;"><div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div></td></tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:24px 40px 8px 40px;">\n'
        f'            <p class="body-text" style="margin:0 0 12px 0;color:#334155;font-size:15px;line-height:1.75;">I know you\'re busy at <strong style="color:#0f172a;">{company}</strong>, so I\'ll keep this short &mdash; just 2 minutes.</p>\n'
        f'            <p class="body-text" style="margin:0 0 12px 0;color:#334155;font-size:15px;line-height:1.75;">I\'m <strong style="color:#0f172a;">Johirul Hoq Akash</strong>, founder of <a href="{COMPANY_URL}" style="color:#2563eb;text-decoration:none;font-weight:700;"><strong style="color:#2563eb;">CodeMyPixel</strong></a>. We\'re an automation developer team that builds custom AI systems plugged directly into your existing workflow &mdash; no off-the-shelf guesswork, just solutions built around your business.</p>\n'
        f'            <p class="body-text" style="margin:0 0 24px 0;color:#334155;font-size:15px;line-height:1.75;">If any of this resonates, I\'d love to show you what this could look like for <strong style="color:#0f172a;">{company}</strong>. No pressure &mdash; just pick a time that works:</p>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:0 40px 32px 40px;" align="center">\n'
        f'            <a href="{BOOKING_URL}" class="cta-button" style="display:inline-block;padding:16px 40px;background:linear-gradient(135deg,#2563eb,#7c3fc8);color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;border-radius:12px;box-shadow:0 4px 12px rgba(37,99,235,0.35);max-width:300px;">Book Your Preferred Time &rarr;</a>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '        <tr>\n'
        '          <td class="email-padding" style="padding:0 40px 36px 40px;border-top:1px solid #f1f5f9;">\n'
        '            <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding-top:24px;">\n'
        '              <p style="margin:0 0 4px 0;color:#64748b;font-size:14px;">Best regards,</p>\n'
        '              <p style="margin:0 0 2px 0;color:#0f172a;font-size:15px;font-weight:700;">Johirul Hoq Akash</p>\n'
        f'              <p style="margin:0 0 2px 0;color:#64748b;font-size:13px;">Founder, <a href="{COMPANY_URL}" style="color:#64748b;text-decoration:none;font-weight:600;">CodeMyPixel</a></p>\n'
        f'              <p style="margin:0;color:#64748b;font-size:13px;"><a href="{BOOKING_URL}" style="color:#2563eb;text-decoration:none;font-weight:600;">cal.com/team-cmp-tk2uvf/from-website</a></p>\n'
        '            </td></tr></table>\n'
        '          </td>\n'
        '        </tr>\n'
        '\n'
        '      </table>\n'
        '\n'
        '      <table class="email-container" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;">\n'
        '        <tr><td align="center" style="padding:20px 40px;">\n'
        f'          <p class="footer-text" style="margin:0;color:#94a3b8;font-size:11px;line-height:1.6;"><a href="{COMPANY_URL}" style="color:#94a3b8;text-decoration:none;font-weight:600;">CodeMyPixel</a> &middot; AI Automation Systems for Growing Businesses<br>\n'
        f'          This email was sent to you because we believe our research is relevant to {company}.<br>\n'
        f'          You can read the full report <a href="{pdf_link}" style="color:#94a3b8;text-decoration:underline;">here</a>.</p>\n'
        '        </td></tr>\n'
        '      </table>\n'
        '\n'
        '    </td></tr>\n'
        '  </table>\n'
        '\n'
        '</body>\n'
        '</html>'
    )
    return html


def send_one(recipient, category, api_key, sender_email):
    """Send a single personalized email with inline HTML (no PDF attachment)."""
    headers = make_headers(api_key)
    subject = SUBJECTS.get(category, "We researched your market and found something interesting")
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
    print(f"Mode: Inline HTML (no Brevo template, variables replaced in Python)")
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
