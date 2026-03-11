#!/usr/bin/env python3
"""
YouTube channel transcript collection script with 4-tier fallback + circuit breaker.

Transcript extraction strategies (adaptive switching with circuit breaker protection):
  - Tier A: yt-dlp subtitle extraction ($0, most reliable)
  - Tier B: youtube-transcript-api + optional Tor SOCKS5 ($0)
  - Tier C: Supadata.ai REST API (100 calls/month free)
  - Tier D: yt-dlp audio download + Groq Whisper transcription ($0, last resort)

Channel tiers (configured in config/sources.json):
  - tier1_daily: Check every day (core channels), lookback_hours=36
  - tier2_weekly: Check weekly (high-value channels), lookback_hours=168
  - tier3_events: Conference recordings (sporadic), lookback_hours=720

Usage:
  python collect_youtube.py              # Collect all tiers
  python collect_youtube.py tier1        # Only tier1_daily
  python collect_youtube.py tier1 tier2  # tier1 + tier2

Output: output/YYYY-MM-DD/raw_youtube.json
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import requests

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("[ERROR] youtube-transcript-api not installed. Run: pip install youtube-transcript-api")
    sys.exit(1)

# Project root directory
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))

# Tor SOCKS5 proxy detection
_TOR_PORT = int(os.environ.get("TOR_SOCKS_PORT", "9050"))


def _check_tor() -> bool:
    """Check if Tor SOCKS5 proxy is running."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", _TOR_PORT))
        sock.close()
        return result == 0
    except Exception:
        return False


_HAS_PYSOCKS = False
try:
    import socks  # noqa: F401
    _HAS_PYSOCKS = True
except ImportError:
    pass

_TOR_AVAILABLE = _check_tor() and _HAS_PYSOCKS
_TOR_PROXY = f"socks5h://127.0.0.1:{_TOR_PORT}"

if _check_tor() and not _HAS_PYSOCKS:
    print(f"[WARN] Tor is running but PySocks not installed. Run: pip install PySocks")
elif _TOR_AVAILABLE:
    print(f"[OK] Tor SOCKS5 proxy available: 127.0.0.1:{_TOR_PORT}")
else:
    print(f"[WARN] Tor not running (port {_TOR_PORT}), Tier B will use direct connection")

# API Keys from config or environment
_yt_config = CONFIG.get("youtube_builders", {})
_SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY") or _yt_config.get("supadata_api_key", "")
_GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or _yt_config.get("groq_api_key", "")

# Optional cookie file for yt-dlp
_cookie_candidates = [
    ROOT / "config" / "youtube_cookies.txt",
    ROOT / "config" / "www.youtube.com_cookies.txt",
]
COOKIE_PATH = next((p for p in _cookie_candidates if p.exists()), _cookie_candidates[0])

# Fallback statistics
_FALLBACK_STATS = {"tier_a_ytdlp": 0, "tier_b_api": 0, "tier_c_supadata": 0, "tier_d_groq": 0, "title_only": 0}

# Circuit breaker: auto-skip tier after N consecutive failures
_CIRCUIT_BREAKER_THRESHOLD = 2
_BREAKER = {
    "tier_a": {"failures": 0, "tripped": False},
    "tier_b": {"failures": 0, "tripped": False},
    "tier_c": {"failures": 0, "tripped": False},
    "tier_d": {"failures": 0, "tripped": False},
}


def _breaker_check(tier: str) -> bool:
    return not _BREAKER[tier]["tripped"]

def _breaker_success(tier: str):
    _BREAKER[tier]["failures"] = 0

def _breaker_fail(tier: str):
    _BREAKER[tier]["failures"] += 1
    if _BREAKER[tier]["failures"] >= _CIRCUIT_BREAKER_THRESHOLD:
        _BREAKER[tier]["tripped"] = True
        print(f"    [circuit-breaker] {tier} tripped after {_CIRCUIT_BREAKER_THRESHOLD} consecutive failures")


