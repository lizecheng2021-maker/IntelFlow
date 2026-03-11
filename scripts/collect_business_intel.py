#!/usr/bin/env python3
"""
Business intelligence collection script: RSS feeds + Reddit.

Covers multiple dimensions:
  - SEO & search ecosystem
  - Indie sites & ecommerce
  - Growth & monetization
  - Startups & business models
  - Creator economy & personal brand
  - Tech media & product discovery

All sources are free RSS feeds and Reddit public RSS (no API key needed).

Output: output/YYYY-MM-DD/raw_business.json
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

# Project root directory
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
CN_TZ = timezone(timedelta(hours=8))

# RSS feed configuration by category
FEEDS = {
    "seo_search": {
        "label": "SEO & Search",
        "sources": [
            {"url": "https://www.searchenginejournal.com/feed/", "source": "Search Engine Journal"},
            {"url": "https://moz.com/blog/feed", "source": "Moz Blog"},
            {"url": "https://ahrefs.com/blog/feed/", "source": "Ahrefs Blog"},
            {"url": "https://searchengineland.com/feed", "source": "Search Engine Land"},
            {"url": "https://blog.google/rss/", "source": "Google Blog"},
            {"url": "https://www.seroundtable.com/feed", "source": "SE Roundtable"},
        ],
    },
    "indie_ecommerce": {
        "label": "Indie Sites & Ecommerce",
        "sources": [
            {"url": "https://wptavern.com/feed", "source": "WP Tavern"},
            {"url": "https://www.shopify.com/blog.atom", "source": "Shopify Blog"},
            {"url": "https://woocommerce.com/feed/", "source": "WooCommerce Blog"},
        ],
    },
    "growth_monetization": {
        "label": "Growth & Monetization",
        "sources": [
            {"url": "https://stratechery.com/feed/", "source": "Stratechery"},
            {"url": "https://www.notboring.co/feed", "source": "Not Boring"},
            {"url": "https://neilpatel.com/blog/feed/", "source": "Neil Patel Blog"},
        ],
    },
    "startup_business": {
        "label": "Startups & Business",
        "sources": [
            {"url": "https://www.producthunt.com/feed", "source": "ProductHunt"},
            {"url": "https://www.indiehackers.com/feed.xml", "source": "IndieHackers"},
            {"url": "https://simonwillison.net/atom/everything/", "source": "Simon Willison"},
            {"url": "https://thebootstrappedfounder.com/feed/", "source": "Bootstrapped Founder"},
            {"url": "https://www.ycombinator.com/blog/rss/", "source": "Y Combinator Blog"},
        ],
    },
    "tech_media": {
        "label": "Tech Media",
        "sources": [
            {"url": "https://techcrunch.com/feed/", "source": "TechCrunch"},
            {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge"},
            {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica"},
            {"url": "https://www.technologyreview.com/feed/", "source": "MIT Technology Review"},
        ],
    },
    "product_discovery": {
        "label": "Product Discovery",
        "sources": [
            {"url": "https://hnrss.org/show", "source": "HN Show"},
            {"url": "https://lobste.rs/rss", "source": "Lobsters"},
            {"url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml", "source": "GitHub Trending"},
        ],
    },
    "creator_economy": {
        "label": "Creator Economy",
        "sources": [
            {"url": "https://www.lennysnewsletter.com/feed", "source": "Lenny's Newsletter"},
            {"url": "https://seths.blog/feed/", "source": "Seth Godin"},
        ],
    },
}

# Reddit subreddits for business pain points
REDDIT_SUBS = [
    {"subreddit": "Entrepreneur", "label": "Entrepreneurs"},
    {"subreddit": "SideProject", "label": "Side Projects"},
    {"subreddit": "startups", "label": "Startups"},
    {"subreddit": "smallbusiness", "label": "Small Business"},
    {"subreddit": "SEO", "label": "SEO Discussion"},
    {"subreddit": "juststart", "label": "Just Start"},
    {"subreddit": "digital_marketing", "label": "Digital Marketing"},
    {"subreddit": "SaaS", "label": "SaaS Products"},
]


def build_n1_to_n_window_utc_naive(pipeline_date: str) -> tuple[datetime, datetime]:
    """
    Build strict time window: N-1 00:00:00 to N 23:59:59 (Asia/Shanghai).
    Returns naive UTC datetimes for comparison with feedparser output.
    """
    day_start_cn = datetime.strptime(pipeline_date, "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=CN_TZ
    )
    window_start_cn = day_start_cn - timedelta(days=1)
    window_end_cn = day_start_cn + timedelta(days=1) - timedelta(seconds=1)
    start_utc = window_start_cn.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = window_end_cn.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def parse_published_date(entry: dict) -> datetime | None:
    """Attempt to parse publication time from an RSS entry."""
    time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if time_struct:
        try:
            return datetime(*time_struct[:6])
        except Exception:
            return None
    return None


def fetch_feed(feed_url: str, source_name: str, window_start: datetime, window_end: datetime) -> list[dict]:
    """
    Fetch a single RSS feed, keeping only entries within the time window.
    """
    try:
        resp = requests.get(feed_url, timeout=15, headers={
            "User-Agent": "IntelFlow/1.0 (RSS Reader)",
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except requests.RequestException as e:
        print(f"[ERROR] {source_name} RSS fetch failed: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] {source_name} RSS parse failed: {e}")
        return []

    articles = []
    for entry in feed.entries:
        pub_date = parse_published_date(entry)
        if pub_date and (pub_date < window_start or pub_date > window_end):
            continue

        raw_content = ""
        if hasattr(entry, "content") and entry.content:
            raw_content = entry.content[0].get("value", "")
        if not raw_content:
            raw_content = entry.get("summary", "") or entry.get("description", "") or ""
        clean_text = re.sub(r"<[^>]+>", "", raw_content).strip()
        clean_text = re.sub(r"\s+", " ", clean_text)
        summary = clean_text[:5000]

        published_str = ""
        if pub_date:
            published_str = pub_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            published_str = entry.get("published", "") or entry.get("updated", "")

        articles.append({
            "title": entry.get("title", "").strip(),
            "url": entry.get("link", ""),
            "source": source_name,
            "published_date": published_str,
            "summary": summary,
        })

    return articles


def collect_category(
    category_key: str,
    category_config: dict,
    window_start: datetime,
    window_end: datetime,
) -> list[dict]:
    """Collect all RSS sources for a given category."""
    label = category_config["label"]
    all_articles = []

    for feed_config in category_config["sources"]:
        articles = fetch_feed(feed_config["url"], feed_config["source"], window_start, window_end)
        all_articles.extend(articles)

    # Deduplicate by title
    seen_titles = set()
    unique = []
    for a in all_articles:
        if a["title"] and a["title"] not in seen_titles:
            seen_titles.add(a["title"])
            unique.append(a)

    print(f"[OK] {label}: collected {len(unique)} items")
    return unique


def _rss_fetch_comments(post_url: str, limit: int = 3) -> list[str]:
    """
    Fetch Reddit post comments via RSS (bypasses .json API blocks).
    """
    rss_url = post_url.replace("www.reddit.com", "old.reddit.com").rstrip("/") + "/.rss"
    try:
        resp = requests.get(rss_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception:
        return []

    comments = []
    for entry in feed.entries[1:]:  # Skip first entry (the post itself)
        if len(comments) >= limit:
            break
        raw = ""
        if hasattr(entry, "content") and entry.content:
            raw = entry.content[0].get("value", "")
        if not raw:
            raw = entry.get("summary", "") or ""
        body = re.sub(r"<[^>]+>", "", raw).strip()
        body = re.sub(r"\s+", " ", body)
        author = entry.get("author", "")
        if "AutoModerator" in author or len(body) < 20:
            continue
        if body:
            comments.append(body[:1500])
    return comments


def fetch_reddit_hot(
    subreddit: str,
    label: str,
    limit: int = 25,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[dict]:
    """
    Fetch hot posts from a Reddit subreddit via native RSS.
    Zero external dependencies, zero API keys, not affected by IP blocks.
    """
    import time

    url = f"https://old.reddit.com/r/{subreddit}/top/.rss?t=week"
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"[ERROR] Reddit RSS r/{subreddit} fetch failed: {e}")
        return []

    posts = []
    total_entries = len(feed.entries)

    for i, entry in enumerate(feed.entries):
        if len(posts) >= 15:
            break

        pub_date = parse_published_date(entry)
        if pub_date and window_start and window_end and (pub_date < window_start or pub_date > window_end):
            continue

        raw_content = ""
        if hasattr(entry, "content") and entry.content:
            raw_content = entry.content[0].get("value", "")
        if not raw_content:
            raw_content = entry.get("summary", "") or ""
        clean_text = re.sub(r"<[^>]+>", "", raw_content).strip()
        clean_text = re.sub(r"\s+", " ", clean_text)[:5000]

        post_url = entry.get("link", "")
        position_score = max(total_entries - i, 1)

        # Fetch comments for top 5 posts
        top_comments = []
        if i < 5 and post_url:
            top_comments = _rss_fetch_comments(post_url, limit=3)
            time.sleep(0.5)

        posts.append({
            "title": entry.get("title", "").strip(),
            "url": post_url,
            "source": f"Reddit r/{subreddit}",
            "subreddit": subreddit,
            "score": position_score,
            "num_comments": len(top_comments),
            "selftext": clean_text,
            "top_comments": top_comments,
            "published_date": pub_date.strftime("%Y-%m-%d %H:%M:%S") if pub_date else "",
        })

    return posts


def collect_reddit(window_start: datetime, window_end: datetime) -> list[dict]:
    """Collect hot posts from all configured Reddit subreddits via RSS."""
    import time
    all_posts = []
    for sub_config in REDDIT_SUBS:
        posts = fetch_reddit_hot(
            sub_config["subreddit"],
            sub_config["label"],
            window_start=window_start,
            window_end=window_end,
        )
        all_posts.extend(posts)
        print(f"[OK] Reddit r/{sub_config['subreddit']}: collected {len(posts)} posts")
        time.sleep(1)

    # Deduplicate by title
    seen = set()
    unique = []
    for p in all_posts:
        if p["title"] and p["title"] not in seen:
            seen.add(p["title"])
            unique.append(p)

    unique.sort(key=lambda x: x["score"], reverse=True)
    unique = unique[:50]

    print(f"[OK] Reddit business intelligence: {len(unique)} hot posts total")
    return unique


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Business intelligence collection")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    window_start, window_end = build_n1_to_n_window_utc_naive(today)
    print(f"[INFO] Business intel time window: {window_start} ~ {window_end} (UTC)")

    result = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
    }

    total_count = 0
    for category_key, category_config in FEEDS.items():
        articles = collect_category(category_key, category_config, window_start, window_end)
        result[category_key] = articles
        total_count += len(articles)

    # Reddit hot posts
    reddit_posts = collect_reddit(window_start, window_end)
    result["reddit_business_painpoints"] = reddit_posts
    total_count += len(reddit_posts)

    result["total_count"] = total_count

    output_file = output_dir / "raw_business.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Business intel saved to {output_file} ({total_count} items, including {len(reddit_posts)} Reddit)")
    return result


if __name__ == "__main__":
    main()
