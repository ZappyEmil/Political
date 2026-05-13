# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add secrets to GitHub repo:
   - `OPENROUTER_API_KEY`
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs automatically every day at 06:00 UTC via GitHub Actions, and can also be triggered manually from the Actions tab.

## Features

- Fetches open Norwegian politics and news RSS feeds
- Stores title, source, published date, summary, and link for each article
- Deduplicates by link and similar title
- Uses source quotas so one feed cannot dominate the whole briefing
- Strictly filters for politics-related items before summarizing
- Sends structured JSON article data to the model to reduce hallucinations
- Prompts the model to use only provided article data
- Writes concise Bokmal analysis with a slightly cynical political tone
- Posts the briefing as a Discord embed with clickable links
