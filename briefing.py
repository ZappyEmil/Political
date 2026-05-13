import json
import os
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

import feedparser
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

FEEDS = [
    {
        "name": "Google News: norsk politikk",
        "url": "https://news.google.com/rss/search?q=norsk%20politikk&hl=no&gl=NO&ceid=NO:no",
        "politics_feed": True,
    },
    {
        "name": "Google News: Stortinget og regjeringen",
        "url": "https://news.google.com/rss/search?q=Stortinget%20OR%20regjeringen&hl=no&gl=NO&ceid=NO:no",
        "politics_feed": True,
    },
    {
        "name": "E24 Makro og politikk",
        "url": "https://e24.no/rss2/?seksjon=makro-og-politikk",
        "politics_feed": True,
    },
    {
        "name": "Khrono",
        "url": "https://www.khrono.no/?lab_viewport=rss",
        "politics_feed": False,
    },
    {
        "name": "NRK Toppsaker",
        "url": "https://www.nrk.no/toppsaker.rss",
        "politics_feed": False,
    },
    {
        "name": "NRK Siste nytt",
        "url": "https://www.nrk.no/nyheter/siste.rss",
        "politics_feed": False,
    },
    {
        "name": "Nettavisen Nyheter",
        "url": "https://www.nettavisen.no/service/rich-rss?tag=nyheter",
        "politics_feed": False,
    },
]

POLITICAL_KEYWORDS = [
    "arbeiderpartiet",
    "bystyre",
    "departement",
    "eos",
    "eøs",
    "finansminister",
    "frp",
    "hoyre",
    "høyre",
    "kommune",
    "kommunestyre",
    "krf",
    "lovforslag",
    "minister",
    "partiet",
    "politiker",
    "politikk",
    "regjering",
    "regjeringen",
    "rodt",
    "rødt",
    "senterpartiet",
    "statsbudsjett",
    "statsminister",
    "storting",
    "stortinget",
    "støre",
    "sv",
    "venstre",
    "valg",
]

MAX_ARTICLES = 14
MAX_PER_SOURCE = 3
MAX_CANDIDATES_PER_SOURCE = 25
SIMILAR_TITLE_THRESHOLD = 0.86


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


def clean_text(value, max_length=None):
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if max_length and len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def fetch_feed(feed):
    response = requests.get(
        feed["url"],
        headers={"User-Agent": "PoliticalBriefingBot/1.0"},
        timeout=30,
    )
    response.raise_for_status()

    cleaned_text = clean_xml_text(response.text)
    return feedparser.parse(cleaned_text)


def entry_text(entry):
    return " ".join(
        clean_text(value)
        for value in [
            getattr(entry, "title", ""),
            getattr(entry, "summary", ""),
            getattr(entry, "description", ""),
        ]
    ).lower()


def is_political(entry):
    text = entry_text(entry)
    return any(keyword in text for keyword in POLITICAL_KEYWORDS)


def entry_source_name(entry, fallback):
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", None):
        return clean_text(source.title, 80)
    return fallback


def entry_summary(entry):
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
    return clean_text(summary, 500)


def entry_published(entry):
    for attribute in ("published", "updated", "created"):
        value = getattr(entry, attribute, "")
        if value:
            return clean_text(value, 120)
    return ""


