# CodeMyPixel Daily Lead Outreach Automation

Sends 300 cold outreach emails per day, fully automatically, via GitHub Actions.
Rotates through 4 lead categories (one category per day): Construction, Banking,
Accounting & CPA, Automotive. No manual sending required once set up.

## How it works

- `leads/*.csv` — the master lead lists per category (email, first name, company).
- `progress.json` — tracks how far each category has progressed and whose turn it is
  today. Updated and committed back to the repo after every run.
- `send_daily_batch.py` — picks today's category, sends the next 300 un-contacted
  leads via Brevo's transactional email API using the matching Brevo template
  (already built: Construction=7, Banking=6, Accounting=8, Automotive=9), then
  advances the pointer.
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
   - Name: `BREVO_API_KEY`
   - Value: your Brevo API key (v3, transactional email + import permissions)
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
