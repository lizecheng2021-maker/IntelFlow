# IntelFlow Plugins

Plugins are **optional** data collection scripts that run before AI section generation.
They add extra context from specific sources you've configured locally — RSS feeds,
private databases, custom APIs — beyond what web search provides.

## How it works

The pipeline auto-discovers all `collect_*.py` scripts in this directory and runs them
before the AI generation step. Each plugin can inject additional context into any
dimension section.

## Plugin interface

A plugin is a standalone Python script that accepts two arguments:

```
python3 plugins/collect_rss.py --date 2026-03-11 --output output/2026-03-11
```

It must write its output as `output/{date}/plugin_{name}.json` with this structure:

```json
{
  "dimension": "ai_tech",
  "items": [
    {
      "title": "Article title",
      "content": "Article summary or key excerpt",
      "url": "https://example.com/article",
      "published": "2026-03-11T08:00:00Z"
    }
  ]
}
```

Or if you prefer to format the context yourself:

```json
{
  "dimension": "ai_tech",
  "context": "Pre-formatted text to inject into the AI prompt for this dimension."
}
```

The `dimension` value must match a key in `config/focus.json` (e.g. `ai_tech`, `seo`, `startup`).

## Backwards compatibility

Old `scripts/collect_*.py` scripts from the pre-v2 pipeline can be moved here unchanged.
They will be discovered and run automatically. Their `raw_*.json` output will be ignored
(the pipeline no longer reads it), but you can update them to emit `plugin_*.json` instead.

## Available plugins

| File | Dimension | Description |
|------|-----------|-------------|
| `collect_rss.py` | configurable | Generic RSS feed collector (reads `config/sources.json`) |

## Adding a plugin

1. Create `plugins/collect_yourname.py`
2. Accept `--date` and `--output` arguments
3. Write `output/{date}/plugin_yourname.json` with the format above
4. Set the `dimension` key to match a key in your `config/focus.json`
5. That's it — the pipeline will pick it up automatically on the next run
