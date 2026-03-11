#!/usr/bin/env python3
"""
IntelFlow plugin: Generic RSS feed collector.

Reads RSS feed URLs from config/sources.json (rss_feeds section),
fetches recent articles, and writes plugin output JSON files per
dimension so that run_pipeline.py can inject them as extra context.

Usage:
    python3 plugins/collect_rss.py --date 2026-03-11 --output output/2026-03-11

Output:
    output/{date}/plugin_rss_{category}.json  (one file per RSS category)

Each output file maps to the focus.json dimension that matches the
category name (e.g. rss_feeds.ai_tech → dimension ai_tech).
Config mapping can be overridden via sources.json "rss_dimension_map".
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Bootstrap: add scripts/ to path so we can use project utilities
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from utils import load_sources_config, save_json, CONFIG_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [collect_rss] %(levelname)s: %(message)s",
)
log = logging.getLogger("collect_rss")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FEED_TIMEOUT = 20        # seconds per feed HTTP request
MAX_ITEMS_PER_FEED = 10  # articles to take per feed URL
MAX_FEEDS_PER_CATEGORY = 15  # don't hammer too many feeds per category
RECENT_DAYS = 2          # only include articles from the last N days


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> Optional[datetime]:
    """Try to parse a date string from RSS (RFC 2822 or ISO 8601)."""
    if not date_str:
        return None
    # RFC 2822 (most RSS)
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    # ISO 8601 / Atom
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _is_recent(pub_date: Optional[datetime], cutoff: datetime) -> bool:
    if pub_date is None:
        return True  # include items with no date (can't filter)
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    return pub_date >= cutoff


def _clean_text(text: str, max_chars: int = 400) -> str:
    """Strip leading/trailing whitespace and truncate."""
    if not text:
        return ""
    cleaned = " ".join(text.split())
    return cleaned[:max_chars] + ("..." if len(cleaned) > max_chars else "")


def _fetch_feed(url: str, cutoff: datetime) -> list[dict]:
    """Fetch and parse one RSS/Atom feed URL. Returns normalized item dicts."""
    try:
        resp = requests.get(
            url,
            timeout=FEED_TIMEOUT,
            headers={"User-Agent": "IntelFlow/2.0 feed reader"},
        )
        resp.raise_for_status()
        content = resp.content
    except requests.RequestException as exc:
        log.warning("Feed fetch failed %s: %s", url, exc)
        return []

    items: list[dict] = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        log.warning("Feed parse error %s: %s", url, exc)
        return []

    # Detect feed type
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # --- RSS 2.0 ---
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item")[:MAX_ITEMS_PER_FEED]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            desc = item.findtext("description", "").strip()
            pub_raw = item.findtext("pubDate", "")
            pub_date = _parse_date(pub_raw)

            if not _is_recent(pub_date, cutoff):
                continue

            items.append({
                "title": title,
                "url": link,
                "content": _clean_text(desc),
                "published": pub_date.isoformat() if pub_date else "",
            })
        return items

    # --- Atom 1.0 ---
    entries = root.findall("atom:entry", ns) or root.findall("{http://www.w3.org/2005/Atom}entry")
    for entry in entries[:MAX_ITEMS_PER_FEED]:
        def _find(tag: str) -> str:
            el = entry.find(f"atom:{tag}", ns) or entry.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
            return (el.text or "").strip() if el is not None else ""

        title = _find("title")
        pub_raw = _find("published") or _find("updated")
        pub_date = _parse_date(pub_raw)

        if not _is_recent(pub_date, cutoff):
            continue

        # Atom link is an element with href attribute
        link_el = entry.find("atom:link", ns) or entry.find("{http://www.w3.org/2005/Atom}link")
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        summary = _find("summary") or _find("content")

        items.append({
            "title": title,
            "url": link,
            "content": _clean_text(summary),
            "published": pub_date.isoformat() if pub_date else "",
        })

    return items


# ---------------------------------------------------------------------------
# Main collection logic
# ---------------------------------------------------------------------------

def _default_dimension_map() -> dict[str, str]:
    """Return a best-guess RSS category → focus.json dimension mapping."""
    return {
        "ai_tech": "ai_tech",
        "ai": "ai_tech",
        "tech": "ai_tech",
        "technology": "ai_tech",
        "finance": "finance",
        "market": "finance",
        "markets": "finance",
        "seo": "seo",
        "search": "seo",
        "startup": "startup",
        "startups": "startup",
        "business": "startup",
        "ecommerce": "ecommerce",
        "creator": "creator",
        "creators": "creator",
        "macro": "macro",
        "policy": "macro",
        "news": "macro",
    }


def collect(date_str: str, output_dir: Path) -> int:
    """Fetch RSS feeds and write plugin_rss_{category}.json files.

    Returns the total number of articles collected.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources = load_sources_config()
    rss_feeds: dict[str, list[str]] = sources.get("rss_feeds", {})

    if not rss_feeds:
        log.info("No RSS feeds configured in sources.json, nothing to collect")
        return 0

    # Load optional custom dimension mapping from sources.json
    try:
        raw_sources = json.loads((ROOT / "config" / "sources.json").read_text("utf-8"))
        custom_map: dict[str, str] = raw_sources.get("rss_dimension_map", {})
    except Exception:
        custom_map = {}

    dim_map = {**_default_dimension_map(), **custom_map}

    # Recency cutoff
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=RECENT_DAYS)

    # Collect per category
    total_articles = 0
    per_dimension: dict[str, list[dict]] = {}

    for category, urls in rss_feeds.items():
        if not isinstance(urls, list) or not urls:
            continue

        log.info("Category: %s (%d feeds)", category, len(urls))
        category_items: list[dict] = []

        for url in urls[:MAX_FEEDS_PER_CATEGORY]:
            items = _fetch_feed(url, cutoff)
            category_items.extend(items)
            if items:
                log.debug("  %s: %d items", url, len(items))

        # Deduplicate by URL
        seen: set[str] = set()
        deduped: list[dict] = []
        for item in category_items:
            u = item.get("url", "")
            if u and u not in seen:
                seen.add(u)
                deduped.append(item)

        # Sort by published date descending (most recent first)
        deduped.sort(key=lambda x: x.get("published", ""), reverse=True)

        log.info("  -> %d unique articles (from %d)", len(deduped), len(category_items))

        # Map to dimension
        dimension = dim_map.get(category.lower(), category)

        if deduped:
            if dimension not in per_dimension:
                per_dimension[dimension] = []
            per_dimension[dimension].extend(deduped)
            total_articles += len(deduped)

    # Write one output file per dimension
    for dimension, items in per_dimension.items():
        # Keep top 30 items per dimension to stay within LLM context limits
        items = items[:30]
        out_file = output_dir / f"plugin_rss_{dimension}.json"
        save_json({"dimension": dimension, "items": items}, out_file)
        log.info("Written: %s (%d items)", out_file.name, len(items))

    log.info("RSS collection complete: %d articles across %d dimensions",
             total_articles, len(per_dimension))
    return total_articles


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect RSS feeds and emit plugin JSON for IntelFlow pipeline"
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date string YYYY-MM-DD",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory (e.g. output/2026-03-11)",
    )
    args = parser.parse_args()

    total = collect(args.date, Path(args.output))
    sys.exit(0 if total >= 0 else 1)


if __name__ == "__main__":
    main()
