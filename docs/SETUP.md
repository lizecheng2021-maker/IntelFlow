# IntelFlow Setup Guide

## Prerequisites

- macOS or Linux (Apple Silicon Mac recommended)
- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (for report generation)

## Step 1: Install

```bash
git clone https://github.com/lizecheng2021-maker/IntelFlow.git
cd IntelFlow
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Configure

### Option A: Web UI (Recommended)

```bash
python web/app.py
```

Open `http://localhost:5000/setup` in your browser. Configure everything through the web interface:

1. **API Keys** — Enter your API keys (see below for free options)
2. **Data Sources** — Toggle which sources to collect from
3. **Focus Areas** — Adjust dimension weights to match your interests
4. **Editorial Voice** — Define your report's personality
5. **Publishing** — Set up auto-publish targets

### Option B: Manual Config

```bash
cp .env.example .env                              # Add your API keys
cp config/sources.json.example config/sources.json
cp config/platforms.json.example config/platforms.json
cp config/focus.json.example config/focus.json
cp config/profile.json.example config/profile.json
```

Edit each file to match your needs.

## Step 3: Get API Keys

### Required (pick at least one AI model)

| Service | Free Tier | Sign Up |
|---------|-----------|---------|
| Anthropic (Claude) | Pay-as-you-go ~$2/day | [console.anthropic.com](https://console.anthropic.com) |
| Google Gemini | Free tier available | [aistudio.google.com](https://aistudio.google.com) |

### Optional Data Sources (all have free tiers)

| Service | Free Tier | Sign Up |
|---------|-----------|---------|
| GNews | 100 requests/day | [gnews.io](https://gnews.io) |
| Tavily | 1,000 requests/month | [tavily.com](https://tavily.com) |
| SerpAPI | 100 requests/month | [serpapi.com](https://serpapi.com) |
| FMP | 250 requests/day | [financialmodelingprep.com](https://financialmodelingprep.com) |

### Free Sources (no API key needed)

These work out of the box:
- Hacker News API
- GitHub Trending
- RSS Feeds (SEO, tech, business)
- Reddit (public JSON API)
- YouTube Transcripts
- AKShare (Chinese stocks)
- yfinance (global markets)
- cnlunar (Chinese calendar)

## Step 4: Run

```bash
# Full pipeline (~25 minutes)
bash scripts/run_daily.sh

# Or trigger from web UI
python web/app.py  # then click "Run Daily Pipeline" on dashboard
```

## Step 5: Schedule (Optional)

### macOS (launchd)

```bash
# Create a launch agent
cat > ~/Library/LaunchAgents/com.intelflow.daily.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.intelflow.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/path/to/IntelFlow/scripts/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>6</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>WorkingDirectory</key><string>/path/to/IntelFlow</string>
</dict>
</plist>
EOF

# Load it
launchctl load ~/Library/LaunchAgents/com.intelflow.daily.plist
```

### Linux (cron)

```bash
crontab -e
# Add:
0 6 * * * cd /path/to/IntelFlow && bash scripts/run_daily.sh >> logs/cron.log 2>&1
```

## Customization

### Adding Custom RSS Feeds

In the web UI, go to **Setup > Data Sources** and add RSS feed URLs.

Or edit `config/sources.json`:
```json
{
  "custom_rss": [
    "https://example.com/feed.xml",
    "https://blog.example.com/rss"
  ]
}
```

### Adjusting Focus Weights

The 10-dimension framework is fully configurable. In **Setup > Focus Areas**, drag sliders to adjust how much coverage each topic gets. Total should equal 100%.

For example, if you're a fintech founder:
- AI & Technology: 30%
- Finance & Markets: 25%
- Startups & Business: 20%
- SEO & Search: 10%
- Others: 15%

### Creating Your Editorial Voice

In **Setup > Editorial Voice**, define:
- **Persona** — Who is speaking? What's their expertise?
- **Tone** — Analytical, casual, professional, or witty
- **Catchphrases** — Signature expressions that make reports feel personal
- **Analysis Style** — How should insights be structured?

This is what separates IntelFlow from generic AI summarizers — your reports have a unique voice.

## Troubleshooting

### Pipeline hangs
```bash
# Check if lock file exists
ls state/.daily_lock
# Remove it to unstick
rm -f state/.daily_lock
```

### Missing data for a dimension
- Check if the relevant API key is set (for paid sources)
- Check `output/YYYY-MM-DD/raw_*.json` to see what was collected
- Free sources (HN, GitHub, RSS, Reddit) should always work

### Report quality issues
- Ensure `config/profile.json` has a detailed analysis style
- Check `config/focus.json` weights add up to ~100%
- More data sources = better cross-referencing = higher quality output
