#!/usr/bin/env python3
"""
News collection script: GNews API + configurable RSS feeds.

Collects international news via GNews and domestic/regional news via RSS feeds
configured in config/sources.json.

Output: output/YYYY-MM-DD/raw_news.json
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import requests

# Project root directory
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
CN_TZ = timezone(timedelta(hours=8))


def build_n1_to_n_window(pipeline_date: str | None) -> tuple[datetime, datetime]:
    """
    Build a strict time window: N-1 00:00:00 to N 23:59:59 (Asia/Shanghai boundary).
    Returns UTC start and end datetimes.
    """
    if pipeline_date:
        day_start_cn = datetime.strptime(pipeline_date, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=CN_TZ
        )
    else:
        now_cn = datetime.now(CN_TZ)
        day_start_cn = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)

    window_start_cn = day_start_cn - timedelta(days=1)
    window_end_cn = day_start_cn + timedelta(days=1) - timedelta(seconds=1)
    return window_start_cn.astimezone(timezone.utc), window_end_cn.astimezone(timezone.utc)


def in_window(dt: datetime, start_utc: datetime, end_utc: datetime) -> bool:
    """Check if a datetime falls within the time window."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return start_utc <= dt <= end_utc


def collect_gnews(api_key: str, max_articles: int = 10, pipeline_date: str = None) -> list[dict]:
    """
    Collect international news from GNews API.
    See: https://gnews.io/docs/v4

    Args:
        api_key: GNews API key
        max_articles: Max articles per category
        pipeline_date: Pipeline date YYYY-MM-DD for time window filtering
    """
    if not api_key:
        print("[WARN] GNews API key not configured, skipping international news")
        return []

    start_utc, end_utc = build_n1_to_n_window(pipeline_date)

    base_url = CONFIG["news"]["gnews"]["base_url"]
    articles = []
    skipped = 0

    for category in ["general", "world", "business", "technology"]:
        url = f"{base_url}/top-headlines"
        params = {
            "category": category,
            "lang": "en",
            "max": max_articles,
            "apikey": api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("articles", []):
                pub_str = article.get("publishedAt", "")
                if pub_str:
                    try:
                        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                        if not in_window(pub_dt, start_utc, end_utc):
                            skipped += 1
                            continue
                    except (ValueError, TypeError):
                        pass
                articles.append({
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "published_at": pub_str,
                    "category": category,
                    "origin": "gnews",
                })
        except requests.RequestException as e:
            print(f"[ERROR] GNews {category} collection failed: {e}")

    # Deduplicate by title
    seen_titles = set()
    unique = []
    for a in articles:
        if a["title"] not in seen_titles:
            seen_titles.add(a["title"])
            unique.append(a)

    if skipped:
        print(f"  [freshness] GNews: dropped {skipped} articles outside N-1~N window")
    print(f"[OK] GNews collected {len(unique)} international news articles")
    return unique


def collect_rss_feeds(pipeline_date: str = None) -> list[dict]:
    """
    Collect news from RSS feeds configured in config/sources.json.

    Args:
        pipeline_date: Pipeline date YYYY-MM-DD for time window filtering
    """
    feeds = CONFIG["news"].get("rss_feeds", CONFIG["news"].get("china_rss", {}).get("feeds", []))
    articles = []

    start_utc, end_utc = build_n1_to_n_window(pipeline_date)
    skipped = 0

    for feed_config in feeds:
        feed_url = feed_config["url"]
        source = feed_config["source"]
        category = feed_config.get("category", "general")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                pub_str = entry.get("published", "")
                if pub_str:
                    try:
                        pub_dt = parsedate_to_datetime(pub_str)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                        if not in_window(pub_dt, start_utc, end_utc):
                            skipped += 1
                            continue
                    except (ValueError, TypeError, IndexError):
                        pass

                # Extract full text from content:encoded (RSS full article)
                raw_content = ""
                if hasattr(entry, "content") and entry.content:
                    raw_content = entry.content[0].get("value", "")
                if not raw_content:
                    raw_content = entry.get("summary", "") or entry.get("description", "") or ""
                clean_text = re.sub(r"<[^>]+>", "", raw_content).strip()
                clean_text = re.sub(r"\s+", " ", clean_text)
                description = clean_text[:2000]

                articles.append({
                    "source": source,
                    "title": entry.get("title", ""),
                    "description": description,
                    "url": entry.get("link", ""),
                    "published_at": pub_str,
                    "category": category,
                    "origin": "rss",
                })
        except Exception as e:
            print(f"[ERROR] {source} RSS collection failed: {e}")

    if skipped:
        print(f"  [freshness] RSS: dropped {skipped} articles outside N-1~N window")
    print(f"[OK] RSS feeds collected {len(articles)} articles")
    return articles


def main():
    import argparse
    parser = argparse.ArgumentParser(description="News collection: GNews + RSS")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    gnews_key = CONFIG["news"]["gnews"].get("api_key", "")
    gnews_articles = collect_gnews(gnews_key, pipeline_date=today)
    rss_articles = collect_rss_feeds(pipeline_date=today)

    result = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
        "gnews": gnews_articles,
        "rss_feeds": rss_articles,
        "total_count": len(gnews_articles) + len(rss_articles),
    }

    output_file = output_dir / "raw_news.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] News data saved to {output_file}")
    return result


if __name__ == "__main__":
    r = main()
    if r and r.get("total_count", 0) == 0:
        print("[WARN] News collection: 0 articles, all sources may have failed")
        sys.exit(1)
