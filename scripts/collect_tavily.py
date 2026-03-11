#!/usr/bin/env python3
"""
Tavily Search API collection script: cross-dimensional deep search.

Tavily is a search API designed for AI agents, providing high-quality
structured search results. Uses advanced search depth + AI summaries.

API docs: https://tavily.com
Free tier: 1000 searches/month

Output: output/YYYY-MM-DD/raw_tavily.json
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Project root directory
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Multi-dimensional search queries with daily rotation
# Design principles:
# 1. Don't hardcode big company names (HN+GNews already cover them)
# 2. Multiple query sets per dimension, rotated by day of week
# 3. Prioritize product discovery, builder insights, real case studies
SEARCH_QUERIES_POOL = {
    "ai_tools_discovery": {
        "label": "AI Tool Discovery (rotating)",
        "queries_rotation": [
            ["new AI tool launched this week site:producthunt.com OR site:theresanaiforthat.com",
             "AI automation workflow tool indie developer built"],
            ["AI agent new product ship developer launched",
             "open source AI project new release GitHub"],
            ["AI writing code productivity tool new feature",
             "small AI startup product launch revenue milestone"],
            ["AI tool niche vertical industry-specific launched",
             "AI replacing specific workflow use case real user"],
        ],
    },
    "builder_indie": {
        "label": "Builder Insights & Pain Points (rotating)",
        "queries_rotation": [
            ["indie hacker launched SaaS revenue first month",
             "side project passive income how built"],
            ["micro SaaS $1000 MRR milestone bootstrapped",
             "solopreneur product launched ProductHunt today"],
            ["reddit entrepreneur pain point business problem unsolved",
             "r/SideProject new launch feedback"],
            ["bootstrapped founder revenue update case study",
             "build in public week update shipped"],
        ],
    },
    "seo_traffic": {
        "label": "SEO & Traffic (rotating)",
        "queries_rotation": [
            ["Google search ranking change impact website traffic",
             "AI search SGE impact SEO organic traffic real data"],
            ["SEO case study traffic growth what worked",
             "content strategy ranking without backlinks"],
            ["search intent change user behavior new keyword trend",
             "zero click search featured snippet optimization"],
            ["niche site income report traffic source breakdown",
             "programmatic SEO results case study"],
        ],
    },
    "ecommerce_product": {
        "label": "Ecommerce Product Opportunities (rotating)",
        "queries_rotation": [
            ["Shopify store niche product winning $10k month",
             "dropshipping product trending high margin"],
            ["WordPress plugin new feature revenue indie developer",
             "WooCommerce store case study conversion rate"],
            ["print on demand digital product passive income creator",
             "Etsy seller new product category trending"],
            ["ecommerce customer acquisition cost comparison channel",
             "subscription box niche market new launch"],
        ],
    },
    "growth_monetization": {
        "label": "Growth & Monetization (rotating)",
        "queries_rotation": [
            ["newsletter monetization sponsor revenue how",
             "paid community membership pricing strategy"],
            ["landing page conversion rate optimization AB test result",
             "cold email outreach B2B conversion rate real"],
            ["YouTube channel monetization milestone case study",
             "Twitter X growth strategy follower engagement"],
            ["affiliate marketing niche site income report",
             "digital product launch sales strategy"],
        ],
    },
    "startup_opportunity": {
        "label": "Market Opportunities (rotating)",
        "queries_rotation": [
            ["untapped market opportunity small business",
             "emerging trend early signal niche growing fast"],
            ["regulation change business impact new opportunity",
             "tech market new product foreign company"],
            ["VC seed funding new sector bet thesis",
             "startup acqui-hire shutdown lesson learned"],
            ["B2B SaaS new vertical underserved market",
             "consumer behavior shift new habit formed"],
        ],
    },
}


def get_todays_queries(pipeline_date: str = None) -> dict:
    """Select today's query rotation based on day of week."""
    if pipeline_date:
        weekday = datetime.strptime(pipeline_date, "%Y-%m-%d").weekday()
    else:
        weekday = datetime.now().weekday()

    result = {}
    for category, config in SEARCH_QUERIES_POOL.items():
        rotations = config["queries_rotation"]
        idx = weekday % len(rotations)
        result[category] = {
            "label": config["label"],
            "queries": rotations[idx],
        }
    return result


def tavily_search(query: str, api_key: str, max_results: int = 10) -> dict:
    """Execute a single Tavily deep search."""
    if not api_key:
        print("[WARN] Tavily API key not configured, skipping search")
        return {"answer": "", "results": []}

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": False,
        "max_results": max_results,
        "days": 2,
    }

    try:
        resp = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {
            "answer": data.get("answer", ""),
            "results": data.get("results", []),
        }
    except requests.RequestException as e:
        print(f"[ERROR] Tavily search failed (query={query!r}): {e}")
        return {"answer": "", "results": []}


def collect_tavily(api_key: str, pipeline_date: str = None) -> dict:
    """
    Run all dimensional search queries, collect and deduplicate results.
    """
    all_results = {}
    seen_urls = set()
    total_raw = 0
    total_deduped = 0

    if pipeline_date:
        pd = datetime.strptime(pipeline_date, "%Y-%m-%d")
    else:
        pd = datetime.now()
    target_date = pd - timedelta(days=1)
    date_prefix = f"{target_date.strftime('%B %d %Y')} OR {pd.strftime('%B %d %Y')}"
    print(f"[INFO] Tavily search date anchor: {target_date.strftime('%Y-%m-%d')} (N-1)")

    todays_queries = get_todays_queries(pipeline_date)

    for category, config in todays_queries.items():
        category_results = []
        category_answers = []

        for query in config["queries"]:
            dated_query = f"{date_prefix} {query}"
            print(f"[...] Tavily search: {dated_query}")
            data = tavily_search(dated_query, api_key)

            if data["answer"]:
                category_answers.append({
                    "query": query,
                    "answer": data["answer"],
                })

            for item in data["results"]:
                total_raw += 1
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    total_deduped += 1
                    category_results.append({
                        "title": item.get("title", ""),
                        "url": url,
                        "content": item.get("content", ""),
                        "score": item.get("score", 0),
                        "category": category,
                        "origin": "tavily",
                    })

            time.sleep(0.5)

        all_results[category] = {
            "label": config["label"],
            "answers": category_answers,
            "results": category_results,
        }
        print(f"[OK] Tavily {config['label']}: {len(category_results)} items (deduplicated)")

    print(f"[OK] Tavily total: {total_raw} raw -> {total_deduped} deduplicated")
    return all_results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tavily search collection")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = CONFIG.get("tavily", {}).get("api_key", "")
    if not api_key:
        print("[ERROR] Tavily API key not configured in config/sources.json")
        return None

    results = collect_tavily(api_key, pipeline_date=today)

    total_results = sum(len(v["results"]) for v in results.values())
    total_answers = sum(len(v["answers"]) for v in results.values())

    output = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
        "source": "tavily_search_api",
        "search_depth": "advanced",
        "time_range": "n-1_to_n",
        **results,
        "total_count": total_results,
        "total_answers": total_answers,
    }

    output_file = output_dir / "raw_tavily.json"
    output_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Tavily data saved to {output_file}")
    return output


if __name__ == "__main__":
    main()
