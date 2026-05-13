# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add this secret to the GitHub repo:
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs automatically every day at 06:00 UTC via GitHub Actions, and can also be triggered manually from the Actions tab.

## Features

- Fetches open Norwegian politics and news RSS feeds
- Stores title, source, published date, summary, link, and inferred political topics for each article
- Deduplicates by link and similar title
- Uses source quotas so one feed cannot dominate the whole briefing
- Filters for politics-related items before posting
- Ranks articles by political relevance signals
- Posts a deterministic Discord embed with clickable links for each item
- Avoids AI-generated prose by default to keep the briefing readable and grounded in source data
