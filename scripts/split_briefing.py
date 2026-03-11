#!/usr/bin/env python3
"""Split briefing.json into per-section data files.

Architecture: 4 thematic sections, categorized by topic (not source).
YouTube data has been distributed to ai/seo/business/finance dimensions
during prepare_briefing.

Principle: Each section only gets its own dimension data + corresponding
web_supplement additions. When data is insufficient, Claude uses
WebSearch to fill gaps.
"""

import json, sys, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

# 4 thematic sections (YouTube content merged into corresponding dimensions)
SECTIONS = {
    "ai":      {"dims": ["ai"],                "ws_dims": ["ai", "tech"]},
    "seo":     {"dims": ["seo"],               "ws_dims": ["seo"]},
    "biz":     {"dims": ["business"],           "ws_dims": ["business", "crypto"]},
    "market":  {"dims": ["finance", "news"],    "ws_dims": ["tech", "crypto"]},
}


def split(date_str: str):
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

        # Market section includes lunar data
        if name == "market":
            sec["lunar"] = data.get("lunar", [])

        # AI section includes YouTube web supplements
        if name == "ai" and ws:
            sec["web_supplements"] = ws.get("youtube_supplements", [])

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
    _generate_recent_coverage(date_str, out)

    print(f"[split] Done -> {out}")


def _generate_recent_coverage(today_str: str, out_dir: Path, days: int = 3):
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

        for name in SECTIONS:
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
