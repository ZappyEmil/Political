import requests
import feedparser
import os

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

feeds = [
    "https://www.regjeringen.no/no/aktuelt/rss/id1330/",
    "https://www.stortinget.no/no/Stottemeny/rss/"
]

articles = []

for feed_url in feeds:
    feed = feedparser.parse(feed_url)
    
    for entry in feed.entries[:5]:
        articles.append(f"- {entry.title}")

news_text = "\n".join(articles)

prompt = f"""
Summarize these Norwegian political developments briefly:

{news_text}

Format:

Top developments

Why they matter

Keep concise
"""


response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "inclusionai/ring-2.6-1t:free",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
)

summary = response.json()["choices"][0]["message"]["content"]

requests.post(
    DISCORD_WEBHOOK_URL,
    json={
        "content": f"🇳🇴 Morning Political Briefing\n\n{summary}"
    }
)