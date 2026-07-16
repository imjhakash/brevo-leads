"""
Check how many emails were sent today from Brevo Account 1.
This will tell us if the daily limit (300) was already reached.

Environment variables required:
  BREVO_API_KEY - Brevo account 1
"""
import json
import os
import sys
import urllib.request
from datetime import date

BASE_URL = "https://api.brevo.com/v3"

API_KEY = os.environ.get("BREVO_API_KEY")
if not API_KEY:
    print("ERROR: BREVO_API_KEY not set", file=sys.stderr)
    sys.exit(1)

print(f"=== Checking Brevo daily quota ===")
print(f"  Account: admin@codemypixel.com")
print(f"  API Key: {API_KEY[:10]}...{API_KEY[-4:]}")

today_str = date.today().strftime("%Y-%m-%d")
print(f"  Date: {today_str}")

headers = {
    "accept": "application/json",
    "api-key": API_KEY,
}

# Get aggregated stats for today
url = f"{BASE_URL}/smtp/statistics/aggregatedReport?startDate={today_str}&endDate={today_str}"
req = urllib.request.Request(url, headers=headers, method="GET")

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        requests = data.get("requests", 0)
        delivered = data.get("delivered", 0)
        bounces = data.get("hardBounces", 0) + data.get("softBounces", 0)
        
        print(f"\n  Today's stats:")
        print(f"    Requests sent: {requests}")
        print(f"    Delivered: {delivered}")
        print(f"    Bounces: {bounces}")
        print(f"    Daily limit: 300")
        print(f"    Remaining: {300 - requests}")
        
        if requests >= 300:
            print(f"\n  ⚠️  DAILY LIMIT REACHED! Cannot send more emails today.")
        elif requests > 250:
            print(f"\n  ⚠️  Nearly at daily limit ({requests}/300).")
        else:
            print(f"\n  ✓ Daily quota available ({300 - requests} remaining).")
            
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", errors="ignore")
    print(f"\n  ✗ Failed to get stats: {e.code} {err}", file=sys.stderr)
except Exception as e:
    print(f"\n  ✗ Failed to get stats: {e}", file=sys.stderr)
