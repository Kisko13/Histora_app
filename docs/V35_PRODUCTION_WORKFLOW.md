# Histora V35 — Production Workflow Dashboard

V35 moves the app from render-engine testing to episode-production workflow.

## Adds

- V35 production dashboard
- Review queue
- Open Episode button
- Real readiness statistics based on:
  - approved voices
  - approved visual slots
  - approved scene music
  - rendered V34 block MP4s
  - final episode MP4
- HTML dashboard and CSV health exports
- HTML/CSV review queue
- Cleaner toolbar focused on current workflow

## Test order

1. Run `run_studio_v24.bat`
2. Click `Health`
3. Click `Review Queue`
4. Click `Open Episode`

## Expected files

- `production/v35_dashboard_latest.json`
- `exports/v35_dashboard/dashboard.html`
- `exports/v35_dashboard/block_health.csv`
- `exports/v35_dashboard/review_queue.html`
- `exports/v35_dashboard/review_queue.csv`

V35 does not change the V34 renderer. V34 already produced the final MP4. V35 makes the production state visible and actionable.
