"""
One-time script: Creates email templates in all 5 Brevo accounts via API.

Run this once via GitHub Actions (workflow_dispatch) to create the templates.
The template IDs will be saved to template_ids.json and committed back to the repo.

After running this, send_daily_batch.py will automatically use the template IDs.

Sender emails (from original setup):
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

# Account configs: (env var name, sender email, sender name, category, template name, subject)
ACCOUNTS = [
    {
        "env": "BREVO_API_KEY",
        "sender_email": "admin@codemypixel.com",
        "sender_name": "Johirul Hoq Akash",
        "category": "healthcare",
        "template_name": "Healthcare & Wellness Outreach",
        "subject": "We researched the Healthcare & Wellness market and found something interesting",
    },
    {
        "env": "BREVO_API_KEY_2",
        "sender_email": "sabbir@team.codemypixel.com",
        "sender_name": "Johirul Hoq Akash",
        "category": "building_materials",
        "template_name": "Building Materials Outreach",
        "subject": "We researched the Building Materials market and found something interesting",
    },
    {
        "env": "BREVO_API_KEY_3",
        "sender_email": "akash@codemypixel.com",
        "sender_name": "Johirul Hoq Akash",
        "category": "building_materials",
        "template_name": "Building Materials Outreach",
        "subject": "We researched the Building Materials market and found something interesting",
    },
    {
        "env": "BREVO_API_KEY_4",
        "sender_email": "neel@connect.codemypixel.com",
        "sender_name": "Johirul Hoq Akash",
        "category": "fashion",
        "template_name": "Apparel & Fashion Outreach",
        "subject": "We researched the Apparel & Fashion market and found something interesting",
    },
    {
        "env": "BREVO_API_KEY_5",
        "sender_email": "pravas@app.codemypixel.com",
        "sender_name": "Johirul Hoq Akash",
        "category": "healthcare",
        "template_name": "Healthcare & Wellness Outreach",
        "subject": "We researched the Healthcare & Wellness market and found something interesting",
    },
]

CATEGORY_NAMES = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}


def build_template_html(category):
    """Build HTML email template using Brevo variables {{params.FIRSTNAME}} and {{params.COMPANY}}."""
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
                Hi {{{{params.FIRSTNAME}}}},
              </h2>
              <p style="margin:0 0 16px 0;color:#475569;font-size:15px;line-height:1.7;">
                I know you're busy, so I'll keep this short &mdash; just 2 minutes, I promise.
              </p>
              <p style="margin:0 0 16px 0;color:#475569;font-size:15px;line-height:1.7;">
                I'm <strong style="color:#0f172a;">Johirul Hoq Akash</strong>, founder of
                <strong style="color:#0f172a;">CodeMyPixel</strong>. My team and I researched the
                <strong style="color:#2563eb;">{cat_name}</strong> market and found some interesting gaps
                that companies like <strong style="color:#0f172a;">{{{{params.COMPANY}}}}</strong> are likely facing right now.
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
                This email was sent to you because we believe our research is relevant to {{{{params.COMPANY}}}}.
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


def create_template(api_key, sender_email, sender_name, template_name, subject, html_content):
    """Create a template in Brevo via API. Returns the template ID."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }
    body = {
        "sender": {"name": sender_name, "email": sender_email},
        "templateName": template_name,
        "htmlContent": html_content,
        "subject": subject,
        "isActive": True,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/smtp/templates", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            template_id = result.get("id")
            print(f"  Created template '{template_name}' → ID: {template_id}")
            return template_id
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"  ERROR creating template '{template_name}': {e.code} {err}")
        return None
    except Exception as e:
        print(f"  ERROR creating template '{template_name}': {e}")
        return None


def main():
    print("=== Creating Brevo email templates ===\n")

    # Load existing template_ids.json if it exists
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
        template_id = create_template(
            api_key,
            acct["sender_email"],
            acct["sender_name"],
            acct["template_name"],
            acct["subject"],
            html,
        )

        if template_id:
            key = f"account_{i}"
            template_ids[key] = {
                "template_id": template_id,
                "category": acct["category"],
                "account_label": str(i),
                "sender_email": acct["sender_email"],
                "sender_name": acct["sender_name"],
            }
        print()

    # Save template IDs
    with open(ids_path, "w") as f:
        json.dump(template_ids, f, indent=2)

    print(f"Template IDs saved to template_ids.json:")
    print(json.dumps(template_ids, indent=2))
    print("\n=== Done! You can now run the daily send workflow. ===")


if __name__ == "__main__":
    main()
