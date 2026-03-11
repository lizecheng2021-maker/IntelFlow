#!/usr/bin/env python3
"""Assemble section markdown files into complete daily / weekly / monthly reports.

Reads output/{date}/sections/ files named {prefix}_{section}_{lang}.md,
concatenates them in order to produce {type}_{lang}.md.

Daily sections have no prefix, weekly uses weekly_, monthly uses monthly_.
"""

import re, json, shutil, argparse
from pathlib import Path
from datetime import datetime
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent

# Daily section order
# Chinese: all 6 sections (including market/macro)
DAILY_ZH = ["overview", "ai", "seo", "biz", "market", "synthesis"]
# English: no standalone market section (A-share/fund data not relevant
# for international readers); global market summary folded into overview/synthesis
DAILY_EN = ["overview", "ai", "biz", "seo", "synthesis"]

# Weekly section order (aligned with daily 4 thematic sections, both languages)
WEEKLY_ZH = ["weekly_overview", "weekly_ai", "weekly_seo", "weekly_biz", "weekly_market", "weekly_synthesis"]
WEEKLY_EN = ["weekly_overview", "weekly_ai", "weekly_seo", "weekly_biz", "weekly_market", "weekly_synthesis"]

# Monthly section order (aligned with daily 4 thematic sections, both languages)
MONTHLY_ZH = ["monthly_overview", "monthly_ai", "monthly_seo", "monthly_biz", "monthly_market", "monthly_synthesis"]
MONTHLY_EN = ["monthly_overview", "monthly_ai", "monthly_seo", "monthly_biz", "monthly_market", "monthly_synthesis"]

ORDERS = {
    "daily":   {"zh": DAILY_ZH,   "en": DAILY_EN},
    "weekly":  {"zh": WEEKLY_ZH,  "en": WEEKLY_EN},
    "monthly": {"zh": MONTHLY_ZH, "en": MONTHLY_EN},
}


def assemble(date_str: str, report_type: str = "daily"):
    # Weekly/monthly reports may be generated directly by Claude, not assembled
    if report_type in ("weekly", "monthly"):
        out_dir = ROOT / "output" / date_str
        target_zh = out_dir / f"{report_type}_zh.md"
        target_en = out_dir / f"{report_type}_en.md"
        if target_zh.exists() or target_en.exists():
            print(f"[assemble] SKIP: {report_type} already generated directly, no assembly needed")
            return True
        else:
            print(f"[assemble] WARNING: {report_type} not in section assembly mode, "
                  f"but {target_zh.name} also doesn't exist, check generation flow")
            return False

    sec_dir = ROOT / "output" / date_str / "sections"
    out_dir = ROOT / "output" / date_str

    if not sec_dir.exists():
        print(f"[assemble] ERROR: {sec_dir} not found")
        return False

    orders = ORDERS.get(report_type, ORDERS["daily"])
    success = True
    total_missing = 0

    for lang, order in [("zh", orders["zh"]), ("en", orders["en"])]:
        parts = []
        missing = []

        for sec in order:
            f = sec_dir / f"{sec}_{lang}.md"
            if f.exists():
                content = f.read_text("utf-8").strip()
                if content:
                    parts.append(content)
                    print(f"  [assemble] + {sec}_{lang}.md ({len(content)} chars)")
                else:
                    missing.append(sec)
                    print(f"  [assemble] ! {sec}_{lang}.md is empty")
            else:
                missing.append(sec)
                print(f"  [assemble] - {sec}_{lang}.md missing")

        total_missing += len(missing)

        if not parts:
            print(f"[assemble] ERROR: no sections for {lang}")
            success = False
            continue

        # Concatenate
        full = "\n\n".join(parts)

        # Cleanup: extra blank lines, horizontal rules
        full = re.sub(r"^---+\s*$", "", full, flags=re.MULTILINE)
        full = re.sub(r"\n{3,}", "\n\n", full)

        out_file = out_dir / f"{report_type}_{lang}.md"
        # Backup before overwriting
        if out_file.exists():
            bak = out_dir / f"{report_type}_{lang}.md.bak"
            shutil.copy2(out_file, bak)
            print(f"  [assemble] backup -> {bak.name}")
        out_file.write_text(full, "utf-8")

        # Expression frequency extraction (Chinese daily only)
        if lang == "zh" and report_type == "daily":
            _extract_expressions(full, date_str)

        if missing:
            pct = len(missing) / len(order) * 100
            print(f"[assemble] INCOMPLETE ({lang}): {len(missing)}/{len(order)} sections missing ({pct:.0f}%): {', '.join(missing)}")
            if pct > 50:
                print(f"[assemble] ERROR ({lang}): >50% sections missing, report quality too low")
                success = False
        # Content length threshold: zh >= 1500 chars, en >= 1000 chars
        min_chars = 1500 if lang == "zh" else 1000
        if len(full) < min_chars:
            print(f"[assemble] ERROR ({lang}): only {len(full)} chars (min {min_chars}), report too short")
            success = False
        print(f"[assemble] => {out_file.name} ({len(full)} chars, {len(parts)}/{len(order)} sections)")

    if total_missing > 0:
        print(f"[assemble] SUMMARY: {total_missing} section(s) missing across all languages -- report is incomplete")

    return success


