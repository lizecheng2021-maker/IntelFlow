#!/usr/bin/env python3
"""
IntelFlow - Unified web search adapter layer.

Provides a common interface for multiple search APIs (Tavily, SerpAPI, Bing, Google CSE).
Each adapter normalizes results to: {"title": str, "url": str, "content": str, "score": float}

Usage:
    from search_adapters import create_search, load_search_config

    config = load_search_config()
    searcher = create_search(config)
    results = searcher.search("AI agent frameworks 2026")
"""

import abc
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from utils import CONFIG_DIR, load_json, _load_env, _resolve_env_placeholders

logger = logging.getLogger("search_adapters")

TIMEOUT = 30  # seconds per search call


# ============================================================
# Exceptions
# ============================================================
class SearchError(Exception):
    """Raised when a search operation fails irrecoverably."""
    pass


# ============================================================
# Abstract base class
# ============================================================
class SearchAdapter(abc.ABC):
    """Abstract base for all search adapters."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name of this search provider."""
        ...

    @abc.abstractmethod
    def search(self, query: str, max_results: int = 10, days: int = 2) -> list[dict]:
        """Execute a web search and return normalized results.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            days: Recency filter — prefer results from the last N days.

        Returns:
            List of dicts with keys: title, url, content, score.
            Returns empty list on failure (logs warning).
        """
        ...

    def test_connection(self) -> bool:
        """Verify the adapter can reach its API with a simple test search.

        Returns:
            True if the test search succeeds, False otherwise.
        """
        try:
            results = self.search("test", max_results=1, days=7)
            return isinstance(results, list)
        except Exception as e:
            logger.warning("%s connection test failed: %s", self.name, e)
            return False


# ============================================================
# Tavily
# ============================================================
class TavilySearchAdapter(SearchAdapter):
    """Search via Tavily API (POST, advanced depth)."""

    def __init__(self, api_key: str):
        if not api_key:
            raise SearchError("Tavily API key is required")
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "Tavily"

    def search(self, query: str, max_results: int = 10, days: int = 2) -> list[dict]:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "include_answer": True,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("Tavily search failed for %r: %s", query, e)
            return []

        results: list[dict] = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": float(item.get("score", 0.0)),
            })
        return results[:max_results]


# ============================================================
# SerpAPI
# ============================================================
class SerpAPISearchAdapter(SearchAdapter):
    """Search via SerpAPI (Google search backend)."""

    def __init__(self, api_key: str):
        if not api_key:
            raise SearchError("SerpAPI API key is required")
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "SerpAPI"

    def search(self, query: str, max_results: int = 10, days: int = 2) -> list[dict]:
        params = {
            "q": query,
            "api_key": self._api_key,
            "num": max_results,
            "tbs": f"qdr:d{days}",
        }
        try:
            resp = requests.get(
                "https://serpapi.com/search.json",
                params=params,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("SerpAPI search failed for %r: %s", query, e)
            return []

        results: list[dict] = []
        organic = data.get("organic_results", [])
        total = len(organic) or 1  # avoid division by zero
        for i, item in enumerate(organic):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "content": item.get("snippet", ""),
                "score": round(1.0 - (i / total), 4),  # position-based score
            })
        return results[:max_results]


# ============================================================
# Bing Web Search
# ============================================================
class BingSearchAdapter(SearchAdapter):
    """Search via Bing Web Search API v7."""

    def __init__(self, api_key: str):
        if not api_key:
            raise SearchError("Bing API key is required")
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "Bing"

    def search(self, query: str, max_results: int = 10, days: int = 2) -> list[dict]:
        # Bing freshness filter: Day, Week, Month, or YYYY-MM-DD..YYYY-MM-DD
        if days <= 1:
            freshness = "Day"
        elif days <= 7:
            freshness = "Week"
        else:
            freshness = "Month"

        params = {
            "q": query,
            "count": max_results,
            "freshness": freshness,
            "textDecorations": "false",
            "textFormat": "Raw",
        }
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}

        try:
            resp = requests.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params=params,
                headers=headers,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("Bing search failed for %r: %s", query, e)
            return []

        results: list[dict] = []
        web_pages = data.get("webPages", {}).get("value", [])
        total = len(web_pages) or 1
        for i, item in enumerate(web_pages):
            results.append({
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "content": item.get("snippet", ""),
                "score": round(1.0 - (i / total), 4),
            })
        return results[:max_results]


# ============================================================
# Google Custom Search Engine
# ============================================================
class GoogleCSEAdapter(SearchAdapter):
    """Search via Google Custom Search JSON API."""

    def __init__(self, api_key: str, cx: str = ""):
        if not api_key:
            raise SearchError("Google CSE API key is required")
        if not cx:
            raise SearchError("Google CSE cx (search engine ID) is required")
        self._api_key = api_key
        self._cx = cx

    @property
    def name(self) -> str:
        return "Google CSE"

    def search(self, query: str, max_results: int = 10, days: int = 2) -> list[dict]:
        # Google CSE caps at 10 results per request
        num = min(max_results, 10)
        params: dict[str, Any] = {
            "key": self._api_key,
            "cx": self._cx,
            "q": query,
            "num": num,
        }
        # dateRestrict: d[N] = past N days
        if days > 0:
            params["dateRestrict"] = f"d{days}"

        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("Google CSE search failed for %r: %s", query, e)
            return []

        results: list[dict] = []
        items = data.get("items", [])
        total = len(items) or 1
        for i, item in enumerate(items):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "content": item.get("snippet", ""),
                "score": round(1.0 - (i / total), 4),
            })
        return results[:max_results]


# ============================================================
# Factory
# ============================================================
_PROVIDER_MAP: dict[str, type[SearchAdapter]] = {
    "tavily": TavilySearchAdapter,
    "serpapi": SerpAPISearchAdapter,
    "bing": BingSearchAdapter,
    "google_cse": GoogleCSEAdapter,
}


def create_search(config: dict) -> SearchAdapter:
    """Create a SearchAdapter instance from a config dict.

    Config format:
        {
            "provider": "tavily",       # tavily | serpapi | bing | google_cse
            "api_key": "tvly-...",       # API key (or resolved from env)
            "cx": "...",                 # Google CSE only: search engine ID
            "max_results": 10            # optional default (not used here)
        }

    Raises:
        SearchError: If provider is unknown or required keys are missing.
    """
    provider = config.get("provider", "").lower()
    if provider not in _PROVIDER_MAP:
        raise SearchError(
            f"Unknown search provider: {provider!r}. "
            f"Available: {', '.join(_PROVIDER_MAP)}"
        )

    api_key = config.get("api_key", "")

    if provider == "google_cse":
        cx = config.get("cx", "")
        return GoogleCSEAdapter(api_key=api_key, cx=cx)

    adapter_cls = _PROVIDER_MAP[provider]
    return adapter_cls(api_key=api_key)


# ============================================================
# Config loader
# ============================================================
def load_search_config() -> dict:
    """Load the search configuration from config/ai.json.

    Looks for the "search" key in ai.json and resolves any ${VAR}
    placeholders from .env or environment variables.

    Returns:
        Config dict ready for create_search().
    """
    raw = load_json(CONFIG_DIR / "ai.json")
    env_vars = _load_env()
    resolved = _resolve_env_placeholders(raw, env_vars)
    search_cfg = resolved.get("search", {})

    if not search_cfg:
        logger.warning(
            "No 'search' section found in config/ai.json. "
            "Returning empty config."
        )

    return search_cfg
