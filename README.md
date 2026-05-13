# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add this secret to the GitHub repo:
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs automatically every day at 06:00 UTC via GitHub Actions, and can also be triggered manually from the Actions tab.

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
- Avoids LLM-generated prose to keep the briefing grounded and non-hallucinated
