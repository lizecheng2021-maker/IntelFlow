#!/usr/bin/env python3
"""
LinkedIn publishing script — posts an article via LinkedIn API v2 (UGC Posts).

Setup steps:
1. Go to linkedin.com/developers → Create an app
2. Request "Share on LinkedIn" and "OpenID Connect" products
3. Generate a 3-legged OAuth 2.0 access token with scope: w_member_social
4. Find your Person URN: GET https://api.linkedin.com/v2/userinfo
   (returns "sub" field — your person ID, format: urn:li:person:XXXXX)
5. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN in .env

LinkedIn UGC Posts API docs:
  https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/ugc-post-api
"""

import argparse
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from utils import load_platforms

PLATFORMS = load_platforms()

UGC_POSTS_ENDPOINT = "https://api.linkedin.com/v2/ugcPosts"
MAX_CONTENT_CHARS = 3000


# ============================================================
# Content helpers
# ============================================================

def _extract_title(markdown: str) -> str:
    """Extract the H1 title from markdown, or return a default."""
    m = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "Daily Intel Briefing"


def _clean_markdown(text: str) -> str:
    """Convert markdown to plain text suitable for LinkedIn."""
    # Remove H1 (already used as title)
    text = re.sub(r"^#\s+.+$", "", text, flags=re.MULTILINE)
    # Convert headings to bold-style plain text
    text = re.sub(r"^#{1,6}\s+(.+)$", r"── \1 ──", text, flags=re.MULTILINE)
    # Bold and italic → plain
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Links — keep display text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Images — remove
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Horizontal rules
    text = re.sub(r"^---+\s*$", "\n", text, flags=re.MULTILINE)
    # List bullets → keep as-is for readability
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    # Collapse excess blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate(text: str, max_chars: int) -> str:
    """Truncate to max_chars, breaking at a word boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    cut = truncated.rfind("\n")
    if cut < max_chars * 0.8:
        cut = truncated.rfind(" ")
    if cut < 0:
        cut = max_chars
    return truncated[:cut].rstrip() + "\n\n[Read the full report →]"


# ============================================================
# Main publish function
# ============================================================

def publish_to_linkedin(
    markdown: str,
    max_chars: int = MAX_CONTENT_CHARS,
) -> str:
    """
    Post the report to LinkedIn as a text share (UGC post).

    Args:
        markdown: Full markdown content of the English report
        max_chars: Maximum characters for the post body

    Returns: Post URN string on success (e.g. "urn:li:ugcPost:..."), or "" on failure
    """
    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    person_urn = os.environ.get("LINKEDIN_PERSON_URN", "")

    if not access_token or not person_urn:
        print("[ERROR] LinkedIn credentials incomplete.")
        print("Required env vars: LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN")
        return ""

    title = _extract_title(markdown)
    body = _clean_markdown(markdown)
    body = _truncate(body, max_chars)

    # Full post text: title on top, then body
    post_text = f"{title}\n\n{body}"

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": post_text,
                },
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        resp = requests.post(UGC_POSTS_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        post_urn = resp.headers.get("x-restli-id", "") or resp.json().get("id", "")
        print(f"[OK] LinkedIn post published: {post_urn}")

        try:
            from utils import save_publish_result
            save_publish_result("linkedin", url="", status="success",
                                detail=f"Post URN: {post_urn}")
        except Exception:
            pass

        return post_urn

    except requests.HTTPError as e:
        msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            msg += f" | {e.response.text[:400]}"
        print(f"[ERROR] LinkedIn publish failed: {msg}")
        try:
            from utils import save_publish_result
            save_publish_result("linkedin", status="error", detail=msg)
        except Exception:
            pass
        return ""

    except Exception as e:
        print(f"[ERROR] LinkedIn unexpected error: {e}")
        try:
            from utils import save_publish_result
            save_publish_result("linkedin", status="error", detail=str(e))
        except Exception:
            pass
        return ""


# ============================================================
# CLI entry point
# ============================================================

if __name__ == "__main__":
    from datetime import datetime

    parser = argparse.ArgumentParser(description="Publish report to LinkedIn")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date YYYY-MM-DD")
    parser.add_argument("--max-chars", type=int, default=MAX_CONTENT_CHARS,
                        help="Max characters for post body")
    args = parser.parse_args()

    config = PLATFORMS.get("linkedin", {})
    if not config.get("enabled", False):
        print("[INFO] LinkedIn publishing disabled in platforms.json. Set enabled=true to activate.")
        sys.exit(0)

    max_chars = config.get("max_chars", args.max_chars)
    lang = config.get("post_language", "en")

    report_file = ROOT / "output" / args.date / f"daily_{lang}.md"
    if not report_file.exists():
        print(f"[ERROR] Report not found: {report_file}")
        sys.exit(1)

    markdown = report_file.read_text(encoding="utf-8")
    post_urn = publish_to_linkedin(markdown, max_chars=max_chars)

    if not post_urn:
        sys.exit(1)
