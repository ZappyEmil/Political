import html
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

FEEDS = [
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
]

TOPIC_KEYWORDS = {
    "Regjering/Storting": [
        "departement",
        "lovforslag",
        "minister",
        "regjering",
        "regjeringen",
        "statsminister",
        "storting",
        "stortinget",
    ],
    "Partipolitikk": [
        "arbeiderpartiet",
        "fremskrittspartiet",
        "frp",
        "hoyre",
        "høyre",
        "krf",
        "partiet",
        "partileder",
        "politiker",
        "politikk",
        "rodt",
        "rødt",
        "senterpartiet",
        "støre",
        "sv",
        "venstre",
        "valg",
    ],
    "Budsjett/økonomi": [
        "avgift",
        "budsjett",
        "finansminister",
        "nasjonalbudsjett",
        "olje",
        "penger",
        "rente",
        "revidert nasjonalbudsjett",
        "skatt",
        "statsbudsjett",
        "økonomi",
    ],
    "Kommune/forvaltning": [
        "barnevern",
        "bystyre",
        "fylke",
        "kommune",
        "kommunal",
        "kommunestyre",
        "nav",
        "skole",
        "velferd",
    ],
    "Justis/sikkerhet": [
        "beredskap",
        "domstol",
        "etterretning",
        "forsvar",
        "helikopter",
        "justis",
        "kriminalitet",
        "politi",
        "pst",
        "sikkerhet",
    ],
    "Utenriks/EØS": [
        "eos",
        "eøs",
        "eu",
        "europeisk",
        "forsvar",
        "nato",
        "russland",
        "sanksjon",
        "ukraina",
        "utenriks",
    ],
    "Utdanning/forskning": [
        "forskningspolitikk",
        "forskningsrådet",
        "høyskole",
        "kunnskapsdepartementet",
        "studentbolig",
        "universitet",
        "utdanningspolitikk",
    ],
}

MAX_ARTICLES = 10
MAX_PER_SOURCE = 3
MAX_CANDIDATES_PER_SOURCE = 25
TOP_ITEMS = 5
SIMILAR_TITLE_THRESHOLD = 0.86
MIN_DIRECT_FEED_TOPICS = 1


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
    text = html.unescape(str(value or ""))
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_length and len(text) > max_length:
        return text[: max_length - 3].rstrip() + "..."
    return text


def clean_google_title(title):
    return re.sub(r"\s+-\s+[^-]+$", "", title).strip()


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


def contains_keyword(text, keyword):
    pattern = rf"(?<![\wæøå]){re.escape(keyword.lower())}(?![\wæøå])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def topics_for_text(text):
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(contains_keyword(text, keyword) for keyword in keywords):
            topics.append(topic)
    return topics


def entry_source_name(entry, fallback):
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", None):
        return clean_text(source.title, 80)
    return fallback


def entry_summary(entry, title):
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
    summary = clean_text(summary, 320)
    normalized_summary = normalized_title(summary)
    normalized_entry_title = normalized_title(title)
    if normalized_summary == normalized_entry_title:
        return ""
    return summary


def entry_published(entry):
    for attribute in ("published", "updated", "created"):
        value = getattr(entry, attribute, "")
        if not value:
            continue
        if isinstance(value, str) and value.isdigit():
            parsed = datetime.fromtimestamp(int(value), tz=timezone.utc)
            return parsed.strftime("%Y-%m-%d %H:%M UTC")
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except (TypeError, ValueError, OverflowError):
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


def relevance_score(article):
    score = len(article["topics"]) * 3
    title = article["title"].lower()
    summary = article["summary"].lower()

    for keyword in ("regjering", "storting", "budsjett", "lov", "minister", "sikkerhet"):
        if contains_keyword(title, keyword):
            score += 3
        elif contains_keyword(summary, keyword):
            score += 1

    if article["summary"]:
        score += 2

    if article["feed"].startswith("Google News"):
        score -= 2

    if "Utdanning/forskning" in article["topics"] and len(article["topics"]) == 1:
        score -= 2

    return score


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
        skipped_low_quality = 0
        for entry in feed.entries[:MAX_CANDIDATES_PER_SOURCE]:
            raw_title = clean_text(getattr(entry, "title", "Untitled"), 180)
            title = clean_google_title(raw_title) if feed_name.startswith("Google News") else raw_title
            text = entry_text(entry)
            topics = topics_for_text(text)

            if not topics:
                skipped_non_political += 1
                continue

            summary = entry_summary(entry, title)
            if not feed_config.get("politics_feed") and not summary and len(topics) <= MIN_DIRECT_FEED_TOPICS:
                skipped_low_quality += 1
                continue

            article = {
                "feed": feed_name,
                "source": entry_source_name(entry, feed_name),
                "published": entry_published(entry),
                "title": title,
                "summary": summary,
                "link": clean_text(getattr(entry, "link", ""), 500),
                "topics": topics,
            }
            article["score"] = relevance_score(article)

            if is_duplicate(article, seen_links, seen_titles):
                skipped_duplicates += 1
                continue

            articles.append(article)
            added_from_source += 1

            if added_from_source >= MAX_PER_SOURCE:
                break

        print(
            f"Collected {added_from_source} political articles from {feed_name}; "
            f"skipped {skipped_non_political} non-political, "
            f"{skipped_duplicates} duplicate, and {skipped_low_quality} low-quality articles."
        )

    return sorted(articles, key=lambda article: article["score"], reverse=True)[:MAX_ARTICLES]


