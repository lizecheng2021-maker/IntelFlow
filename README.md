<p align="center">
  <h1 align="center">IntelFlow</h1>
  <p align="center"><strong>One API Key. Tell the AI What You Care About. Get Your Daily Briefing.</strong></p>
  <p align="center">Open-source framework that uses AI + Web Search to automatically discover, analyze, and deliver intelligence on any topic you define.</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/live%20demo-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

**[English](README.md)** | [中文](README_CN.md)

---

## How It Works

1. **Plug in an AI model** — Claude, GPT, Gemini, Zhipu GLM, Qwen, or a local Ollama model
2. **Tell it what you care about** — Define your focus dimensions through the Web UI (e.g., "AI 30%, Crypto 25%, SaaS 20%...")
3. **AI discovers the sources** — The engine uses web search and built-in collectors to automatically find relevant information
4. **Get your daily briefing** — Multi-dimensional analysis report, generated and published automatically

No fixed data sources. No hardcoded topics. The AI finds what matters based on *your* dimensions.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow

# 2. Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Open the Web UI and paste your AI API key
python web/app.py
# Open http://localhost:5050 → paste ONE API key → define your focus areas → done

# 4. Run your first briefing
bash scripts/run_daily.sh
```

**That's it.** One API key is all you need to get started. Everything else is optional.

## Supported AI Models

| Provider | Models | Notes |
|----------|--------|-------|
| Anthropic | Claude Sonnet / Opus / Haiku | Best analytical depth |
| OpenAI | GPT-4o / GPT-4o-mini / o1 | Widely available |
| Google | Gemini 2.5 Pro / Flash | Free tier available |
| 智谱 AI | GLM-4-Plus / GLM-4 | Best for Chinese content |
| 阿里通义 | Qwen-Max / Plus / Turbo | OpenAI-compatible API |
| Ollama | Llama 3 / Mistral / Qwen2 | 100% local, no API key needed |

Switch models anytime in the Web UI. No code changes needed.

## At a Glance

| Metric | Value |
|--------|-------|
| Setup Time | ~5 minutes (paste API key + define dimensions) |
| End-to-End Runtime | ~25 minutes per briefing |
| Daily Cost | ~$2-3 (depends on your AI model) |
| Output | Multi-dimensional analysis reports, optional AI cover images |
| Hardware | Runs on a single laptop |

## Define Your Dimensions

IntelFlow's core concept is **dimensions** — independent analysis tracks the AI uses to organize its research. You define what matters to you through the Web UI.

**Crypto Trader:**
- Market Signals 30% | On-chain Data 25% | Regulatory 20% | DeFi Protocols 15% | Macro 10%

**SaaS Founder:**
- Competitor Intel 25% | Customer Pain Points 25% | Tech Stack 20% | Funding Landscape 15% | Growth Tactics 15%

**Academic Researcher:**
- Paper Releases 30% | Grant Funding 20% | Conference News 20% | Industry Applications 15% | Policy Impact 15%

**Game Developer:**
- Industry News 30% | Tech Releases 25% | Community Sentiment 20% | Competitor Moves 15% | Platform Changes 10%

The AI uses these dimensions to guide its web search, prioritize information, and structure the final report.

## What Makes IntelFlow Different

**AI-Driven Discovery** — You don't manually curate sources. The AI uses web search to find relevant information for each of your dimensions. It discovers what's happening, not just what you already know to look for.

**Thinking-Model Analysis** — The AI doesn't just summarize. It cross-references signals across dimensions, identifies structural shifts, and outputs independent judgment. You configure the analytical depth and editorial voice.

**Section-Based Parallel Generation** — Each dimension is analyzed independently and in parallel. If one section fails, it retries without blocking others.

**Configurable Editorial Voice** — Define the persona through the Web UI — tone, catchphrases, analysis style. Your briefing sounds like *you*, not generic AI output.

**Multi-Platform Publishing** — Auto-publish to WordPress, Feishu, Dev.to, Hashnode. Or just read the markdown files locally.

## Architecture

```
                         IntelFlow Pipeline (~25 min)
 ============================================================================

 COLLECT (parallel)          PROCESS             GENERATE (parallel)      PUBLISH
 ______________________     ___________         ____________________     ________
| Web Search           |   |           |       |                    |   |        |
| RSS Feeds            |   |  prepare  |       |  Section 1         |   | WP     |
| Hacker News          |-->|  briefing |--+--->|  Section 2         |-->| Feishu |
| GitHub Trending      |   |   .py     |  |   |  Section 3         |   | Dev.to |
| Reddit               |   |___________|  |   |  Section N         |   |________|
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
- Built-in collectors (RSS, HN, GitHub, Reddit, YouTube) work with no API keys

## Extend with Custom Collectors

Want to add your own data source? Write a Python script that outputs JSON:

```bash
# 1. Create scripts/collect_mydata.py
#    - Accept --date and --output args
#    - Save output as raw_mydata.json

# 2. That's it — the pipeline auto-discovers collect_*.py scripts
```

## Output Formats

- **Daily Briefing** — 4,000-5,000 words, with AI-generated cover images
- **Weekly Deep-Dive** — 8,000-10,000 words, aggregated cross-dimensional analysis
- **Monthly Review** — 12,000-15,000 words, trend synthesis

## Author's Output

The author uses IntelFlow daily. Published output:

- **English:** [www.lizecheng.net](https://www.lizecheng.net)
- **Chinese (Feishu):** [feishu.cn/wiki](https://xv7exvpv861.feishu.cn/wiki/Sh8OwOyqningOvkE8MAcYSOwn8e?fromScene=spaceOverview)

Your setup will look completely different — it depends on your dimensions and your AI model.

## Contributing

Contributions welcome:

- **New data collectors** — More RSS feeds, APIs, or platform adapters
- **AI model adapters** — Add support for more LLM providers
- **Publishing integrations** — Substack, Medium, Ghost, LinkedIn, etc.
- **Web UI improvements** — Better setup flow, real-time progress

Please open an issue first to discuss significant changes.

## License

[MIT License](LICENSE) - Use it, modify it, ship it.

---

<p align="center">
  If IntelFlow helps you think better, consider giving it a star.<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
