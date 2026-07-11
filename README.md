# CodeMyPixel Daily Lead Outreach Automation

Sends 1500 cold outreach emails per day, fully automatically, via GitHub Actions.
Uses FIVE Brevo accounts (300/day each). Construction gets 2 accounts (600/day),
the other 3 categories get 1 account each (300/day). All 4 categories are sent
every day — no rotation needed.

## How it works

- `leads/*.csv` — the master lead lists per category (email, first name, company).
- `progress.json` — tracks how far each category has progressed. Updated and
  committed back to the repo after every run.
- `send_daily_batch.py` — sends all 4 categories every day:
  - Account 1 → Construction (300/day, template 7, sender: admin@codemypixel.com)
  - Account 2 → Banking (300/day, template 23, sender: sabbir@team.codemypixel.com)
  - Account 3 → Accounting (300/day, template 6, sender: akash@codemypixel.com)
  - Account 4 → Automotive (300/day, template 4, sender: neel@connect.codemypixel.com)
  - Account 5 → Construction (300/day, template 2, sender: pravas@app.codemypixel.com)
  Construction gets 600/day total (accounts 1 and 5 send consecutive slices).
- `.github/workflows/daily-send.yml` — GitHub Actions workflow that runs the script
  every day at 09:00 UTC and commits the updated `progress.json` + logs back to repo.
- `.github/workflows/hourly-stats-update.yml` — Updates Google Sheets dashboard hourly.

## One-time setup

1. **Create a GitHub repository** (make it **private** — the CSV files contain real
   email addresses and company names).
2. Push the contents of this `automation/` folder as the repo root:
   ```
   cd automation
   git init
   git add .
   git commit -m "Initial setup"
   git branch -M main
   git remote add origin <your-repo-url>
   git push -u origin main
   ```
3. In the repo, go to **Settings > Secrets and variables > Actions > New repository
   secret**, and add:
   - Name: `BREVO_API_KEY` — Value: Brevo API key for account 1 (v3, transactional)
   - Name: `BREVO_API_KEY_2` — Value: Brevo API key for account 2 (v3, transactional)
   - Name: `BREVO_API_KEY_3` — Value: Brevo API key for account 3 (v3, transactional)
   - Name: `BREVO_API_KEY_4` — Value: Brevo API key for account 4 (v3, transactional)
   - Name: `BREVO_API_KEY_5` — Value: Brevo API key for account 5 (v3, transactional)
4. Go to the **Actions** tab and enable workflows if prompted. That's it — from
   here it runs automatically every day, no further action needed.

## Testing it manually

From the Actions tab, open "Daily Lead Outreach" and click **Run workflow** to
trigger an on-demand test run without waiting for the schedule.

## Monitoring

- `progress.json` shows a `history` array with every day's send counts.
- `logs/YYYY-MM-DD_<category>.json` records exactly which emails succeeded or
  failed on any given day.
- Check deliverability/bounce/spam trends periodically in Brevo's transactional
  reports.

## Adjusting the daily volume or rotation

- Change `DAILY_BATCH_SIZE` in `send_daily_batch.py` to send more/less than 300/day.
- Change the order or set of categories in the `CATEGORIES` list to adjust rotation.
- Consider starting with a lower `DAILY_BATCH_SIZE` (e.g. 50-100) for the first
  1-2 weeks to warm up sender reputation before ramping to the full 300/day.

## Running out of leads

Each category will naturally run out once its pointer reaches the end of its CSV
file. The script detects this and skips to the next category for that day rather
than erroring out. Re-run the categorization/export process to add fresh leads
to a CSV file, or append new rows to the relevant `leads/*.csv` file.
