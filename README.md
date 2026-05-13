# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add this secret to the GitHub repo:
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs automatically every day at 06:00 UTC via GitHub Actions. That is normally 08:00 in Norway during summer time and 07:00 during winter time. It can also be triggered manually from the Actions tab.

## Features

- Fetches open Norwegian politics and news RSS feeds
- Uses only RSS metadata: title, source, date, summary/description, and link
- Scores articles with deterministic weighted political relevance rules
- Applies negative keyword penalties for sport, celebrities, weather, lifestyle, campus trivia, and entertainment
- Filters out weak policy-angle stories before posting
- Boosts stronger political sources and reduces generic/local/clickbait sources
- Tags articles by policy area, including budget, security, municipalities, health, education, AI/digitalization, climate/energy, and foreign policy
- Generates short rule-based observations from counts and source patterns
- Posts a deterministic Discord embed with clickable links for each item
- Prints debugging details for fetched counts, exclusions, reasons, and final scores
- Keeps the briefing grounded in RSS metadata and deterministic rules

## Source Mix

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
