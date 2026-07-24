"""
One-time script: Creates/updates email templates in all 5 Brevo accounts via API.

Templates are now plain, human-written emails — no images, no links, no styling.
Just a personal note from Johirul asking if they'd like to hear an idea.

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

ACCOUNTS = [
    {"env": "BREVO_API_KEY", "sender_email": "admin@codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "healthcare", "template_name": "Healthcare & Wellness Outreach", "subject": "An idea for {{ params.COMPANY }}"},
    {"env": "BREVO_API_KEY_2", "sender_email": "sabbir@team.codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "building_materials", "template_name": "Building Materials Outreach", "subject": "An idea for {{ params.COMPANY }}"},
    {"env": "BREVO_API_KEY_3", "sender_email": "akash@codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "building_materials", "template_name": "Building Materials Outreach", "subject": "An idea for {{ params.COMPANY }}"},
    {"env": "BREVO_API_KEY_4", "sender_email": "neel@connect.codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "fashion", "template_name": "Apparel & Fashion Outreach", "subject": "An idea for {{ params.COMPANY }}"},
    {"env": "BREVO_API_KEY_5", "sender_email": "pravas@app.codemypixel.com", "sender_name": "Johirul Hoq Akash", "category": "healthcare", "template_name": "Healthcare & Wellness Outreach", "subject": "An idea for {{ params.COMPANY }}"},
]

CATEGORY_NAMES = {
    "healthcare": "Healthcare & Wellness",
    "building_materials": "Building Materials",
    "fashion": "Apparel & Fashion",
}


def build_template_html(category):
    cat_name = CATEGORY_NAMES.get(category, category)

    html = (
        f"Hi {{{{ params.FIRSTNAME }}}},<br><br>"
        f"Hope you're doing well.<br><br>"
        f"I'm Johirul Hoq Akash. I came across {{{{ params.COMPANY }}}} recently and spent some time looking at what you do in the {cat_name} space.<br><br>"
        f"While going through your website and services, an idea came to mind that I honestly think could help your business. I'm not trying to sell you anything in this email. I'm just genuinely curious to know what you think about the idea.<br><br>"
        f"If this email ended up in your promotions or spam folder, I'd really appreciate it if you gave it a quick look. I'm a real person. You can search Johirul Hoq Akash on Google and you'll find me and my company, CodeMyPixel.<br><br>"
        f"If the idea sounds interesting, just reply with \"sure\" and I'll send it over. If it isn't something you're looking for right now, no worries at all. You can simply ignore this email.<br><br>"
        f"Thanks for reading, and I hope you have a great week.<br><br>"
        f"Best,<br><br>"
        f"Johirul Hoq Akash<br>"
        f"Founder, CodeMyPixel"
    )
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
    print("\n=== Done! Templates updated to plain human-written emails. ===")


if __name__ == "__main__":
    main()
