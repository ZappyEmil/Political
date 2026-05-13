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
        "model": "meta-llama/llama-2-7b-chat:free",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
)

# Check for HTTP errors
response.raise_for_status()
response_data = response.json()

# Check for API errors in response
if "error" in response_data:
    print(f"API Error: {response_data['error']}")
    exit(1)

if "choices" not in response_data:
    print(f"Unexpected response format: {response_data}")
    exit(1)

summary = response_data["choices"][0]["message"]["content"]

requests.post(
    DISCORD_WEBHOOK_URL,
    json={
        "content": f"🇳🇴 Morning Political Briefing\n\n{summary}"
    }
)