def _extract_expressions(text: str, date_str: str):
    """Extract usage frequency of catchphrases, transitions, and synthesis patterns.
    Write to state/expression_log.json for future generation reference
    to avoid repetitive expression patterns.
    """
    # Tracked expression patterns (configurable per writing style)
    catchphrases = {}
    transitions = {}

    # Load expression patterns from config if available
    config_file = ROOT / "config" / "profile.json"
    if config_file.exists():
        try:
            profile = json.loads(config_file.read_text("utf-8"))
            tracked = profile.get("expression_tracking", {})
            catchphrases = {k: k for k in tracked.get("catchphrases", [])}
            transitions = {k: k for k in tracked.get("transitions", [])}
        except Exception:
            pass

    # Default patterns if config doesn't define any
    if not catchphrases:
        catchphrases = {
            "but wait": r"but wait",
            "here is the thing": r"here.?s the thing",
            "let me break": r"let me break",
            "the real question": r"the real question",
        }
    if not transitions:
        transitions = {
            "bottom line": r"bottom line",
            "big picture": r"big picture",
            "the takeaway": r"the takeaway",
        }

    counts = {}
    for label, pat in {**catchphrases, **transitions}.items():
        counts[label] = len(re.findall(pat, text, re.IGNORECASE))

    # Read existing log, append today
    state_dir = ROOT / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_file = state_dir / "expression_log.json"

    log_data = {}
    if log_file.exists():
        try:
            log_data = json.loads(log_file.read_text("utf-8"))
        except Exception:
            log_data = {}

    log_data[date_str] = counts

    # Keep only last 14 days
    sorted_dates = sorted(log_data.keys(), reverse=True)[:14]
    log_data = {d: log_data[d] for d in sorted_dates}

    log_file.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), "utf-8")

    # Detect high-frequency expressions (5+ times in last 7 days)
    recent_7 = sorted_dates[:7]
    freq = Counter()
    for d in recent_7:
        for expr, cnt in log_data[d].items():
            freq[expr] += cnt

    overused = [(expr, cnt) for expr, cnt in freq.most_common() if cnt >= 5]
    if overused:
        print(f"  [expression] Overused (past 7 days): {', '.join(f'{e}({c}x)' for e, c in overused[:5])}")
    else:
        print(f"  [expression] Expression frequency normal")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--date")
    p.add_argument("--type", default="daily")
    a = p.parse_args()
    ok = assemble(a.date or datetime.now().strftime("%Y-%m-%d"), a.type)
    if not ok:
        exit(1)
