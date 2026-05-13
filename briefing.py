import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

FEEDS = [
    {
        "name": "NRK Toppsaker",
        "url": "https://www.nrk.no/toppsaker.rss",
        "politics_only": False,
    },
    {
        "name": "NRK Siste nytt",
        "url": "https://www.nrk.no/nyheter/siste.rss",
        "politics_only": False,
    },
    {
        "name": "E24 Makro og politikk",
        "url": "https://e24.no/rss2/?seksjon=makro-og-politikk",
        "politics_only": True,
    },
    {
        "name": "Nettavisen Nyheter",
        "url": "https://www.nettavisen.no/service/rich-rss?tag=nyheter",
        "politics_only": False,
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

MAX_ARTICLES = 12
MAX_PER_SOURCE = 8


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


def entry_text(entry):
    return " ".join(
        str(value)
        for value in [
            getattr(entry, "title", ""),
            getattr(entry, "summary", ""),
            getattr(entry, "description", ""),
        ]
    ).lower()


def is_political(entry):
    text = entry_text(entry)
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
        skipped_non_political = 0
        for entry in feed.entries[:20]:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            unique_key = link or title
            political_match = is_political(entry)

            if not feed_config.get("politics_only") and not political_match:
                skipped_non_political += 1
                continue

            if unique_key in seen:
                continue

            seen.add(unique_key)
            article = {
                "source": source_name,
                "title": title,
                "link": link,
            }
            articles.append(article)
            added_from_source += 1

            if added_from_source >= MAX_PER_SOURCE or len(articles) >= MAX_ARTICLES:
                break

        print(
            f"Collected {added_from_source} political articles from {source_name} "
            f"and skipped {skipped_non_political} non-political articles."
        )

        if len(articles) >= MAX_ARTICLES:
            break

    return articles


def format_articles_for_prompt(articles):
    lines = []
    for index, article in enumerate(articles, start=1):
        link = article["link"] or "No link"
        lines.append(f"{index}. [{article['source']}] {article['title']}\n   {link}")
    return "\n".join(lines)


def summarize(articles, openrouter_api_key):
    news_text = format_articles_for_prompt(articles)
    prompt = f"""
Skriv en norsk politisk briefing for Discord basert kun på sakene under.

Strenge regler:
- Ta bare med politikk, offentlig styring, partier, Storting/regjering, kommunepolitikk, lovverk, skatt, budsjett, velferd, justis, energi eller utenriks/sikkerhetspolitikk.
- Ikke ta med sport, kjendiser, forbrukerstoff, ulykker eller generell krim med mindre saken har tydelig politisk konsekvens.
- Ikke bruk Markdown-tabeller.
- Skriv litt mer utfyllende enn en notis, men hold det lett å skanne.
- Velg maks 5 saker.
- For hver sak: tittel, kort forklaring, hvorfor det er politisk viktig.

Saker:
{news_text}

Format:
**Toppsaker**
1. **Tittel**
   Hva skjedde: ...
   Politisk betydning: ...

**Kort vurdering**
2-3 setninger om hva dagens saker samlet peker mot.
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


def truncate_text(text, max_length):
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def source_links(articles):
    links = []
    for article in articles[:5]:
        if article["link"]:
            links.append(f"[{article['source']}]({article['link']})")
    return " | ".join(links) or "Ingen lenker tilgjengelig"


def post_to_discord(summary, articles, webhook_url):
    embed = {
        "title": "Morning Political Briefing",
        "description": truncate_text(summary, 3800),
        "color": 3447003,
        "fields": [
            {
                "name": "Kilder",
                "value": truncate_text(source_links(articles), 1000),
                "inline": False,
            }
        ],
        "footer": {
            "text": f"{len(articles)} politiske saker vurdert"
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
