import os
import sys

import feedparser
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

FEEDS = [
    "https://www.regjeringen.no/no/aktuelt/rss/id1330/",
    "https://www.stortinget.no/no/Stottemeny/rss/",
]


def require_env(name, value):
    if not value:
        print(f"Missing required environment variable: {name}")
        sys.exit(1)


def collect_articles():
    articles = []

    for feed_url in FEEDS:
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            print(f"Warning: could not parse feed {feed_url}: {feed.bozo_exception}")
            continue

        for entry in feed.entries[:5]:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            if link:
                articles.append(f"- {title}\n  {link}")
            else:
                articles.append(f"- {title}")

    return articles


def summarize(news_text):
    prompt = f"""
Summarize these Norwegian political developments briefly in Norwegian:

{news_text}

Format:

Toppsaker

Hvorfor det betyr noe

Keep concise.
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openrouter/free",
            "messages": [
                {"role": "user", "content": prompt},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    response_data = response.json()

    if "error" in response_data:
        raise RuntimeError(f"OpenRouter API error: {response_data['error']}")

    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response: {response_data}") from exc


def post_to_discord(summary):
    content = f"Morning Political Briefing\n\n{summary}"

    # Discord messages have a 2000 character limit.
    if len(content) > 1900:
        content = content[:1897] + "..."

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": content},
        timeout=30,
    )
    response.raise_for_status()


def main():
    require_env("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    require_env("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK_URL)

    articles = collect_articles()
    if not articles:
        print("No articles found in configured feeds.")
        sys.exit(1)

    news_text = "\n".join(articles)
    summary = summarize(news_text)
    post_to_discord(summary)
    print("Briefing posted to Discord.")


if __name__ == "__main__":
    main()