# Tier B: transcript-api instances
def _create_api() -> YouTubeTranscriptApi:
    from youtube_transcript_api.proxies import GenericProxyConfig
    proxy_config = None
    if _TOR_AVAILABLE:
        try:
            proxy_config = GenericProxyConfig(http_url=_TOR_PROXY, https_url=_TOR_PROXY)
        except Exception as e:
            print(f"[WARN] Tor proxy config failed: {e}")

    http_client = None
    if COOKIE_PATH.exists():
        import http.cookiejar
        try:
            cj = http.cookiejar.MozillaCookieJar(str(COOKIE_PATH))
            cj.load(ignore_discard=True, ignore_expires=True)
            session = requests.Session()
            session.cookies = cj
            if _TOR_AVAILABLE:
                session.proxies = {"http": _TOR_PROXY, "https": _TOR_PROXY}
            http_client = session
        except Exception:
            pass

    return YouTubeTranscriptApi(proxy_config=proxy_config, http_client=http_client)


YT_API_DIRECT = YouTubeTranscriptApi()
YT_API_TOR = _create_api() if _TOR_AVAILABLE else None


def _get_proxied_session() -> requests.Session:
    session = requests.Session()
    if _TOR_AVAILABLE:
        session.proxies = {"http": _TOR_PROXY, "https": _TOR_PROXY}
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })
    return session

_RSS_SESSION = _get_proxied_session()


# ---- Four-tier transcript extraction ----

def _tier_a_ytdlp_subs(video_id: str, max_length: int) -> tuple[str, str]:
    """Tier A: yt-dlp auto-subtitle extraction (most reliable)."""
    if not shutil.which("yt-dlp"):
        return "", ""

    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    cookie_args = ["--cookies", str(COOKIE_PATH)] if COOKIE_PATH.exists() else []

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "subs")
        cmd = [
            "yt-dlp", "--write-subs", "--write-auto-subs",
            "--sub-lang", "en,zh-Hans,zh-Hant,zh",
            "--skip-download", "--sub-format", "vtt", "--no-warnings",
            "-o", out_path, *cookie_args, yt_url,
        ]
        if shutil.which("node"):
            cmd.insert(1, "--js-runtimes")
            cmd.insert(2, "node")

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=90, check=False)
        except subprocess.TimeoutExpired:
            return "", ""
        except Exception:
            return "", ""

        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return "", ""

        en_files = [f for f in vtt_files if ".en." in f.name]
        chosen = en_files[0] if en_files else vtt_files[0]

        vtt_text = chosen.read_text(encoding="utf-8", errors="ignore")
        lines = []
        for line in vtt_text.splitlines():
            line = line.strip()
            if (not line or line.startswith("WEBVTT") or "-->" in line
                    or line.startswith("Kind:") or line.startswith("Language:")):
                continue
            if re.match(r"^\d+$", line):
                continue
            line = re.sub(r"<[^>]+>", "", line).strip()
            if line and (not lines or line != lines[-1]):
                lines.append(line)

        text = " ".join(lines).strip()[:max_length]
        if text:
            return text, "en"
    return "", ""


def _tier_b_transcript_api(video_id: str, max_length: int) -> tuple[str, str]:
    """Tier B: youtube-transcript-api (direct, then Tor fallback)."""
    languages = ["en", "zh-Hans", "zh-Hant", "zh"]
    try:
        result = YT_API_DIRECT.fetch(video_id, languages=languages)
        text = " ".join(snippet.text for snippet in result).strip()[:max_length]
        lang = getattr(result, "language_code", languages[0])
        if text:
            return text, lang
    except Exception:
        pass

    if YT_API_TOR:
        try:
            result = YT_API_TOR.fetch(video_id, languages=languages)
            text = " ".join(snippet.text for snippet in result).strip()[:max_length]
            lang = getattr(result, "language_code", languages[0])
            if text:
                return text, lang
        except Exception:
            pass

    return "", ""


