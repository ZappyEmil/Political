import html
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests

OSLO_TZ = ZoneInfo("Europe/Oslo")

FEEDS = [
    {"name": "E24 Makro og politikk", "url": "https://e24.no/rss2/?seksjon=makro-og-politikk", "politics_feed": True, "max_per_source": 4},
    {"name": "Khrono", "url": "https://www.khrono.no/?lab_viewport=rss", "politics_feed": False, "max_per_source": 3},
    {"name": "NRK Toppsaker", "url": "https://www.nrk.no/toppsaker.rss", "politics_feed": False, "max_per_source": 4},
    {"name": "NRK Siste nytt", "url": "https://www.nrk.no/nyheter/siste.rss", "politics_feed": False, "max_per_source": 4},
    {"name": "Nettavisen Nyheter", "url": "https://www.nettavisen.no/service/rich-rss?tag=nyheter", "politics_feed": False, "max_per_source": 3},
    {"name": "Google News: Altinget", "url": "https://news.google.com/rss/search?q=site%3Aaltinget.no%20politikk&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
    {"name": "Google News: Aftenposten politikk", "url": "https://news.google.com/rss/search?q=site%3Aaftenposten.no%20politikk&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
    {"name": "Google News: VG politikk", "url": "https://news.google.com/rss/search?q=site%3Avg.no%20politikk&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
    {"name": "Google News: Politiforum", "url": "https://news.google.com/rss/search?q=site%3Apolitiforum.no%20politi%20OR%20regjeringen&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
    {"name": "Google News: Kommunal Rapport", "url": "https://news.google.com/rss/search?q=site%3Akommunal-rapport.no%20kommune%20politikk&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
    {"name": "Google News: norsk politikk", "url": "https://news.google.com/rss/search?q=norsk%20politikk&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
    {"name": "Google News: Stortinget og regjeringen", "url": "https://news.google.com/rss/search?q=Stortinget%20OR%20regjeringen&hl=no&gl=NO&ceid=NO:no", "politics_feed": True, "max_per_source": 2},
]

HIGH_WEIGHT_KEYWORDS = {
    "regjeringen": 12, "regjering": 10, "stortinget": 12, "storting": 10,
    "statsråd": 11, "departement": 10, "budsjett": 12, "statsbudsjett": 13,
    "nasjonalbudsjett": 13, "kommuneøkonomi": 12, "lovforslag": 12, "høring": 9,
    "vedtak": 8, "parti": 7, "partiet": 7, "partileder": 10, "nato": 11,
    "eu": 9, "ukraina": 10, "forsvar": 11, "politi": 9, "sikkerhet": 9,
    "digitalisering": 9, "kunstig intelligens": 11, "offentlig sektor": 10,
    "skatt": 9, "nav": 9, "helsepolitikk": 11, "utdanningspolitikk": 11,
    "energipolitikk": 11,
}

NEGATIVE_KEYWORDS = {
    "sport": 12, "fotball": 12, "håndball": 12, "kjendiser": 12, "kjendis": 12,
    "vær": 9, "ulykke": 9, "savnet": 9, "konkurranse": 8, "kultur": 7,
    "studentliv": 12, "humor": 10, "underholdning": 12, "bolledusør": 20,
    "konsert": 9, "film": 8, "tv": 7,
}

TOPIC_RULES = {
    "Budsjett/økonomi": ["budsjett", "statsbudsjett", "nasjonalbudsjett", "kommuneøkonomi", "skatt", "avgift", "penger", "rente", "økonomi"],
    "Forsvar/sikkerhet": ["forsvar", "nato", "politi", "sikkerhet", "beredskap", "pst", "etterretning", "ukraina"],
    "Kommunepolitikk": ["kommune", "kommuneøkonomi", "kommunestyre", "bystyre", "fylkeskommune", "ordfører", "barnevern", "lokalpolitikk"],
    "Helse": ["helsepolitikk", "helse", "sykehus", "fastlege", "pasient", "eldreomsorg"],
    "Utdanning/forskning": ["utdanningspolitikk", "forskning", "forskningsrådet", "universitet", "høyskole", "kunnskapsdepartementet", "studentbolig"],
    "AI/digitalisering": ["digitalisering", "kunstig intelligens", "offentlig sektor", "ki", "ai", "data"],
    "Klima/energi": ["energipolitikk", "energi", "kraft", "strøm", "olje", "gass", "klima"],
    "Utenriks/EU/NATO": ["eu", "eøs", "eos", "nato", "ukraina", "russland", "utenriks", "sanksjon"],
    "Styring/lovverk": ["regjeringen", "regjering", "stortinget", "storting", "departement", "statsråd", "lovforslag", "høring", "vedtak"],
}

SOURCE_BOOSTS = {
    "stortinget": 18, "regjeringen": 18, "altinget": 14, "aftenposten": 11,
    "kommunal rapport": 9, "nrk": 9, "vg": 7, "e24": 12, "politiforum": 10,
}

LOCAL_OR_GENERIC_SOURCES = ["nordlys", "nettavisen", "dagbladet", "abc nyheter", "tv 2", "ba", "bt", "adresseavisen", "fvn", "rbnett"]
CAMPUS_TRIVIA_KEYWORDS = ["bolledusør", "campus", "studentliv", "forsvinningssak", "kantine", "maskot", "semesterstart"]
HUMAN_INTEREST_KEYWORDS = ["savnet", "ulykke", "døde", "familie", "personlig", "kjendis", "kjendiser"]
CLICKBAIT_PATTERNS = ["dette gnager", "du vil ikke tro", "slik blir", "norge er ute å kjøre", "raser", "sjokk"]

MAX_ARTICLES = 24
DEFAULT_MAX_PER_SOURCE = 3
MAX_CANDIDATES_PER_SOURCE = 30
MIN_THEMES = 4
MAX_THEMES = 6
SIMILAR_TITLE_THRESHOLD = 0.86
MIN_SCORE = 20
MIN_HIGH_SIGNAL_SCORE = 12
FIELD_NAME_LIMIT = 130
FIELD_VALUE_LIMIT = 900
OBSERVATION_LIMIT = 650
DISCORD_EMBED_TOTAL_LIMIT = 5600
DISCORD_MAX_ATTEMPTS = 3


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
        print("Invalid DISCORD_WEBHOOK_URL: expected a full Discord webhook URL starting with https://discord.com/api/webhooks/")
        sys.exit(1)
    if parsed.netloc not in ("discord.com", "discordapp.com") or not parsed.path.startswith("/api/webhooks/"):
        print("Invalid DISCORD_WEBHOOK_URL: the secret should look like https://discord.com/api/webhooks/<webhook_id>/<token>")
        sys.exit(1)


def is_valid_xml_char(char):
    codepoint = ord(char)
    return codepoint in (0x09, 0x0A, 0x0D) or 0x20 <= codepoint <= 0xD7FF or 0xE000 <= codepoint <= 0xFFFD or 0x10000 <= codepoint <= 0x10FFFF


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


def normalize_for_matching(text):
    return clean_text(text).lower()


def contains_term(text, term):
    pattern = rf"(?<![\wæøå]){re.escape(term.lower())}(?![\wæøå])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def fetch_feed(feed):
    response = requests.get(feed["url"], headers={"User-Agent": "PoliticalBriefingBot/1.0"}, timeout=30)
    response.raise_for_status()
    return feedparser.parse(clean_xml_text(response.text))


def entry_source_name(entry, fallback):
    source = getattr(entry, "source", None)
    if source and getattr(source, "title", None):
        return clean_text(source.title, 80)
    return fallback


def normalized_title(title):
    title = clean_text(title).lower()
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    title = re.sub(r"[^a-zæøå0-9 ]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def clean_summary(entry, title, source):
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
    summary = clean_text(summary, 360)
    if not summary:
        return ""
    normalized_summary = normalized_title(summary)
    normalized_entry_title = normalized_title(title)
    normalized_source = normalized_title(source)
    if normalized_summary in {normalized_entry_title, normalized_title(f"{title} {source}"), normalized_title(f"{title} {normalized_source}")}:
        return ""
    if normalized_entry_title and normalized_summary.startswith(normalized_entry_title):
        summary = clean_text(summary[len(title) :], 360)
    return re.sub(rf"\s*{re.escape(source)}\s*$", "", summary, flags=re.IGNORECASE).strip()


def parse_date(value):
    if not value:
        return ""
    raw = str(value).strip()
    if raw.isdigit():
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).astimezone(OSLO_TZ).strftime("%Y-%m-%d %H:%M %Z")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(OSLO_TZ).strftime("%Y-%m-%d %H:%M %Z")
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(OSLO_TZ).strftime("%Y-%m-%d %H:%M %Z")
    except (TypeError, ValueError, OverflowError):
        return clean_text(raw, 120)


def entry_published(entry):
    for attribute in ("published", "updated", "created"):
        value = getattr(entry, attribute, "")
        if value:
            return parse_date(value)
    return ""


def keyword_score(text, keywords, title_text=None):
    total = 0
    matches = []
    for keyword, weight in keywords.items():
        in_text = contains_term(text, keyword)
        in_title = contains_term(title_text, keyword) if title_text else False
        if in_title:
            total += weight * 2
            matches.append(keyword)
        elif in_text:
            total += weight
            matches.append(keyword)
    return total, matches


def tags_for_text(text):
    return [tag for tag, terms in TOPIC_RULES.items() if any(contains_term(text, term) for term in terms)]


def source_weight(source, feed, tags, high_score):
    source_text = normalize_for_matching(f"{source} {feed}")
    weight = 0
    for source_name, boost in SOURCE_BOOSTS.items():
        if contains_term(source_text, source_name):
            weight += boost
    if contains_term(source_text, "khrono"):
        weight += 8 if "Utdanning/forskning" in tags and high_score >= MIN_HIGH_SIGNAL_SCORE else -12
    if feed.startswith("Google News"):
        weight -= 3
    if any(contains_term(source_text, source) for source in LOCAL_OR_GENERIC_SOURCES):
        weight -= 4
    return weight


def is_duplicate(article, seen_links, seen_titles):
    link = article["link"]
    title = normalized_title(article["title"])
    if link and link in seen_links:
        return True
    if any(SequenceMatcher(None, title, seen_title).ratio() >= SIMILAR_TITLE_THRESHOLD for seen_title in seen_titles):
        return True
    if link:
        seen_links.add(link)
    if title:
        seen_titles.append(title)
    return False


def has_any(text, terms):
    return any(contains_term(text, term) for term in terms)


def exclusion_reason(article):
    text = article["text"]
    source_text = normalize_for_matching(f"{article['source']} {article['feed']}")
    if article["negative_score"] >= 18 and article["high_score"] < 28:
        return "negative keyword dominance"
    if has_any(text, CAMPUS_TRIVIA_KEYWORDS) and article["high_score"] < 30:
        return "campus trivia without policy angle"
    if has_any(text, HUMAN_INTEREST_KEYWORDS) and article["high_score"] < 30:
        return "human-interest story without policy angle"
    if not article["tags"] and article["high_score"] < MIN_HIGH_SIGNAL_SCORE:
        return "weak or missing policy angle"
    if any(contains_term(source_text, source) for source in LOCAL_OR_GENERIC_SOURCES):
        if article["high_score"] < 20 and "Kommunepolitikk" not in article["tags"]:
            return "generic local news without clear political consequence"
    if article["score"] < MIN_SCORE:
        return f"score below threshold ({article['score']})"
    return ""


def build_article(entry, feed_config, feed_name):
    raw_title = clean_text(getattr(entry, "title", "Untitled"), 180)
    title = clean_google_title(raw_title) if feed_name.startswith("Google News") else raw_title
    source = entry_source_name(entry, feed_name)
    summary = clean_summary(entry, title, source)
    text = normalize_for_matching(f"{title} {summary}")
    title_text = normalize_for_matching(title)
    high_score, high_matches = keyword_score(text, HIGH_WEIGHT_KEYWORDS, title_text)
    negative_score, negative_matches = keyword_score(text, NEGATIVE_KEYWORDS, title_text)
    tags = tags_for_text(text)
    source_bonus = source_weight(source, feed_name, tags, high_score)
    score = high_score + (len(tags) * 4) + (6 if feed_config.get("politics_feed") else 0) + source_bonus + (4 if summary else -3)
    score -= negative_score + (4 if has_any(text, CLICKBAIT_PATTERNS) else 0)
    return {
        "feed": feed_name,
        "source": source,
        "published": entry_published(entry),
        "title": title,
        "summary": summary,
        "link": clean_text(getattr(entry, "link", "")),
        "tags": tags,
        "high_score": high_score,
        "high_matches": high_matches,
        "negative_score": negative_score,
        "negative_matches": negative_matches,
        "source_weight": source_bonus,
        "score": score,
        "text": text,
    }


def collect_articles():
    articles = []
    excluded = []
    seen_links = set()
    seen_titles = []
    fetched_count = 0
    for feed_config in FEEDS:
        feed_name = feed_config["name"]
        max_for_source = feed_config.get("max_per_source", DEFAULT_MAX_PER_SOURCE)
        try:
            feed = fetch_feed(feed_config)
        except requests.RequestException as exc:
            print(f"Warning: could not fetch {feed_name}: {exc}")
            continue
        if feed.bozo:
            print(f"Warning: {feed_name} had malformed content: {feed.bozo_exception}")
        entries = feed.entries[:MAX_CANDIDATES_PER_SOURCE]
        fetched_count += len(entries)
        source_candidates = []
        print(f"Fetched {len(entries)} entries from {feed_name}.")
        for entry in entries:
            article = build_article(entry, feed_config, feed_name)
            reason = exclusion_reason(article)
            if reason:
                excluded.append((reason, article))
                print(f"Excluded [{reason}]: {article['title']} ({article['source']})")
                continue
            source_candidates.append(article)
        added_from_source = 0
        for article in sorted(source_candidates, key=lambda item: item["score"], reverse=True):
            if is_duplicate(article, seen_links, seen_titles):
                excluded.append(("duplicate", article))
                print(f"Excluded [duplicate]: {article['title']} ({article['source']})")
                continue
            articles.append(article)
            added_from_source += 1
            if added_from_source >= max_for_source:
                break
        print(f"Accepted {added_from_source} articles from {feed_name} after scoring {len(source_candidates)} candidates.")
    ranked = sorted(articles, key=lambda article: article["score"], reverse=True)[:MAX_ARTICLES]
    print(f"Fetched total: {fetched_count}")
    print(f"Filtered/accepted total before ranking: {len(articles)}")
    print(f"Ranked total sent to briefing: {len(ranked)}")
    print(f"Excluded total: {len(excluded)}")
    for article in ranked:
        tags = ", ".join(article["tags"]) or "Ingen tag"
        print(f"Final score {article['score']}: {article['title']} ({article['source']}) | tags={tags} | positive={article['high_matches']} negative={article['negative_matches']}")
    return ranked


def truncate_text(text, max_length):
    value = str(text or "")
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def today_label():
    return datetime.now(OSLO_TZ).strftime("%Y-%m-%d")


def discord_link(url):
    if not url:
        return "Ingen lenke"
    safe_url = url.replace(" ", "%20").replace(")", "%29")
    return f"[Åpne saken]({safe_url})"


def source_list(articles):
    sources = []
    for article in articles:
        if article["source"] and article["source"] not in sources:
            sources.append(article["source"])
    return sources


def theme_label(article):
    if article["tags"]:
        return article["tags"][0]
    if article["high_matches"]:
        return article["high_matches"][0].capitalize()
    return "Andre politiske signaler"


def article_framing(article):
    if article["summary"]:
        return truncate_text(article["summary"], 260)
    title = article["title"].rstrip(".")
    source = article["source"] or "RSS-kilden"
    return truncate_text(f"{source} melder om «{title}». Vurderingen er basert på tittel, kilde og regelbaserte politiske signaler.", 260)


def build_themes(articles):
    grouped = {}
    for article in articles:
        grouped.setdefault(theme_label(article), []).append(article)
    themes = []
    for label, group in grouped.items():
        ranked_group = sorted(group, key=lambda item: item["score"], reverse=True)
        themes.append({
            "label": label,
            "articles": ranked_group,
            "score": sum(article["score"] for article in ranked_group),
            "top_score": ranked_group[0]["score"],
            "sources": source_list(ranked_group),
            "missing_summaries": sum(1 for article in ranked_group if not article["summary"]),
        })
    themes.sort(key=lambda item: (item["score"], item["top_score"], len(item["articles"])), reverse=True)
    selected = themes[:MAX_THEMES]
    if len(selected) < MIN_THEMES and len(themes) > len(selected):
        selected.extend(themes[len(selected) : MIN_THEMES])
    return selected


def observations(articles, themes):
    tag_counts = Counter(tag for article in articles for tag in article["tags"])
    lines = []
    if tag_counts["Budsjett/økonomi"] >= 3:
        lines.append("Mye av nyhetsbildet dreier seg om budsjett og økonomiske prioriteringer.")
    if tag_counts["Forsvar/sikkerhet"] >= 2:
        lines.append("Forsvar og sikkerhet har høy synlighet i dagens nyhetsbilde.")
    if tag_counts["Kommunepolitikk"] >= 2:
        lines.append("Kommunale prioriteringer og lokal styring tar uvanlig mye plass.")
    if tag_counts["Utdanning/forskning"] >= 2:
        lines.append("Utdanning og forskning dukker opp som politisk budsjett- og styringsfelt.")
    if len(themes) >= MIN_THEMES:
        lines.append(f"Sakene samles i {len(themes)} tydelige temaer fremfor enkeltoppslag.")
    if not lines:
        top_tags = [tag for tag, _ in tag_counts.most_common(2)]
        lines.append(f"Nyhetsbildet er spredt, med {', '.join(top_tags).lower()} som tydeligste spor." if top_tags else "Nyhetsbildet er spredt, og ingen politisk kategori dominerer tydelig.")
    return "\n".join(lines[:2])


def theme_field_value(theme):
    articles = theme["articles"]
    lead = articles[0]
    source_text = ", ".join(theme["sources"][:4])
    if len(theme["sources"]) > 4:
        source_text += f" +{len(theme['sources']) - 4}"
    links = [f"{article['source']}: {discord_link(article['link'])}" for article in articles[:3] if article["link"]]
    lines = [
        f"Kilder: {source_text or 'Ukjent'}",
        f"Tidsstempel: {lead['published'] or 'ukjent'}",
        f"Kategori: {theme['label']}",
        f"Analyse: {article_framing(lead)}",
    ]
    if len(articles) > 1:
        related = "; ".join(truncate_text(f"{article['source']}: {article['title']}", 110) for article in articles[1:3])
        if related:
            lines.append(f"Relatert: {related}")
    if links:
        lines.append("Lenker: " + " | ".join(links))
    return truncate_text("\n".join(lines), FIELD_VALUE_LIMIT)


def theme_fields(themes):
    fields = []
    for index, theme in enumerate(themes, start=1):
        article_count = len(theme["articles"])
        name = f"{index}. {theme['label']} ({article_count} sak{'er' if article_count != 1 else ''})"
        fields.append({"name": truncate_text(name, FIELD_NAME_LIMIT), "value": theme_field_value(theme), "inline": False})
    return fields


def embed_size(embed):
    field_size = sum(len(field["name"]) + len(field["value"]) for field in embed.get("fields", []))
    return len(embed.get("title", "")) + len(embed.get("description", "")) + field_size


def clamp_embed(embed):
    while embed_size(embed) > DISCORD_EMBED_TOTAL_LIMIT and len(embed["fields"]) > 2:
        removed = embed["fields"].pop()
        print(f"Trimmed Discord field to stay under embed limit: {removed['name']}")
    return embed


def missing_summary_note(themes):
    missing = sum(theme["missing_summaries"] for theme in themes)
    if missing == 0:
        return ""
    return f"Merk: Kort sammendrag mangler i RSS for {missing} sak{'er' if missing != 1 else ''}; disse er forsiktig rammet inn fra tittel og kilde."


def empty_brief_embed():
    return {
        "title": f"Politisk morgenbrief — {today_label()}",
        "description": "Ingen tydelige politiske saker passerte den regelbaserte RSS-filtreringen i denne kjøringen.",
        "color": 0x95A5A6,
        "fields": [{"name": "Status", "value": "RSS-feedene ble sjekket, men ingen saker hadde nok politisk relevans til å tas med.", "inline": False}],
        "footer": {"text": f"0 politiske saker vurdert fra {len(FEEDS)} feeds"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_brief_embed(articles):
    if not articles:
        return empty_brief_embed()
    themes = build_themes(articles)
    fields = [{"name": "Kort vurdering", "value": truncate_text(observations(articles, themes), OBSERVATION_LIMIT), "inline": False}]
    fields.extend(theme_fields(themes))
    note = missing_summary_note(themes)
    if note:
        fields.append({"name": "RSS-notat", "value": truncate_text(note, FIELD_VALUE_LIMIT), "inline": False})
    embed = {
        "title": f"Politisk morgenbrief — {today_label()}",
        "description": "Tematisk morgenbrief fra åpne RSS-kilder, gruppert og valgt med regelbasert scoring.",
        "color": 3447003,
        "fields": fields,
        "footer": {"text": f"{len(articles)} politiske saker gruppert i {len(themes)} temaer fra {len(FEEDS)} feeds"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return clamp_embed(embed)


def post_payload_to_discord(webhook_url, payload):
    for attempt in range(1, DISCORD_MAX_ATTEMPTS + 1):
        response = requests.post(webhook_url, json=payload, timeout=30)
        print(f"Discord webhook response: {response.status_code} {response.reason}")
        if response.status_code == 429 and attempt < DISCORD_MAX_ATTEMPTS:
            retry_after = 1
            try:
                retry_after = float(response.json().get("retry_after", 1))
            except (TypeError, ValueError, requests.JSONDecodeError):
                pass
            wait_seconds = retry_after + 0.25
            print(f"Discord rate limited. Retrying in {wait_seconds:.2f}s.")
            time.sleep(wait_seconds)
            continue
        if response.status_code >= 500 and attempt < DISCORD_MAX_ATTEMPTS:
            wait_seconds = attempt
            print(f"Discord server error. Retrying in {wait_seconds}s.")
            time.sleep(wait_seconds)
            continue
        if response.status_code >= 400:
            print(f"Discord webhook failed ({response.status_code}): {response.text[:500]}")
        response.raise_for_status()
        return


def post_to_discord(articles, webhook_url):
    embed = build_brief_embed(articles)
    print(f"Posting political brief with {len(embed['fields'])} Discord field(s).")
    post_payload_to_discord(webhook_url, {"embeds": [embed]})


def main():
    discord_webhook_url = get_required_env("DISCORD_WEBHOOK_URL")
    require_discord_webhook_url(discord_webhook_url)
    articles = collect_articles()
    if not articles:
        print("No political articles found in configured feeds. Posting empty brief.")
    post_to_discord(articles, discord_webhook_url)
    print("Briefing posted to Discord.")


if __name__ == "__main__":
    main()
