<p align="center">
  <h1 align="center">IntelFlow — Your Personal Intelligence Engine, Running 24/7</h1>
  <p align="center"><strong>One API key. Define what you care about. Get a publication-quality daily briefing in two languages.</strong></p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/live%20demo-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

**[English](README.md)** | [中文](README_CN.md)

---

The only open-source intelligence system that:

- **Generates native Chinese + English briefings simultaneously** — not translation, two independent editorial voices
- **Publishes to WordPress, WeChat Official Account, and Feishu in one command** — no other open-source project does all three
- **Lets you define your own analysis dimensions** — AI/Finance/Crypto/Biotech/SEO, anything you want
- **Supports any LLM** — Claude, GPT-4, Gemini, Qwen, GLM, or local Ollama
- **Self-hosted, production-grade, no vendor lock-in, no per-article fees**

---

## Why IntelFlow?

| | Morning Brew / The Rundown | Feedly / Curated | hn-digest / newsletter-gpt | **IntelFlow** |
|---|---|---|---|---|
| Bilingual native output | No — English only | No — English only | No — English only | **Yes — Chinese + English** |
| WeChat + Feishu + WordPress | No | No | No | **Yes — one command** |
| Custom analysis dimensions | No — fixed editorial | No — you curate manually | No — hardcoded topics | **Yes — fully configurable** |
| Authentic editorial voice | Human teams required | Not applicable | Generic AI output | **Config file, no team needed** |
| Self-hosted + production grade | No | No | Hobby-grade, fragile JSON | **Yes — failover built in** |
| Cost | Subscription fees | Subscription fees | Free but limited | **~$2-3/day, you own it** |

Commercial products like Morning Brew need large editorial teams to achieve a consistent, authentic voice. Open-source alternatives are hobby projects with fragile storage and no publishing pipeline. IntelFlow is the only self-hosted system that delivers both production reliability and genuine editorial personality — configured entirely through a file.

---

## Live Demo

See IntelFlow running in production:

- **English briefings:** [www.lizecheng.net](https://www.lizecheng.net)
- **Chinese briefings (Feishu):** [feishu.cn/wiki](https://xv7exvpv861.feishu.cn/wiki/Sh8OwOyqningOvkE8MAcYSOwn8e)

Your output will look completely different — it's shaped by your dimensions, your AI model, and your configured editorial voice.

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow

# 2. Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Launch the Web UI — paste one API key, define your focus areas, done
python web/app.py
# Open http://localhost:5050
```

That's the setup. To run your first briefing:

```bash
bash scripts/run_daily.sh
```

One API key is all you need. Everything else — publishing targets, additional data sources, editorial persona — is optional configuration.

---

## What You Get

A full daily briefing run produces:

```
output/2026-03-11/
├── daily_en.md          # English briefing (~4,000-5,000 words)
├── daily_zh.md          # Chinese briefing (~4,000-5,000 words, independent editorial voice)
├── cover_en.png         # AI-generated cover image
├── cover_zh.png         # AI-generated cover image
└── briefing.json        # Structured source data
```

**Briefing structure** (adapts to your configured dimensions):

```
30-Second Summary
─────────────────
[Your Dimension 1]   e.g., AI Industry — 3-5 items, each with independent analysis
[Your Dimension 2]   e.g., Crypto — signals, not summaries
[Your Dimension 3]   e.g., SaaS — competitive moves, funding
...
Today's Synthesis    Cross-dimensional insight, 400-600 words
```

Each item carries a judgment, not just a headline. The AI cross-references signals across dimensions and calls structural shifts when it sees them.

**Output cadence:**

| Format | Length | Cadence |
|--------|--------|---------|
| Daily Briefing | 4,000-5,000 words | Every day |
| Weekly Deep-Dive | 8,000-10,000 words | Aggregated |
| Monthly Review | 12,000-15,000 words | Trend synthesis |

---

## Configure Your Domain

IntelFlow's core concept is **dimensions** — independent analysis tracks the AI uses to organize its research. Define them once in the Web UI.

**Crypto Trader:**
- Market Signals 30% | On-chain Data 25% | Regulatory 20% | DeFi Protocols 15% | Macro 10%

**SaaS Founder:**
- Competitor Intel 25% | Customer Pain Points 25% | Tech Stack 20% | Funding Landscape 15% | Growth Tactics 15%

**Academic Researcher:**
- Paper Releases 30% | Grant Funding 20% | Conference News 20% | Industry Applications 15% | Policy Impact 15%

**Game Developer:**
- Industry News 30% | Tech Releases 25% | Community Sentiment 20% | Competitor Moves 15% | Platform Changes 10%

Beyond dimensions, you can configure:

- **Editorial voice** — tone, style, recurring phrases, analysis depth
- **Language output** — Chinese only, English only, or both simultaneously
- **Publishing targets** — WordPress, WeChat, Feishu, or just local Markdown
- **AI model** — switch between Claude, GPT-4, Gemini, Qwen, GLM, or local Ollama with no code changes

---

## Architecture

```
                         IntelFlow Pipeline (~25 min)
 ============================================================================

 COLLECT (parallel)          PROCESS             GENERATE (parallel)      PUBLISH
 ______________________     ___________         ____________________     ________
| Web Search           |   |           |       |                    |   |        |
| RSS Feeds            |   |  prepare  |       |  Section 1 (EN+ZH) |   | WP     |
| Hacker News          |-->|  briefing |--+--->|  Section 2 (EN+ZH) |-->| WeChat |
| GitHub Trending      |   |   .py     |  |   |  Section 3 (EN+ZH) |   | Feishu |
| Reddit               |   |___________|  |   |  Section N (EN+ZH) |   |________|
| YouTube Transcripts  |        |         |   |____________________|
| Custom Collectors    |        v         |            |
|______________________|   AI WebSearch   |            v
                          verification    |     assemble_report.py
                                          +------------+
```

**Key design decisions:**

- Each collector has a 10-minute timeout — one slow source never blocks the pipeline
- The AI model is pluggable — switch providers without changing any pipeline code
- Failed sections auto-retry once without affecting other sections
- Built-in collectors (RSS, HN, GitHub, Reddit, YouTube) work with no extra API keys
- Bilingual generation runs in parallel — not sequential translation

**Extend with custom collectors:**

```bash
# Create scripts/collect_mydata.py
# Accept --date and --output args, save output as raw_mydata.json
# That's it — the pipeline auto-discovers collect_*.py scripts
```

---

## Supported AI Models

| Provider | Models | Notes |
|----------|--------|-------|
| Anthropic | Claude Sonnet / Opus / Haiku | Best analytical depth |
| OpenAI | GPT-4o / GPT-4o-mini / o1 | Widely available |
| Google | Gemini 2.5 Pro / Flash | Free tier available |
| Zhipu AI | GLM-4-Plus / GLM-4 | Best for Chinese content |
| Alibaba | Qwen-Max / Plus / Turbo | OpenAI-compatible API |
| Ollama | Llama 3 / Mistral / Qwen2 | 100% local, no API key needed |

---

## Contributing

Contributions welcome:

- **New data collectors** — More RSS feeds, APIs, or platform adapters
- **AI model adapters** — Add support for more LLM providers
- **Publishing integrations** — Substack, Medium, Ghost, LinkedIn, etc.
- **Web UI improvements** — Better setup flow, real-time progress

Please open an issue first to discuss significant changes.

---

## License

[MIT License](LICENSE) — Use it, modify it, ship it.

---

<p align="center">
  If IntelFlow helps you think better, consider giving it a star.<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
