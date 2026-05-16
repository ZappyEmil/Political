# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord by webhook.

## What it does

- Fetches open Norwegian politics and news RSS feeds.
- Uses RSS metadata only: title, source, date, summary/description, and link.
- Scores articles with deterministic weighted political relevance rules.
- Filters weak policy-angle stories and obvious non-policy matches.
- Groups related stories into policy themes before creating the Discord brief.
- Posts 4-6 thematic brief points instead of a plain ranked article list.
- Keeps links available inside each theme without making the main message link-heavy.
- Prints debugging details for fetched counts, exclusions, reasons, and final scores.

## Project layout

```txt
briefing.py                    Main RSS scoring, theme grouping, and Discord webhook script
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

## Webhook output

The briefing uses one Discord embed with thematic points. Articles are still selected by rule-based scoring, but related stories are grouped before ranking so the brief reads more like an analytical morning note.

Example embed:

```txt
Title: Politisk morgenbrief - 2026-05-16
Description: Tematisk morgenbrief fra åpne RSS-kilder, gruppert og valgt med regelbasert scoring.

Field: Kort vurdering
Sakene samles i 5 tydelige temaer fremfor enkeltoppslag.

Field: 1. Budsjett/økonomi (3 saker)
Kilder: E24, NRK, Aftenposten
Tidsstempel: 2026-05-16 08:03 CEST
Kategori: Budsjett/økonomi
Analyse: Kort analytisk framing basert på RSS-sammendrag, eller forsiktig framing fra tittel og kilde.
Relatert: NRK: Regjeringen legger frem nytt forslag; E24: Budsjettgrep skaper reaksjoner
Lenker: NRK: Åpne saken | E24: Åpne saken

Field: RSS-notat
Merk: Kort sammendrag mangler i RSS for 2 saker; disse er forsiktig rammet inn fra tittel og kilde.
```

Output safety:

- The webhook URL is validated and never printed.
- The bot does not scrape article pages; it only uses RSS metadata.
- Missing summaries are not repeated per item.
- Article and theme text is truncated before it is added to Discord fields.
- The embed is trimmed if needed to stay below Discord limits.
- 429 and 5xx Discord responses retry with backoff.
- Failed Discord responses log status and a short body for debugging.

## GitHub Actions

The workflow runs automatically every day at `06:00 UTC` via GitHub Actions. That is normally `08:00` in Norway during summer time and `07:00` during winter time. It can also be triggered manually from the Actions tab.

## Source mix

The bot fetches up to 30 candidates per feed, scores them, then keeps only the strongest articles within each source quota before doing the final ranking. `MAX_ARTICLES` is set to 24 for the internal ranked pool, while the Discord post shows 4-6 thematic brief points to keep the briefing readable.

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
