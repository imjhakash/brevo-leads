# CodeMyPixel Daily Lead Outreach Automation

Sends 900 cold outreach emails per day, fully automatically, via GitHub Actions.
Uses THREE Brevo accounts (300/day each) to send THREE categories per day:
Account 1 sends 300 from one category, Account 2 sends 300 from the next,
Account 3 sends 300 from the third. Rotates through 4 lead categories:
Construction, Banking, Accounting & CPA, Automotive. No manual sending
required once set up.

## How it works

- `leads/*.csv` — the master lead lists per category (email, first name, company).
- `progress.json` — tracks how far each category has progressed and whose turn it is
  today. Updated and committed back to the repo after every run.
- `send_daily_batch.py` — picks THREE consecutive categories each day.
  Account 1 sends 300 leads from category A (templates: Construction=7,
  Banking=6, Accounting=8, Automotive=9). Account 2 sends 300 leads from
  category B (templates: Construction=20, Banking=23, Accounting=21,
  Automotive=22). Account 3 sends 300 leads from category C (templates:
  Construction=8, Banking=5, Accounting=6, Automotive=7). Advances the
  cycle by 3 each day.
- `.github/workflows/daily-send.yml` — GitHub Actions workflow that runs the script
  every day at 09:00 UTC (edit the cron line to change the time) and commits the
  updated `progress.json` + logs back to the repo.

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
