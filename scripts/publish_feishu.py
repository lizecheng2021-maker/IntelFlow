#!/usr/bin/env python3
"""
Feishu/Lark document publishing script.

Supports two modes:
1. Wiki mode (recommended): Publish to Feishu wiki space, auto-categorized
   by daily/weekly/monthly, with automatic index page link insertion
2. Legacy mode (fallback): Publish to cloud space folder

API docs: https://open.feishu.cn/document/server-docs/docs/docs-overview
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from utils import load_platforms
PLATFORMS = load_platforms()


def get_tenant_token(app_id: str, app_secret: str) -> str:
    """Get Feishu tenant_access_token."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise ValueError(f"Feishu auth failed: {data.get('msg')}")
    return data["tenant_access_token"]


def get_document_url(token: str, document_id: str) -> str:
    """Get document real URL via API (auto-adapts feishu.cn / larksuite.com domain)."""
    url = "https://open.feishu.cn/open-apis/drive/v1/metas/batch_query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"request_docs": [{"doc_token": document_id, "doc_type": "docx"}]}
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                metas = data.get("data", {}).get("metas", [])
                if metas and metas[0].get("url"):
                    return metas[0]["url"]
    except Exception:
        pass
    return f"https://feishu.cn/docx/{document_id}"


def add_collaborator(token: str, document_id: str, member_type: str, member_id: str, perm: str = "full_access"):
    """Add document collaborator so the document appears in user's Feishu doc list.

    member_type: "email" | "openid" | "userid"
    perm: "full_access" | "edit" | "view"
    """
    url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/members?type=docx&need_notification=false"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "member_type": member_type,
        "member_id": member_id,
        "perm": perm,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print(f"[OK] Collaborator added: {member_id} ({perm})")
        return True
    else:
        print(f"[WARN] Failed to add collaborator: {resp.status_code} - {resp.text}")
        return False


def create_wiki_node(token: str, space_id: str, parent_node_token: str, title: str) -> dict:
    """Create a child document node in wiki space."""
    url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"obj_type": "docx", "node_type": "origin", "parent_node_token": parent_node_token, "title": title}
    resp = requests.post(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise ValueError(f"Failed to create wiki node: {data.get('msg')}")
    node = data["data"]["node"]
    return {
        "node_token": node["node_token"],
        "obj_token": node["obj_token"],
        "title": title,
    }


def update_index_page(token: str, index_obj_token: str, title: str, node_url: str):
    """Insert new document link at top of index page (daily/weekly/monthly)."""
    import urllib.parse
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Get root block_id
    get_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{index_obj_token}/blocks"
    resp = requests.get(get_url, headers=headers, timeout=10)
    if resp.status_code != 200 or resp.json().get("code") != 0:
        print(f"[WARN] Failed to get index page info: {resp.text[:200]}")
        return

    root_block_id = resp.json()["data"]["items"][0]["block_id"]

    # Insert link at top (index=0 = front)
    encoded_url = urllib.parse.quote(node_url, safe="")
    create_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{index_obj_token}/blocks/{root_block_id}/children"
    link_block = {
        "block_type": 2,
        "text": {
            "elements": [{
                "text_run": {
                    "content": title,
                    "text_element_style": {
                        "link": {"url": encoded_url}
                    },
                }
            }]
        },
    }

    resp = requests.post(create_url, headers=headers,
        json={"children": [link_block], "index": 0}, timeout=15)
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print(f"[OK] Index page link added: {title}")
    else:
        print(f"[WARN] Failed to add index link: {resp.status_code} - {resp.text[:200]}")


def create_document(token: str, title: str, folder_token: str = "") -> dict:
    """Create a Feishu document, return document_id."""
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token

    resp = requests.post(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise ValueError(f"Failed to create document: {data.get('msg')}")

    doc = data["data"]["document"]
    doc_id = doc["document_id"]
    real_url = get_document_url(token, doc_id)
    return {
        "document_id": doc_id,
        "title": doc["title"],
        "url": real_url,
    }


def set_public_permission(token: str, document_id: str):
    """Set document to publicly editable (anyone with link can edit)."""
    url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/public?type=docx"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "external_access_entity": "open",
        "security_entity": "anyone_can_edit",
        "comment_entity": "anyone_can_view",
        "share_entity": "anyone",
        "link_share_entity": "anyone_editable",
    }
    resp = requests.patch(url, headers=headers, json=body, timeout=10)
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print("[OK] Document set to publicly editable")
    else:
        print(f"[WARN] Failed to set public permission: {resp.status_code} - {resp.text}")


def delete_document(token: str, document_id: str) -> bool:
    """Delete (move to trash) a Feishu document."""
    url = f"https://open.feishu.cn/open-apis/drive/v1/files/{document_id}?type=docx"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.delete(url, headers=headers, timeout=10)
    if resp.status_code == 200 and resp.json().get("code") == 0:
        print(f"[OK] Document deleted: {document_id}")
        return True
    else:
        print(f"[ERROR] Delete failed: {resp.status_code} - {resp.text}")
        return False


def list_app_documents(token: str) -> list[dict]:
    """List all documents created by the app (via search API)."""
    url = "https://open.feishu.cn/open-apis/drive/v1/files"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"folder_token": "", "order_by": "EditedTime", "direction": "DESC"}
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    if resp.status_code == 200 and resp.json().get("code") == 0:
        files = resp.json().get("data", {}).get("files", [])
        return files
    return []


