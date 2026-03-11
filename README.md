<p align="center">
  <h1 align="center">IntelFlow</h1>
  <p align="center"><strong>Your AI-Powered Daily Intelligence Engine</strong></p>
  <p align="center">Self-hosted. Multi-source. Thinking-model driven.</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/python-3.11+-green.svg" alt="Python 3.11+">
  <a href="https://github.com/lizecheng2021-maker/IntelFlow/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
  <a href="https://www.lizecheng.net"><img src="https://img.shields.io/badge/live%20demo-lizecheng.net-orange.svg" alt="Live Demo"></a>
</p>

---

## What Is This?

IntelFlow is **not** a news aggregator. It is a self-hosted intelligence briefing system that collects from 30+ data sources, runs multi-dimensional analysis through AI thinking models, and generates publication-ready bilingual reports — automatically, every day.

Most AI newsletter tools summarize headlines. IntelFlow asks: *What is actually happening here? What structural shift does this signal? How do these dots connect across industries?*

The result is a daily intelligence briefing that breaks information bubbles and trains pattern recognition — not just another feed of summaries.

**Live output:** [www.lizecheng.net](https://www.lizecheng.net)

## At a Glance

| Metric | Value |
|--------|-------|
| Data Sources | 30+ (news, finance, AI, SEO, e-commerce, Reddit, YouTube, RSS) |
| Analysis Dimensions | 10 (macro, finance, AI, SEO, e-commerce, growth, startups, creator economy, Reddit pain points, YouTube builders) |
| End-to-End Runtime | ~25 minutes |
| Daily API Cost | ~$2-3 |
| Output | Bilingual reports (EN + CN), AI cover images, auto-published to 5+ platforms |
| Hardware | Runs on a single MacBook |

## Why IntelFlow?

**1. Multi-Dimensional Coverage**
Not just tech news or just finance. IntelFlow cross-references 10 dimensions — macro policy, capital flows, AI releases, SEO shifts, e-commerce trends, startup signals, builder tactics, and more. Patterns emerge at the intersections.

**2. Thinking-Model Analysis, Not Summarization**
Each piece of information passes through layered analytical frameworks. The system identifies root causes, structural shifts, and cross-domain implications — then writes with independent judgment, not regurgitation.

**3. Section-Based Parallel Generation**
The briefing data is split by dimension. Each section is generated independently and in parallel, then assembled. If one section fails, it retries alone without blocking others. This keeps generation fast and reliable.

**4. 3-Layer Deduplication Engine**
Raw data from 30+ sources contains massive overlap. IntelFlow deduplicates at three stages to ensure every paragraph carries unique information.

**5. Configurable Editorial Voice**
Through the web UI, you define the analytical persona — tone, focus weights, depth preferences. The system adapts its writing style to match your editorial identity.

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

## 10-Dimension Intelligence Framework

| # | Dimension | What It Captures | Key Sources |
|---|-----------|-----------------|-------------|
| 1 | Macro Trends & Policy | Regulatory shifts, geopolitical signals | GNews, China RSS feeds |
| 2 | Finance & Investment | Capital flows, earnings, market structure | FMP, AKShare, yfinance |
| 3 | AI & Tech Frontier | Model releases, tool launches, research | Hacker News, GitHub Trending |
| 4 | SEO & Search Ecosystem | Algorithm updates, traffic pattern shifts | SEJ, Moz, Ahrefs Blog, Search Engine Land |
| 5 | Indie Sites & E-Commerce | Platform changes, conversion tactics | WP Tavern, Shopify, WooCommerce |
| 6 | Growth & Monetization | Funnel strategies, pricing experiments | a16z, First Round Review, Neil Patel |
| 7 | Startups & Business Models | New launches, funding, pivots | Product Hunt, Indie Hackers, Reddit |
| 8 | Personal Brand & Creator Economy | Audience building, content strategy | Publish Press, creator newsletters |
| 9 | Reddit Business Pain Points | Real user problems, unmet demand signals | r/Entrepreneur, r/SideProject, r/startups, r/SaaS |
| 10 | YouTube Builder Intelligence | Practitioner playbooks, tactical breakdowns | 22+ channels (3-tier priority system) |

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

## Live Demo

See IntelFlow output published daily at **[www.lizecheng.net](https://www.lizecheng.net)**

## License

[MIT License](LICENSE) - Use it, modify it, ship it.

---

<p align="center">
  If IntelFlow helps you think better, consider giving it a star.<br>
  <a href="https://github.com/lizecheng2021-maker/IntelFlow">github.com/lizecheng2021-maker/IntelFlow</a>
</p>
