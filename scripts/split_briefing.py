#!/usr/bin/env python3
"""Split briefing.json into per-section data files.

Config-driven: reads dimension definitions and source mappings from
config/focus.json. Supports arbitrary user-defined dimensions.

Principle: Each section only gets its own dimension data + corresponding
web_supplement additions. When data is insufficient, Claude uses
WebSearch to fill gaps.
"""

import json, sys, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

# Default sections used when no focus.json exists (backward compatibility)
_DEFAULT_SECTIONS = {
    "ai":      {"dims": ["ai"],                "ws_dims": ["ai", "tech"]},
    "seo":     {"dims": ["seo"],               "ws_dims": ["seo"]},
    "biz":     {"dims": ["business"],           "ws_dims": ["business", "crypto"]},
    "market":  {"dims": ["finance", "news"],    "ws_dims": ["tech", "crypto"]},
}

# Maps focus.json dimension keys to briefing.json internal dimension names
# (briefing.json uses short names like "ai", "business", "news", etc.)
_DIM_KEY_TO_BRIEFING_DIMS = {
    "ai_tech": ["ai"],
    "finance": ["finance"],
    "seo": ["seo"],
    "startup": ["business"],
    "ecommerce": ["business"],
    "creator": ["business"],
    "macro": ["news"],
    # Legacy keys (direct match)
    "ai": ["ai"],
    "business": ["business"],
    "news": ["news"],
    "market": ["finance", "news"],
}


def _load_focus_config() -> dict | None:
    """Load focus.json from config directory."""
    for path in [ROOT / "config" / "focus.json", ROOT / "config" / "focus.json.example"]:
        if path.exists():
            try:
                return json.loads(path.read_text("utf-8"))
            except Exception as e:
                print(f"[split] WARNING: Failed to read {path.name}: {e}")
    return None


def _build_sections_from_focus(focus: dict) -> dict:
    """Build SECTIONS dict from focus.json dimensions.

    Each enabled dimension in focus.json becomes a section.
    The dimension_source_mapping and internal mapping determine which
    briefing.json keys feed into each section.
    """
    dimensions = focus.get("dimensions", {})
    source_mapping = focus.get("dimension_source_mapping", {})
    sections = {}

    for dim_key, dim_config in dimensions.items():
        if dim_key.startswith("_"):
            continue
        if not dim_config.get("enabled", True):
            continue

        # Determine which briefing.json dimension arrays to pull from
        briefing_dims = _DIM_KEY_TO_BRIEFING_DIMS.get(dim_key, [dim_key])

        # Build ws_dims: the dimension tags used in web_supplement breaking_news etc.
        ws_dims = list(briefing_dims)
        # Add source-derived hints for web supplement filtering
        sources = source_mapping.get(dim_key, [])
        for src in sources:
            if "tech" in src:
                ws_dims.append("tech")
            if "crypto" in src or "finance" in src:
                ws_dims.append("crypto")

        ws_dims = list(set(ws_dims))

        sections[dim_key] = {
            "dims": briefing_dims,
            "ws_dims": ws_dims,
            "label": dim_config.get("label", dim_key),
            "weight": dim_config.get("weight", 10),
        }

    return sections


def _get_sections() -> dict:
    """Get the sections config: from focus.json if available, else defaults."""
    focus = _load_focus_config()
    if focus and focus.get("dimensions"):
        sections = _build_sections_from_focus(focus)
        if sections:
            print(f"[split] Loaded {len(sections)} dimensions from focus.json: {list(sections.keys())}")
            return sections
    print("[split] Using default section definitions (no focus.json found)")
    return _DEFAULT_SECTIONS