def normalized_title(title):
    title = clean_text(title).lower()
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    title = re.sub(r"[^a-zæøå0-9 ]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def is_duplicate(article, seen_links, seen_titles):
    link = article["link"]
    title = normalized_title(article["title"])

    if link and link in seen_links:
        return True

    for seen_title in seen_titles:
        if SequenceMatcher(None, title, seen_title).ratio() >= SIMILAR_TITLE_THRESHOLD:
            return True

    if link:
        seen_links.add(link)
    if title:
        seen_titles.append(title)

    return False


def collect_articles():
    articles = []
    seen_links = set()
    seen_titles = []

    for feed_config in FEEDS:
        feed_name = feed_config["name"]

        try:
            feed = fetch_feed(feed_config)
        except requests.RequestException as exc:
            print(f"Warning: could not fetch {feed_name}: {exc}")
            continue

        if feed.bozo:
            print(f"Warning: {feed_name} had malformed content: {feed.bozo_exception}")

        if not feed.entries:
            print(f"Warning: no entries found in {feed_name}")
            continue

        added_from_source = 0
        skipped_non_political = 0
        skipped_duplicates = 0
        for entry in feed.entries[:MAX_CANDIDATES_PER_SOURCE]:
            political_match = feed_config.get("politics_feed") or is_political(entry)
            if not political_match:
                skipped_non_political += 1
                continue

            article = {
                "feed": feed_name,
                "source": entry_source_name(entry, feed_name),
                "published": entry_published(entry),
                "title": clean_text(getattr(entry, "title", "Untitled"), 180),
                "summary": entry_summary(entry),
                "link": clean_text(getattr(entry, "link", ""), 500),
            }

            if is_duplicate(article, seen_links, seen_titles):
                skipped_duplicates += 1
                continue

            articles.append(article)
            added_from_source += 1

            if added_from_source >= MAX_PER_SOURCE:
                break

        print(
            f"Collected {added_from_source} political articles from {feed_name}; "
            f"skipped {skipped_non_political} non-political and "
            f"{skipped_duplicates} duplicate articles."
        )

    return articles[:MAX_ARTICLES]


def articles_json(articles):
    return json.dumps(articles, ensure_ascii=False, indent=2)


def summarize(articles, openrouter_api_key):
    prompt = f"""
Du skriver en norsk politisk morgenbriefing for en leser med mastergrad i politikk.

Du får KUN strukturerte RSS-artikler som JSON. Bruk bare disse feltene: title, source, published, summary og link.
Ikke inventer fakta, årsaker, konsekvenser, aktører eller bakgrunn som ikke finnes i JSON-dataene.
Hvis datagrunnlaget er tynt, skriv nøkternt at saken bør følges, ikke fyll inn med gjetning.

Stil:
- Norsk bokmål.
- Konsis, analytisk og litt kynisk.
- Ikke skoleaktig. Ikke forklar banale institusjonelle selvfølgeligheter.
- Ikke bruk Markdown-tabeller.
- Velg maks 5 saker.
- Hver sak skal ha klikkbar lenke i tittelen: **[Tittel](link)**.
- Bruk bare lenker fra JSON-dataene.

Format:
**Dagens mønster**
2-3 korte analytiske setninger basert på artiklene.

**Toppsaker**
1. **[Tittel](link)**
   Kort: ...
   Konfliktlinje: ...
   Følg med på: ...

**Kildemerknad**
1 kort setning om hva materialet dekker godt eller dårlig.

JSON-artikler:
{articles_json(articles)}
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
            "temperature": 0.15,
            "max_tokens": 1500,
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


def truncate_text(text, max_length):
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def source_links(articles):
    links = []
    for article in articles:
        if article["link"]:
            title = truncate_text(article["title"], 70)
            links.append(f"[{title}]({article['link']})")
    return "\n".join(links) or "Ingen lenker tilgjengelig"


def post_to_discord(summary, articles, webhook_url):
    embed = {
        "title": "Morning Political Briefing",
        "description": truncate_text(summary, 3900),
        "color": 3447003,
        "fields": [
            {
                "name": "Kilder",
                "value": truncate_text(source_links(articles), 1000),
                "inline": False,
            }
        ],
        "footer": {
            "text": f"{len(articles)} politiske saker vurdert fra {len(FEEDS)} feeds"
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    response = requests.post(
        webhook_url,
        json={"embeds": [embed]},
        timeout=30,
    )
    response.raise_for_status()


def main():
    openrouter_api_key = get_required_env("OPENROUTER_API_KEY")
    discord_webhook_url = get_required_env("DISCORD_WEBHOOK_URL")
    require_discord_webhook_url(discord_webhook_url)

    articles = collect_articles()
    if not articles:
        print("No political articles found in configured feeds.")
        sys.exit(1)

    summary = summarize(articles, openrouter_api_key)
    post_to_discord(summary, articles, discord_webhook_url)
    print("Briefing posted to Discord.")


if __name__ == "__main__":
    main()
