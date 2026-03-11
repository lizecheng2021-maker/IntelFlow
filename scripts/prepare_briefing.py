#!/usr/bin/env python3
"""
Two-stage AI preprocessing engine: raw_*.json -> briefing.json

Core features:
- Scoring and ranking of collected items
- Token budget control per dimension
- Content density labeling (FULL/MEDIUM/TITLE_ONLY)
- Cross-reference detection across dimensions
- Cross-day deduplication (exact + fuzzy entity matching)
- Cross-day topic penalty (reduce score for repeated topics)
- YouTube transcript proper noun correction (fuzzy matching)

Output: output/YYYY-MM-DD/briefing.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parent.parent

# Token budgets (in characters)
# Each dimension gets its own LLM call, so budgets are generous
BUDGETS = {
    "youtube": 150000,
    "ai": 100000,
    "business": 80000,
    "seo": 50000,
    "finance": 50000,
    "news": 50000,
    "lunar": 5000,
    "tavily": 60000,
    "cross_ref": 5000,
}

# ============================================================
# YouTube transcript proper noun correction
# ============================================================

# Canonical AI/tech proper nouns
CANONICAL_NAMES = {
    "Anthropic", "OpenAI", "Google", "Meta", "Microsoft", "Mistral",
    "DeepSeek", "Stability AI", "Cohere", "Groq", "Replicate",
    "Claude", "ChatGPT", "GPT", "Gemini", "LLaMA", "Midjourney", "DALL-E",
    "Copilot", "Cursor", "Perplexity", "Sora", "Whisper", "Grok",
    "Claude Code", "Claude Sonnet", "Claude Opus", "Claude Haiku",
    "Manus", "AutoGPT", "AgentGPT", "Browser Use",
    "LangChain", "LlamaIndex", "CrewAI",
    "GitHub", "Vercel", "Supabase", "Cloudflare", "WordPress",
    "Hugging Face", "Replit", "Windsurf",
    "Sam Altman", "Dario Amodei", "Elon Musk", "Satya Nadella",
}

# Known high-frequency transcription errors (exact replacement)
EXACT_CORRECTIONS = {
    "Chat GBT": "ChatGPT", "chat GBT": "ChatGPT", "Chat GPT": "ChatGPT",
    "G P T": "GPT", "Open A I": "OpenAI",
}

FUZZY_SKIP = {"Maui", "Manor", "Manual", "Manga", "Many", "Main", "Man"}


def _build_fuzzy_index():
    index = {}
    for name in CANONICAL_NAMES:
        index[name.lower()] = name
        for word in name.split():
            if len(word) >= 4:
                index[word.lower()] = word
    return index

_FUZZY_INDEX = _build_fuzzy_index()


def _fuzzy_correct_word(word: str) -> str | None:
    if len(word) < 4 or word in FUZZY_SKIP:
        return None
    if word.lower() in _FUZZY_INDEX:
        return None
    best_match = None
    best_ratio = 0.0
    for canonical_lower, canonical in _FUZZY_INDEX.items():
        ratio = SequenceMatcher(None, word.lower(), canonical_lower).ratio()
        if ratio > best_ratio and ratio >= 0.75:
            best_ratio = ratio
            best_match = canonical
    if best_match and word[0].lower() == best_match[0].lower():
        return best_match
    return None


def fix_transcript_errors(data, depth=0):
    """Recursively fix transcript errors: exact replacement + fuzzy matching."""
    if depth > 10:
        return data
    if isinstance(data, str):
        for wrong, correct in EXACT_CORRECTIONS.items():
            data = data.replace(wrong, correct)
        words = re.split(r'(\s+|[,;:!?.()"\'\-])', data)
        changed = False
        for i, w in enumerate(words):
            if len(w) >= 4 and w[0].isupper() and w.isalpha():
                correction = _fuzzy_correct_word(w)
                if correction and correction != w:
                    words[i] = correction
                    changed = True
        if changed:
            data = "".join(words)
        return data
    elif isinstance(data, list):
        return [fix_transcript_errors(item, depth + 1) for item in data]
    elif isinstance(data, dict):
        return {k: fix_transcript_errors(v, depth + 1) for k, v in data.items()}
    return data


# ============================================================
# Core utilities
# ============================================================

def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Cannot read {path.name}: {e}")
        return None


def density_label(content: str) -> str:
    length = len(content) if content else 0
    if length > 500:
        return "FULL"
    elif length > 100:
        return "MEDIUM"
    else:
        return "TITLE_ONLY"


def parse_item_date(item: dict) -> datetime | None:
    """Parse date from a data item, supporting multiple field names and formats."""
    date_fields = ["published_at", "publishedAt", "pub_date", "published",
                   "published_date", "date", "created_at", "timestamp", "time"]
    for field in date_fields:
        val = item.get(field)
        if not val:
            continue
        if isinstance(val, (int, float)):
            try:
                return datetime.fromtimestamp(val, tz=timezone.utc)
            except (ValueError, OSError):
                continue
        if not isinstance(val, str):
            continue
        cleaned_val = val.strip()
        if ", +0000 UTC" in cleaned_val:
            cleaned_val = cleaned_val.replace(", +0000 UTC", "")
        for fmt in [
            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z",
            "%m/%d/%Y, %I:%M %p", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y",
        ]:
            try:
                dt = datetime.strptime(cleaned_val, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
    return None


def is_fresh(item_date: datetime | None, window_start: datetime, window_end: datetime) -> bool:
    """Check if item falls within the N-1 to N time window."""
    if item_date is None:
        return True
    start = window_start.replace(tzinfo=timezone.utc) if window_start.tzinfo is None else window_start
    end = window_end.replace(tzinfo=timezone.utc) if window_end.tzinfo is None else window_end
    idate = item_date.replace(tzinfo=timezone.utc) if item_date.tzinfo is None else item_date
    return start <= idate <= end


def extract_keywords(text: str) -> set:
    words = re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}', text.lower())
    return set(words)


_NOISE_KEYWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "are",
    "was", "has", "but", "not", "its", "new", "can", "will", "all",
    "one", "out", "use", "also", "more", "they", "been", "their", "into",
    "would", "could", "about", "after", "which", "other", "what", "over",
    "ai", "model", "data", "tool", "tech", "app", "software", "platform",
}

_ENTITY_KEYWORDS = {
    "openai", "anthropic", "google", "microsoft", "apple", "meta", "amazon",
    "nvidia", "claude", "gemini", "chatgpt", "gpt", "deepseek", "mistral",
}


def load_recent_topics(pipeline_date: str, days: int = 5) -> set:
    """Load high-frequency topic keywords from recent days for cross-day penalty."""
    if not pipeline_date:
        return set()
    pd = datetime.strptime(pipeline_date, "%Y-%m-%d")
    recent_keywords = Counter()
    for i in range(1, days + 1):
        past_date = (pd - timedelta(days=i)).strftime("%Y-%m-%d")
        bf = ROOT / "output" / past_date / "briefing.json"
        if not bf.exists():
            continue
        try:
            data = json.loads(bf.read_text(encoding="utf-8"))
            # Scan all dimension arrays dynamically (not just hardcoded names)
            for section_key, section_data in data.items():
                if not isinstance(section_data, list):
                    continue
                for item in section_data[:30]:
                    if not isinstance(item, dict):
                        continue
                    text = (item.get("title") or "") + " " + (item.get("content") or "")[:200]
                    kws = extract_keywords(text)
                    entity_kws = (kws & _ENTITY_KEYWORDS) | (kws - _NOISE_KEYWORDS - _ENTITY_KEYWORDS)
                    for kw in entity_kws:
                        if len(kw) > 4:
                            recent_keywords[kw] += 1
        except Exception:
            continue
    return {kw for kw, cnt in recent_keywords.items() if cnt >= 2}


def detect_cross_references(all_items: list[dict]) -> dict[str, list[str]]:
    """Find topics appearing across 2+ dimensions."""
    keyword_sources = {}
    for item in all_items:
        keywords = extract_keywords((item.get("title") or "") + " " + (item.get("content") or "")[:200])
        dim = item.get("dimension", "unknown")
        for kw in keywords:
            if len(kw) > 3:
                keyword_sources.setdefault(kw, []).append((dim, item.get("title", "")))
    cross_refs = {}
    for kw, sources in keyword_sources.items():
        dims = set(s[0] for s in sources)
        if len(dims) >= 2:
            cross_refs[kw] = list(set(s[1] for s in sources))[:3]
    return cross_refs


def score_item(item: dict, cross_ref_keywords: set, recent_topics: set = None) -> float:
    score = 1.0
    title = item.get("title", "").lower()
    content = item.get("content", "")
    item_keywords = extract_keywords(title)
    if item_keywords & cross_ref_keywords:
        score += 2.0
    hn_score = item.get("score", 0)
    if hn_score > 200: score += 1.5
    elif hn_score > 100: score += 1.0
    elif hn_score > 50: score += 0.5
    if len(content) > 500: score += 1.0
    elif len(content) > 200: score += 0.5
    if item.get("top_comments") or item.get("comments", 0) > 10:
        score += 0.5
    if recent_topics:
        text_keywords = extract_keywords(title + " " + content[:200])
        overlap = text_keywords & recent_topics
        if len(overlap) >= 2:
            score *= 0.4
            item["_repeated_topic"] = True
    return score


def _youtube_category_to_dimension(category: str) -> str:
    """Map YouTube channel category to theme dimension."""
    cat = category.lower()
    if cat in ("ai_builder", "ai_eng", "ai_agency", "ai_automation", "ai"):
        return "ai"
    if cat in ("seo_builder", "seo_data", "ai_seo", "blogging_seo"):
        return "seo"
    if cat in ("ecommerce", "indie_hacker", "saas_builder", "content_builder", "wordpress"):
        return "business"
    if cat in ("finance",):
        return "finance"
    if cat in ("dev_builder", "startup"):
        return "ai"
    return "ai"


# ============================================================
# Dimension processors
# ============================================================

def process_youtube(data, budget, window_start=None, window_end=None):
    if not data:
        return []
    items = []
    for video in data.get("videos", []):
        if window_start and window_end and not is_fresh(parse_item_date(video), window_start, window_end):
            continue
        transcript = video.get("transcript", "")
        dim = _youtube_category_to_dimension(video.get("category", ""))
        items.append({
            "dimension": dim,
            "title": f"[YouTube {video.get('channel', '')}] {video.get('title', '')}",
            "content": transcript[:budget // max(len(data.get("videos", [])), 1)],
            "density": density_label(transcript),
            "url": video.get("url", ""),
            "source": f"youtube_{video.get('channel', '')}",
            "score": 5.0,
            "origin": "youtube",
        })
    items.sort(key=lambda x: len(x["content"]), reverse=True)
    return _trim_to_budget(items, budget)


def process_news(news_data, supplement_data, budget, window_start=None, window_end=None):
    items = []
    if news_data:
        for article in news_data.get("gnews", []) + news_data.get("rss_feeds", news_data.get("china_rss", [])):
            if window_start and window_end and not is_fresh(parse_item_date(article), window_start, window_end):
                continue
            items.append({
                "dimension": "news",
                "title": article.get("title", ""),
                "content": article.get("description", ""),
                "density": density_label(article.get("description", "")),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "category": article.get("category", ""),
                "score": 1.0,
            })
    if supplement_data:
        for article in supplement_data.get("results", []):
            if window_start and window_end and not is_fresh(parse_item_date(article), window_start, window_end):
                continue
            items.append({
                "dimension": "news",
                "title": article.get("title", ""),
                "content": article.get("snippet", ""),
                "density": density_label(article.get("snippet", "")),
                "url": article.get("link", ""),
                "source": "serpapi",
                "score": 0.8,
            })
    return _trim_to_budget(items, budget)


def process_finance(data, budget):
    if not data:
        return []
    items = []
    us = data.get("us_market", {})
    if us.get("movers"):
        gainers = us["movers"].get("gainers", [])[:5]
        losers = us["movers"].get("losers", [])[:5]
        text = "US top gainers: " + ", ".join(f"{g['symbol']}({g.get('change_pct',0):.1f}%)" for g in gainers)
        text += " | Top losers: " + ", ".join(f"{l['symbol']}({l.get('change_pct',0):.1f}%)" for l in losers)
        items.append({"dimension": "finance", "title": "US Market Movers", "content": text, "density": "DATA", "score": 2.0, "source": "yfinance", "url": ""})

    if us.get("sector_performance"):
        text = "US Sectors: " + ", ".join(f"{s['sector']}({s.get('change_pct','')})" for s in us["sector_performance"][:10])
        items.append({"dimension": "finance", "title": "US Sector Performance", "content": text, "density": "DATA", "score": 2.0, "source": "yfinance", "url": ""})

    ashare = data.get("a_share", {})
    if ashare.get("indices"):
        text = "A-share Indices: " + ", ".join(f"{i['name']}({i.get('change_pct',0):.2f}%)" for i in ashare["indices"])
        items.append({"dimension": "finance", "title": "A-share Major Indices", "content": text, "density": "DATA", "score": 2.0, "source": "AKShare", "url": ""})

    if ashare.get("sector_flow"):
        text = "Sector Flow: " + ", ".join(f"{s['sector']}(net:{s.get('net_inflow','')})" for s in ashare["sector_flow"][:10])
        items.append({"dimension": "finance", "title": "Sector Capital Flow", "content": text, "density": "DATA", "score": 2.5, "source": "AKShare", "url": ""})

    macro = data.get("macro", {})
    if macro:
        parts = []
        for key in ["cpi", "pmi", "m2"]:
            if macro.get(key):
                latest = macro[key][-1] if macro[key] else {}
                parts.append(f"{key.upper()}: {latest.get('value', latest.get('m2_value', 'N/A'))}")
        if parts:
            items.append({"dimension": "finance", "title": "Macro Indicators", "content": " | ".join(parts), "density": "DATA", "score": 2.0, "source": "AKShare", "url": ""})

    funds = data.get("funds", {})
    if funds.get("tracked_funds"):
        parts = []
        for f in funds["tracked_funds"]:
            parts.append(f"{f['name']}({f['code']})[{f.get('theme','')}] NAV={f.get('latest_nav',0)} W{f.get('week_return_pct',0):+.2f}% M{f.get('month_return_pct',0):+.2f}%")
        text = "Tracked Funds: " + " | ".join(parts)
        items.append({"dimension": "finance", "title": "Tracked Fund NAV", "content": text, "density": "DATA", "score": 3.0, "source": "AKShare", "url": ""})

    return _trim_to_budget(items, budget)


def process_ai(data, budget, window_start=None, window_end=None):
    if not data:
        return []
    items = []
    for story in data.get("hackernews", []):
        if window_start and window_end and not is_fresh(parse_item_date(story), window_start, window_end):
            continue
        content = story.get("title", "")
        if story.get("top_comments"):
            content += "\n---Top comments---\n" + "\n".join(story["top_comments"])
        items.append({
            "dimension": "ai", "title": story.get("title", ""), "content": content,
            "density": density_label(content), "url": story.get("url", ""),
            "source": "HackerNews", "score": story.get("score", 0) / 50,
        })
    for repo in data.get("github_trending", [])[:10]:
        items.append({
            "dimension": "ai", "title": f"[GitHub] {repo.get('name', '')}",
            "content": repo.get("description", ""), "density": density_label(repo.get("description", "")),
            "url": repo.get("url", ""), "source": "GitHub", "score": repo.get("stars", 0) / 100,
        })
    for blog in data.get("ai_blogs", []):
        items.append({
            "dimension": "ai", "title": blog.get("title", ""), "content": blog.get("content", ""),
            "density": density_label(blog.get("content", "")), "url": blog.get("url", ""),
            "source": blog.get("source", "AI Blog"), "score": 3.0,
        })
    return _trim_to_budget(items, budget)


def process_business(data, budget, window_start=None, window_end=None):
    if not data:
        return []
    items = []
    seo_keys = {"sej", "moz", "ahrefs", "sel", "google_search_central", "seo"}
    for key, section in data.items():
        if key in ("collected_at", "date", "total_count") or key.lower() in seo_keys:
            continue
        if isinstance(section, list):
            for article in section:
                if window_start and window_end and not is_fresh(parse_item_date(article), window_start, window_end):
                    continue
                content = article.get("summary", "") or article.get("description", "")
                if article.get("top_comments"):
                    content += "\n---Comments---\n" + "\n".join(c[:300] for c in article["top_comments"][:3])
                items.append({
                    "dimension": "business", "title": article.get("title", ""), "content": content,
                    "density": density_label(content), "url": article.get("url", ""),
                    "source": article.get("source", key),
                    "score": 1.0 + (0.5 if article.get("top_comments") else 0),
                })
    return _trim_to_budget(items, budget)


def process_seo(data, budget, window_start=None, window_end=None):
    if not data:
        return []
    items = []
    seo_keys = {"sej", "moz", "ahrefs", "sel", "google_search_central", "seo", "seo_search"}
    for key, section in data.items():
        if key in ("collected_at", "date", "total_count") or key.lower() not in seo_keys:
            continue
        if isinstance(section, list):
            for article in section:
                if window_start and window_end and not is_fresh(parse_item_date(article), window_start, window_end):
                    continue
                content = article.get("summary", "") or article.get("description", "")
                items.append({
                    "dimension": "seo", "title": article.get("title", ""), "content": content,
                    "density": density_label(content), "url": article.get("url", ""),
                    "source": article.get("source", key), "score": 1.0,
                })
    return _trim_to_budget(items, budget)


def process_lunar(data, budget):
    if not data:
        return []
    text = json.dumps(data, ensure_ascii=False)[:budget]
    return [{"dimension": "lunar", "title": "Lunar Data", "content": text, "density": "DATA", "score": 1.0, "source": "cnlunar", "url": ""}]


def process_tavily(data, budget, window_start=None, window_end=None):
    if not data:
        return []
    items = []
    dimension_map = {
        "ai_tools_discovery": "ai", "builder_indie": "business",
        "seo_traffic": "seo", "ecommerce_product": "business",
        "growth_monetization": "business", "startup_opportunity": "news",
    }
    for section_key, section_data in data.items():
        if not isinstance(section_data, dict) or "results" not in section_data:
            continue
        dim = dimension_map.get(section_key, "news")
        for answer in section_data.get("answers", []):
            if answer.get("answer"):
                items.append({
                    "dimension": dim, "title": f"[Tavily Summary] {answer.get('query', '')}",
                    "content": answer["answer"], "density": density_label(answer["answer"]),
                    "url": "", "source": "tavily_answer", "score": 3.0,
                })
        for result in section_data.get("results", []):
            if window_start and window_end and not is_fresh(parse_item_date(result), window_start, window_end):
                continue
            items.append({
                "dimension": dim, "title": result.get("title", ""), "content": result.get("content", ""),
                "density": density_label(result.get("content", "")), "url": result.get("url", ""),
                "source": "tavily", "score": result.get("score", 0.5) * 3,
            })
    return _trim_to_budget(items, budget)


def _trim_to_budget(items: list[dict], budget: int) -> list[dict]:
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    total = 0
    result = []
    for item in items:
        content_len = len(item.get("content") or "")
        if total + content_len > budget:
            remaining = budget - total
            if remaining > 100:
                item["content"] = item["content"][:remaining]
                item["density"] = density_label(item["content"])
                result.append(item)
            break
        total += content_len
        result.append(item)
    return result


# ============================================================
# Cross-day deduplication
# ============================================================

def _extract_entity_pairs(text: str) -> set:
    tokens = set()
    for m in re.findall(r'[a-z][a-z0-9]{2,}', text.lower()):
        if m not in {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'has', 'have',
                     'are', 'was', 'were', 'been', 'will', 'can', 'not', 'but', 'http',
                     'https', 'www', 'com', 'org', 'html'}:
            tokens.add(m)
    for m in re.findall(r'\$?\d+[kmb]', text.lower()):
        tokens.add(m)
    pairs = set()
    token_list = sorted(tokens)[:8]
    for i in range(len(token_list)):
        for j in range(i + 1, len(token_list)):
            pairs.add(f"{token_list[i]}+{token_list[j]}")
    return pairs


def load_recent_fingerprints(today_str: str, days: int = 7) -> tuple[set, set]:
    """Load exact + fuzzy fingerprints from recent days for deduplication."""
    fingerprints = set()
    fuzzy_fps = set()
    loaded_days = 0
    try:
        for offset in range(1, days + 1):
            past_date = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=offset)).strftime("%Y-%m-%d")
            past_file = ROOT / "output" / past_date / "briefing.json"
            if not past_file.exists():
                continue
            data = json.loads(past_file.read_text(encoding="utf-8"))
            for dim_items in data.values():
                if not isinstance(dim_items, list):
                    continue
                for item in dim_items:
                    title = (item.get("title") or "").strip().lower()
                    if title:
                        fingerprints.add(title)
                    url = (item.get("url") or "").strip()
                    if url:
                        fingerprints.add(url)
                    text = title + " " + (item.get("content") or "")[:300]
                    fuzzy_fps |= _extract_entity_pairs(text)
            loaded_days += 1
        print(f"[dedup] Loaded {loaded_days} days: {len(fingerprints)} exact + {len(fuzzy_fps)} fuzzy fingerprints")
    except Exception as e:
        print(f"[dedup] Failed to load historical fingerprints: {e}")
    return fingerprints, fuzzy_fps


def dedup_items(items: list[dict], recent_fps: tuple[set, set] | set) -> list[dict]:
    """Remove items that duplicate recent days (exact + fuzzy matching)."""
    if isinstance(recent_fps, tuple):
        exact_fps, fuzzy_fps = recent_fps
    else:
        exact_fps, fuzzy_fps = recent_fps, set()
    if not exact_fps and not fuzzy_fps:
        return items
    kept = []
    for item in items:
        title = (item.get("title") or "").strip().lower()
        url = (item.get("url") or "").strip()
        if (title and title in exact_fps) or (url and url in exact_fps):
            continue
        if fuzzy_fps:
            text = title + " " + (item.get("content") or "")[:300]
            item_pairs = _extract_entity_pairs(text)
            if len(item_pairs & fuzzy_fps) >= 3:
                continue
        kept.append(item)
    return kept


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Preprocessing: raw_*.json -> briefing.json")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    output_dir = ROOT / "output" / args.date
    if not output_dir.exists():
        print(f"[ERROR] Output directory not found: {output_dir}")
        sys.exit(1)

    recent_fps = load_recent_fingerprints(args.date)
    recent_topics = load_recent_topics(args.date, days=5)

    # Load all raw data
    news = load_json(output_dir / "raw_news.json")
    finance = load_json(output_dir / "raw_finance.json")
    ai = load_json(output_dir / "raw_ai.json")
    business = load_json(output_dir / "raw_business.json")
    supplement = load_json(output_dir / "raw_supplement.json")
    lunar = load_json(output_dir / "raw_lunar.json")
    youtube = load_json(output_dir / "raw_youtube.json")
    tavily = load_json(output_dir / "raw_tavily.json")

    dt = datetime.strptime(args.date, "%Y-%m-%d")
    weekday_en = dt.strftime("%A")

    # Strict time window: N-1 00:00:00 ~ N 23:59:59
    cn_tz = timezone(timedelta(hours=8))
    day_start_cn = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=cn_tz)
    window_start = (day_start_cn - timedelta(days=1)).astimezone(timezone.utc)
    window_end = (day_start_cn + timedelta(days=1) - timedelta(seconds=1)).astimezone(timezone.utc)
    print(f"[freshness] Time window: {window_start.isoformat()} ~ {window_end.isoformat()} (UTC)")

    briefing = {
        "generated_at": datetime.now().isoformat(),
        "date": args.date,
        "weekday_en": weekday_en,
        "date_display_en": f"{weekday_en}, {dt.strftime('%B %d, %Y')}",
        "ai": dedup_items(process_ai(ai, BUDGETS["ai"], window_start, window_end), recent_fps),
        "business": dedup_items(process_business(business, BUDGETS["business"], window_start, window_end), recent_fps),
        "seo": dedup_items(process_seo(business, BUDGETS["seo"], window_start, window_end), recent_fps),
        "finance": process_finance(finance, BUDGETS["finance"]),
        "news": dedup_items(process_news(news, supplement, BUDGETS["news"], window_start, window_end), recent_fps),
        "lunar": process_lunar(lunar, BUDGETS["lunar"]),
        "tavily": dedup_items(process_tavily(tavily, BUDGETS.get("tavily", 30000), window_start, window_end), recent_fps),
    }

    # Distribute YouTube items into their respective dimensions
    yt_items = dedup_items(process_youtube(youtube, BUDGETS["youtube"], window_start, window_end), recent_fps)
    for item in yt_items:
        dim = item.get("dimension", "ai")
        if dim in briefing and isinstance(briefing[dim], list):
            briefing[dim].append(item)
        else:
            briefing.setdefault("ai", []).append(item)

    # Cross-reference detection
    all_items = []
    for dim_items in briefing.values():
        if isinstance(dim_items, list):
            all_items.extend(dim_items)
    cross_refs = detect_cross_references(all_items)
    cross_ref_keywords = set(cross_refs.keys())
    if cross_refs:
        top_refs = sorted(cross_refs.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        briefing["cross_references"] = {k: v for k, v in top_refs}

    # Score and sort all dimensions
    skip_dims = {"finance", "lunar", "cross_references", "stats",
                 "generated_at", "date", "weekday_en", "date_display_en"}
    for dim, dim_items in briefing.items():
        if dim in skip_dims or not isinstance(dim_items, list):
            continue
        for item in dim_items:
            item["score"] = score_item(item, cross_ref_keywords, recent_topics)
        dim_items.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Stats
    total_chars = sum(len(item.get("content") or "") for items in briefing.values() if isinstance(items, list) for item in items)
    total_items = sum(len(items) for items in briefing.values() if isinstance(items, list))
    briefing["stats"] = {
        "total_items": total_items,
        "total_chars": total_chars,
        "budget_total": sum(BUDGETS.values()),
        "freshness_mode": "n-1_to_n",
    }

    briefing = fix_transcript_errors(briefing)

    output_file = output_dir / "briefing.json"
    output_file.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Briefing generated: {total_items} items, {total_chars} chars -> {output_file}")

    if total_items == 0:
        print("[ERROR] Briefing is empty (0 items), data sources may have all failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
