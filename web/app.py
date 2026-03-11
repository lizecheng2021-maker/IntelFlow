"""IntelFlow Web Configuration Panel.

A self-hosted web UI for configuring your personal intelligence briefing system.
Users can set up API keys, data sources, focus areas, and schedule through the browser.
"""

import json, os, subprocess, sys
try:
    import markdown as _markdown
    def _md(text): return _markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
except ImportError:
    def _md(text): return "<pre>" + text + "</pre>"
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


@app.route("/onboard")
def onboard():
    """Conversational AI-powered setup wizard."""
    return render_template("onboard.html")


@app.route("/report/<date>")
def view_report(date):
    """View a generated report."""
    report_dir = OUTPUT_DIR / date
    zh_path = report_dir / "daily_zh.md"
    en_path = report_dir / "daily_en.md"
    zh_content = _md(zh_path.read_text("utf-8")) if zh_path.exists() else None
    en_content = _md(en_path.read_text("utf-8")) if en_path.exists() else None
    return render_template("report.html", date=date, zh=zh_content, en=en_content)


# ─── API Endpoints ───────────────────────────────────────────

@app.route("/api/ai-config")
def get_ai_config():
    """Get AI model configuration."""
    return jsonify(_load_json(CONFIG_DIR / "ai.json", {}))


@app.route("/api/save-ai", methods=["POST"])
def save_ai():
    """Save AI model configuration."""
    try:
        data = request.get_json()
        _save_json(CONFIG_DIR / "ai.json", data)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/test-ai", methods=["POST"])
