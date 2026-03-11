#!/usr/bin/env python3
"""
AI/tech news collection script: Hacker News API + GitHub Trending + AI blog RSS.

All sources are free and require no API keys.
- Hacker News API: https://github.com/HackerNews/API
- GitHub Search API: https://docs.github.com/en/rest/search

Output: output/YYYY-MM-DD/raw_ai.json
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Project root directory
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))

HN_BASE = "https://hacker-news.firebaseio.com/v0"
GITHUB_API = "https://api.github.com"
CN_TZ = timezone(timedelta(hours=8))

# AI-related keyword filter
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "gpt", "claude", "openai", "anthropic", "gemini", "mistral",
    "transformer", "neural", "diffusion", "stable diffusion", "midjourney",
    "copilot", "agent", "rag", "embedding", "fine-tun", "lora",
    "langchain", "llamaindex", "vector database", "prompt",
    "sora", "deepseek", "qwen", "llama",
]


def build_n1_to_n_window(pipeline_date: str | None) -> tuple[datetime, datetime]:
    """Build strict time window: N-1 00:00:00 to N 23:59:59 (Asia/Shanghai). Returns UTC."""
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


def parse_iso_utc(value: str) -> datetime | None:
    """Parse an ISO datetime string to UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def fetch_hn_item(item_id: int) -> dict | None:
    """Fetch a single Hacker News item by ID."""
    try:
        resp = requests.get(f"{HN_BASE}/item/{item_id}.json", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_hn_top_comments(item_id: int, limit: int = 5) -> list[str]:
    """Fetch top N comments for a HN story."""
    item = fetch_hn_item(item_id)
    if not item:
        return []
    kid_ids = item.get("kids", [])[:limit * 2]
    comments = []
    for kid_id in kid_ids:
        if len(comments) >= limit:
            break
        comment = fetch_hn_item(kid_id)
        if comment and comment.get("text"):
            text = re.sub(r"<[^>]+>", "", comment["text"]).strip()
            text = re.sub(r"\s+", " ", text)
            if text:
                comments.append(text[:2000])
    return comments


def is_ai_related(title: str) -> bool:
    """Check if a title is AI-related based on keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in AI_KEYWORDS)


def collect_hn_top_stories(max_stories: int = 30, pipeline_date: str = None) -> list[dict]:
    """
    Collect AI-related stories from Hacker News top stories.
    Also collects high-score general tech stories.
    """
    try:
        resp = requests.get(f"{HN_BASE}/topstories.json", timeout=10)
        resp.raise_for_status()
        story_ids = resp.json()[:100]
    except requests.RequestException as e:
        print(f"[ERROR] HN top stories fetch failed: {e}")
        return []

    ai_stories = []
    start_utc, end_utc = build_n1_to_n_window(pipeline_date)
    start_ts = start_utc.timestamp()
    end_ts = end_utc.timestamp()

    for sid in story_ids:
        if len(ai_stories) >= max_stories:
            break
        item = fetch_hn_item(sid)
        if not item or item.get("type") != "story":
            continue
        item_ts = item.get("time", 0)
        if item_ts < start_ts or item_ts > end_ts:
            continue
        title = item.get("title", "")
        if is_ai_related(title):
            top_comments = []
            if item.get("score", 0) > 100:
                top_comments = fetch_hn_top_comments(sid)
            ai_stories.append({
                "title": title,
                "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "author": item.get("by", ""),
                "time": datetime.fromtimestamp(item_ts, tz=timezone.utc).isoformat(),
                "hn_url": f"https://news.ycombinator.com/item?id={sid}",
                "top_comments": top_comments,
                "origin": "hackernews",
            })

    # Also collect non-AI high-score tech stories
    general_tech = []
    for sid in story_ids:
        if len(general_tech) >= 10:
            break
        item = fetch_hn_item(sid)
        if not item or item.get("type") != "story":
            continue
        item_ts = item.get("time", 0)
        if item_ts < start_ts or item_ts > end_ts:
            continue
        title = item.get("title", "")
        if not is_ai_related(title) and item.get("score", 0) > 50:
            top_comments = []
            if item.get("score", 0) > 100:
                top_comments = fetch_hn_top_comments(sid)
            general_tech.append({
                "title": title,
                "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "author": item.get("by", ""),
                "time": datetime.fromtimestamp(item_ts, tz=timezone.utc).isoformat(),
                "hn_url": f"https://news.ycombinator.com/item?id={sid}",
                "top_comments": top_comments,
                "origin": "hackernews",
            })

    print(f"[OK] Hacker News: {len(ai_stories)} AI-related + {len(general_tech)} general tech")
    return ai_stories + general_tech


def collect_github_trending(pipeline_date: str = None) -> list[dict]:
    """
    Collect trending AI-related GitHub repositories.
    Uses search API + pushed:>date + sort:stars to simulate trending.
    """
    start_utc, end_utc = build_n1_to_n_window(pipeline_date)
    since_date = start_utc.strftime("%Y-%m-%d")

    queries = [
        "topic:artificial-intelligence",
        "topic:llm",
        "topic:machine-learning",
        "ai agent",
        "large language model",
    ]

    all_repos = []
    seen_names = set()

    for query in queries:
        url = f"{GITHUB_API}/search/repositories"
        params = {
            "q": f"{query} pushed:>{since_date}",
            "sort": "stars",
            "order": "desc",
            "per_page": 10,
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 403:
                print("[WARN] GitHub API rate limited, results may be incomplete")
                break
            resp.raise_for_status()
            data = resp.json()
            for repo in data.get("items", []):
                full_name = repo.get("full_name", "")
                if full_name not in seen_names:
                    pushed_at = parse_iso_utc(repo.get("pushed_at", ""))
                    if pushed_at and not (start_utc <= pushed_at <= end_utc):
                        continue
                    seen_names.add(full_name)
                    all_repos.append({
                        "name": full_name,
                        "description": repo.get("description", ""),
                        "url": repo.get("html_url", ""),
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language", ""),
                        "created_at": repo.get("created_at", ""),
                        "pushed_at": repo.get("pushed_at", ""),
                        "topics": repo.get("topics", []),
                        "origin": "github",
                    })
        except requests.RequestException as e:
            print(f"[ERROR] GitHub search '{query}' failed: {e}")

    all_repos.sort(key=lambda x: x["stars"], reverse=True)
    result = all_repos[:20]

    print(f"[OK] GitHub Trending AI repos: {len(result)}")
    return result


# AI company blog RSS feeds (configurable)
AI_BLOG_FEEDS = CONFIG.get("ai", {}).get("blog_feeds", [
    {"url": "https://openai.com/blog/rss.xml", "source": "OpenAI Blog"},
    {"url": "https://blog.google/technology/ai/rss/", "source": "Google AI Blog"},
])


def collect_ai_blogs(pipeline_date: str = None) -> list[dict]:
    """Collect AI company official blog posts from RSS feeds."""
    import feedparser

    window_start, window_end = build_n1_to_n_window(pipeline_date)
    result = []

    for feed_info in AI_BLOG_FEEDS:
        try:
            resp = requests.get(feed_info["url"], timeout=15,
                                headers={"User-Agent": "Mozilla/5.0 IntelFlow/1.0"})
            if resp.status_code != 200:
                print(f"  [WARN] {feed_info['source']} HTTP {resp.status_code}")
                continue
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:20]:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    try:
                        pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    except Exception:
                        continue
                    if pub_dt < window_start or pub_dt > window_end:
                        continue
                result.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "content": (entry.get("summary") or "")[:500],
                    "published_date": entry.get("published", ""),
                    "source": feed_info["source"],
                    "origin": "ai_blog",
                })
            print(f"  [OK] {feed_info['source']}: {sum(1 for r in result if r['source'] == feed_info['source'])} items")
        except Exception as e:
            print(f"  [WARN] {feed_info['source']} collection failed: {e}")

    print(f"[OK] AI official blogs: {len(result)} items")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI/tech news collection")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    hn_stories = collect_hn_top_stories(pipeline_date=today)
    github_repos = collect_github_trending(pipeline_date=today)
    ai_blogs = collect_ai_blogs(pipeline_date=today)

    result = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
        "hackernews": hn_stories,
        "github_trending": github_repos,
        "ai_blogs": ai_blogs,
        "total_count": len(hn_stories) + len(github_repos) + len(ai_blogs),
    }

    output_file = output_dir / "raw_ai.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] AI news data saved to {output_file}")
    return result


if __name__ == "__main__":
    r = main()
    if r and r.get("total_count", 0) == 0:
        print("[WARN] AI collection: 0 items, all sources may have failed")
        sys.exit(1)