def _tier_c_supadata(video_id: str, max_length: int) -> tuple[str, str]:
    """Tier C: Supadata.ai REST API (100 calls/month free)."""
    if not _SUPADATA_API_KEY:
        return "", ""
    try:
        resp = requests.get(
            "https://api.supadata.ai/v1/youtube/transcript",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "lang": "en"},
            headers={"x-api-key": _SUPADATA_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = ""
        lang = "en"
        if isinstance(data, dict):
            if "content" in data and isinstance(data["content"], list):
                text = " ".join(seg.get("text", "") for seg in data["content"] if seg.get("text"))
            elif "content" in data and isinstance(data["content"], str):
                text = data["content"]
            elif "transcript" in data:
                text = data["transcript"]
            lang = data.get("lang", "en")
        text = text.strip()[:max_length]
        if text:
            return text, lang
    except Exception:
        pass
    return "", ""


def _tier_d_groq_whisper(video_id: str, max_length: int) -> tuple[str, str]:
    """Tier D: yt-dlp audio download + Groq Whisper transcription (last resort)."""
    if not _GROQ_API_KEY or not shutil.which("yt-dlp"):
        return "", ""

    yt_url = f"https://www.youtube.com/watch?v={video_id}"
    cookie_args = ["--cookies", str(COOKIE_PATH)] if COOKIE_PATH.exists() else []

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.m4a")
        cmd = ["yt-dlp", "-f", "ba[ext=m4a]/ba/b", "--no-playlist", "--no-warnings",
               "-o", audio_path, *cookie_args, yt_url]
        if shutil.which("node"):
            cmd.insert(1, "--js-runtimes")
            cmd.insert(2, "node")

        try:
            subprocess.run(cmd, capture_output=True, timeout=180, check=False)
        except Exception:
            return "", ""

        if not os.path.exists(audio_path):
            return "", ""

        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size_mb > 25:
            return "", ""

        try:
            with open(audio_path, "rb") as f:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {_GROQ_API_KEY}"},
                    files={"file": ("audio.m4a", f, "audio/m4a")},
                    data={"model": "whisper-large-v3", "response_format": "text"},
                    timeout=180,
                )
                resp.raise_for_status()
                text = resp.text.strip()[:max_length]
                if text:
                    return text, "en"
        except Exception:
            pass

    return "", ""


# ---- Constants ----

YT_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={id}"
TIER_KEYS = ["tier1_daily", "tier2_weekly", "tier3_events"]
TIER_ALIASES = {
    "tier1": "tier1_daily", "tier1_daily": "tier1_daily", "daily": "tier1_daily",
    "tier2": "tier2_weekly", "tier2_weekly": "tier2_weekly", "weekly": "tier2_weekly",
    "tier3": "tier3_events", "tier3_events": "tier3_events", "events": "tier3_events",
}

DEFAULT_MAX_VIDEOS = 3
DEFAULT_LOOKBACK_HOURS = 36
DEFAULT_MAX_TRANSCRIPT_LENGTH = 30000

# Default channel list (fallback when config has no tiered structure)
DEFAULT_CHANNELS = [
    {"channel_id": "UCMcoud_ZW7cfxeIugBflSBw", "name": "Riley Brown", "category": "ai_tools"},
    {"channel_id": "UCXZFVVCFahewxr3est7aT7Q", "name": "McKay Wrigley", "category": "ai_tools"},
    {"channel_id": "UCPjNBjflYl0-HQtUvOx0Ibw", "name": "Greg Isenberg", "category": "startup"},
    {"channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ", "name": "Andrej Karpathy", "category": "ai"},
    {"channel_id": "UCSw5U1MuzDED2Nvlx9m65-Q", "name": "Pieter Levels", "category": "indie"},
    {"channel_id": "UCxIJaCMEptJjxmmQgGFsnCg", "name": "Y Combinator", "category": "startup"},
    {"channel_id": "UC6t1O76G0jYXOAoYCm153dA", "name": "Lenny Rachitsky", "category": "growth"},
]


def get_tiered_channels(requested_tiers: list[str] | None = None) -> list[dict]:
    """Load tiered channel config from config/sources.json."""
    yt_config = CONFIG.get("youtube_builders", {})
    has_tiers = any(tier_key in yt_config for tier_key in TIER_KEYS)

    if not has_tiers:
        channels = yt_config.get("channels", DEFAULT_CHANNELS)
        return [{
            "tier": "tier1_daily",
            "channels": channels,
            "max_videos_per_channel": yt_config.get("max_videos_per_channel", DEFAULT_MAX_VIDEOS),
            "max_transcript_length": yt_config.get("max_transcript_length", DEFAULT_MAX_TRANSCRIPT_LENGTH),
            "lookback_hours": yt_config.get("lookback_hours", DEFAULT_LOOKBACK_HOURS),
        }]

    tiers_to_collect = requested_tiers if requested_tiers else TIER_KEYS
    result = []
    for tier_key in tiers_to_collect:
        tier_config = yt_config.get(tier_key)
        if not tier_config:
            continue
        channels = tier_config.get("channels", [])
        if not channels:
            continue
        lookback_hours = tier_config.get("lookback_hours")
        if lookback_hours is None:
            lookback_hours = tier_config.get("lookback_days", 2) * 24
        result.append({
            "tier": tier_key,
            "channels": channels,
            "max_videos_per_channel": tier_config.get("max_videos_per_channel", DEFAULT_MAX_VIDEOS),
            "max_transcript_length": tier_config.get("max_transcript_length", DEFAULT_MAX_TRANSCRIPT_LENGTH),
            "lookback_hours": lookback_hours,
        })

    return result


