#!/usr/bin/env python3
"""
IntelFlow AI-first pipeline.

Architecture: focus.json dimensions → parallel web search + AI generation
              → assemble daily_zh.md + daily_en.md → publish

Usage:
    python3 scripts/run_pipeline.py --date 2026-03-11 --output output/2026-03-11
    python3 scripts/run_pipeline.py --date 2026-03-11 --output output/2026-03-11 --type weekly
    python3 scripts/run_pipeline.py --date 2026-03-11 --output output/2026-03-11 --no-publish
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from utils import (
    load_ai_config,
    load_focus_config,
    load_platforms,
    save_json,
    setup_logger,
    CONFIG_DIR,
    ROOT as UTILS_ROOT,
)
from ai_adapters import create_llm, LLMError
from search_adapters import create_search, SearchError

log = setup_logger("pipeline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECTION_TIMEOUT = 180          # seconds per dimension (search + generate)
PUBLISH_TIMEOUT = 120          # seconds per platform publish script
PLUGIN_TIMEOUT = 120           # seconds per plugin

WORD_TARGETS = {
    "daily":   (800, 1500),
    "weekly":  (1500, 2500),
    "monthly": (2000, 3500),
}

# Section ordering for assembler — mirrors assemble_report.py logic.
# The pipeline generates each dimension as its own section, plus overview
# and synthesis. The assembler uses these names to find the files.
DAILY_ZH_ORDER = ["overview", "ai_tech", "finance", "seo", "startup",
                  "ecommerce", "creator", "macro", "synthesis"]
DAILY_EN_ORDER = ["overview", "ai_tech", "startup", "seo",
                  "creator", "macro", "synthesis"]


# ---------------------------------------------------------------------------
# Query generation helpers
# ---------------------------------------------------------------------------

def _build_queries(dim_key: str, dim_cfg: dict, date_str: str) -> list[str]:
    """Return 3–5 search queries for a dimension.

    Uses explicit search_queries from focus.json if present, otherwise
    auto-generates sensible queries from the label and description.
    """
    explicit: list[str] = dim_cfg.get("search_queries", [])
    if explicit:
        # Interpolate {date} placeholder
        return [q.replace("{date}", date_str) for q in explicit[:5]]

    label: str = dim_cfg.get("label", dim_key)
    desc: str = dim_cfg.get("description", "")

    queries = [
        f"{label} news {date_str}",
        f"{label} latest updates {date_str}",
    ]
    if desc:
        # Use first keyword phrase from description as a third query
        first_phrase = desc.split(",")[0].strip()
        queries.append(f"{first_phrase} {date_str}")
    else:
        queries.append(f"{label} trends analysis")

    return queries


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _run_searches(
    searcher,
    queries: list[str],
    max_results_per_query: int = 10,
    days: int = 2,
) -> list[dict]:
    """Execute multiple search queries, deduplicate by URL, return merged list."""
    seen_urls: set[str] = set()
    all_results: list[dict] = []

    for query in queries:
        try:
            results = searcher.search(query, max_results=max_results_per_query, days=days)
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as exc:
            log.warning("Search query failed %r: %s", query, exc)

    return all_results


def _format_search_context(results: list[dict], max_chars: int = 40_000) -> str:
    """Format search results as a readable context block for the LLM prompt."""
    if not results:
        return "(No search results available — generate from training knowledge.)"

    lines: list[str] = []
    chars = 0
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        url = r.get("url", "")
        content = r.get("content", "").strip()

        entry = f"[{i}] {title}\nURL: {url}\n{content}\n"
        if chars + len(entry) > max_chars:
            lines.append(f"... [{len(results) - i + 1} more results truncated]")
            break
        lines.append(entry)
        chars += len(entry)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_system_prompt(profile: dict, lang: str) -> str:
    """Build system prompt from editorial profile."""
    name = profile.get("name", "IntelFlow")
    tone = profile.get("tone", "analytical")
    style = profile.get("analysis_style", "")
    catchphrases = profile.get("catchphrases", [])

    lang_instruction = (
        "Write your analysis in Chinese (中文)." if lang == "zh"
        else "Write your analysis in English."
    )

    parts = [
        f"You are an intelligence analyst for {name}.",
        f"Tone: {tone}.",
    ]
    if style:
        parts.append(f"Analysis style: {style}.")
    if catchphrases:
        parts.append(f"Occasional phrases (use sparingly): {', '.join(catchphrases[:5])}.")
    parts.append(lang_instruction)
    parts.append(
        "Requirements:\n"
        "- Use specific numbers and data points from the search results\n"
        "- Provide your own analytical judgment, not just news summaries\n"
        "- Cross-reference signals across domains when relevant\n"
        "- Never fabricate data — if uncertain, clearly say so or skip\n"
        "- Output well-structured Markdown with a clear ## heading\n"
        "- Do not start or end with a horizontal rule (---)"
    )
    return "\n".join(parts)


def _build_section_prompt(
    dim_key: str,
    dim_cfg: dict,
    search_context: str,
    report_type: str,
    date_str: str,
) -> str:
    """Build the user prompt for a single dimension section."""
    label = dim_cfg.get("label", dim_key)
    weight = dim_cfg.get("weight", 10)
    desc = dim_cfg.get("description", "")

    word_min, word_max = WORD_TARGETS.get(report_type, WORD_TARGETS["daily"])

    guidance_parts = [
        f"Write a {report_type} intelligence briefing section on **{label}**.",
        f"Date: {date_str}.",
        f"This section has a {weight}% content weight — calibrate depth accordingly.",
    ]
    if desc:
        guidance_parts.append(f"Focus areas: {desc}.")
    guidance_parts.append(
        f"Target length: {word_min}–{word_max} words.\n"
        "Structure:\n"
        "1. Lead with the single most important signal (1–2 sentences)\n"
        "2. Unpack 2–4 key stories with data and your analytical take\n"
        "3. Cross-domain connections (how this interacts with other areas)\n"
        "4. Brief forward implication — what this means next week/month\n"
        "\nBe direct. Give concrete numbers. State your own view explicitly."
    )

    return (
        "\n".join(guidance_parts)
        + "\n\n---\nSearch results for context (today's web data):\n\n"
        + search_context
    )


def _build_overview_prompt(
    sections_context: str,
    report_type: str,
    date_str: str,
    lang: str,
) -> str:
    """Build prompt for the overview/opening section."""
    return (
        f"Write a {report_type} intelligence briefing overview for {date_str}.\n"
        "This is the opening section — hook the reader with the most important signal.\n"
        "Length: 200–400 words.\n"
        "Do NOT include a table of contents or list every section.\n"
        "State the single biggest takeaway up front, then 2–3 supporting signals.\n"
        "End with one sentence that makes the reader want to keep reading.\n\n"
        "---\nSummary of today's sections (use these to find the lead story):\n\n"
        + sections_context
    )


def _build_synthesis_prompt(
    all_sections_text: str,
    report_type: str,
    date_str: str,
) -> str:
    """Build prompt for the synthesis/closing section."""
    return (
        f"Write a synthesis section for today's {date_str} {report_type} briefing.\n"
        "Length: 400–600 words.\n"
        "This is the closing section. Do NOT recap each section.\n"
        "Instead:\n"
        "- Find the single thread that connects today's signals across domains\n"
        "- Name the structural shift or tension that most matters\n"
        "- End with one strong, memorable line — not a list, not 'stay tuned'\n\n"
        "---\nAll sections for today:\n\n"
        + all_sections_text
    )


# ---------------------------------------------------------------------------
# Core: generate one section (search + LLM)
# ---------------------------------------------------------------------------

def _generate_dimension_section(
    dim_key: str,
    dim_cfg: dict,
    date_str: str,
    report_type: str,
    lang: str,
    llm,
    searcher,
    sections_dir: Path,
    plugin_context: dict[str, str],
) -> tuple[str, str, bool]:
    """Research and write one dimension section.

    Returns: (dim_key, lang, success)
    """
    label = dim_cfg.get("label", dim_key)
    log.info("  [%s/%s] Building queries...", dim_key, lang)

    queries = _build_queries(dim_key, dim_cfg, date_str)

    # Search
    raw_results: list[dict] = []
    if searcher is not None:
        log.info("  [%s/%s] Searching %d queries via %s...", dim_key, lang, len(queries), searcher.name)
        raw_results = _run_searches(searcher, queries, max_results_per_query=10)
        log.info("  [%s/%s] Got %d unique results", dim_key, lang, len(raw_results))
    else:
        log.warning("  [%s/%s] No search adapter — generating from training knowledge", dim_key, lang)

    search_context = _format_search_context(raw_results)

    # Inject plugin context if available for this dimension
    extra_ctx = plugin_context.get(dim_key, "")
    if extra_ctx:
        search_context = (
            "=== Additional context from local plugins ===\n"
            + extra_ctx
            + "\n\n=== Web search results ===\n"
            + search_context
        )

    system = _build_system_prompt(_load_profile(), lang)
    prompt = _build_section_prompt(dim_key, dim_cfg, search_context, report_type, date_str)

    log.info("  [%s/%s] Generating with LLM (%d chars context)...", dim_key, lang, len(search_context))
    try:
        response = llm.generate(prompt=prompt, system=system, max_tokens=2048)
    except LLMError as exc:
        log.error("  [%s/%s] LLM failed: %s", dim_key, lang, exc)
        return dim_key, lang, False

    if not response or len(response.strip()) < 100:
        log.warning("  [%s/%s] Response too short (%d chars)", dim_key, lang, len(response or ""))
        return dim_key, lang, False

    # Save raw search results alongside for auditability
    results_file = sections_dir / f"search_{dim_key}.json"
    if not results_file.exists():  # only write once (shared across langs)
        save_json({"queries": queries, "results": raw_results}, results_file)

    out_file = sections_dir / f"{dim_key}_{lang}.md"
    out_file.write_text(response.strip(), "utf-8")
    log.info("  [%s/%s] Written %d chars -> %s", dim_key, lang, len(response), out_file.name)
    return dim_key, lang, True


# ---------------------------------------------------------------------------
# Overview + synthesis (assembled after all dimension sections)
# ---------------------------------------------------------------------------

def _generate_overview(
    llm,
    sections_dir: Path,
    lang: str,
    report_type: str,
    date_str: str,
) -> bool:
    """Generate opening overview from completed dimension sections."""
    summaries: list[str] = []
    for md in sorted(sections_dir.glob(f"*_{lang}.md")):
        if md.stem.startswith(("overview", "synthesis")):
            continue
        preview = md.read_text("utf-8")[:600].strip()
        summaries.append(f"### {md.stem.replace(f'_{lang}', '')}\n{preview}...")

    if not summaries:
        log.warning("[overview/%s] No dimension sections found, skipping", lang)
        return False

    system = _build_system_prompt(_load_profile(), lang)
    prompt = _build_overview_prompt("\n\n".join(summaries), report_type, date_str, lang)

    try:
        response = llm.generate(prompt=prompt, system=system, max_tokens=800)
    except LLMError as exc:
        log.error("[overview/%s] LLM failed: %s", lang, exc)
        return False

    if not response or len(response.strip()) < 80:
        log.warning("[overview/%s] Response too short", lang)
        return False

    out = sections_dir / f"overview_{lang}.md"
    out.write_text(response.strip(), "utf-8")
    log.info("[overview/%s] Written %d chars", lang, len(response))
    return True


def _generate_synthesis(
    llm,
    sections_dir: Path,
    lang: str,
    report_type: str,
    date_str: str,
) -> bool:
    """Generate closing synthesis from all dimension sections."""
    all_parts: list[str] = []
    for md in sorted(sections_dir.glob(f"*_{lang}.md")):
        if md.stem.startswith("synthesis"):
            continue
        all_parts.append(md.read_text("utf-8"))

    if not all_parts:
        log.warning("[synthesis/%s] No sections found, skipping", lang)
        return False

    combined = "\n\n---\n\n".join(all_parts)
    if len(combined) > 80_000:
        combined = combined[:80_000] + "\n... [truncated]"

    system = _build_system_prompt(_load_profile(), lang)
    prompt = _build_synthesis_prompt(combined, report_type, date_str)

    try:
        response = llm.generate(prompt=prompt, system=system, max_tokens=1200)
    except LLMError as exc:
        log.error("[synthesis/%s] LLM failed: %s", lang, exc)
        return False

    if not response or len(response.strip()) < 100:
        log.warning("[synthesis/%s] Response too short", lang)
        return False

    out = sections_dir / f"synthesis_{lang}.md"
    out.write_text(response.strip(), "utf-8")
    log.info("[synthesis/%s] Written %d chars", lang, len(response))
    return True


# ---------------------------------------------------------------------------
# Profile loader (kept local to avoid circular import)
# ---------------------------------------------------------------------------

def _load_profile() -> dict:
    """Load editorial voice profile from config/profile.json."""
    profile_path = CONFIG_DIR / "profile.json"
    if profile_path.exists():
        try:
            return json.loads(profile_path.read_text("utf-8"))
        except Exception:
            pass
    return {
        "name": "IntelFlow",
        "tone": "analytical",
        "analysis_style": (
            "Start with the conclusion, then explain why, then discuss implications. "
            "Be direct, use specific numbers, and always give your own take."
        ),
        "catchphrases": [],
    }


# ---------------------------------------------------------------------------
# Plugin runner
# ---------------------------------------------------------------------------

def _run_plugins(date_str: str, output_dir: Path) -> dict[str, str]:
    """Discover and run plugins/collect_*.py scripts.

    Each plugin may write a JSON file named after itself (e.g. collect_rss.json)
    into output_dir. We read those back and return a dict mapping dimension keys
    to additional context strings.

    Returns:
        dict mapping dimension_key → extra context string (may be empty)
    """
    plugins_dir = ROOT / "plugins"
    if not plugins_dir.exists():
        return {}

    plugin_scripts = sorted(plugins_dir.glob("collect_*.py"))
    if not plugin_scripts:
        return {}

    log.info("[plugins] Found %d plugin(s)", len(plugin_scripts))
    python = _find_python()

    for script in plugin_scripts:
        log.info("[plugins] Running %s ...", script.name)
        try:
            result = subprocess.run(
                [python, str(script), "--date", date_str, "--output", str(output_dir)],
                timeout=PLUGIN_TIMEOUT,
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            if result.returncode != 0:
                log.warning("[plugins] %s exited %d: %s",
                            script.name, result.returncode, result.stderr[:500])
            else:
                log.info("[plugins] %s done", script.name)
        except subprocess.TimeoutExpired:
            log.warning("[plugins] %s timed out after %ds", script.name, PLUGIN_TIMEOUT)
        except Exception as exc:
            log.warning("[plugins] %s failed: %s", script.name, exc)

    # Collect plugin output JSONs and map to dimensions
    context: dict[str, str] = {}
    for json_file in output_dir.glob("plugin_*.json"):
        try:
            data = json.loads(json_file.read_text("utf-8"))
            # Plugin output format: {"dimension": str, "context": str}
            # OR {"items": [{"title":..., "content":..., "url":...}], "dimension": str}
            dim = data.get("dimension", "")
            if not dim:
                continue
            if "context" in data:
                context[dim] = data["context"]
            elif "items" in data:
                items = data["items"]
                lines = []
                for item in items[:20]:
                    t = item.get("title", "")
                    c = item.get("content", "")
                    u = item.get("url", "")
                    lines.append(f"- {t}: {c} ({u})")
                context[dim] = "\n".join(lines)
        except Exception as exc:
            log.warning("[plugins] Could not parse %s: %s", json_file.name, exc)

    if context:
        log.info("[plugins] Loaded plugin context for dimensions: %s", list(context.keys()))
    return context


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def _assemble_reports(
    output_dir: Path,
    sections_dir: Path,
    date_str: str,
    report_type: str,
    languages: list[str],
    focus: dict,
) -> dict[str, Path]:
    """Concatenate section files into final daily_zh.md / daily_en.md.

    Returns dict of lang -> output file path for successfully assembled reports.
    """
    # Build dynamic section order from focus.json dimensions (enabled only)
    dims = [
        k for k, v in focus.get("dimensions", {}).items()
        if isinstance(v, dict) and v.get("enabled", True)
    ]
    # Sort by weight descending so heaviest sections come first
    dims.sort(
        key=lambda k: focus["dimensions"][k].get("weight", 0),
        reverse=True,
    )

    assembled: dict[str, Path] = {}

    for lang in languages:
        order = ["overview"] + dims + ["synthesis"]
        parts: list[str] = []
        missing: list[str] = []

        for sec in order:
            f = sections_dir / f"{sec}_{lang}.md"
            if f.exists():
                content = f.read_text("utf-8").strip()
                if content:
                    parts.append(content)
                    log.info("  [assemble/%s] + %s (%d chars)", lang, f.name, len(content))
                else:
                    missing.append(sec)
                    log.warning("  [assemble/%s] empty: %s", lang, f.name)
            else:
                missing.append(sec)
                log.warning("  [assemble/%s] missing: %s", lang, f.name)

        if not parts:
            log.error("[assemble/%s] No sections found, skipping", lang)
            continue

        import re
        full = "\n\n".join(parts)
        full = re.sub(r"^---+\s*$", "", full, flags=re.MULTILINE)
        full = re.sub(r"\n{3,}", "\n\n", full)

        prefix = report_type if report_type != "daily" else "daily"
        out_file = output_dir / f"{prefix}_{lang}.md"

        # Backup if exists
        if out_file.exists():
            bak = output_dir / f"{prefix}_{lang}.md.bak"
            import shutil
            shutil.copy2(out_file, bak)
            log.info("  [assemble/%s] backup -> %s", lang, bak.name)

        out_file.write_text(full, "utf-8")
        assembled[lang] = out_file
        log.info(
            "[assemble/%s] => %s (%d chars, %d/%d sections)",
            lang, out_file.name, len(full), len(parts), len(order),
        )
        if missing:
            log.warning("[assemble/%s] missing sections: %s", lang, ", ".join(missing))

    return assembled


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def _publish(output_dir: Path, date_str: str, assembled: dict[str, Path]) -> None:
    """Run publish scripts based on config/platforms.json and env vars."""
    try:
        platforms = load_platforms()
    except Exception as exc:
        log.warning("[publish] Could not load platforms.json: %s", exc)
        platforms = {}

    python = _find_python()
    scripts_dir = ROOT / "scripts"

    def _run_publish(script_name: str, label: str, extra_check: bool = True) -> None:
        script = scripts_dir / script_name
        if not script.exists():
            return
        if not extra_check:
            log.info("[publish] %s not configured, skipping", label)
            return
        log.info("[publish] %s ...", label)
        try:
            result = subprocess.run(
                [python, str(script), "--date", date_str, "--output", str(output_dir)],
                timeout=PUBLISH_TIMEOUT,
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            if result.returncode == 0:
                log.info("[publish] %s done", label)
            else:
                log.warning("[publish] %s failed (exit %d): %s",
                            label, result.returncode, result.stderr[:500])
        except subprocess.TimeoutExpired:
            log.warning("[publish] %s timed out", label)
        except Exception as exc:
            log.warning("[publish] %s error: %s", label, exc)

    _run_publish(
        "publish_wordpress.py", "WordPress",
        extra_check=(
            bool(os.environ.get("WORDPRESS_URL"))
            and bool(os.environ.get("WORDPRESS_APP_PASSWORD"))
            and "en" in assembled
        ),
    )
    _run_publish(
        "publish_feishu.py", "Feishu",
        extra_check=(
            bool(os.environ.get("FEISHU_WEBHOOK"))
            and "zh" in assembled
        ),
    )
    _run_publish(
        "publish_twitter.py", "Twitter/X",
        extra_check=(
            bool(os.environ.get("TWITTER_API_KEY"))
            and bool(os.environ.get("TWITTER_ACCESS_TOKEN"))
            and platforms.get("twitter", {}).get("enabled", False)
        ),
    )
    _run_publish(
        "publish_linkedin.py", "LinkedIn",
        extra_check=(
            bool(os.environ.get("LINKEDIN_ACCESS_TOKEN"))
            and bool(os.environ.get("LINKEDIN_PERSON_URN"))
            and platforms.get("linkedin", {}).get("enabled", False)
        ),
    )


# ---------------------------------------------------------------------------
# Python finder
# ---------------------------------------------------------------------------

def _find_python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    return sys.executable


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    date_str: str,
    output_dir: Path,
    report_type: str = "daily",
    publish: bool = True,
) -> bool:
    """Execute the full AI-first IntelFlow pipeline.

    Returns True if at least one report was assembled successfully.
    """
    start_ts = time.time()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    log.info("=== IntelFlow AI-first pipeline ===")
    log.info("Date:   %s", date_str)
    log.info("Type:   %s", report_type)
    log.info("Output: %s", output_dir)

    # ------------------------------------------------------------------
    # 1. Load configuration
    # ------------------------------------------------------------------
    log.info("[1/6] Loading configuration...")
    ai_config = load_ai_config()
    focus = load_focus_config()

    # Enabled dimensions only
    all_dims: dict[str, dict] = {
        k: v for k, v in focus.get("dimensions", {}).items()
        if isinstance(v, dict) and v.get("enabled", True)
    }
    if not all_dims:
        log.error("No enabled dimensions in config/focus.json. Aborting.")
        return False

    languages: list[str] = focus.get("languages", ["en"])
    if isinstance(languages, str):
        languages = [languages]

    log.info("Dimensions: %s", list(all_dims.keys()))
    log.info("Languages: %s", languages)

    # ------------------------------------------------------------------
    # 2. Create adapters
    # ------------------------------------------------------------------
    log.info("[2/6] Creating AI and search adapters...")
    llm_config = ai_config.get("llm", {})
    try:
        llm = create_llm(llm_config)
        log.info("LLM: %s / %s", llm.name, llm_config.get("model", ""))
    except LLMError as exc:
        log.error("Failed to create LLM adapter: %s", exc)
        return False

    search_config = ai_config.get("search", {})
    searcher = None
    if search_config.get("provider"):
        try:
            searcher = create_search(search_config)
            log.info("Search: %s", searcher.name)
        except SearchError as exc:
            log.warning("Search adapter unavailable (%s) — will generate without search", exc)
    else:
        log.warning("No search provider configured in config/ai.json — sections will use training knowledge only")

    # ------------------------------------------------------------------
    # 3. Run optional plugins
    # ------------------------------------------------------------------
    log.info("[3/6] Running plugins...")
    plugin_context = _run_plugins(date_str, output_dir)

    # ------------------------------------------------------------------
    # 4. Parallel dimension generation (search + write section)
    # ------------------------------------------------------------------
    log.info("[4/6] Generating dimension sections (parallel)...")

    # Build flat list of (dim_key, dim_cfg, lang) tasks
    tasks: list[tuple[str, dict, str]] = []
    for dim_key, dim_cfg in all_dims.items():
        for lang in languages:
            tasks.append((dim_key, dim_cfg, lang))

    max_workers = min(6, len(tasks))  # cap parallelism to avoid rate limits
    results: dict[tuple[str, str], bool] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for dim_key, dim_cfg, lang in tasks:
            future = executor.submit(
                _generate_dimension_section,
                dim_key, dim_cfg, date_str, report_type,
                lang, llm, searcher,
                sections_dir, plugin_context,
            )
            future_map[future] = (dim_key, lang)

        for future in as_completed(future_map):
            dim_key, lang = future_map[future]
            try:
                _, _, ok = future.result(timeout=SECTION_TIMEOUT)
                results[(dim_key, lang)] = ok
                status = "OK" if ok else "FAIL"
                log.info("  [%s/%s] %s", dim_key, lang, status)
            except FuturesTimeout:
                log.error("  [%s/%s] TIMEOUT after %ds", dim_key, lang, SECTION_TIMEOUT)
                results[(dim_key, lang)] = False
            except Exception as exc:
                log.error("  [%s/%s] ERROR: %s", dim_key, lang, exc)
                results[(dim_key, lang)] = False

    succeeded = sum(1 for v in results.values() if v)
    log.info("Dimension sections: %d/%d succeeded", succeeded, len(tasks))

    if succeeded == 0:
        log.error("All dimension sections failed. Aborting.")
        return False

    # ------------------------------------------------------------------
    # 5. Overview + synthesis (sequential, needs sections to exist first)
    # ------------------------------------------------------------------
    log.info("[5/6] Generating overview and synthesis...")
    for lang in languages:
        _generate_overview(llm, sections_dir, lang, report_type, date_str)
        _generate_synthesis(llm, sections_dir, lang, report_type, date_str)

    # ------------------------------------------------------------------
    # 5b. Assemble final reports
    # ------------------------------------------------------------------
    assembled = _assemble_reports(output_dir, sections_dir, date_str, report_type, languages, focus)

    if not assembled:
        log.error("Assembly produced no output files. Aborting.")
        return False

    for lang, fpath in assembled.items():
        size = fpath.stat().st_size
        words = len(fpath.read_text("utf-8").split())
        log.info("Report %s: %s — %d bytes / ~%d words", lang, fpath.name, size, words)

    # ------------------------------------------------------------------
    # 6. Publish
    # ------------------------------------------------------------------
    if publish:
        log.info("[6/6] Publishing...")
        _publish(output_dir, date_str, assembled)
    else:
        log.info("[6/6] Publishing skipped (--no-publish)")

    elapsed = int(time.time() - start_ts)
    log.info("=== Pipeline complete in %dm %ds ===", elapsed // 60, elapsed % 60)
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="IntelFlow AI-first pipeline — search + generate + publish",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/run_pipeline.py --date 2026-03-11\n"
            "  python3 scripts/run_pipeline.py --date 2026-03-11 --type weekly\n"
            "  python3 scripts/run_pipeline.py --date 2026-03-11 --no-publish\n"
        ),
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date string YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: output/{date})",
    )
    parser.add_argument(
        "--type",
        default="daily",
        choices=["daily", "weekly", "monthly"],
        help="Report type (default: daily)",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Skip publishing step",
    )
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else ROOT / "output" / args.date

    ok = run_pipeline(
        date_str=args.date,
        output_dir=output_dir,
        report_type=args.type,
        publish=not args.no_publish,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
