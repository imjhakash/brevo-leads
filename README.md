# CodeMyPixel Daily Lead Outreach Automation

Sends 1500 cold outreach emails per day, fully automatically, via GitHub Actions.
Uses FIVE Brevo accounts (300/day each). Healthcare and Building Materials get
2 accounts each (600/day), Fashion gets 1 account (300/day). All 3 categories
are sent every day — no rotation needed.

Each email includes a personalized HTML body with the recipient's name and
company, a sector-specific AI Automation Report PDF attachment, the founder's
photo, and a Cal.com booking link.

## How it works

- `leads/*.csv` — the master lead lists per category (email; first name; company).
- `assets/` — PDF reports and founder image used in emails.
- `progress.json` — tracks how far each category has progressed. Updated and
  committed back to the repo after every run.
- `send_daily_batch.py` — sends all 3 categories every day:
  - Account 1 → Healthcare & Wellness (300/day)
  - Account 2 → Building Materials (300/day)
  - Account 3 → Building Materials (300/day, second batch)
  - Account 4 → Apparel & Fashion (300/day)
  - Account 5 → Healthcare & Wellness (300/day, second batch)
  Healthcare gets 600/day total (accounts 1 and 5).
  Building Materials gets 600/day total (accounts 2 and 3).
  Fashion gets 300/day (account 4).
- `.github/workflows/daily-send.yml` — GitHub Actions workflow that runs the script
  every day at 09:00 UTC and commits the updated `progress.json` + logs back to repo.
- `.github/workflows/hourly-stats-update.yml` — Updates Google Sheets dashboard hourly.

## Email content

Each email is sent as inline HTML (no Brevo template needed) with:
- **Subject**: "We researched the [Sector] market and found something interesting"
- **Body**: Personalized greeting with recipient name, mention of their company,
  2-minute promise, founder intro (Johirul Hoq Akash), report summary, and
  booking CTA button linking to https://cal.com/team-cmp-tk2uvf/from-website
- **Attachment**: 4-page AI Automation Report PDF (sector-specific)
- **Founder image**: Displayed in email header
- **Tags**: Each email is tagged with the category name for stats tracking

## One-time setup

1. **Create a GitHub repository** (make it **private** — the CSV files contain real
   email addresses and company names).
2. Push the contents of this folder as the repo root.
3. In the repo, go to **Settings > Secrets and variables > Actions > New repository
   secret**, and add:
   - `BREVO_API_KEY` — Brevo API key for account 1 (Healthcare)
   - `BREVO_API_KEY_2` — Brevo API key for account 2 (Building Materials)
   - `BREVO_API_KEY_3` — Brevo API key for account 3 (Building Materials)
   - `BREVO_API_KEY_4` — Brevo API key for account 4 (Fashion)
   - `BREVO_API_KEY_5` — Brevo API key for account 5 (Healthcare)
   - `SHEET_WEBHOOK_URL` — Google Apps Script web app URL (for stats)
   - `SHEET_AUTH_TOKEN` — Auth token for the sheet webhook
4. Go to the **Actions** tab and enable workflows if prompted.

## Testing it manually

From the Actions tab, open "Daily Lead Outreach" and click **Run workflow** to
trigger an on-demand test run without waiting for the schedule.

## Monitoring

- `progress.json` shows a `history` array with every day's send counts.
- `logs/YYYY-MM-DD.json` records exactly which emails succeeded or failed.
- Check deliverability/bounce/spam trends periodically in Brevo's transactional
  reports.
- Google Sheets dashboard updates hourly with per-account and per-email stats.

## Lead counts

| Category | Leads | Daily volume | Accounts |
|----------|-------|-------------|----------|
| Healthcare & Wellness | ~36,400 | 600/day | 1, 5 |
| Building Materials | ~24,000 | 600/day | 2, 3 |
| Apparel & Fashion | ~36,600 | 300/day | 4 |
| **Total** | **~97,000** | **1,500/day** | **5** |

## Running out of leads

Each category will naturally run out once its pointer reaches the end of its CSV
file. The script detects this and skips to the next category for that day rather
than erroring out. Re-run the categorization/export process to add fresh leads
to a CSV file, or append new rows to the relevant `leads/*.csv` file.