def parse_published_date(entry: dict) -> datetime | None:
    time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if time_struct:
        try:
            return datetime(*time_struct[:6])
        except Exception:
            return None
    return None


def fetch_recent_videos(channel_id: str, channel_name: str, cutoff: datetime,
                        max_videos: int = DEFAULT_MAX_VIDEOS) -> list[dict]:
    """Fetch recent videos from a YouTube channel via RSS."""
    feed_url = YT_RSS_URL.format(id=channel_id)
    try:
        resp = _RSS_SESSION.get(feed_url, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"[ERROR] {channel_name} RSS fetch failed: {e}")
        return []

    videos = []
    for entry in feed.entries:
        if len(videos) >= max_videos:
            break
        pub_date = parse_published_date(entry)
        if pub_date and pub_date < cutoff:
            continue

        video_id = entry.get("yt_videoid", "")
        if not video_id:
            link = entry.get("link", "")
            if "v=" in link:
                video_id = link.split("v=")[-1].split("&")[0]
        if not video_id:
            continue

        published_str = pub_date.isoformat() if pub_date else entry.get("published", "")

        description = ""
        if hasattr(entry, "media_group") and entry.media_group:
            for mg in entry.media_group:
                if hasattr(mg, "media_description"):
                    description = mg.media_description.strip()
                    break
        if not description:
            description = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()

        videos.append({
            "video_id": video_id,
            "title": entry.get("title", "").strip(),
            "description": description,
            "published": published_str,
        })

    return videos


def fetch_transcript(video_id: str, max_length: int = DEFAULT_MAX_TRANSCRIPT_LENGTH) -> tuple[str, str, str]:
    """
    Four-tier fallback transcript extraction with circuit breaker.
    Returns (transcript_text, language_code, source_tier).
    """
    if _breaker_check("tier_a"):
        text, lang = _tier_a_ytdlp_subs(video_id, max_length)
        if text:
            _breaker_success("tier_a")
            _FALLBACK_STATS["tier_a_ytdlp"] += 1
            return text, lang, "tier_a_ytdlp"
        else:
            _breaker_fail("tier_a")

    if _breaker_check("tier_b"):
        text, lang = _tier_b_transcript_api(video_id, max_length)
        if text:
            _breaker_success("tier_b")
            _FALLBACK_STATS["tier_b_api"] += 1
            return text, lang, "tier_b_api"
        else:
            _breaker_fail("tier_b")

    if _breaker_check("tier_c"):
        text, lang = _tier_c_supadata(video_id, max_length)
        if text:
            _breaker_success("tier_c")
            _FALLBACK_STATS["tier_c_supadata"] += 1
            return text, lang, "tier_c_supadata"
        else:
            _breaker_fail("tier_c")

    if _breaker_check("tier_d"):
        text, lang = _tier_d_groq_whisper(video_id, max_length)
        if text:
            _breaker_success("tier_d")
            _FALLBACK_STATS["tier_d_groq"] += 1
            return text, lang, "tier_d_groq"
        else:
            _breaker_fail("tier_d")

    _FALLBACK_STATS["title_only"] += 1
    return "", "", ""


def collect_channel(channel_config: dict, cutoff: datetime, tier: str = "",
                    max_videos: int = DEFAULT_MAX_VIDEOS,
                    max_transcript_length: int = DEFAULT_MAX_TRANSCRIPT_LENGTH) -> list[dict]:
    """Collect video transcripts for a single channel."""
    channel_id = channel_config["channel_id"]
    channel_name = channel_config["name"]
    category = channel_config.get("category", "")

    videos = fetch_recent_videos(channel_id, channel_name, cutoff, max_videos=max_videos)
    if not videos:
        return []

    results = []
    for video in videos:
        video_id = video["video_id"]
        transcript_text, transcript_lang, source_tier = fetch_transcript(
            video_id, max_length=max_transcript_length
        )
        results.append({
            "channel": channel_name,
            "category": category,
            "tier": tier,
            "title": video["title"],
            "description": video.get("description", ""),
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            "published": video["published"],
            "transcript": transcript_text or "",
            "transcript_language": transcript_lang or "",
            "transcript_source": source_tier or "title_only",
            "origin": "youtube_builder",
        })

    return results


