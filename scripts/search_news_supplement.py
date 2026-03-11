#!/usr/bin/env python3
"""
SerpAPI news supplement search script.

Acts as a third-tier fallback to supplement news missed by other APIs.

Tier 1 (free unlimited): AKShare / Hacker News / RSS feeds
Tier 2 (free with limits): GNews / FMP
Tier 3 (fallback search): SerpAPI Google Search <- this script

SerpAPI: https://serpapi.com/users/sign_up
Free tier: 250 searches/month (3-6 searches/day is sufficient)

Output: output/YYYY-MM-DD/raw_supplement.json
"""

import json
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))

SERPAPI_URL = "https://serpapi.com/search.json"


def search_google(query: str, api_key: str, num_results: int = 10) -> list[dict]:
    """Search Google via SerpAPI, returning structured results."""
    if not api_key:
        print("[WARN] SerpAPI key not configured, skipping supplement search")
        return []

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
        "hl": "en",
        "tbs": "qdr:d",  # Past 24 hours
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[ERROR] SerpAPI search failed: {e}")
        return []

    results = []
    for item in data.get("organic_results", [])[:num_results]:
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
            "source": item.get("source", ""),
            "date": item.get("date", ""),
        })

    return results


def search_google_news(query: str, api_key: str, num_results: int = 10) -> list[dict]:
    """Search Google News via SerpAPI for news-specific results."""
    if not api_key:
        return []

    params = {
        "engine": "google_news",
        "q": f"when:1d {query}",
        "api_key": api_key,
        "hl": "en",
        "gl": "us",
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[ERROR] SerpAPI Google News search failed: {e}")
        return []

    results = []
    for item in data.get("news_results", [])[:num_results]:
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
            "source": item.get("source", {}).get("name", "") if isinstance(item.get("source"), dict) else str(item.get("source", "")),
            "date": item.get("date", ""),
        })

    return results


def collect_supplement(api_key: str, date_str: str = "") -> dict:
    """
    Run targeted searches across key dimensions to fill gaps.
    Consumes 3-6 API calls per day (well within 250/month free tier).
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    from datetime import timedelta
    pd = datetime.strptime(date_str, "%Y-%m-%d")
    target = pd - timedelta(days=1)
    target_str = target.strftime("%Y-%m-%d")
    print(f"[INFO] SerpAPI search target date: {target_str} (N-1)")

    searches = {
        "ai_news": {
            "queries": [
                f"AI artificial intelligence latest news {target_str}",
            ],
            "description": "AI/artificial intelligence news",
        },
        "finance_news": {
            "queries": [
                f"stock market earnings report analysis {target_str}",
            ],
            "description": "Finance/earnings analysis",
        },
        "world_news": {
            "queries": [
                f"world news headlines today {target_str}",
            ],
            "description": "World/international news",
        },
        "seo_news": {
            "queries": [
                f"SEO Google algorithm update {target_str}",
            ],
            "description": "SEO/search ecosystem",
        },
        "startup_news": {
            "queries": [
                f"indie hacker SaaS startup launch {target_str}",
            ],
            "description": "Startups/indie development",
        },
        "monetization_news": {
            "queries": [
                f"creator economy monetization growth strategy {target_str}",
            ],
            "description": "Growth/monetization/creator economy",
        },
    }

    results = {}
    total_searches = 0

    for category, config in searches.items():
        category_results = []
        for query in config["queries"]:
            items = search_google_news(query, api_key, num_results=10)
            if not items:
                items = search_google(query, api_key, num_results=10)
            total_searches += 1

            for item in items:
                item["category"] = category
                item["query"] = query
                item["origin"] = "serpapi_supplement"
                category_results.append(item)

        # Deduplicate by title
        seen = set()
        unique = []
        for item in category_results:
            if item["title"] not in seen:
                seen.add(item["title"])
                unique.append(item)
        results[category] = unique
        print(f"[OK] SerpAPI supplement - {config['description']}: {len(unique)} items")

    print(f"[OK] Total SerpAPI searches consumed: {total_searches}")
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SerpAPI supplement search")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = CONFIG.get("supplement", {}).get("serpapi", {}).get("api_key", "")
    if not api_key:
        api_key = CONFIG.get("images", {}).get("serpapi", {}).get("api_key", "")

    results = collect_supplement(api_key, today)

    output = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
        **results,
        "total_count": sum(len(v) for v in results.values()),
    }

    output_file = output_dir / "raw_supplement.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Supplement search data saved to {output_file}")
    return output


if __name__ == "__main__":
    main()
