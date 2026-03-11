"""IntelFlow Web Configuration Panel.

A self-hosted web UI for configuring your personal intelligence briefing system.
Users can set up API keys, data sources, focus areas, and schedule through the browser.
"""

import json, os, subprocess, sys
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
STATE_DIR = ROOT / "state"

app = Flask(__name__, static_folder="static", template_folder="templates")


def _load_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text("utf-8"))
    return default or {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


# ─── Pages ───────────────────────────────────────────────────

@app.route("/")
def index():
    """Dashboard: show recent reports and system status."""
    reports = []
    if OUTPUT_DIR.exists():
        for d in sorted(OUTPUT_DIR.iterdir(), reverse=True):
            if d.is_dir() and len(d.name) == 10:  # YYYY-MM-DD
                zh = d / "daily_zh.md"
                en = d / "daily_en.md"
                reports.append({
                    "date": d.name,
                    "has_zh": zh.exists(),
                    "has_en": en.exists(),
                    "zh_size": f"{zh.stat().st_size // 1024}KB" if zh.exists() else "-",
                    "en_size": f"{en.stat().st_size // 1024}KB" if en.exists() else "-",
                })
            if len(reports) >= 14:
                break

    status = "ready"
    lock = STATE_DIR / ".daily_lock"
    if lock.exists():
        status = "running"

    return render_template("index.html", reports=reports, status=status)


@app.route("/setup")
def setup():
    """Setup wizard: API keys, sources, platforms, focus areas."""
    env_path = ROOT / ".env"
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                # Mask secrets: show first 4 chars + ****
                env_vars[k] = v[:4] + "****" if len(v) > 4 else v

    sources = _load_json(CONFIG_DIR / "sources.json")
    platforms = _load_json(CONFIG_DIR / "platforms.json")
    profile = _load_json(CONFIG_DIR / "profile.json")
    focus = _load_json(CONFIG_DIR / "focus.json", {
        "dimensions": {
            "ai_tech": {"enabled": True, "weight": 30, "label": "AI & Technology"},
            "finance": {"enabled": True, "weight": 15, "label": "Finance & Markets"},
            "seo": {"enabled": True, "weight": 15, "label": "SEO & Search"},
            "startup": {"enabled": True, "weight": 15, "label": "Startups & Business"},
            "ecommerce": {"enabled": True, "weight": 10, "label": "E-commerce"},
            "creator": {"enabled": True, "weight": 10, "label": "Creator Economy"},
            "macro": {"enabled": True, "weight": 5, "label": "Macro & Policy"},
        },
        "custom_rss": [],
        "custom_subreddits": [],
        "custom_youtube_channels": [],
        "languages": ["en", "zh"],
        "report_length": "standard",
    })

    return render_template("setup.html",
                           env_vars=env_vars, sources=sources,
                           platforms=platforms, profile=profile, focus=focus)


@app.route("/report/<date>")
def view_report(date):
    """View a generated report."""
    report_dir = OUTPUT_DIR / date
    zh_path = report_dir / "daily_zh.md"
    en_path = report_dir / "daily_en.md"
    zh_content = zh_path.read_text("utf-8") if zh_path.exists() else None
    en_content = en_path.read_text("utf-8") if en_path.exists() else None
    return render_template("report.html", date=date, zh=zh_content, en=en_content)


# ─── API Endpoints ───────────────────────────────────────────

@app.route("/api/save-env", methods=["POST"])
def save_env():
    """Save API keys to .env file."""
    data = request.json
    env_path = ROOT / ".env"

    # Read existing .env to preserve comments
    lines = []
    existing = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip() and not line.strip().startswith("#") and "=" in line:
                k = line.split("=", 1)[0]
                existing[k] = line
            lines.append(line)

    # Update values (only if not masked "****")
    for key, value in data.items():
        if "****" in value:
            continue  # Skip masked values
        if key in existing:
            # Replace existing line
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}"
                    break
        else:
            lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", "utf-8")
    return jsonify({"ok": True})


@app.route("/api/save-sources", methods=["POST"])
def save_sources():
    """Save data sources configuration."""
    data = request.json
    _save_json(CONFIG_DIR / "sources.json", data)
    return jsonify({"ok": True})


@app.route("/api/save-platforms", methods=["POST"])
def save_platforms():
    """Save publishing platform configuration."""
    data = request.json
    _save_json(CONFIG_DIR / "platforms.json", data)
    return jsonify({"ok": True})


@app.route("/api/save-focus", methods=["POST"])
def save_focus():
    """Save focus areas and custom sources."""
    data = request.json
    _save_json(CONFIG_DIR / "focus.json", data)
    return jsonify({"ok": True})


@app.route("/api/save-profile", methods=["POST"])
def save_profile():
    """Save editorial voice profile."""
    data = request.json
    _save_json(CONFIG_DIR / "profile.json", data)
    return jsonify({"ok": True})


@app.route("/api/test-key", methods=["POST"])
def test_api_key():
    """Test if an API key is valid."""
    data = request.json
    service = data.get("service")
    key = data.get("key")

    try:
        import urllib.request
        if service == "gnews":
            url = f"https://gnews.io/api/v4/top-headlines?lang=en&max=1&apikey={key}"
            resp = urllib.request.urlopen(url, timeout=10)
            return jsonify({"ok": resp.status == 200})
        elif service == "tavily":
            import urllib.parse
            req_data = json.dumps({"query": "test", "max_results": 1, "api_key": key}).encode()
            req = urllib.request.Request("https://api.tavily.com/search",
                                         data=req_data,
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=10)
            return jsonify({"ok": resp.status == 200})
        elif service == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            resp = urllib.request.urlopen(url, timeout=10)
            return jsonify({"ok": resp.status == 200})
        else:
            return jsonify({"ok": False, "error": "Unknown service"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/run", methods=["POST"])
def run_pipeline():
    """Trigger the daily pipeline."""
    lock = STATE_DIR / ".daily_lock"
    if lock.exists():
        return jsonify({"ok": False, "error": "Pipeline already running"})

    date = request.json.get("date", datetime.now().strftime("%Y-%m-%d"))
    subprocess.Popen(
        ["bash", str(ROOT / "scripts" / "run_daily.sh")],
        env={**os.environ, "TODAY": date},
        cwd=str(ROOT),
        stdout=open(str(STATE_DIR / "pipeline.log"), "w"),
        stderr=subprocess.STDOUT,
    )
    return jsonify({"ok": True, "message": f"Pipeline started for {date}"})


@app.route("/api/status")
def pipeline_status():
    """Check pipeline status."""
    lock = STATE_DIR / ".daily_lock"
    log_path = STATE_DIR / "pipeline.log"
    status = "running" if lock.exists() else "idle"
    last_lines = []
    if log_path.exists():
        lines = log_path.read_text("utf-8").splitlines()
        last_lines = lines[-20:]
    return jsonify({"status": status, "log": last_lines})


if __name__ == "__main__":
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
