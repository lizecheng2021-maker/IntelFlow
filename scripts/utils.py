#!/usr/bin/env python3
"""
IntelFlow - Shared utilities module.

Provides common path constants, config loading, JSON I/O, logging,
and text processing functions used across all pipeline scripts.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============================================================
# Path constants
# ============================================================
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
CONFIG_DIR = ROOT / "config"
LOGS_DIR = ROOT / "logs"
TZ_CN = timezone(timedelta(hours=8))


# ============================================================
# Date utilities
# ============================================================
def get_today_str() -> str:
    """Return today's date string as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def get_today_dir() -> Path:
    """Return today's output directory, creating it if needed."""
    d = OUTPUT_DIR / get_today_str()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================
# Configuration loading
# ============================================================
def load_config(name: str = "sources.json") -> dict:
    """Load a JSON config file from the config/ directory."""
    return load_json(CONFIG_DIR / name)


def _load_env() -> dict[str, str]:
    """Load environment variables from .env file (KEY=VALUE format)."""
    env_path = ROOT / ".env"
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env_vars[key.strip()] = value.strip()
    return env_vars


def _resolve_env_placeholders(obj, env_vars: dict[str, str]):
    """Recursively replace ${VAR_NAME} placeholders in JSON with .env values."""
    if isinstance(obj, str):
        def _replacer(m):
            var_name = m.group(1)
            return os.environ.get(var_name, env_vars.get(var_name, m.group(0)))
        return re.sub(r'\$\{(\w+)\}', _replacer, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_placeholders(v, env_vars) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_placeholders(item, env_vars) for item in obj]
    return obj


def load_sources_config() -> dict:
    """Load sources.json and return only enabled sources with their configs.

    Returns a dict with three keys:
      - "builtin_sources": dict of enabled builtin sources (name → config)
      - "rss_feeds": dict of RSS feed categories (category → [urls])
      - "custom_sources": dict of enabled custom sources (name → config)
    """
    raw = load_config("sources.json")
    result = {}

    # Filter builtin sources to enabled only
    builtin = raw.get("builtin_sources", {})
    result["builtin_sources"] = {
        name: cfg
        for name, cfg in builtin.items()
        if isinstance(cfg, dict) and cfg.get("enabled", False)
    }

    # RSS feeds pass through as-is (strip _comment keys)
    rss = raw.get("rss_feeds", {})
    result["rss_feeds"] = {
        cat: urls for cat, urls in rss.items()
        if not cat.startswith("_") and isinstance(urls, list)
    }

    # Filter custom sources to enabled only
    custom = raw.get("custom_sources", {})
    result["custom_sources"] = {
        name: cfg
        for name, cfg in custom.items()
        if isinstance(cfg, dict) and cfg.get("enabled", False)
    }

    return result


def get_rss_feeds(category: str | None = None) -> list[str]:
    """Return RSS feed URLs from sources.json, optionally filtered by category.

    Args:
        category: If provided, return only feeds from that category (e.g. "tech", "seo").
                  If None, return all feeds across all categories.

    Returns:
        A flat list of RSS feed URL strings.
    """
    sources = load_sources_config()
    rss = sources.get("rss_feeds", {})

    if category is not None:
        return list(rss.get(category, []))

    # Flatten all categories
    all_feeds = []
    for urls in rss.values():
        if isinstance(urls, list):
            all_feeds.extend(urls)
    return all_feeds


def load_ai_config() -> dict:
    """Load config/ai.json with API keys resolved from environment.

    Returns dict with 'llm' and 'search' sections, e.g.:
      {"llm": {"provider": "anthropic", "model": "...", "api_key": "sk-..."}, "search": {...}}
    """
    raw = load_config("ai.json")
    if not raw:
        return {"llm": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "temperature": 0.7, "max_tokens": 4096}, "search": {}}

    # Resolve API key from environment
    llm = raw.get("llm", {})
    providers = raw.get("providers", {})
    provider_name = llm.get("provider", "anthropic")
    provider_info = providers.get(provider_name, {})
    env_key = provider_info.get("env_key")
    if env_key:
        llm["api_key"] = os.environ.get(env_key, _load_env().get(env_key, ""))
    if provider_name == "ollama":
        llm.setdefault("base_url", provider_info.get("base_url", "http://localhost:11434"))

    # Resolve search API key
    search = raw.get("search", {})
    search_provider = search.get("provider", "")
    search_env_map = {"tavily": "TAVILY_API_KEY", "serpapi": "SERPAPI_API_KEY", "bing": "BING_API_KEY", "google_cse": "GOOGLE_CSE_KEY"}
    if search_provider in search_env_map:
        skey = search_env_map[search_provider]
        search["api_key"] = os.environ.get(skey, _load_env().get(skey, ""))

    return {"llm": llm, "search": search, "providers": providers}


def load_focus_config() -> dict:
    """Load config/focus.json and return dimension definitions.

    Returns dict with 'dimensions' key, each dimension has:
      {"enabled": bool, "weight": int, "label": str, "description": str}
    """
    raw = load_config("focus.json")
    if not raw:
        return {"dimensions": {}}
    return raw


def load_platforms() -> dict:
    """Load config/platforms.json with ${VAR} placeholders resolved from .env."""
    raw = load_json(CONFIG_DIR / "platforms.json")
    env_vars = _load_env()
    return _resolve_env_placeholders(raw, env_vars)


# ============================================================
# JSON I/O
# ============================================================
def load_json(path: Path | str) -> dict:
    """Safely load a JSON file. Returns empty dict on failure."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[WARN] JSON parse error {path.name}: {e}")
        return {}


def save_json(data: dict | list, path: Path | str):
    """Save data as JSON file (auto-creates parent directories)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# Logging
# ============================================================
def setup_logger(name: str) -> logging.Logger:
    """Configure a named logger with console + file output."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
        fh = logging.FileHandler(LOGS_DIR / f"{get_today_str()}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


# ============================================================
# Text processing
# ============================================================
def clean_html(html_text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", html_text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def truncate(text: str, max_chars: int = 2000) -> str:
    """Truncate text to the specified length."""
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + "..."


# ============================================================
# Publish result tracking
# ============================================================
def save_publish_result(
    platform: str,
    url: str = "",
    status: str = "success",
    detail: str = "",
    date: str | None = None,
):
    """
    Save a publish result to output/{today}/publish_results.json.
    Each call appends/updates one platform's publish result.
    """
    if date:
        day_dir = OUTPUT_DIR / date
        day_dir.mkdir(parents=True, exist_ok=True)
    else:
        day_dir = get_today_dir()
    results_path = day_dir / "publish_results.json"
    results = load_json(results_path)
    results[platform] = {
        "status": status,
        "url": url,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    }
    save_json(results, results_path)


def extract_report_title(md_text: str, fallback: str = "Daily Report") -> str:
    """Extract the first # heading from Markdown text."""
    for line in md_text.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
