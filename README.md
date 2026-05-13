# Political Briefing Bot

Automated daily briefings on Norwegian political developments, delivered to Discord.

## Setup

1. Add secrets to GitHub repo:
   - `OPENROUTER_API_KEY`
   - `DISCORD_WEBHOOK_URL`

2. The workflow runs automatically every day at 06:00 UTC via GitHub Actions, and can also be triggered manually from the Actions tab.

## Features

- Fetches open Norwegian politics and news RSS feeds
- Uses source quotas so one feed cannot dominate the whole briefing
- Strictly filters for politics-related items before summarizing
- Writes for a politically knowledgeable reader, with conflict lines and what to watch next
- Summarizes up to five political developments with more context
- Posts the briefing as a Discord embed with source links