def truncate_text(text, max_length):
    value = str(text or "")
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def article_markdown_title(article):
    title = article["title"] or "Uten tittel"
    link = article["link"] or ""
    if link:
        return f"[{title}]({link})"
    return title


def watch_line(article):
    topics = set(article["topics"])
    if "Budsjett/økonomi" in topics:
        return "Om dette blir et reelt budsjettkrav, eller bare en lekkasje med kort halveringstid."
    if "Regjering/Storting" in topics:
        return "Om saken får proposisjon, vedtak eller partipolitisk etterspill."
    if "Kommune/forvaltning" in topics:
        return "Om ansvaret faktisk flyttes, eller bare parkeres hos neste forvaltningsnivå."
    if "Justis/sikkerhet" in topics:
        return "Om krav om penger, hjemler eller kapasitet følger etter overskriften."
    if "Utenriks/EØS" in topics:
        return "Om Norge må posisjonere seg, eller kan holde seg til standard bekymringsspråk."
    if "Utdanning/forskning" in topics:
        return "Om sektoren får styringssignal, finansiering eller bare nye forventninger."
    return "Om saken får konkret politisk oppfølging, eller bare blir en dagsordenmarkør."


def briefing_pattern(articles):
    topic_counts = Counter(topic for article in articles for topic in article["topics"])
    source_counts = Counter(article["source"] for article in articles)
    top_topics = [topic for topic, _ in topic_counts.most_common(3)]
    top_sources = [source for source, _ in source_counts.most_common(3)]

    if top_topics:
        topic_text = ", ".join(top_topics).lower()
    else:
        topic_text = "generell politikk"

    source_text = ", ".join(top_sources) if top_sources else "RSS-kildene"
    return (
        f"Tyngdepunktet ligger i {topic_text}. "
        f"Kildebildet heller mot {source_text}; les dette som morgenradar, ikke fasit. "
        "Kun RSS-data brukes: tittel, kilde, dato, sammendrag og lenke."
    )


def article_field_value(article):
    summary = article["summary"] or "RSS-kilden har bare tittel og lenke for denne saken."
    source = article["source"] or article["feed"] or "Ukjent kilde"
    published = article["published"] or "ukjent tidspunkt"
    topics = ", ".join(article["topics"])

    return truncate_text(
        "\n".join(
            [
                f"**{article_markdown_title(article)}**",
                f"Kilde: {source} | {published}",
                f"Tema: {topics}",
                f"Kort: {summary}",
                f"Følg med på: {watch_line(article)}",
            ]
        ),
        1024,
    )


def source_links(articles, max_length=1000):
    links = []
    used_length = 0
    for article in articles:
        if not article["link"]:
            continue
        title = truncate_text(article["title"], 70)
        item = f"[{title}]({article['link']})"
        next_length = used_length + len(item) + (1 if links else 0)
        if next_length > max_length:
            break
        links.append(item)
        used_length = next_length
    return "\n".join(links) or "Ingen lenker tilgjengelig"


def post_to_discord(articles, webhook_url):
    top_articles = articles[:TOP_ITEMS]
    fields = [
        {
            "name": f"{index}. {truncate_text(article['source'], 80)}",
            "value": article_field_value(article),
            "inline": False,
        }
        for index, article in enumerate(top_articles, start=1)
    ]
    fields.append(
        {
            "name": "Kilder",
            "value": source_links(top_articles),
            "inline": False,
        }
    )

    embed = {
        "title": "Politisk morgenbrief",
        "description": truncate_text(briefing_pattern(articles), 700),
        "color": 3447003,
        "fields": fields,
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
    discord_webhook_url = get_required_env("DISCORD_WEBHOOK_URL")
    require_discord_webhook_url(discord_webhook_url)

    articles = collect_articles()
    if not articles:
        print("No political articles found in configured feeds.")
        sys.exit(1)

    post_to_discord(articles, discord_webhook_url)
    print("Briefing posted to Discord.")


if __name__ == "__main__":
    main()