def split(date_str: str):
    SECTIONS = _get_sections()

    bf = ROOT / "output" / date_str / "briefing.json"
    ws_file = ROOT / "output" / date_str / "web_supplement.json"

    if bf.exists():
        data = json.loads(bf.read_text("utf-8"))
    elif ws_file.exists():
        print(f"[split] WARNING: briefing.json missing, using web_supplement.json for minimal data files")
        data = {"date": date_str}
    else:
        print(f"[split] ERROR: Neither briefing.json nor web_supplement.json exist, cannot split")
        sys.exit(1)

    ws = json.loads(ws_file.read_text("utf-8")) if ws_file.exists() else {}

    # Load stale_items (items marked as stale by WebSearch freshness validation)
    stale_titles = set()
    if ws.get("stale_items"):
        for si in ws["stale_items"]:
            t = (si.get("title") or "").strip().lower()
            if t:
                stale_titles.add(t)
        print(f"  [stale] Will filter {len(stale_titles)} stale items")

    out = ROOT / "output" / date_str / "sections"
    out.mkdir(parents=True, exist_ok=True)

    meta = {
        k: data.get(k)
        for k in ["date", "weekday_cn", "weekday_en", "date_display_cn", "date_display_en"]
    }

    for name, cfg in SECTIONS.items():
        sec = {**meta, "items": []}

        for dim in cfg["dims"]:
            sec["items"].extend(data.get(dim, []))

        # Distribute tavily supplement data by dimension
        for tavily_item in data.get("tavily", []):
            tavily_dim = tavily_item.get("dimension", "")
            if tavily_dim in cfg["dims"] or tavily_dim in cfg.get("ws_dims", []):
                sec["items"].append(tavily_item)

        # Sections that include finance dims get lunar data
        if "finance" in cfg["dims"] or "news" in cfg["dims"] or name == "market":
            lunar_data = data.get("lunar", [])
            if lunar_data:
                sec["lunar"] = lunar_data

        # AI-related sections get YouTube web supplements
        if ("ai" in cfg["dims"] or name in ("ai", "ai_tech")) and ws:
            yt_supplements = ws.get("youtube_supplements", [])
            if yt_supplements:
                sec["web_supplements"] = yt_supplements

        # Filter stale items (old projects/news with repeated exposure)
        if stale_titles:
            before = len(sec["items"])
            sec["items"] = [
                item for item in sec["items"]
                if (item.get("title") or "").strip().lower() not in stale_titles
            ]
            filtered = before - len(sec["items"])
            if filtered:
                print(f"    {name}: filtered {filtered} stale items")

        # Data corrections from WebSearch validation
        if ws and ws.get("data_corrections"):
            sec["data_corrections"] = ws["data_corrections"]

        # Breaking news (filtered by dimension)
        ws_dims = cfg.get("ws_dims", []) + cfg["dims"]
        if ws and ws.get("breaking_news"):
            relevant = [
                n for n in ws["breaking_news"]
                if n.get("dimension", "") in ws_dims
            ]
            if relevant:
                sec["breaking_news"] = relevant

        # News supplements (distributed by dimension)
        if ws and ws.get("news_supplements"):
            relevant = [
                n for n in ws["news_supplements"]
                if n.get("dimension", "") in ws_dims
            ]
            if relevant:
                sec["news_supplements"] = relevant

        path = out / f"data_{name}.json"
        path.write_text(json.dumps(sec, ensure_ascii=False, indent=2), "utf-8")
        size_kb = len(json.dumps(sec, ensure_ascii=False)) // 1024
        print(f"  {name}: {len(sec['items'])} items, {size_kb}KB")

    # Save lunar data separately (overview section needs it)
    lunar_meta = {**meta, "lunar": data.get("lunar", [])}
    (out / "data_lunar.json").write_text(
        json.dumps(lunar_meta, ensure_ascii=False, indent=2), "utf-8"
    )

    # Generate recent coverage summary for dedup guidance
    _generate_recent_coverage(date_str, out, SECTIONS)

    print(f"[split] Done -> {out}")


def _generate_recent_coverage(today_str: str, out_dir: Path, sections: dict, days: int = 3):
    """Scan recent N days of section markdown files, extract headlines + key stats.
    Output recent_coverage.json for Claude section generation to read
    and avoid repetition.

    v4.1 enhancement: Besides headlines, also extracts recurring statistics
    and key expressions to prevent the same data points from appearing
    verbatim across multiple daily reports.
    """
    import re
    from datetime import timedelta
    coverage = {}  # section_name -> [{"date": "...", "headlines": [...], "key_stats": [...]}]

    # Regex for statistics: captures phrases containing numbers + %/$/multiplier/etc.
    stat_pattern = re.compile(
        r'(?:[\u4e00-\u9fff\w]{0,20})'      # optional prefix (Chinese or English)
        r'(?:\$[\d,.]+[BMKT]?'               # $amount
        r'|[\d,.]+\s*%'                       # percentage
        r'|[\d,.]+\s*(?:billion|million|thousand|x|times))'  # English number units
        r'(?:[\u4e00-\u9fff\w]{0,15})',       # optional suffix
        re.UNICODE
    )

    for offset in range(1, days + 1):
        past = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=offset)).strftime("%Y-%m-%d")
        sec_dir = ROOT / "output" / past / "sections"
        if not sec_dir.exists():
            continue

        for name in sections:
            zh_file = sec_dir / f"{name}_zh.md"
            if not zh_file.exists():
                continue
            headlines = []
            key_stats = []
            try:
                text = zh_file.read_text("utf-8")
                for line in text.splitlines():
                    if line.startswith("### "):
                        headlines.append(line[4:].strip())
                # Extract key statistics (deduplicated, max 20)
                stats_found = stat_pattern.findall(text)
                seen = set()
                for s in stats_found:
                    s = s.strip()
                    if len(s) >= 4 and s not in seen:
                        seen.add(s)
                        key_stats.append(s)
                key_stats = key_stats[:20]
            except Exception:
                continue
            if headlines:
                coverage.setdefault(name, []).append({
                    "date": past,
                    "headlines": headlines,
                    "key_stats": key_stats,
                })

    # Detect cross-day repeated statistics
    repeated_stats = []
    all_stats = {}  # stat -> [dates]
    for name, entries in coverage.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for stat in entry.get("key_stats", []):
                all_stats.setdefault(stat, set()).add(entry["date"])
    for stat, dates in all_stats.items():
        if len(dates) >= 2:
            repeated_stats.append(stat)

    coverage["_repeated_stats"] = repeated_stats[:30]
    coverage["_dedup_rules"] = (
        "The following statistics have appeared 2+ times in the past 3 days. "
        "In this generation: (1) do not quote these verbatim, (2) if you must mention them, "
        "use a new angle or updated data, (3) if no updated data is available, skip entirely."
    )

    out_file = out_dir / "recent_coverage.json"
    out_file.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), "utf-8")
    total = sum(len(v) for v in coverage.values() if isinstance(v, list) and v and isinstance(v[0], dict))
    print(f"  [coverage] Recent {days} days coverage: {total} day*section entries, {len(repeated_stats)} repeated stats")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--date")
    a = p.parse_args()
    split(a.date or datetime.now().strftime("%Y-%m-%d"))
