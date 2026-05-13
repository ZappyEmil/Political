# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add secrets to GitHub repo:
   - `OPENROUTER_API_KEY`
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs daily at 6 AM UTC (or trigger manually via Actions)

## Features

- Fetches Norwegian government and parliament news feeds
- Summarizes developments using AI
- Posts to Discord webhook
- Runs automatically every day
