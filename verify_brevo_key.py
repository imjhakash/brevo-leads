"""
Verify Brevo API key is valid by checking account info.
Does not send any email - just tests authentication.

Environment variables required:
  BREVO_API_KEY - Brevo account 1
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE_URL = "https://api.brevo.com/v3"

API_KEY = os.environ.get("BREVO_API_KEY")
if not API_KEY:
    print("ERROR: BREVO_API_KEY not set", file=sys.stderr)
    sys.exit(1)

print(f"=== Verifying Brevo API key ===")
print(f"  API Key: {API_KEY[:10]}...{API_KEY[-4:]}")

# Try to get account info
headers = {
    "accept": "application/json",
    "api-key": API_KEY,
}

# Try multiple endpoints to verify the key works
endpoints = [
    ("Account info", "/account"),
    ("SMTP templates", "/smtp/templates"),
    ("Campaigns", "/emailCampaigns"),
]

for name, path in endpoints:
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}", headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            print(f"\n  ✓ {name}: API key is valid")
            print(f"    Response keys: {list(data.keys()) if isinstance(data, dict) else 'non-dict response'}")
            if name == "Account info" and isinstance(data, dict):
                print(f"    Account email: {data.get('email', 'N/A')}")
                print(f"    Account name: {data.get('companyName', 'N/A')}")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        print(f"\n  ✗ {name}: {e.code} {err}", file=sys.stderr)
        if e.code == 401:
            print(f"    API key is INVALID or EXPIRED", file=sys.stderr)
        elif e.code == 403:
            print(f"    API key lacks permissions for this endpoint", file=sys.stderr)
    except Exception as e:
        print(f"\n  ✗ {name}: {e}", file=sys.stderr)

print(f"\n=== Verification complete ===")