def upload_image_to_feishu(token: str, document_id: str, file_path: str) -> str | None:
    """Upload image to Feishu, return file_token."""
    if not os.path.exists(file_path):
        print(f"[WARN] Image not found: {file_path}")
        return None

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    headers = {"Authorization": f"Bearer {token}"}

    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            headers=headers,
            data={
                "file_name": file_name,
                "parent_type": "docx_image",
                "parent_node": document_id,
                "size": str(file_size),
            },
            files={"file": (file_name, f)},
            timeout=60,
        )

    if resp.status_code == 200 and resp.json().get("code") == 0:
        file_token = resp.json()["data"]["file_token"]
        print(f"[OK] Feishu image uploaded: {file_name} -> {file_token}")
        return file_token
    else:
        print(f"[WARN] Feishu image upload failed: {resp.status_code} - {resp.text}")
        return None


def markdown_to_blocks(markdown_text: str, image_files: dict | None = None, skip_title: bool = False) -> list[dict]:
    """
    Convert Markdown text to Feishu document Block format.
    Tested block types: 2=text, 3=heading1, 4=heading2, 5=heading3, 22=divider, 27=image
    bullet/callout simulated via text blocks.

    image_files: {"cover": "/path/to/cover.png", "finance": "/path/to/finance.png", ...}
    skip_title: True in wiki mode, skip # title line in markdown (avoid duplication with node title)
    """
    if image_files is None:
        image_files = {}

    blocks = []
    lines = markdown_text.split("\n")
    title_skipped = False

    # Insert cover image at article start (placeholder, write_blocks processes further)
    if "cover" in image_files:
        blocks.append({"block_type": 27, "image": {}, "_image_file_path": image_files["cover"]})

    # Track current section for image insertion at section transitions
    current_section = None

    # Section title keywords to image_files key mapping
    section_map = {
        "AI": "ai",
        "SEO": "seo",
        "Business": "biz",
        "Market": "market",
    }

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Wiki mode: skip first # title in markdown (node creation already sets title)
        if skip_title and not title_skipped and line.startswith("# ") and not line.startswith("## "):
            title_skipped = True
            continue

        # Divider
        if line == "---":
            blocks.append({"block_type": 22, "divider": {}})
            continue

        # Detect ## heading for section image insertion
        if line.startswith("## "):
            for keyword, section_key in section_map.items():
                if keyword in line:
                    if current_section and current_section in image_files:
                        blocks.append({"block_type": 27, "image": {}, "_image_file_path": image_files[current_section]})
                    current_section = section_key
                    break
            else:
                if current_section and current_section in image_files:
                    blocks.append({"block_type": 27, "image": {}, "_image_file_path": image_files[current_section]})
                current_section = None

        # Headings
        if line.startswith("### "):
            blocks.append({
                "block_type": 5,
                "heading3": {
                    "elements": [{"text_run": {"content": line[4:]}}]
                },
            })
        elif line.startswith("## "):
            blocks.append({
                "block_type": 4,
                "heading2": {
                    "elements": [{"text_run": {"content": line[3:]}}]
                },
            })
        elif line.startswith("# "):
            blocks.append({
                "block_type": 3,
                "heading1": {
                    "elements": [{"text_run": {"content": line[2:]}}]
                },
            })
        # Blockquote -> parse bold then add italic
        elif line.startswith("> "):
            elements = _parse_inline(line[2:])
            for el in elements:
                if "text_run" in el:
                    style = el["text_run"].get("text_element_style", {})
                    style["italic"] = True
                    el["text_run"]["text_element_style"] = style
            blocks.append({
                "block_type": 2,
                "text": {"elements": elements},
            })
        # List item -> bullet prefix
        elif line.startswith("- "):
            elements = _parse_inline(f"\u2022 {line[2:]}")
            blocks.append({
                "block_type": 2,
                "text": {"elements": elements},
            })
        # Table row
        elif line.startswith("|"):
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": line}}]},
            })
        # Regular paragraph
        else:
            elements = _parse_inline(line)
            blocks.append({
                "block_type": 2,
                "text": {"elements": elements},
            })

    # End of article: insert image for last section if pending
    if current_section and current_section in image_files:
        blocks.append({"block_type": 27, "image": {}, "_image_file_path": image_files[current_section]})

    # Insert summary image at article end
    if "summary" in image_files:
        blocks.append({"block_type": 27, "image": {}, "_image_file_path": image_files["summary"]})

    return blocks


