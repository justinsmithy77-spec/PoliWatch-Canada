name: Daily Bill Updater

on:
  schedule:
    - cron: '0 12 * * *' # Runs daily at 6:00 AM Mountain Time
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-bills:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies and Playwright browser
        run: |
          python -m pip install --upgrade pip
          pip install requests beautifulsoup4 pypdf playwright
          playwright install --with-deps chromium

      - name: Run bill updater script
        run: python scripts/update_bills.py

      - name: Commit and push updated bills
        run: |
          git config --local user.name "PoliWatch Bot"
          git config --local user.email "bot@polimonitor.ca"
          git add data/all_bills.json
          git diff --staged --quiet || git commit -m "Auto-update daily Canadian bills"
          git push
