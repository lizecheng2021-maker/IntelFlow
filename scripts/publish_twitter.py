#!/usr/bin/env python3
"""
Twitter/X publishing script — posts a thread via Twitter API v2.

Setup steps:
1. Go to developer.twitter.com → Create a project + app
2. Enable OAuth 1.0a with Read and Write permissions
3. Generate Access Token + Secret under "Keys and Tokens"
4. Set TWITTER_API_KEY, TWITTER_API_SECRET,
       TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET in .env

Twitter API v2 docs: https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets
"""

import argparse
import hashlib
import hmac
import os
import re
import sys
import time
import urllib.parse
import base64
import secrets
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from utils import load_platforms

PLATFORMS = load_platforms()

TWEET_ENDPOINT = "https://api.twitter.com/2/tweets"
MAX_TWEET_CHARS = 280


# ============================================================
# OAuth 1.0a signing (no SDK needed)
# ============================================================

def _percent_encode(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


def _build_oauth_header(method: str, url: str, params: dict, credentials: dict) -> str:
    """Build OAuth 1.0a Authorization header."""
    oauth_params = {
        "oauth_consumer_key": credentials["api_key"],
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": credentials["access_token"],
        "oauth_version": "1.0",
    }

    # Merge all params for signature base string
    all_params = {**params, **oauth_params}
    sorted_params = sorted(all_params.items())
    param_string = "&".join(f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted_params)

    base_string = "&".join([
        _percent_encode(method.upper()),
        _percent_encode(url),
        _percent_encode(param_string),
    ])

    signing_key = "&".join([
        _percent_encode(credentials["api_secret"]),
        _percent_encode(credentials["access_token_secret"]),
    ])

    hashed = hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1)
    signature = base64.b64encode(hashed.digest()).decode("utf-8")

    oauth_params["oauth_signature"] = signature
    header_parts = ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