def _parse_inline(text: str) -> list[dict]:
    """Parse inline formatting (bold), return elements list."""
    elements = []
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        if i % 2 == 1:  # Bold part
            elements.append({
                "text_run": {
                    "content": part,
                    "text_element_style": {"bold": True},
                }
            })
        else:
            elements.append({"text_run": {"content": part}})
    return elements if elements else [{"text_run": {"content": text}}]


def write_blocks(token: str, document_id: str, blocks: list[dict]):
    """
    Write content blocks to Feishu document (batched, max 50 per batch).
    Image blocks use two-step process: create empty placeholder block,
    then upload image and bind to that block.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Get document root block_id
    get_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks"
    resp = requests.get(get_url, headers=headers, timeout=10)
    resp.raise_for_status()
    root_data = resp.json()
    if root_data.get("code") != 0:
        raise ValueError(f"Failed to get document blocks: {root_data.get('msg')}")

    root_block_id = root_data["data"]["items"][0]["block_id"]
    create_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{root_block_id}/children"

    # Separate image blocks and regular blocks, track image block positions
    image_positions = {}  # {index in clean_blocks: file_path}
    clean_blocks = []
    for idx, block in enumerate(blocks):
        file_path = block.pop("_image_file_path", None)
        if file_path:
            image_positions[len(clean_blocks)] = file_path
        clean_blocks.append(block)

    # Batch write (API limit: max 50 blocks per request)
    batch_size = 50
    total_written = 0
    created_block_ids = []  # Track block_id for each block in order

    for i in range(0, len(clean_blocks), batch_size):
        batch = clean_blocks[i : i + batch_size]
        resp = requests.post(
            create_url, headers=headers, json={"children": batch}, timeout=30
        )
        if resp.status_code != 200:
            error_body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            print(f"[WARN] Feishu write batch {i//batch_size + 1} failed: {resp.status_code} - {error_body}")
            created_block_ids.extend([None] * len(batch))
            continue
        result = resp.json()
        if result.get("code") != 0:
            print(f"[WARN] Feishu write batch {i//batch_size + 1} failed: {result.get('msg')}")
            created_block_ids.extend([None] * len(batch))
            continue
        total_written += len(batch)
        for item in result.get("data", {}).get("children", []):
            created_block_ids.append(item.get("block_id"))

    print(f"[OK] Written {total_written}/{len(clean_blocks)} content blocks")

    # Step 2: Upload images and bind to corresponding empty image blocks
    if image_positions:
        upload_url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        upload_headers = {"Authorization": f"Bearer {token}"}
        img_ok = 0
        for pos, file_path in image_positions.items():
            if pos >= len(created_block_ids) or not created_block_ids[pos]:
                print(f"[WARN] Image block position {pos} has no valid block_id, skipping upload")
                continue
            block_id = created_block_ids[pos]
            if not os.path.exists(file_path):
                print(f"[WARN] Image file not found: {file_path}")
                continue
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            # Step A: Upload image to block_id, get file_token
            with open(file_path, "rb") as f:
                resp = requests.post(
                    upload_url,
                    headers=upload_headers,
                    data={
                        "file_name": file_name,
                        "parent_type": "docx_image",
                        "parent_node": block_id,
                        "size": str(file_size),
                    },
                    files={"file": (file_name, f)},
                    timeout=60,
                )
            if resp.status_code != 200 or resp.json().get("code") != 0:
                error_info = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                print(f"[WARN] Image upload failed ({file_name}): {resp.status_code} - {error_info}")
                continue
            file_token = resp.json()["data"]["file_token"]
            # Step B: PATCH replace_image to bind file_token to image block
            patch_resp = requests.patch(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}",
                headers=headers,
                json={"replace_image": {"token": file_token}},
                timeout=15,
            )
            if patch_resp.status_code == 200 and patch_resp.json().get("code") == 0:
                img_ok += 1
                print(f"[OK] Image bound: {file_name} -> {block_id}")
            else:
                error_info = patch_resp.json() if patch_resp.headers.get("content-type", "").startswith("application/json") else patch_resp.text
                print(f"[WARN] Image bind failed ({file_name}): {patch_resp.status_code} - {error_info}")
        if img_ok > 0:
            print(f"[OK] Bound {img_ok}/{len(image_positions)} images")


def publish_to_feishu(title: str, markdown_content: str, image_dir: str = None, report_type: str = "daily") -> dict:
    """
    One-click publish Markdown content to Feishu wiki (or cloud space document).

    Args:
        title: Document title
        markdown_content: Markdown-formatted content
        image_dir: Image directory path (optional)
        report_type: Report type "daily" | "weekly" | "monthly"

    Returns: {"document_id": "...", "url": "..."}
    """
    config = PLATFORMS["feishu"]
    app_id = config.get("app_id", "")
    app_secret = config.get("app_secret", "")
    wiki_config = config.get("wiki", {})

    if not app_id or not app_secret:
        print("[ERROR] Feishu App ID / App Secret not configured")
        return {}

    # 1. Get token
    token = get_tenant_token(app_id, app_secret)

    # 2. Create document
    use_wiki = bool(wiki_config.get("space_id") and wiki_config.get("nodes", {}).get(report_type))

    if use_wiki:
        # Wiki mode: create child document under corresponding category
        space_id = wiki_config["space_id"]
        parent = wiki_config["nodes"][report_type]
        node = create_wiki_node(token, space_id, parent["node_token"], title)
        document_id = node["obj_token"]
        base_url = wiki_config.get("base_url", "https://feishu.cn/wiki")
        doc_url = f"{base_url}/{node['node_token']}"
        print(f"[OK] Wiki node created: {report_type}/{title}")
    else:
        # Legacy mode: create document in cloud space folder
        folder_token = config.get("folder_token", "")
        doc = create_document(token, title, folder_token)
        document_id = doc["document_id"]
        doc_url = doc["url"]
        set_public_permission(token, document_id)
        user_open_id = config.get("user_open_id", "")
        if user_open_id:
            add_collaborator(token, document_id, "openid", user_open_id)

    # 3. Collect image file paths (deferred upload in write_blocks for correct parent_node)
    image_files = {}  # key -> file path
    if image_dir and os.path.isdir(image_dir):
        image_names = {
            "cover": ["cover.png", "cover.webp", "cover.jpg", "cover_zh.png", "cover_zh.webp"],
            "ai": ["ai.png", "ai.webp"],
            "seo": ["seo.png", "seo.webp"],
            "biz": ["biz.png", "biz.webp"],
            "market": ["market.png", "market.webp"],
            "summary": ["summary.png", "summary.webp"],
        }
        for key, filenames in image_names.items():
            for fname in filenames:
                fpath = os.path.join(image_dir, fname)
                if os.path.exists(fpath):
                    image_files[key] = fpath
                    break

    # 4. Convert markdown to blocks + write
    # Wiki mode: skip_title=True to avoid title duplication with node title
    blocks = markdown_to_blocks(markdown_content, image_files, skip_title=use_wiki)
    write_blocks(token, document_id, blocks)

    # 5. Wiki mode: insert link at top of index page
    if use_wiki:
        index_obj_token = wiki_config["nodes"][report_type]["obj_token"]
        update_index_page(token, index_obj_token, title, doc_url)

    print(f"[OK] Feishu published: {doc_url}")

    # Record publish result
    try:
        from utils import save_publish_result
        save_publish_result("feishu", url=doc_url, status="success",
                           detail=f"{report_type}: {title}")
    except Exception:
        pass

    return {"document_id": document_id, "url": doc_url}


def send_feishu_card(title: str, content: str, links: dict = None):
    """Send Feishu interactive card message to group chat.

    Args:
        title: Card title (e.g. "Daily Report | 2026-02-22")
        content: Markdown-formatted social content
        links: Platform link dict (e.g. {"Feishu Full": url, "WordPress": url})
    """
    config = PLATFORMS["feishu"]
    chat_id = config.get("chat_id", "")
    if not chat_id:
        print("[WARN] chat_id not configured, skipping group chat push")
        return

    app_id = config.get("app_id", "")
    app_secret = config.get("app_secret", "")
    if not app_id or not app_secret:
        print("[WARN] Feishu App ID/Secret not configured, skipping group chat push")
        return

    token = get_tenant_token(app_id, app_secret)

    # Build interactive card
    elements = [
        {"tag": "markdown", "content": content},
    ]

    # Add platform link buttons
    if links:
        buttons = []
        for label, url in links.items():
            if url:
                buttons.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": label},
                    "url": url,
                    "type": "primary" if len(buttons) == 0 else "default",
                })
        if buttons:
            elements.append({"tag": "action", "actions": buttons})

    card = {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue",
        },
        "elements": elements,
    }

    try:
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
            timeout=15,
        )
        if resp.status_code == 200 and resp.json().get("code") == 0:
            print(f"[OK] Group chat card sent: {title}")
        else:
            print(f"[WARN] Group chat card send failed: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"[ERROR] Group chat card send error: {e}")


if __name__ == "__main__":
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(description="Feishu document publish/manage")
    parser.add_argument("action", nargs="?", default="publish", choices=["publish", "delete", "list", "setup"],
                        help="Action: publish, delete, list, setup (initialize folder permissions)")
    parser.add_argument("--doc-id", help="Document ID to delete (delete mode)")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date YYYY-MM-DD")
    parser.add_argument("--type", default="daily", choices=["daily", "weekly", "monthly"],
                        help="Report type (daily/weekly/monthly)")
    args = parser.parse_args()

    config = PLATFORMS["feishu"]
    app_id = config.get("app_id", "")
    app_secret = config.get("app_secret", "")

    if not app_id or not app_secret:
        print("[ERROR] Feishu App ID / App Secret not configured")
        sys.exit(1)

    if args.action == "delete":
        if not args.doc_id:
            print("[ERROR] Please specify --doc-id")
            print("Usage: python publish_feishu.py delete --doc-id JHUpdq3aGodQT3xAnUmcFHjFnQb")
            sys.exit(1)
        token = get_tenant_token(app_id, app_secret)
        delete_document(token, args.doc_id)

    elif args.action == "list":
        token = get_tenant_token(app_id, app_secret)
        files = list_app_documents(token)
        if files:
            print(f"Found {len(files)} documents:")
            for f in files:
                print(f"  {f.get('name', '?')} | ID: {f.get('token', '?')} | {f.get('type', '?')}")
        else:
            print("No documents found (may need folder_token or app permissions)")

    elif args.action == "setup":
        # One-time init: add user as collaborator for folder and all existing documents
        folder_token = config.get("folder_token", "")
        user_open_id = config.get("user_open_id", "")
        if not user_open_id:
            print("[ERROR] user_open_id not configured, please get it via batch_get_id API first")
            sys.exit(1)
        if not folder_token:
            print("[ERROR] folder_token not configured")
            sys.exit(1)

        token = get_tenant_token(app_id, app_secret)

        # 1. Add user as full_access collaborator for folder
        print(f"Adding user ({user_open_id}) as folder collaborator...")
        folder_url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{folder_token}/members?type=folder&need_notification=false"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"member_type": "openid", "member_id": user_open_id, "perm": "full_access"}
        resp = requests.post(folder_url, headers=headers, json=body, timeout=10)
        if resp.status_code == 200 and resp.json().get("code") == 0:
            print("[OK] Folder permission set! You are now folder admin")
        else:
            print(f"[WARN] Folder permission setup failed: {resp.status_code} - {resp.text}")

        # 2. Add user as collaborator for all existing documents
        print("Adding collaborator for existing documents...")
        files = list_app_documents(token)
        ok_count = 0
        for f in files:
            doc_token = f.get("token", "")
            if doc_token:
                success = add_collaborator(token, doc_token, "openid", user_open_id)
                if success:
                    ok_count += 1
        print(f"[OK] Added collaborator for {ok_count}/{len(files)} documents")
        print()
        print("Setup complete! You can now:")
        print("  1. See the IntelFlow folder in Feishu docs (Shared with me / Shared spaces)")
        print("  2. View, edit, delete documents directly in Feishu UI")
        print("  3. New documents will automatically add you as collaborator")

    else:  # publish
        today = args.date
        FILE_MAP = {"daily": "daily_zh.md", "weekly": "weekly_zh.md", "monthly": "monthly_zh.md"}
        daily_file = ROOT / "output" / today / FILE_MAP.get(args.type, "daily_zh.md")

        if not daily_file.exists():
            print(f"[ERROR] {args.type} report not found: {daily_file}")
            print("Please run the report generation pipeline first")
            sys.exit(1)

        markdown = daily_file.read_text(encoding="utf-8")

        # Extract title from first line
        title = f"Daily Report | {today}"
        for line in markdown.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Check image directory
        image_dir = ROOT / "output" / today / "images" / "domestic"
        if not image_dir.exists():
            image_dir = ROOT / "output" / today / "images"
        img_dir_str = str(image_dir) if image_dir.exists() else None

        result = publish_to_feishu(title, markdown, image_dir=img_dir_str, report_type=args.type)
        if result:
            print(f"Document URL: {result['url']}")
