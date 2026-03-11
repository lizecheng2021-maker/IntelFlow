<p align="center">
  <h1 align="center">IntelFlow</h1>
  <p align="center"><strong>Build Your Own AI-Powered Daily Intelligence System</strong></p>
  <p align="center">An open-source framework for creating personalized, multi-source intelligence briefings.<br/>Define your dimensions. Plug in your sources. Own your information flow.</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/live%20demo-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

---

## What Is This?

IntelFlow is an **open-source framework** for building your own AI-powered daily intelligence system. It provides the engine — you decide what to track, which sources to pull from, how deep to analyze, and where to publish.

Most AI newsletter tools are hardcoded: fixed sources, fixed topics, generic summaries. IntelFlow gives you the **underlying architecture** so you can build an intelligence system tailored to your world — whether you're tracking crypto markets, biotech research, SaaS competitors, local politics, or anything else.

The framework handles the hard parts: parallel data collection, intelligent deduplication, section-based AI analysis, report assembly, and multi-platform publishing. You just configure what matters to you.

**Built by the author using IntelFlow:** [www.lizecheng.net](https://www.lizecheng.net)

## At a Glance

| Metric | Value |
|--------|-------|
| Data Source Types | RSS, APIs, web scraping, YouTube transcripts, Reddit, search engines |
| Analysis Dimensions | Fully customizable (default template includes 7 dimensions) |
| End-to-End Runtime | ~25 minutes |
| Daily API Cost | ~$2-3 |
| Output | Bilingual reports, AI cover images, auto-published to multiple platforms |
| Hardware | Runs on a single laptop |

## Why IntelFlow?

**1. You Define the Dimensions**
IntelFlow doesn't decide what's important — you do. Through the web UI, define your own analysis dimensions with custom weights. A VC might track: Deal Flow 30%, Market Signals 25%, Portfolio News 20%, Regulatory 15%, Talent 10%. A game developer might track: Industry News 30%, Tech Releases 25%, Community Sentiment 20%, Competitor Moves 15%, Platform Changes 10%. The framework adapts to any domain.

**2. Plug-In Data Architecture**
Data collectors are modular scripts. The framework ships with collectors for common sources (RSS, news APIs, Hacker News, GitHub, Reddit, YouTube, finance APIs). Adding your own is straightforward — write a Python script that outputs JSON, drop it in `scripts/`, and it joins the pipeline.

**3. Thinking-Model Analysis, Not Summarization**
The AI doesn't just summarize — it analyzes. Cross-references signals across dimensions, identifies structural shifts, and outputs independent judgment. You configure the analytical depth and editorial voice.

**4. Section-Based Parallel Generation**
Data is split by dimension. Each section is generated independently and in parallel, then assembled. If one section fails, it retries alone without blocking others. Fast and resilient.

**5. 3-Layer Deduplication Engine**
Multiple sources inevitably overlap. IntelFlow deduplicates at collection, preprocessing, and generation stages — every paragraph carries unique information.

**6. Configurable Editorial Voice**
Define the analytical persona through the web UI — tone, catchphrases, analysis style. Your daily briefing sounds like *you*, not generic AI output.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow

# 2. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure via Web UI
python web/app.py
# Open http://localhost:5000 in your browser
# Set up API keys, data sources, focus areas, and schedule

# 4. Run your first briefing
bash scripts/run_daily.sh
```

### Required API Keys

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| Claude (Anthropic) | Analysis & writing | Pay-per-use |
| Gemini (Google) | Cover image generation | Free tier available |
| GNews | International news | 100 req/day free |
| FMP | US stock data | 250 req/day free |
| SerpAPI | Search fallback | 250 req/month free |

Most data sources (Hacker News, GitHub Trending, AKShare, RSS feeds, Reddit, YouTube transcripts) require **no API key**.

## Web UI

IntelFlow includes a Flask-based configuration panel at `http://localhost:5000`:

- **Dashboard** — View recent reports, system health, generation status
- **API Keys** — Securely configure all service credentials
- **Data Sources** — Enable/disable individual sources, set collection parameters
- **Focus Areas** — Adjust dimension weights (e.g., 30% AI, 20% startups, 10% SEO)
- **Editorial Profile** — Define writing tone, analytical depth, persona traits
- **Platform Publishing** — Configure auto-publish to WordPress, Feishu, WeChat, Dev.to, LinkedIn
- **Schedule** — Set daily run time, enable/disable weekend deep-dives

## Dimension Framework (Fully Customizable)

IntelFlow's core concept is **dimensions** — independent analysis tracks, each with its own data sources and weight. You define what matters to you.

### Default Template (7 dimensions)

| Dimension | Default Weight | Description |
|-----------|---------------|-------------|
| AI & Technology | 25% | Model releases, tool launches, research breakthroughs |
| Finance & Markets | 15% | Capital flows, earnings, market structure changes |
| SEO & Search | 15% | Algorithm updates, traffic pattern shifts |
| Startups & Business | 15% | New launches, funding rounds, business model innovations |
| E-commerce | 10% | Platform changes, conversion tactics, marketplace trends |
| Creator Economy | 10% | Audience building, content strategy, monetization |
| Macro & Policy | 10% | Regulatory shifts, geopolitical signals |

### Example: Customize for Your Domain

**Crypto Trader:**
- Market Signals 30% | On-chain Data 25% | Regulatory 20% | DeFi Protocols 15% | Macro 10%

**SaaS Founder:**
- Competitor Intel 25% | Customer Pain Points 25% | Tech Stack 20% | Funding Landscape 15% | Growth Tactics 15%

**Academic Researcher:**
- Paper Releases 30% | Grant Funding 20% | Conference News 20% | Industry Applications 15% | Policy Impact 15%

Add/remove/rename dimensions through the web UI or `config/focus.json`. Each dimension maps to data sources you configure.

## Architecture

```
                         IntelFlow Pipeline (~25 min)
 ============================================================================

 COLLECT (parallel)          PROCESS             GENERATE (parallel)      PUBLISH
 ______________________     ___________         ____________________     ________
| collect_news.py      |   |           |       |                    |   |        |
| collect_finance.py   |   |  prepare  |       |  Section 1: AI     |   | Feishu |
| collect_ai.py        |-->|  briefing |--+--->|  Section 2: Builder|-->| WP     |
| collect_business.py  |   |   .py     |  |   |  Section 3: Biz    |   | WeChat |
| collect_youtube.py   |   |___________|  |   |  Section 4: SEO    |   | Dev.to |
| collect_tavily.py    |        |         |   |  Section 5: Finance|   | LI     |
| search_supplement.py |        v         |   |  Section 6: Macro  |   |________|
| collect_lunar.py     |   WebSearch      |   |____________________|
|______________________|   verification   |            |
                            (Claude)      |            v
                                          |     assemble_report.py
                                          |            |
                                          |            v
                                          |     AI Cover Images
                                          |     (Gemini + style ref)
                                          |            |
                                          +------------+
```

**Key design decisions:**
- Each collector has a 10-minute timeout — one slow API never blocks the pipeline
- Section-based generation means each dimension reads only its own data slice
- Failed sections auto-retry once without affecting other sections
- YouTube transcript API has 3-layer fallback: direct API, WebSearch supplement, section-level search

## 3-Layer Deduplication Engine

| Layer | Stage | Method |
|-------|-------|--------|
| 1 | Collection | URL + title dedup across all sources |
| 2 | Preprocessing | Semantic similarity clustering, merge related items |
| 3 | Generation | Cross-section reference check, eliminate redundant analysis |

## Monthly Cost Estimate

| Component | Cost |
|-----------|------|
| Claude API (analysis + writing) | ~$60-75/month |
| Gemini API (cover images) | ~$8/month |
| GNews, FMP, SerpAPI | Free tier |
| All other sources | Free (RSS, public APIs) |
| **Total** | **~$70-85/month** |

Runs entirely on your local machine. No server costs.

## Output Formats

- **Daily Briefing** — 4,000-5,000 words, bilingual (EN + CN), with AI-generated cover images
- **Weekly Deep-Dive** — 8,000-10,000 words, aggregated cross-dimensional analysis
- **Monthly Review** — 12,000-15,000 words, trend synthesis with 30-day financial data

## Contributing

IntelFlow is in active development. Contributions welcome in these areas:

- **New data source collectors** — Add support for more RSS feeds, APIs, or platforms
- **Analysis improvements** — Better deduplication, smarter section splitting
- **Publishing integrations** — New platform adapters (Substack, Medium, Ghost, etc.)
- **Web UI enhancements** — Better dashboard, real-time progress tracking
- **Documentation** — Tutorials, setup guides, configuration examples

Please open an issue first to discuss significant changes.

## Author's Output

The author uses IntelFlow daily to track AI, SEO, finance, and startups. Published output:

- **English reports:** [www.lizecheng.net](https://www.lizecheng.net)

Your setup will look completely different based on your dimensions and sources.

## License

[MIT License](LICENSE) - Use it, modify it, ship it.

---

<p align="center">
  If IntelFlow helps you think better, consider giving it a star.<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
