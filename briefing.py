import os
import sys
from urllib.parse import urlparse

import feedparser
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

FEEDS = [
    {
        "name": "NRK Toppsaker",
        "url": "https://www.nrk.no/toppsaker.rss",
    },
    {
        "name": "NRK Siste nytt",
        "url": "https://www.nrk.no/nyheter/siste.rss",
    },
    {
        "name": "E24 Makro og politikk",
        "url": "https://e24.no/rss2/?seksjon=makro-og-politikk",
    },
    {
        "name": "Nettavisen Nyheter",
        "url": "https://www.nettavisen.no/service/rich-rss?tag=nyheter",
    },
]

POLITICAL_KEYWORDS = [
    "ap",
    "arbeiderpartiet",
    "erna",
    "eos",
    "eøs",
    "frp",
    "hoyre",
    "høyre",
    "kommune",
    "minister",
    "parti",
    "politikk",
    "regjering",
    "rodt",
    "rødt",
    "sp",
    "stoltenberg",
    "storting",
    "store",
    "støre",
    "sv",
    "valg",
    "venstre",
]


def require_env(name, value):
    if not value or not value.strip():
        print(f"Missing required environment variable: {name}")
        sys.exit(1)


def get_required_env(name):
    value = os.getenv(name)
    require_env(name, value)
    return value.strip()


def require_discord_webhook_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print(
            "Invalid DISCORD_WEBHOOK_URL: expected a full Discord webhook URL "
            "starting with https://discord.com/api/webhooks/"
        )
        sys.exit(1)

    if parsed.netloc not in ("discord.com", "discordapp.com") or not parsed.path.startswith(
        "/api/webhooks/"
    ):
        print(
            "Invalid DISCORD_WEBHOOK_URL: the secret should look like "
            "https://discord.com/api/webhooks/<webhook_id>/<token>"
        )
        sys.exit(1)


def is_valid_xml_char(char):
    codepoint = ord(char)
    return (
        codepoint in (0x09, 0x0A, 0x0D)
        or 0x20 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def clean_xml_text(text):
    return "".join(char for char in text if is_valid_xml_char(char))


def fetch_feed(feed):
    response = requests.get(
        feed["url"],
        headers={"User-Agent": "PoliticalBriefingBot/1.0"},
        timeout=30,
    )
    response.raise_for_status()

    cleaned_text = clean_xml_text(response.text)
    return feedparser.parse(cleaned_text)


def is_political(entry):
    text = " ".join(
        str(value)
        for value in [
            getattr(entry, "title", ""),
            getattr(entry, "summary", ""),
            getattr(entry, "description", ""),
        ]
    ).lower()
    return any(keyword in text for keyword in POLITICAL_KEYWORDS)


def collect_articles():
    articles = []
    seen = set()

    for feed_config in FEEDS:
        source_name = feed_config["name"]

        try:
            feed = fetch_feed(feed_config)
        except requests.RequestException as exc:
            print(f"Warning: could not fetch {source_name}: {exc}")
            continue

        if feed.bozo:
            print(f"Warning: {source_name} had malformed content: {feed.bozo_exception}")

        if not feed.entries:
            print(f"Warning: no entries found in {source_name}")
            continue

        added_from_source = 0
        for entry in feed.entries[:15]:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            unique_key = link or title

            if unique_key in seen:
                continue

            seen.add(unique_key)
            prefix = "*" if is_political(entry) else "-"
            if link:
                articles.append(f"{prefix} [{source_name}] {title}\n  {link}")
            else:
                articles.append(f"{prefix} [{source_name}] {title}")
            added_from_source += 1

            if len(articles) >= 30:
                break

        print(f"Collected {added_from_source} articles from {source_name}.")

        if len(articles) >= 30:
            break

    return articles


def summarize(news_text, openrouter_api_key):
    prompt = f"""
Summarize these Norwegian news items as a short Norwegian political briefing.

Items marked with * matched political keywords. Prioritize those items, but include other major national developments if they matter politically.

{news_text}

Format:

Toppsaker

Hvorfor det betyr noe

Keep concise.
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {openrouter_api_key}",
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


def post_to_discord(summary, webhook_url):
    content = f"Morning Political Briefing\n\n{summary}"

    # Discord messages have a 2000 character limit.
    if len(content) > 1900:
        content = content[:1897] + "..."

    response = requests.post(
        webhook_url,
        json={"content": content},
        timeout=30,
    )
    response.raise_for_status()


def main():
    openrouter_api_key = get_required_env("OPENROUTER_API_KEY")
    discord_webhook_url = get_required_env("DISCORD_WEBHOOK_URL")
    require_discord_webhook_url(discord_webhook_url)

    articles = collect_articles()
    if not articles:
        print("No articles found in configured feeds.")
        sys.exit(1)

    news_text = "\n".join(articles)
    summary = summarize(news_text, openrouter_api_key)
    post_to_discord(summary, discord_webhook_url)
    print("Briefing posted to Discord.")


if __name__ == "__main__":
    main()
