#!/usr/bin/env python3
"""Generate report sections using any configured LLM provider.

Replaces the previous claude -p CLI calls with a model-agnostic Python script.
Reads per-dimension data from sections/ dir, generates analysis markdown,
writes section files for assemble_report.py to combine.

Usage:
    python generate_sections.py --date 2025-01-15 --output output/2025-01-15
    python generate_sections.py --date 2025-01-15 --output output/2025-01-15 --type weekly
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from utils import load_json, load_ai_config, load_focus_config, setup_logger

log = setup_logger("generate")


def _load_profile() -> dict:
    """Load editorial voice profile."""
    return load_json(ROOT / "config" / "profile.json")


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
        parts.append(f"Occasional phrases: {', '.join(catchphrases[:5])}.")
    parts.append(lang_instruction)
    parts.append(
        "Requirements:\n"
        "- Use specific numbers and data points from the source data\n"
        "- Provide your own judgment, not just summaries\n"
        "- Cross-reference signals across domains when relevant\n"
        "- Never fabricate data — if uncertain, skip it\n"
        "- Output well-structured Markdown"
    )
    return "\n".join(parts)


def _build_section_prompt(section_name: str, section_data: str, report_type: str) -> str:
    """Build the user prompt for a section."""
    type_guidance = {
        "daily": "Write a detailed analysis section (800-1500 words).",
        "weekly": "Write a deep-dive weekly analysis (1500-2500 words) aggregating the week's data.",
        "monthly": "Write a comprehensive monthly review (2000-3500 words) with trend synthesis.",
    }
    guidance = type_guidance.get(report_type, type_guidance["daily"])

    return (
        f"## Section: {section_name}\n\n"
        f"{guidance}\n\n"
        f"Analyze the following data and write your analysis:\n\n"
        f"```json\n{section_data}\n```"
    )


def _generate_one_section(
    llm, section_name: str, section_file: Path,
    profile: dict, lang: str, report_type: str, output_dir: Path
) -> tuple[str, bool]:
    """Generate a single section. Returns (section_name, success)."""
    try:
        data_text = section_file.read_text("utf-8")
        # Truncate if too large (keep under ~100KB to fit most model contexts)
        if len(data_text) > 100_000:
            data_text = data_text[:100_000] + "\n... [truncated]"

        system = _build_system_prompt(profile, lang)
        prompt = _build_section_prompt(section_name, data_text, report_type)

        log.info(f"Generating: {section_name}_{lang} ({len(data_text)} chars input)")
        response = llm.generate(prompt=prompt, system=system)

        if not response or len(response.strip()) < 100:
            log.warning(f"Response too short for {section_name}_{lang}: {len(response)} chars")
            return section_name, False

        out_file = output_dir / "sections" / f"{section_name}_{lang}.md"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(response.strip(), "utf-8")
        log.info(f"Written: {section_name}_{lang}.md ({len(response)} chars)")
        return section_name, True

    except Exception as e:
        log.error(f"Failed {section_name}_{lang}: {e}")
        return section_name, False


def generate_sections(date_str: str, output_dir: str, report_type: str = "daily"):
    """Main generation flow: load config, create LLM, generate all sections."""
    out = Path(output_dir)
    sections_dir = out / "sections"

    if not sections_dir.exists():
        log.error(f"Sections directory not found: {sections_dir}")
        return False

    # Find section data files (created by split_briefing.py)
    data_files = sorted(sections_dir.glob("data_*.json"))
    if not data_files:
        log.error("No data_*.json files found in sections/")
        return False

    log.info(f"Found {len(data_files)} section data files")

    # Load configs
    ai_config = load_ai_config()
    profile = _load_profile()
    focus = load_focus_config()

    # Determine languages
    languages = focus.get("languages", ["en", "zh"])
    if isinstance(languages, str):
        languages = [languages]

    # Create LLM adapter
    try:
        from ai_adapters import create_llm, LLMError
    except ImportError:
        log.error("ai_adapters.py not found. Run from the IntelFlow root directory.")
        return False

    llm_config = ai_config.get("llm", {})
    try:
        llm = create_llm(llm_config)
        log.info(f"Using LLM: {llm.name} ({llm_config.get('model', 'default')})")
    except Exception as e:
        log.error(f"Failed to create LLM adapter: {e}")
        return False

    # Generate sections in parallel
    max_workers = min(3, len(data_files))  # Don't overwhelm API
    results = {}
    failed = []

    for lang in languages:
        log.info(f"=== Generating {lang.upper()} sections ===")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for df in data_files:
                section_name = df.stem.replace("data_", "")
                future = executor.submit(
                    _generate_one_section,
                    llm, section_name, df, profile, lang, report_type, out
                )
                futures[future] = (section_name, lang)

            for future in as_completed(futures):
                section_name, lang_code = futures[future]
                try:
                    name, ok = future.result(timeout=900)  # 15min per section
                    results[(name, lang_code)] = ok
                    if not ok:
                        failed.append((name, lang_code))
                except Exception as e:
                    log.error(f"Timeout/error for {section_name}_{lang_code}: {e}")
                    failed.append((section_name, lang_code))

    # Retry failed sections once
    if failed:
        log.info(f"Retrying {len(failed)} failed section(s)...")
        for section_name, lang in failed:
            df = sections_dir / f"data_{section_name}.json"
            if df.exists():
                name, ok = _generate_one_section(
                    llm, section_name, df, profile, lang, report_type, out
                )
                results[(name, lang)] = ok
                if ok:
                    log.info(f"Retry succeeded: {section_name}_{lang}")
                else:
                    log.error(f"Retry failed: {section_name}_{lang}")

    # Generate overview and synthesis sections
    for lang in languages:
        _generate_overview(llm, profile, lang, report_type, out, sections_dir)
        _generate_synthesis(llm, profile, lang, report_type, out, sections_dir)

    # Summary
    total = len(data_files) * len(languages)
    succeeded = sum(1 for v in results.values() if v)
    log.info(f"Generation complete: {succeeded}/{total} sections succeeded")
    return succeeded > 0


def _generate_overview(llm, profile, lang, report_type, out, sections_dir):
    """Generate the overview/summary section from all section data."""
    try:
        all_data = []
        for df in sorted(sections_dir.glob("data_*.json")):
            data = load_json(df)
            section_name = df.stem.replace("data_", "")
            count = len(data) if isinstance(data, list) else len(data.get("items", []))
            all_data.append(f"- {section_name}: {count} items")

        system = _build_system_prompt(profile, lang)
        prompt = (
            "Write a brief overview section (200-400 words) summarizing today's key stories.\n"
            "This is the opening section of the report — hook the reader.\n\n"
            f"Available sections and data volume:\n" + "\n".join(all_data)
        )

        # Read existing generated sections for context
        generated = []
        for md in sorted(sections_dir.glob(f"*_{lang}.md")):
            if md.stem.startswith("overview") or md.stem.startswith("synthesis"):
                continue
            content = md.read_text("utf-8")[:500]
            generated.append(f"### {md.stem}\n{content}...")

        if generated:
            prompt += "\n\nGenerated section previews:\n" + "\n".join(generated)

        response = llm.generate(prompt=prompt, system=system)
        prefix = f"weekly_overview" if report_type == "weekly" else (
            f"monthly_overview" if report_type == "monthly" else "overview"
        )
        out_file = out / "sections" / f"{prefix}_{lang}.md"
        out_file.write_text(response.strip(), "utf-8")
        log.info(f"Written: {prefix}_{lang}.md")
    except Exception as e:
        log.error(f"Failed overview_{lang}: {e}")


def _generate_synthesis(llm, profile, lang, report_type, out, sections_dir):
    """Generate the synthesis/takeaways section from all generated sections."""
    try:
        # Read all generated section content
        all_content = []
        for md in sorted(sections_dir.glob(f"*_{lang}.md")):
            if md.stem.startswith("synthesis"):
                continue
            all_content.append(md.read_text("utf-8"))

        combined = "\n\n---\n\n".join(all_content)
        # Truncate if needed
        if len(combined) > 80_000:
            combined = combined[:80_000] + "\n... [truncated]"

        system = _build_system_prompt(profile, lang)
        prompt = (
            "Write a synthesis section (400-600 words) that:\n"
            "- Connects signals across different domains\n"
            "- Identifies cross-cutting themes and patterns\n"
            "- Provides the 'so what' — what does today's information mean when combined?\n"
            "- Ends with a strong, memorable closing line\n\n"
            f"All sections for today:\n\n{combined}"
        )

        response = llm.generate(prompt=prompt, system=system)
        prefix = f"weekly_synthesis" if report_type == "weekly" else (
            f"monthly_synthesis" if report_type == "monthly" else "synthesis"
        )
        out_file = out / "sections" / f"{prefix}_{lang}.md"
        out_file.write_text(response.strip(), "utf-8")
        log.info(f"Written: {prefix}_{lang}.md")
    except Exception as e:
        log.error(f"Failed synthesis_{lang}: {e}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate report sections using configured LLM")
    p.add_argument("--date", required=True, help="Date string YYYY-MM-DD")
    p.add_argument("--output", required=True, help="Output directory path")
    p.add_argument("--type", default="daily", choices=["daily", "weekly", "monthly"])
    args = p.parse_args()

    ok = generate_sections(args.date, args.output, args.type)
    sys.exit(0 if ok else 1)
