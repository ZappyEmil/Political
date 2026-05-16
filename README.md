# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord by webhook.

## What it does

- Fetches open Norwegian politics and news RSS feeds.
- Uses RSS metadata: title, source, date, summary/description, and link.
- Scores articles with deterministic weighted political relevance rules.
- Filters weak policy-angle stories and obvious non-policy matches.
- Tags articles by policy area, including budget, security, municipalities, health, education, AI/digitalization, climate/energy, and foreign policy.
- Posts a deterministic Discord embed with clickable links for the top stories.
- Prints debugging details for fetched counts, exclusions, reasons, and final scores.

## Project layout

```txt
briefing.py                    Main RSS scoring and Discord webhook script
requirements.txt               Python dependencies
.env.example                   Local environment template with placeholders only
.github/workflows/briefing.yml Daily GitHub Actions schedule
```

## Setup

Required secret:

```txt
DISCORD_WEBHOOK_URL
```

For GitHub Actions, add it under `Settings -> Secrets and variables -> Actions -> New repository secret`.

## Windows PowerShell setup

Run these commands from the repository folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
$env:DISCORD_WEBHOOK_URL = (Get-Content .env | Where-Object { $_ -match '^DISCORD_WEBHOOK_URL=' }) -replace '^DISCORD_WEBHOOK_URL=', ''
python briefing.py
```

For a normal local run after setup:

```powershell
.\.venv\Scripts\Activate.ps1
$env:DISCORD_WEBHOOK_URL = (Get-Content .env | Where-Object { $_ -match '^DISCORD_WEBHOOK_URL=' }) -replace '^DISCORD_WEBHOOK_URL=', ''
python briefing.py
```

Do not commit `.env`. The real Discord webhook URL belongs only in `.env`, GitHub Actions secrets, or your hosting provider's secret manager.

## GitHub Actions

The workflow runs automatically every day at `06:00 UTC` via GitHub Actions. That is normally `08:00` in Norway during summer time and `07:00` during winter time. It can also be triggered manually from the Actions tab.

## Source mix

The bot fetches up to 30 candidates per feed, scores them, then keeps only the strongest articles within each source quota before doing the final ranking. `MAX_ARTICLES` is set to 24 for the internal ranked pool, while the Discord post shows the top 6 stories to keep the briefing readable.

| Feed | Max articles kept |
| --- | ---: |
| E24 Makro og politikk | 4 |
| Khrono | 3 |
| NRK Toppsaker | 4 |
| NRK Siste nytt | 4 |
| Nettavisen Nyheter | 3 |
| Google News: Altinget | 2 |
| Google News: Aftenposten politikk | 2 |
| Google News: VG politikk | 2 |
| Google News: Politiforum | 2 |
| Google News: Kommunal Rapport | 2 |
| Google News: norsk politikk | 2 |
| Google News: Stortinget og regjeringen | 2 |

## Notes

This project uses a Discord webhook only. It is not a full Discord bot: no bot token, no slash commands, and no gateway connection.
