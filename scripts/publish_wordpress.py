#!/usr/bin/env python3
"""
WordPress publishing script.

Setup steps:
1. WordPress Admin -> Users -> Your Profile -> Application Passwords -> Add New
2. Fill site URL, username, and app password into config/platforms.json

WordPress REST API docs: https://developer.wordpress.org/rest-api/
"""

import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from utils import load_platforms
PLATFORMS = load_platforms()


def publish_to_wordpress(
    title: str,
    content_html: str,
    status: str = "draft",
    categories: list[int] | None = None,
    tags: list[str] | None = None,
    featured_image_url: str | None = None,
) -> dict:
    """
    Publish an article to WordPress.

    Args:
        title: Article title
        content_html: HTML-formatted article content
        status: "draft" or "publish"
        categories: List of category IDs
        tags: List of tag names
        featured_image_url: Featured image URL (optional)

    Returns: {"id": 123, "url": "...", "status": "..."}
    """
    config = PLATFORMS["wordpress"]
    site_url = config.get("site_url", "").rstrip("/")
    username = config.get("username", "")
    app_password = config.get("app_password", "")

    if not all([site_url, username, app_password]):
        print("[ERROR] WordPress configuration incomplete")
        print("Please fill site_url, username, app_password in config/platforms.json")
        return {}

    # Basic Auth
    auth_str = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json",
    }

    # Upload featured image if provided
    featured_media_id = None
    if featured_image_url:
        featured_media_id = upload_media(site_url, headers, featured_image_url)

    # Create post
    post_data = {
        "title": title,
        "content": content_html,
        "status": status,
    }
    if categories:
        post_data["categories"] = categories
    if featured_media_id:
        post_data["featured_media"] = featured_media_id

    api_url = f"{site_url}/wp-json/wp/v2/posts"

    try:
        resp = requests.post(api_url, headers=headers, json=post_data, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Add tags (WordPress tags need to be created or looked up by ID)
        if tags:
            tag_ids = get_or_create_tags(site_url, headers, tags)
            if tag_ids:
                update_url = f"{api_url}/{data['id']}"
                requests.post(update_url, headers=headers, json={"tags": tag_ids}, timeout=15)

        result = {
            "id": data.get("id"),
            "url": data.get("link", ""),
            "status": data.get("status", ""),
        }
        print(f"[OK] WordPress published: {result['url']} (status: {result['status']})")

        # Record publish result
        try:
            from utils import save_publish_result
            save_publish_result("wordpress", url=result["url"], status="success",
                               detail=f"Post ID: {result['id']}")
        except Exception:
            pass

        return result

    except requests.RequestException as e:
        print(f"[ERROR] WordPress publish failed: {e}")
        try:
            from utils import save_publish_result
            save_publish_result("wordpress", status="error", detail=str(e))
        except Exception:
            pass
        return {}


def upload_media(site_url: str, headers: dict, image_url: str) -> int | None:
    """Download image and upload to WordPress media library."""
    try:
        img_resp = requests.get(image_url, timeout=15)
        img_resp.raise_for_status()

        media_headers = headers.copy()
        media_headers["Content-Type"] = img_resp.headers.get("Content-Type", "image/jpeg")
        media_headers["Content-Disposition"] = 'attachment; filename="featured.jpg"'

        resp = requests.post(
            f"{site_url}/wp-json/wp/v2/media",
            headers=media_headers,
            data=img_resp.content,
            timeout=30,
        )
        resp.raise_for_status()
        media_id = resp.json().get("id")
        print(f"[OK] WordPress media uploaded: ID={media_id}")
        return media_id
    except Exception as e:
        print(f"[WARN] WordPress media upload failed: {e}")
        return None


def upload_media_file(site_url: str, headers: dict, file_path: str, filename: str = None) -> dict | None:
    """Upload a local image file to WordPress media library."""
    if not os.path.exists(file_path):
        print(f"[WARN] File not found: {file_path}")
        return None

    if filename is None:
        filename = os.path.basename(file_path)

    content_type = mimetypes.guess_type(file_path)[0] or "image/png"

    with open(file_path, "rb") as f:
        media_headers = {
            "Authorization": headers["Authorization"],
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        resp = requests.post(
            f"{site_url}/wp-json/wp/v2/media",
            headers=media_headers,
            data=f.read(),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[OK] WP media upload: {filename} -> ID={data.get('id')}, URL={data.get('source_url', '')}")
        return {"id": data.get("id"), "url": data.get("source_url", "")}


def embed_images_in_markdown(markdown_text: str, image_urls: dict) -> str:
    """Insert images at corresponding section positions in markdown.

    image_urls: {"cover": "url", "ai": "url", "seo": "url", "biz": "url", "market": "url", "summary": "url"}
    """
    lines = markdown_text.split("\n")
    result = []

    # Insert cover image at the beginning
    if "cover" in image_urls:
        result.append(f"![Cover]({image_urls['cover']})")
        result.append("")

    # Section title keywords -> image key (matching 4 main thematic sections)
    section_map = {
        "AI": "ai",
        "SEO": "seo",
        "Business": "biz",
        "Market": "market",
    }

    current_section = None
    for line in lines:
        # Detect ## heading to switch sections, insert image at previous section end
        if line.startswith("## "):
            matched = None
            for keyword, section_key in section_map.items():
                if keyword in line:
                    matched = section_key
                    break
            # Previous section ended: insert image
            if current_section and current_section in image_urls:
                result.append(f"\n![{current_section}]({image_urls[current_section]})\n")
            current_section = matched  # None if no match (e.g. synthesis)

        result.append(line)

    # Insert summary image at article end
    if "summary" in image_urls:
        result.append(f"\n![Summary]({image_urls['summary']})")

    return "\n".join(result)


def get_or_create_tags(site_url: str, headers: dict, tag_names: list[str]) -> list[int]:
    """Get or create WordPress tags."""
    tag_ids = []
    for name in tag_names:
        try:
            resp = requests.get(
                f"{site_url}/wp-json/wp/v2/tags",
                headers=headers,
                params={"search": name},
                timeout=10,
            )
            resp.raise_for_status()
            tags = resp.json()
            if tags:
                tag_ids.append(tags[0]["id"])
            else:
                resp = requests.post(
                    f"{site_url}/wp-json/wp/v2/tags",
                    headers=headers,
                    json={"name": name},
                    timeout=10,
                )
                resp.raise_for_status()
                tag_ids.append(resp.json()["id"])
        except Exception:
            pass
    return tag_ids


def markdown_to_html(markdown_text: str) -> str:
    """Convert Markdown to WordPress HTML."""
    import re

    lines = markdown_text.split("\n")
    html_lines = []
    in_list = False
    in_blockquote = False

    for line in lines:
        stripped = line.strip()

        # Horizontal rule -> skip (WordPress uses headings for separation)
        if stripped in ("---", "***", "___"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        # Empty line
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_blockquote:
                html_lines.append("</blockquote>")
                in_blockquote = False
            html_lines.append("")
            continue

        # Inline formatting
        def inline_format(text):
            # Images ![alt](url)
            text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" />', text)
            # Links [text](url)
            text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
            # Bold
            text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
            # Italic
            text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
            # Inline code
            text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
            return text

        # Headings
        if stripped.startswith("#### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h4>{inline_format(stripped[5:])}</h4>")
        elif stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{inline_format(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{inline_format(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{inline_format(stripped[2:])}</h1>")
        # Blockquote
        elif stripped.startswith("> "):
            if not in_blockquote:
                html_lines.append("<blockquote>")
                in_blockquote = True
            html_lines.append(f"<p>{inline_format(stripped[2:])}</p>")
        # List
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{inline_format(stripped[2:])}</li>")
        # Regular paragraph
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_blockquote:
                html_lines.append("</blockquote>")
                in_blockquote = False
            html_lines.append(f"<p>{inline_format(stripped)}</p>")

    # Close unclosed tags
    if in_list:
        html_lines.append("</ul>")
    if in_blockquote:
        html_lines.append("</blockquote>")

    # Clean consecutive blank lines
    result = "\n".join(html_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


if __name__ == "__main__":
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(description="WordPress publishing")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date YYYY-MM-DD")
    parser.add_argument("--type", default="daily", choices=["daily", "weekly", "monthly"], help="Report type")
    args = parser.parse_args()

    today = args.date
    FILE_MAP = {"daily": "daily_en.md", "weekly": "weekly_en.md", "monthly": "monthly_en.md"}
    TITLE_MAP = {"daily": "Daily Intel", "weekly": "Weekly Intel", "monthly": "Monthly Intel"}
    daily_file = ROOT / "output" / today / FILE_MAP.get(args.type, "daily_en.md")

    if not daily_file.exists():
        print(f"[ERROR] {args.type} English report not found: {daily_file}")
        sys.exit(1)

    markdown = daily_file.read_text(encoding="utf-8")

    # Extract title from content and remove from body (avoid WordPress title duplication)
    title = f"{TITLE_MAP.get(args.type, 'Daily Intel')} | {today}"
    lines = markdown.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            lines[i] = ""  # Remove title line from body
            break
    markdown = "\n".join(lines).lstrip("\n")

    # Clean horizontal rules that shouldn't appear in English report
    import re
    markdown = re.sub(r"^---+\s*$", "", markdown, flags=re.MULTILINE)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)

    # ============================================
    # Internal link insertion (SEO optimization)
    # ============================================
    try:
        from internal_links import fetch_sitemap, build_keyword_map, insert_internal_links

        config = PLATFORMS["wordpress"]
        site_url = config.get("site_url", "").rstrip("/")
        if site_url:
            print("[INFO] Parsing sitemap and inserting internal links...")
            posts = fetch_sitemap(f"{site_url}/sitemap_index.xml")
            if posts:
                keyword_map = build_keyword_map(posts)
                markdown = insert_internal_links(markdown, keyword_map, max_links=5)
    except ImportError:
        print("[WARN] internal_links module not found, skipping internal link insertion")
    except Exception as e:
        print(f"[WARN] Internal link insertion failed: {e}, continuing with publish")

    # ============================================
    # Upload images and embed in markdown
    # ============================================
    image_dir = ROOT / "output" / today / "images" / "wp"
    if not image_dir.exists():
        image_dir = ROOT / "output" / today / "images"

    if image_dir.exists():
        config = PLATFORMS["wordpress"]
        site_url = config.get("site_url", "").rstrip("/")
        username = config.get("username", "")
        app_password = config.get("app_password", "")

        if all([site_url, username, app_password]):
            import base64 as _b64
            auth_str = _b64.b64encode(f"{username}:{app_password}".encode()).decode()
            wp_headers = {
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
            }

            image_urls = {}
            image_names = {
                "cover": ["cover_en.webp", "cover_en.png", "cover.webp", "cover.png", "cover.jpg"],
                "ai": ["ai_tech.webp", "ai_tech.png", "ai.webp", "ai.png", "ai.jpg"],
                "seo": ["seo.webp", "seo.png"],
                "biz": ["biz.webp", "biz.png", "ecommerce.webp", "ecommerce.png"],
                "market": ["market.webp", "market.png", "finance.webp", "finance.png"],
                "summary": ["summary.webp", "summary.png", "summary.jpg"],
            }
            for key, filenames in image_names.items():
                for fname in filenames:
                    fpath = image_dir / fname
                    if fpath.exists():
                        media = upload_media_file(site_url, wp_headers, str(fpath))
                        if media:
                            image_urls[key] = media["url"]
                        break

            if image_urls:
                markdown = embed_images_in_markdown(markdown, image_urls)

    # Markdown -> HTML conversion (WordPress needs HTML)
    content_html = markdown_to_html(markdown)
    print(f"[INFO] Markdown -> HTML conversion complete ({len(content_html)} chars)")

    # Load tags from config or use defaults
    default_tags = ["daily-report", "AI", "finance", "SEO"]
    try:
        import json as _json
        sources_cfg = _json.loads((ROOT / "config" / "sources.json").read_text("utf-8"))
        wp_tags = sources_cfg.get("wordpress", {}).get("tags", default_tags)
    except Exception:
        wp_tags = default_tags

    result = publish_to_wordpress(
        title=title,
        content_html=content_html,
        status="publish",
        tags=wp_tags,
    )
    if result and result.get('url'):
        print(f"Article URL: {result['url']}")
    else:
        print("[ERROR] WordPress publish failed, no article URL returned")
        sys.exit(1)