def test_ai():
    """Test AI model connection."""
    try:
        import urllib.request
        data = request.get_json()
        provider = data.get("provider", "anthropic")

        if provider == "ollama":
            base_url = data.get("base_url", "http://localhost:11434")
            url = f"{base_url.rstrip('/')}/api/tags"
            resp = urllib.request.urlopen(url, timeout=10)
            return jsonify({"ok": resp.status == 200})

        # Get API key: from request first, then .env, then env vars
        api_key = data.get("api_key", "")
        if not api_key or "****" in api_key:
            env_key = _get_env_key(provider)
            api_key = os.environ.get(env_key, "")
            if not api_key:
                env_path = ROOT / ".env"
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        line = line.strip()
                        if line.startswith(f"{env_key}="):
                            api_key = line.split("=", 1)[1]
                            break
        if not api_key:
            return jsonify({"ok": False, "error": "Enter your API key first."})

        # Test connectivity based on provider
        if provider == "anthropic":
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({"model": data.get("model", "claude-sonnet-4-20250514"), "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]}).encode(),
                headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            )
            resp = urllib.request.urlopen(req, timeout=15)
            return jsonify({"ok": resp.status == 200})
        elif provider == "openai":
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            return jsonify({"ok": resp.status == 200})
        elif provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            resp = urllib.request.urlopen(url, timeout=10)
            return jsonify({"ok": resp.status == 200})
        elif provider == "zhipu":
            req = urllib.request.Request(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                data=json.dumps({"model": data.get("model", "glm-4"), "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            )
            resp = urllib.request.urlopen(req, timeout=15)
            return jsonify({"ok": resp.status == 200})
        elif provider == "dashscope":
            req = urllib.request.Request(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            return jsonify({"ok": resp.status == 200})
        else:
            return jsonify({"ok": False, "error": "Unknown provider"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _get_env_key(provider):
    """Map provider name to environment variable key."""
    mapping = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "zhipu": "ZHIPU_API_KEY",
        "dashscope": "DASHSCOPE_API_KEY",
        "kimi": "KIMI_API_KEY",
        "ernie": "ERNIE_API_KEY",
        "ollama": "",
    }
    return mapping.get(provider, "")


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
        if service == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            resp = urllib.request.urlopen(url, timeout=10)
            return jsonify({"ok": resp.status == 200})
        else:
            return jsonify({"ok": False, "error": "Unknown service"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/onboard/research", methods=["POST"])
def onboard_research():
    """AI-powered source discovery for the onboarding wizard.

    Takes {'interests': 'free text'} and returns structured JSON with
    suggested dimensions, RSS feeds, subreddits, and YouTube channels.
    Falls back to keyword matching when no LLM is configured.
    """
    data = request.get_json() or {}
    interests = data.get("interests", "").strip()
    if not interests:
        return jsonify({"error": "interests field is required"}), 400

    # ── Try to call the configured LLM ─────────────────────────────────────
    ai_config = _load_json(CONFIG_DIR / "ai.json", {})
    llm_cfg = ai_config.get("llm", {})

    system_prompt = (
        "You are an intelligence system configurator. "
        "The user wants to build a personalized daily briefing system. "
        "Your job is to recommend data dimensions and real, well-known sources."
    )

    user_prompt = f"""User's interests: {interests}

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
  "dimensions": [
    {{"key": "ai_tools", "label": "AI Tools & Dev", "weight": 35, "description": "LLM tools, coding assistants, AI productivity"}},
    ...
  ],
  "sources": {{
    "rss": [
      {{"url": "https://...", "title": "The Batch", "dimension": "ai_tools"}},
      ...
    ],
    "reddit": ["MachineLearning", "LocalLLaMA"],
    "youtube": ["Andrej Karpathy", "Fireship"]
  }}
}}

Rules:
- 3-5 dimensions whose weights sum to exactly 100
- Only suggest real, well-known sources that actually exist and are publicly accessible
- Match sources specifically to the user's stated interests
- Keep dimension labels short (2-4 words)
- For RSS: prefer feeds from newsletters, blogs, or official sources (not paywalled)
- 2-3 RSS feeds per dimension, 1-3 subreddits total, 1-3 YouTube channels total
- Respond with valid JSON only"""

    result_json = None

    # Build effective LLM config: prefer ai.json, but fall back to any available key
    def _resolve_llm_cfg():
        """Return (provider, model, api_key) — tries ai.json first, then env vars."""
        # 1. Use ai.json if fully configured
        if llm_cfg.get("provider") and llm_cfg.get("model"):
            provider = llm_cfg["provider"]
            model = llm_cfg["model"]
            api_key = llm_cfg.get("api_key") or ""
            if not api_key:
                env_key = _get_env_key(provider)
                api_key = _read_env_key(env_key)
            if api_key or provider == "ollama":
                return {**llm_cfg, "api_key": api_key, "max_tokens": 1500, "temperature": 0.4}
        # 2. Auto-detect any available API key from env / .env
        for provider, env_key, model in [
            ("anthropic", "ANTHROPIC_API_KEY", "claude-haiku-4-5-20251001"),
            ("openai",    "OPENAI_API_KEY",    "gpt-5-mini"),
            ("gemini",    "GEMINI_API_KEY",    "gemini-2.5-flash"),
            ("dashscope", "DASHSCOPE_API_KEY", "qwen3-max"),
            ("zhipu",     "ZHIPU_API_KEY",     "glm-4.6"),
            ("kimi",      "KIMI_API_KEY",      "kimi-k2.5"),
            ("ernie",     "ERNIE_API_KEY",     "ernie-4.5"),
        ]:
            api_key = _read_env_key(env_key)
            if api_key:
                return {"provider": provider, "model": model, "api_key": api_key,
                        "max_tokens": 1500, "temperature": 0.4}
        return None

    def _read_env_key(env_key):
        """Read a key from os.environ or .env file."""
        val = os.environ.get(env_key, "")
        if val:
            return val
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith(f"{env_key}="):
                    return line.split("=", 1)[1].strip()
        return ""

    effective_cfg = _resolve_llm_cfg()
    if effective_cfg:
        try:
            import sys
            sys.path.insert(0, str(ROOT / "scripts"))
            from ai_adapters import create_llm  # noqa: PLC0415

            llm = create_llm(effective_cfg)
            raw = llm.generate(user_prompt, system=system_prompt)

            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.rsplit("```", 1)[0].strip()

            result_json = json.loads(raw)
            result_json["_source"] = "ai"
            result_json["_model"] = effective_cfg.get("model", "")
        except Exception as exc:
            # LLM unavailable or parse error — fall through to keyword fallback
            app.logger.warning("onboard LLM call failed (%s), using fallback", exc)

    # ── Keyword-based fallback ─────────────────────────────────────────────
    if result_json is None:
        result_json = _keyword_fallback(interests)

    # Basic validation / normalisation
    dims = result_json.get("dimensions", [])
    if not dims:
        result_json = _keyword_fallback(interests)
        dims = result_json.get("dimensions", [])

    # Ensure weights sum to 100
    total = sum(d.get("weight", 0) for d in dims)
    if total != 100 and total > 0:
        remainder = 100
        for i, d in enumerate(dims):
            if i < len(dims) - 1:
                d["weight"] = round(d["weight"] * 100 / total)
                remainder -= d["weight"]
            else:
                d["weight"] = remainder

    return jsonify(result_json)


def _keyword_fallback(interests: str) -> dict:
    """Return a canned configuration based on keyword matching in interests."""
    text = interests.lower()

    # Keyword → dimension mapping
    matches = []

    kw_map = [
        (["ai", "llm", "gpt", "claude", "machine learning", "ml", "langchain", "agent", "openai"],
         {"key": "ai_tools", "label": "AI Tools & Dev", "weight": 35,
          "description": "LLMs, coding assistants, AI productivity",
          "_rss": [
              {"url": "https://www.deeplearning.ai/the-batch/feed/", "title": "The Batch", "dimension": "ai_tools"},
              {"url": "https://simonwillison.net/atom/everything/", "title": "Simon Willison's Weblog", "dimension": "ai_tools"},
              {"url": "https://buttondown.com/ainews/rss", "title": "AI News", "dimension": "ai_tools"},
          ],
          "_reddit": ["MachineLearning", "LocalLLaMA", "ChatGPT"],
          "_youtube": ["Andrej Karpathy", "Fireship", "Two Minute Papers"]}),

        (["defi", "crypto", "bitcoin", "ethereum", "web3", "blockchain", "nft", "solana"],
         {"key": "defi", "label": "DeFi & Crypto", "weight": 25,
          "description": "Decentralised finance, blockchain protocols, crypto markets",
          "_rss": [
              {"url": "https://bankless.com/feed", "title": "Bankless", "dimension": "defi"},
              {"url": "https://thedefiant.io/feed", "title": "The Defiant", "dimension": "defi"},
          ],
          "_reddit": ["defi", "ethfinance", "CryptoCurrency"],
          "_youtube": ["Bankless", "Coin Bureau"]}),

        (["indie", "solo founder", "indiehacker", "indie hacker", "bootstrapped", "saas", "micro-saas"],
         {"key": "indie_hacking", "label": "Indie Hacking", "weight": 25,
          "description": "Solo founders, bootstrapped SaaS, side projects",
          "_rss": [
              {"url": "https://www.indiehackers.com/feed.rss", "title": "Indie Hackers", "dimension": "indie_hacking"},
              {"url": "https://levels.io/rss/", "title": "levels.io blog", "dimension": "indie_hacking"},
          ],
          "_reddit": ["indiehackers", "SideProject", "SaaS"],
          "_youtube": ["levels.io", "Starter Story"]}),

        (["startup", "vc", "venture", "funding", "techcrunch", "yc", "y combinator"],
         {"key": "startups", "label": "Startups & VC", "weight": 20,
          "description": "Venture capital, funding rounds, growth stage startups",
          "_rss": [
              {"url": "https://techcrunch.com/feed/", "title": "TechCrunch", "dimension": "startups"},
              {"url": "https://news.ycombinator.com/rss", "title": "Hacker News", "dimension": "startups"},
          ],
          "_reddit": ["startups", "entrepreneur"],
          "_youtube": ["Y Combinator", "20VC"]}),

        (["seo", "search", "google", "keyword", "rank", "backlink", "serp"],
         {"key": "seo", "label": "SEO & Growth", "weight": 20,
          "description": "Search engine optimisation, content marketing, growth hacking",
          "_rss": [
              {"url": "https://searchengineland.com/feed", "title": "Search Engine Land", "dimension": "seo"},
              {"url": "https://www.searchenginejournal.com/feed/", "title": "Search Engine Journal", "dimension": "seo"},
          ],
          "_reddit": ["SEO", "bigseo"],
          "_youtube": ["Ahrefs", "Neil Patel"]}),

        (["stock", "market", "invest", "finance", "equity", "trading", "nasdaq", "s&p"],
         {"key": "markets", "label": "Markets & Finance", "weight": 20,
          "description": "Equities, macro, personal finance, trading",
          "_rss": [
              {"url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "title": "WSJ Markets", "dimension": "markets"},
              {"url": "https://feeds.bloomberg.com/markets/news.rss", "title": "Bloomberg Markets", "dimension": "markets"},
          ],
          "_reddit": ["investing", "stocks", "wallstreetbets"],
          "_youtube": ["CNBC", "Bloomberg Technology"]}),
    ]

    chosen = []
    rss_out, reddit_out, yt_out = [], [], []

    for keywords, config in kw_map:
        if any(kw in text for kw in keywords):
            entry = {k: v for k, v in config.items() if not k.startswith("_")}
            chosen.append(entry)
            rss_out.extend(config.get("_rss", []))
            for sub in config.get("_reddit", []):
                if sub not in reddit_out:
                    reddit_out.append(sub)
            for ch in config.get("_youtube", []):
                if ch not in yt_out:
                    yt_out.append(ch)

    # Default if nothing matched
    if not chosen:
        chosen = [
            {"key": "ai_tools",  "label": "AI & Technology", "weight": 40,
             "description": "AI tools, software, developer ecosystem"},
            {"key": "startups",  "label": "Startups & VC",   "weight": 35,
             "description": "Venture capital, funding, entrepreneurship"},
            {"key": "markets",   "label": "Markets",          "weight": 25,
             "description": "Financial markets and macro trends"},
        ]
        rss_out = [
            {"url": "https://news.ycombinator.com/rss", "title": "Hacker News", "dimension": "ai_tools"},
            {"url": "https://techcrunch.com/feed/",     "title": "TechCrunch",  "dimension": "startups"},
        ]
        reddit_out = ["technology", "entrepreneur", "investing"]
        yt_out = ["Lex Fridman", "Y Combinator"]

    # Trim to max 5 dimensions and rebalance weights
    chosen = chosen[:5]
    per = 100 // len(chosen)
    remainder = 100 - per * len(chosen)
    for i, d in enumerate(chosen):
        d["weight"] = per + (1 if i < remainder else 0)

    return {
        "dimensions": chosen,
        "sources": {
            "rss":     rss_out[:9],
            "reddit":  reddit_out[:5],
            "youtube": yt_out[:4],
        }
    }


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
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