def parse_requested_tiers(args: list[str]) -> list[str] | None:
    """Parse CLI arguments to determine which tiers to collect."""
    if not args:
        return None
    tiers = []
    for arg in args:
        tier_key = TIER_ALIASES.get(arg.lower())
        if tier_key:
            if tier_key not in tiers:
                tiers.append(tier_key)
        else:
            print(f"[WARN] Unknown tier '{arg}', valid: {', '.join(TIER_ALIASES.keys())}")
    return tiers if tiers else None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="YouTube channel transcript collection")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    parser.add_argument("tiers", nargs="*", help="Tiers to collect (e.g., tier1 tier2)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    requested_tiers = parse_requested_tiers(args.tiers)
    tier_configs = get_tiered_channels(requested_tiers)

    if not tier_configs:
        print("[ERROR] No channel configuration found. Check config/sources.json")
        sys.exit(1)

    print(f"\n[Fallback] TierA(yt-dlp): {'available' if shutil.which('yt-dlp') else 'not installed'} | "
          f"TierB(transcript-api): {'available(+Tor)' if _TOR_AVAILABLE else 'direct only'} | "
          f"TierC(Supadata): {'available' if _SUPADATA_API_KEY else 'not configured'} | "
          f"TierD(Groq Whisper): {'available' if _GROQ_API_KEY else 'not configured'}")

    all_videos = []
    total_channels_checked = 0
    total_channels_with_content = 0
    tier_stats = {}

    for tier_cfg in tier_configs:
        tier_name = tier_cfg["tier"]
        channels = tier_cfg["channels"]
        max_videos = tier_cfg["max_videos_per_channel"]
        max_transcript_length = tier_cfg["max_transcript_length"]
        lookback_hours = tier_cfg["lookback_hours"]
        pd = datetime.strptime(today, "%Y-%m-%d")
        cutoff = pd - timedelta(hours=lookback_hours)

        tier_video_count = 0
        tier_channel_count = 0

        print(f"\n{'='*60}")
        print(f"[TIER] {tier_name} ({len(channels)} channels, lookback {lookback_hours}h, max {max_videos}/channel)")
        print(f"{'='*60}")

        for ch in channels:
            total_channels_checked += 1
            videos = collect_channel(ch, cutoff, tier=tier_name,
                                     max_videos=max_videos, max_transcript_length=max_transcript_length)
            if videos:
                total_channels_with_content += 1
                tier_channel_count += 1
                tier_video_count += len(videos)
                all_videos.extend(videos)
                has_transcript = sum(1 for v in videos if v.get("transcript"))
                print(f"  [OK] {ch['name']}: {len(videos)} videos ({has_transcript} with transcript)")
            else:
                print(f"  [--] {ch['name']}: no new videos in last {lookback_hours}h")

        tier_stats[tier_name] = {
            "channels_checked": len(channels),
            "channels_with_content": tier_channel_count,
            "videos_collected": tier_video_count,
        }

    breaker_summary = {k: {"tripped": v["tripped"], "failures": v["failures"]} for k, v in _BREAKER.items()}

    result = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
        "tier_stats": tier_stats,
        "fallback_stats": dict(_FALLBACK_STATS),
        "circuit_breaker": breaker_summary,
        "videos": all_videos,
        "total_count": len(all_videos),
        "channels_checked": total_channels_checked,
        "channels_with_content": total_channels_with_content,
    }

    output_file = output_dir / "raw_youtube.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    total_with_transcript = sum(1 for v in all_videos if v.get("transcript"))
    print(f"\n{'='*60}")
    print(f"[Summary] YouTube transcript data saved to {output_file}")
    print(f"  Total: {len(all_videos)} videos, {total_with_transcript} with transcript, "
          f"{total_channels_with_content}/{total_channels_checked} channels with content")
    fs = _FALLBACK_STATS
    print(f"  Sources: TierA={fs['tier_a_ytdlp']} | TierB={fs['tier_b_api']} | "
          f"TierC={fs['tier_c_supadata']} | TierD={fs['tier_d_groq']} | title_only={fs['title_only']}")
    print(f"{'='*60}")

    return result


if __name__ == "__main__":
    main()