def _post_tweet(text: str, credentials: dict, reply_to_id: str | None = None) -> dict:
    """Post a single tweet. Returns the response dict with 'id' and 'text'."""
    payload: dict = {"text": text}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

    auth_header = _build_oauth_header("POST", TWEET_ENDPOINT, {}, credentials)

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
    }

    resp = requests.post(TWEET_ENDPOINT, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json().get("data", {})


# ============================================================
# Content extraction helpers
# ============================================================

def _extract_section(markdown: str, zh: bool = True) -> str:
    """
    Extract the Quick Summary / 30秒速览 section from a markdown report.
    Returns plain text content of that section.
    """
    patterns = [
        r"##\s*[⚡🔥📋]?\s*30[秒秒]速[览覧].*?\n(.*?)(?=\n##|\Z)",
        r"##\s*Quick\s*Summary.*?\n(.*?)(?=\n##|\Z)",
        r"##\s*TL;DR.*?\n(.*?)(?=\n##|\Z)",
    ]
    for pat in patterns:
        m = re.search(pat, markdown, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # Fallback: first non-heading paragraph
    lines = [l.strip() for l in markdown.split("\n") if l.strip() and not l.startswith("#")]
    return "\n".join(lines[:10])


def _clean_text(text: str) -> str:
    """Strip markdown formatting for plain tweet text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_tweets(text: str, max_chars: int = MAX_TWEET_CHARS) -> list[str]:
    """
    Split a block of text into tweet-sized chunks.
    Tries to break on sentence boundaries (。.!?) first.
    """
    text = _clean_text(text)
    if len(text) <= max_chars:
        return [text]

    tweets = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            tweets.append(remaining)
            break

        chunk = remaining[:max_chars]

        # Try to break at sentence boundary
        cut = -1
        for sep in ("。", ". ", "！", "! ", "？", "? ", "\n"):
            idx = chunk.rfind(sep)
            if idx > max_chars // 2:
                cut = idx + len(sep)
                break

        if cut == -1:
            # Fall back to last space
            cut = chunk.rfind(" ")
            if cut == -1:
                cut = max_chars

        tweets.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    return [t for t in tweets if t]


# ============================================================
# Main publish function
# ============================================================

def publish_twitter_thread(
    markdown: str,
    language: str = "en",
    max_tweets: int = 5,
) -> list[str]:
    """
    Post a Twitter thread from a markdown report.

    Args:
        markdown: Full markdown content of the report
        language: "zh" or "en" — used for section detection
        max_tweets: Maximum number of tweets in the thread

    Returns: List of tweet IDs posted, or [] on failure
    """
    credentials = {
        "api_key": os.environ.get("TWITTER_API_KEY", ""),
        "api_secret": os.environ.get("TWITTER_API_SECRET", ""),
        "access_token": os.environ.get("TWITTER_ACCESS_TOKEN", ""),
        "access_token_secret": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", ""),
    }

    if not all(credentials.values()):
        print("[ERROR] Twitter credentials incomplete.")
        print("Required env vars: TWITTER_API_KEY, TWITTER_API_SECRET, "
              "TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")
        return []

    # Extract quick summary section
    section_text = _extract_section(markdown, zh=(language == "zh"))
    if not section_text:
        print("[WARN] Could not extract summary section from report. Using full content start.")
        section_text = _clean_text(markdown)[:1000]

    # Split into tweet-sized chunks
    tweets_text = _split_into_tweets(section_text)
    tweets_text = tweets_text[:max_tweets]

    if not tweets_text:
        print("[ERROR] No content to tweet.")
        return []

    print(f"[INFO] Posting Twitter thread: {len(tweets_text)} tweet(s)")

    posted_ids = []
    reply_to = None

    for i, tweet_text in enumerate(tweets_text):
        try:
            data = _post_tweet(tweet_text, credentials, reply_to_id=reply_to)
            tweet_id = data.get("id", "")
            if tweet_id:
                posted_ids.append(tweet_id)
                reply_to = tweet_id
                print(f"[OK] Tweet {i+1}/{len(tweets_text)}: id={tweet_id}")
            else:
                print(f"[WARN] Tweet {i+1} returned no ID: {data}")
            # Respect rate limits
            if i < len(tweets_text) - 1:
                time.sleep(1)
        except requests.HTTPError as e:
            print(f"[ERROR] Tweet {i+1} failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"        Response: {e.response.text[:300]}")
            # Continue — partial thread is better than nothing
            continue
        except Exception as e:
            print(f"[ERROR] Tweet {i+1} unexpected error: {e}")
            continue

    if posted_ids:
        thread_url = f"https://twitter.com/i/web/status/{posted_ids[0]}"
        print(f"[OK] Twitter thread posted: {thread_url} ({len(posted_ids)} tweets)")
        try:
            from utils import save_publish_result
            save_publish_result("twitter", url=thread_url, status="success",
                                detail=f"Thread: {len(posted_ids)} tweets, first_id={posted_ids[0]}")
        except Exception:
            pass
    else:
        print("[ERROR] Twitter thread posting failed — no tweets published.")
        try:
            from utils import save_publish_result
            save_publish_result("twitter", status="error", detail="No tweets published")
        except Exception:
            pass

    return posted_ids


# ============================================================
# CLI entry point
# ============================================================

if __name__ == "__main__":
    from datetime import datetime

    parser = argparse.ArgumentParser(description="Publish report as Twitter thread")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date YYYY-MM-DD")
    parser.add_argument("--lang", default="en", choices=["zh", "en"], help="Report language")
    parser.add_argument("--max-tweets", type=int, default=5, help="Max tweets in thread")
    args = parser.parse_args()

    config = PLATFORMS.get("twitter", {})
    if not config.get("enabled", False):
        print("[INFO] Twitter publishing disabled in platforms.json. Set enabled=true to activate.")
        sys.exit(0)

    lang = config.get("post_language", args.lang)
    max_tweets = config.get("thread_max_tweets", args.max_tweets)

    report_file = ROOT / "output" / args.date / f"daily_{lang}.md"
    if not report_file.exists():
        print(f"[ERROR] Report not found: {report_file}")
        sys.exit(1)

    markdown = report_file.read_text(encoding="utf-8")
    tweet_ids = publish_twitter_thread(markdown, language=lang, max_tweets=max_tweets)

    if not tweet_ids:
        sys.exit(1)
