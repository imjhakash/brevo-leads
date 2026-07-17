"""
One-time script: Creates/updates email templates in all 5 Brevo accounts via API.

If template_ids.json already has IDs, updates existing templates.
Otherwise creates new ones.

Sender emails:
  Account 1: admin@codemypixel.com       → Healthcare
  Account 2: sabbir@team.codemypixel.com → Building Materials
  Account 3: akash@codemypixel.com       → Building Materials
  Account 4: neel@connect.codemypixel.com → Fashion
  Account 5: pravas@app.codemypixel.com  → Healthcare

Environment variables required:
  BREVO_API_KEY    through    BREVO_API_KEY_5
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE_URL = "https://api.brevo.com/v3"
FOUNDER_IMAGE_URL = "https://raw.githubusercontent.com/imjhakash/brevo-leads/main/assets/founder.png"
BOOKING_URL = "https://cal.com/team-cmp-tk2uvf/from-website"

# Google Drive PDF links per category
PDF_LINKS = {
    "healthcare": "https://drive.google.com/file/d/1YacIAJuoxoE3zZWdpmta9-A2fZArOLnp/view?usp=sharing",
    "building_materials": "https://drive.google.com/file/d/1q3V2x7u-PMXHxR4XZumvHT5EvJYufO5O/view?usp=sharing",
    "fashion": "https://drive.google.com/file/d/1A_bGfA_DO-mUeTrx40DcKWazGIg7vihr/view?usp=sharing",
}

ACCOUNTS = [
    {"env": "BREVO_API_KEY", "sender_email": "admin@codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "healthcare", "template_name": "Healthcare & Wellness Outreach", "subject": "We researched the Healthcare & Wellness market and found something interesting"},
    {"env": "BREVO_API_KEY_2", "sender_email": "sabbir@team.codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "building_materials", "template_name": "Building Materials Outreach", "subject": "We researched the Building Materials market and found something interesting"},
    {"env": "BREVO_API_KEY_3", "sender_email": "akash@codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "building_materials", "template_name": "Building Materials Outreach", "subject": "We researched the Building Materials market and found something interesting"},
    {"env": "BREVO_API_KEY_4", "sender_email": "neel@connect.codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "fashion", "template_name": "Apparel & Fashion Outreach", "subject": "We researched the Apparel & Fashion market and found something interesting"},
    {"env": "BREVO_API_KEY_5", "sender_email": "pravas@app.codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "healthcare", "template_name": "Healthcare & Wellness Outreach", "subject": "We researched the Healthcare & Wellness market and found something interesting"},
]

CATEGORY_NAMES = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}

# Use placeholder tokens that won't conflict with f-strings or Brevo braces
# These get replaced AFTER the f-string is built
VAR_FIRSTNAME = "<<FIRSTNAME>>"
VAR_COMPANY = "<<COMPANY>>"


def build_stat_card(number, label, accent="#2563eb"):
    return (
        '<td class="stat-card" style="padding:0 6px;width:33.33%;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">'
        '<tr><td align="center" style="padding:18px 8px;">'
        f'<p style="margin:0;font-size:26px;font-weight:800;color:{accent};line-height:1.1;letter-spacing:-1px;">{number}</p>'
        f'<p style="margin:8px 0 0 0;font-size:11px;color:#64748b;line-height:1.4;font-weight:500;">{label}</p>'
        '</td></tr></table></td>'
    )


def build_template_html(category):
    cat_name = CATEGORY_NAMES.get(category, category)
    pdf_link = PDF_LINKS.get(category, "")

    # Category-specific content
    if category == "healthcare":
        stats_html = (
            build_stat_card("40%", "of clinician hours consumed by admin", "#ef4444")
            + build_stat_card("5.3 hrs", "recovered daily with AI scribes", "#10b981")
            + build_stat_card("$31B", "spent yearly on prior-auth paperwork", "#f59e0b")
        )
        hook = 'Your clinicians spend <strong style="color:#0f172a;">2 hours on paperwork for every 1 hour with a patient</strong>. We found a way to flip that ratio.'
        summary_points = [
            ("Ambient AI scribes", "Cut patient encounter time from 41 minutes to 16 minutes &mdash; recovering 5+ hours of clinical capacity every day."),
            ("Prior-authorization automation", "Turnaround from 5&ndash;7 days down to 24&ndash;48 hours, automating up to 75% of manual admin tasks."),
            ("Predictive scheduling & RCM", "30&ndash;45% reduction in no-show rates and 98%+ coding accuracy with automated billing verification."),
        ]
        report_title = "AI Automation Briefing: Healthcare & Wellness"
        report_subtitle = "How ambient AI is recovering 5+ hours per day for clinics like yours"
    elif category == "building_materials":
        stats_html = (
            build_stat_card("36%", "of workweek lost to manual admin", "#ef4444")
            + build_stat_card("60%", "faster order processing with AI", "#10b981")
            + build_stat_card("99%+", "order accuracy after automation", "#2563eb")
        )
        hook = 'Your sales reps spend <strong style="color:#0f172a;">only 1/3 of their day actually selling</strong>. The rest is eaten by manual order entry and invoice reconciliation.'
        summary_points = [
            ("Intelligent Document Processing", "Turns a 5-minute manual order entry into a 100-millisecond automated extraction &mdash; reclaiming ~5 hours of daily labor."),
            ("Automated 3-way AP matching", "Cuts accounts payable from 6&ndash;7 hours daily to under 1 hour, protecting early-payment discounts."),
            ("Predictive demand forecasting", "40% labor reduction in sourcing and 95% forecast accuracy &mdash; no more spreadsheet guessing."),
        ]
        report_title = "AI Automation Briefing: Building Materials Distribution"
        report_subtitle = "How AI-powered order processing cuts cycle times by 60%"
    else:  # fashion
        stats_html = (
            build_stat_card("68%", "of workweek on operations, not growth", "#ef4444")
            + build_stat_card("91%", "less time on visual production with AI", "#10b981")
            + build_stat_card("98%+", "cost reduction per finished image", "#2563eb")
        )
        hook = 'You spend <strong style="color:#0f172a;">68% of your week running the business. Only 32% grows it.</strong> We found where the time goes and how to get it back.'
        summary_points = [
            ("Generative AI visual production", "Turns a 3-week photoshoot into a 1-hour render &mdash; cutting cost per image from $84 to ~$1."),
            ("AI catalog enrichment", "Auto-generates SEO descriptions, tags, and sizing data 5x faster than manual entry."),
            ("Conversational commerce AI", "Resolves 70% of routine customer questions autonomously, cutting support costs by 39%."),
        ]
        report_title = "AI Automation Briefing: Apparel & Fashion E-Commerce"
        report_subtitle = "How generative AI cuts visual production costs by 98%"

    # Build summary points HTML
    summary_html = ""
    for i, (title, desc) in enumerate(summary_points, 1):
        summary_html += (
            '<tr><td style="padding:0 0 18px 0;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            '<td valign="top" style="width:40px;padding-right:14px;">'
            f'<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#2563eb,#7c3fc8);color:#ffffff;font-size:14px;font-weight:700;text-align:center;line-height:32px;">{i}</div>'
            '</td><td valign="top">'
            f'<p style="margin:0 0 5px 0;font-size:15px;font-weight:700;color:#0f172a;line-height:1.3;">{title}</p>'
            f'<p style="margin:0;font-size:13px;color:#64748b;line-height:1.65;">{desc}</p>'
            '</td></tr></table></td></tr>'
        )

    # Build the full HTML template using placeholder tokens for Brevo variables
    # We use a regular string (not f-string) for the parts with Brevo variables
    # and .replace() to swap in the real content

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>CodeMyPixel Research Report</title>
<style>
  /* Mobile-responsive styles */
  @media only screen and (max-width: 620px) {
    .email-container { width: 100% !important; border-radius: 0 !important; }
    .email-padding { padding: 24px 20px !important; }
    .email-padding-tight { padding: 20px 20px !important; }
    .hero-padding { padding: 32px 20px 24px 20px !important; }
    .stat-card { width: 100% !important; display: block !important; padding: 0 0 10px 0 !important; }
    .stat-card table { width: 100% !important; }
    .cta-button { width: 100% !important; box-sizing: border-box !important; text-align: center !important; }
    .footer-text { font-size: 10px !important; }
    h1 { font-size: 20px !important; }
    h2 { font-size: 16px !important; }
    .body-text { font-size: 14px !important; line-height: 1.7 !important; }
    .pdf-box { padding: 18px 16px !important; }
    .badge-circle { width: 28px !important; height: 28px !important; line-height: 28px !important; font-size: 12px !important; }
  }
  @media only screen and (max-width: 480px) {
    .stat-card { padding: 0 0 8px 0 !important; }
    .stat-card p:first-child { font-size: 22px !important; }
    .email-padding { padding: 20px 16px !important; }
    .hero-padding { padding: 28px 16px 20px 16px !important; }
  }
</style>
</head>
<body style="margin:0;padding:0;background-color:#eef2f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">

  <!-- Preheader (hidden preview text) -->
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
    We researched the __CAT_NAME__ market and found gaps that companies like yours are facing right now. 2-minute read + 4-page report inside.
  </div>

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#eef2f6;padding:28px 12px;">
    <tr>
      <td align="center">

        <!-- Main card -->
        <table class="email-container" width="620" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(15,23,42,0.08);max-width:620px;">

          <!-- Hero header with gradient -->
          <tr>
            <td class="hero-padding" style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#2563eb 100%);padding:40px 40px 32px 40px;" align="center">
              <img src="__FOUNDER_IMG__" alt="Johirul Hoq Akash" width="88" height="88"
                style="border-radius:50%;border:3px solid rgba(255,255,255,0.25);object-fit:cover;display:block;margin-bottom:14px;" />
              <p style="margin:0;color:#94a3b8;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">CodeMyPixel Research</p>
              <p style="margin:6px 0 0 0;color:#f8fafc;font-size:18px;font-weight:600;">Johirul Hoq Akash &middot; Founder</p>
            </td>
          </tr>

          <!-- Greeting + hook -->
          <tr>
            <td class="email-padding" style="padding:36px 40px 0 40px;">
              <h1 style="margin:0 0 14px 0;color:#0f172a;font-size:24px;font-weight:800;letter-spacing:-0.5px;line-height:1.3;">
                Hi __VAR_FIRSTNAME__,
              </h1>
              <p class="body-text" style="margin:0 0 20px 0;color:#334155;font-size:15px;line-height:1.75;">
                __HOOK__
              </p>
            </td>
          </tr>

          <!-- Stat cards row -->
          <tr>
            <td class="email-padding" style="padding:0 40px 28px 40px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>__STATS_HTML__</tr>
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div>
            </td>
          </tr>

          <!-- Report section -->
          <tr>
            <td class="email-padding" style="padding:28px 40px 8px 40px;">
              <p style="margin:0 0 6px 0;color:#2563eb;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;">The Report</p>
              <h2 style="margin:0 0 8px 0;color:#0f172a;font-size:18px;font-weight:700;line-height:1.4;">__REPORT_TITLE__</h2>
              <p style="margin:0 0 20px 0;color:#64748b;font-size:13px;font-style:italic;">__REPORT_SUBTITLE__</p>
            </td>
          </tr>

          <!-- Summary points -->
          <tr>
            <td class="email-padding" style="padding:0 40px 24px 40px;">
              <table width="100%" cellpadding="0" cellspacing="0">__SUMMARY_HTML__</table>
            </td>
          </tr>

          <!-- PDF link box -->
          <tr>
            <td class="email-padding" style="padding:0 40px 28px 40px;">
              <table class="pdf-box" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border:1px solid #bae6fd;border-radius:12px;">
                <tr>
                  <td class="pdf-box" style="padding:22px 24px;">
                    <p style="margin:0 0 4px 0;color:#0c4a6e;font-size:14px;font-weight:700;">&#128206; Read the full 4-page report</p>
                    <p style="margin:0 0 14px 0;color:#0369a1;font-size:12px;line-height:1.5;">Open the PDF to see the complete data, sources, and real-world impact numbers for the __CAT_NAME__ sector.</p>
                    <a href="__PDF_LINK__" style="display:inline-block;padding:11px 26px;background-color:#2563eb;color:#ffffff;text-decoration:none;font-size:13px;font-weight:600;border-radius:8px;">Open Report PDF &rarr;</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Personal note -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div>
            </td>
          </tr>
          <tr>
            <td class="email-padding" style="padding:24px 40px 8px 40px;">
              <p class="body-text" style="margin:0 0 12px 0;color:#334155;font-size:15px;line-height:1.75;">
                I know you're busy at __VAR_COMPANY__, so I'll keep this short &mdash; just 2 minutes.
              </p>
              <p class="body-text" style="margin:0 0 12px 0;color:#334155;font-size:15px;line-height:1.75;">
                I'm <strong style="color:#0f172a;">Johirul Hoq Akash</strong>, founder of <strong style="color:#0f172a;">CodeMyPixel</strong>.
                We're an automation developer team that builds custom AI systems plugged directly into your existing workflow &mdash;
                no off-the-shelf guesswork, just solutions built around your business.
              </p>
              <p class="body-text" style="margin:0 0 24px 0;color:#334155;font-size:15px;line-height:1.75;">
                If any of this resonates, I'd love to show you what this could look like for __VAR_COMPANY__. No pressure &mdash; just pick a time that works:
              </p>
            </td>
          </tr>

          <!-- CTA button -->
          <tr>
            <td class="email-padding" style="padding:0 40px 32px 40px;" align="center">
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
                href="__BOOKING_URL__" style="height:54px;v-text-anchor:middle;width:300px;" arcsize="11%"
                strokecolor="#2563eb" fillcolor="#2563eb">
                <w:anchorlock/>
                <center style="color:#ffffff;font-family:sans-serif;font-size:16px;font-weight:bold;">
                  Book Your Preferred Time
                </center>
              </v:roundrect>
              <![endif]-->
              <!--[if !mso]><!-->
              <a href="__BOOKING_URL__" class="cta-button"
                style="display:inline-block;padding:16px 40px;background:linear-gradient(135deg,#2563eb,#7c3fc8);color:#ffffff;
                       text-decoration:none;font-size:16px;font-weight:700;border-radius:12px;
                       box-shadow:0 4px 12px rgba(37,99,235,0.35);max-width:300px;">
                Book Your Preferred Time &rarr;
              </a>
              <!--<![endif]-->
            </td>
          </tr>

          <!-- Signature -->
          <tr>
            <td class="email-padding" style="padding:0 40px 36px 40px;border-top:1px solid #f1f5f9;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding-top:24px;">
                    <p style="margin:0 0 4px 0;color:#64748b;font-size:14px;">Best regards,</p>
                    <p style="margin:0 0 2px 0;color:#0f172a;font-size:15px;font-weight:700;">Johirul Hoq Akash</p>
                    <p style="margin:0 0 2px 0;color:#64748b;font-size:13px;">Founder, CodeMyPixel</p>
                    <p style="margin:0;color:#64748b;font-size:13px;">
                      <a href="__BOOKING_URL__" style="color:#2563eb;text-decoration:none;font-weight:600;">cal.com/team-cmp-tk2uvf/from-website</a>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>

        <!-- Footer -->
        <table class="email-container" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;">
          <tr>
            <td align="center" style="padding:20px 40px;">
              <p class="footer-text" style="margin:0;color:#94a3b8;font-size:11px;line-height:1.6;">
                CodeMyPixel &middot; AI Automation Systems for Growing Businesses<br>
                This email was sent to you because we believe our research is relevant to __VAR_COMPANY__.<br>
                You can read the full report <a href="__PDF_LINK__" style="color:#94a3b8;text-decoration:underline;">here</a>.
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""

    # Replace all placeholders with real values
    # Brevo variables use {{ params.NAME }} format (with spaces around params.X)
    replacements = {
        "__VAR_FIRSTNAME__": "{{ params.FIRSTNAME }}",
        "__VAR_COMPANY__": "{{ params.COMPANY }}",
        "__FOUNDER_IMG__": FOUNDER_IMAGE_URL,
        "__BOOKING_URL__": BOOKING_URL,
        "__PDF_LINK__": pdf_link,
        "__CAT_NAME__": cat_name,
        "__HOOK__": hook,
        "__STATS_HTML__": stats_html,
        "__SUMMARY_HTML__": summary_html,
        "__REPORT_TITLE__": report_title,
        "__REPORT_SUBTITLE__": report_subtitle,
    }
    for key, value in replacements.items():
        html = html.replace(key, value)

    return html


def update_template(api_key, template_id, sender_email, sender_name, template_name, subject, html_content):
    headers = {"accept": "application/json", "content-type": "application/json", "api-key": api_key}
    body = {"sender": {"name": sender_name, "email": sender_email}, "templateName": template_name, "htmlContent": html_content, "subject": subject, "isActive": True}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/smtp/templates/{template_id}", data=data, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  Updated template '{template_name}' (ID: {template_id})")
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"  ERROR updating template {template_id}: {e.code} {err}")
        return False
    except Exception as e:
        print(f"  ERROR updating template {template_id}: {e}")
        return False


def create_template(api_key, sender_email, sender_name, template_name, subject, html_content):
    headers = {"accept": "application/json", "content-type": "application/json", "api-key": api_key}
    body = {"sender": {"name": sender_name, "email": sender_email}, "templateName": template_name, "htmlContent": html_content, "subject": subject, "isActive": True}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/smtp/templates", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            template_id = result.get("id")
            print(f"  Created template '{template_name}' -> ID: {template_id}")
            return template_id
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"  ERROR creating template '{template_name}': {e.code} {err}")
        return None
    except Exception as e:
        print(f"  ERROR creating template '{template_name}': {e}")
        return None


def main():
    print("=== Creating/Updating Brevo email templates ===\n")

    ids_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template_ids.json")
    if os.path.exists(ids_path):
        with open(ids_path) as f:
            template_ids = json.load(f)
    else:
        template_ids = {}

    for i, acct in enumerate(ACCOUNTS, 1):
        api_key = os.environ.get(acct["env"])
        if not api_key:
            print(f"Account {i}: SKIP - {acct['env']} not set")
            continue

        print(f"Account {i} ({acct['env']}):")
        print(f"  Category: {acct['category']}")
        print(f"  Sender: {acct['sender_name']} <{acct['sender_email']}>")
        print(f"  Template: {acct['template_name']}")

        html = build_template_html(acct["category"])

        # Verify Brevo variables are present
        if "{{ params.FIRSTNAME }}" in html:
            print("  ✓ Brevo variable {{ params.FIRSTNAME }} found in template")
        else:
            print("  ✗ WARNING: {{ params.FIRSTNAME }} NOT found!")

        if "{{ params.COMPANY }}" in html:
            print("  ✓ Brevo variable {{ params.COMPANY }} found in template")
        else:
            print("  ✗ WARNING: {{ params.COMPANY }} NOT found!")

        key = f"account_{i}"
        existing_id = template_ids.get(key, {}).get("template_id")

        if existing_id:
            print(f"  Existing template found (ID: {existing_id}), updating...")
            success = update_template(api_key, existing_id, acct["sender_email"], acct["sender_name"], acct["template_name"], acct["subject"], html)
            if success:
                template_ids[key] = {"template_id": existing_id, "category": acct["category"], "account_label": str(i), "sender_email": acct["sender_email"], "sender_name": acct["sender_name"]}
        else:
            print(f"  No existing template, creating new...")
            template_id = create_template(api_key, acct["sender_email"], acct["sender_name"], acct["template_name"], acct["subject"], html)
            if template_id:
                template_ids[key] = {"template_id": template_id, "category": acct["category"], "account_label": str(i), "sender_email": acct["sender_email"], "sender_name": acct["sender_name"]}
        print()

    with open(ids_path, "w") as f:
        json.dump(template_ids, f, indent=2)

    print(f"Template IDs saved to template_ids.json:")
    print(json.dumps(template_ids, indent=2))
    print("\n=== Done! Templates updated with fixed variables + mobile responsive design. ===")


if __name__ == "__main__":
    main()
