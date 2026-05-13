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


def entry_source_name(entry, fallback):
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", None):
        return source.title
    return fallback


def collect_articles():
    articles = []
    seen = set()

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
        for entry in feed.entries[:MAX_CANDIDATES_PER_SOURCE]:
            title = getattr(entry, "title", "Untitled")
            link = getattr(entry, "link", "")
            unique_key = link or title
            political_match = feed_config.get("politics_feed") or is_political(entry)

            if not political_match:
                skipped_non_political += 1
                continue

            if unique_key in seen:
                continue

            seen.add(unique_key)
            articles.append(
                {
                    "feed": feed_name,
                    "source": entry_source_name(entry, feed_name),
                    "title": title,
                    "link": link,
                }
            )
            added_from_source += 1

            if added_from_source >= MAX_PER_SOURCE:
                break

        print(
            f"Collected {added_from_source} political articles from {feed_name} "
            f"and skipped {skipped_non_political} non-political articles."
        )

    return articles[:MAX_ARTICLES]


def format_articles_for_prompt(articles):
    lines = []
    for index, article in enumerate(articles, start=1):
        link = article["link"] or "No link"
        lines.append(
            f"{index}. [{article['source']} via {article['feed']}] {article['title']}\n"
            f"   {link}"
        )
    return "\n".join(lines)


def summarize(articles, openrouter_api_key):
    news_text = format_articles_for_prompt(articles)
    prompt = f"""
Skriv en norsk politisk morgenbriefing for en leser med mastergrad i politikk.

Strenge regler:
- Ta bare med saker med reell politisk relevans: makt, institusjoner, partier, styring, budsjett, lovverk, forvaltning, velferd, justis, energi, sikkerhetspolitikk eller utenrikspolitikk.
- Ikke forklar banale ting som at kommuner har ansvar, at Stortinget vedtar lover, eller at budsjett påvirker prioriteringer.
- Ikke bruk skoleaktige formuleringer som "dette viser hvordan" eller generiske setninger uten analytisk verdi.
- Ikke bruk Markdown-tabeller.
- Velg maks 5 saker.
- Skriv substansielt, men stramt. Hver sak kan ha 3-5 setninger.
- Vær eksplisitt om konfliktlinje, aktører, maktmidler, budsjettmessig/institusjonell betydning og hva som bør følges videre.
- Ikke dikte detaljer som ikke finnes i sakstitlene. Marker usikkerhet nøkternt hvis grunnlaget er tynt.

Saker:
{news_text}

Format:
**Dagens mønster**
2-3 analytiske setninger om den samlede politiske tendensen.

**Toppsaker**
1. **Tittel**
   Kort: ...
   Konfliktlinje: ...
   Følg med på: ...

**Kilder vurdert**
Kort setning om kildemiks og eventuelle hull i materialet.
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
            "temperature": 0.25,
            "max_tokens": 1400,
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
    for article in articles[:10]:
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
