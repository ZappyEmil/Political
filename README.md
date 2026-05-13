# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add secrets to GitHub repo:
   - `OPENROUTER_API_KEY`
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs daily at 6 AM UTC (or trigger manually via Actions)

## Features

- Fetches open Norwegian news RSS feeds
- Strictly filters for politics-related items before summarizing
- Summarizes up to five political developments with more context
- Posts the briefing as a Discord embed with source links
- Runs automatically every day
