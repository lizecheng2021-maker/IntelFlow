#!/usr/bin/env python3
"""
Chinese lunar calendar data collection script.

Collects daily lunar calendar information for analytical context:
- Lunar date (year/month/day + Heavenly Stems & Earthly Branches + zodiac)
- Solar terms (if any)
- Moon phase / season determination
- Analysis hints for cycle-based reasoning

Requires: pip install cnlunar

Output: output/YYYY-MM-DD/raw_lunar.json
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_lunar_info(date: datetime = None) -> dict:
    """Collect lunar calendar information for the given date."""
    try:
        import cnlunar
    except ImportError:
        print("[WARN] cnlunar not installed. Run: pip install cnlunar")
        return {"error": "cnlunar not installed", "available": False}

    if date is None:
        date = datetime.now()

    lunar = cnlunar.Lunar(date, godType="8char")

    lunar_date = {
        "solar_date": date.strftime("%Y-%m-%d"),
        "lunar_year": lunar.lunarYear,
        "lunar_month": lunar.lunarMonth,
        "lunar_day": lunar.lunarDay,
        "lunar_date_cn": f"Lunar {lunar.lunarYearCn}{lunar.lunarMonthCn}{lunar.lunarDayCn}",
        "is_leap_month": lunar.isLunarLeapMonth,
    }

    tiangan_dizhi = {
        "year_gz": lunar.year8Char,
        "month_gz": lunar.month8Char,
        "day_gz": lunar.day8Char,
        "two_hour_gz": lunar.twohour8Char,
    }

    zodiac = {
        "year_zodiac": lunar.chineseYearZodiac,
        "day_zodiac": lunar.chineseDayZodiac if hasattr(lunar, 'chineseDayZodiac') else "",
    }

    solar_terms = {
        "today_term": lunar.todaySolarTerms if lunar.todaySolarTerms != "无" else None,
        "next_term": None,
        "season_cn": _get_season_cn(date.month),
    }

    yi_ji = {
        "yi": lunar.goodThing if hasattr(lunar, 'goodThing') else [],
        "ji": lunar.badThing if hasattr(lunar, 'badThing') else [],
    }

    moon_phase = _get_moon_phase(lunar.lunarDay)

    result = {
        "available": True,
        "date": lunar_date,
        "tiangan_dizhi": tiangan_dizhi,
        "zodiac": zodiac,
        "solar_terms": solar_terms,
        "yi_ji": yi_ji,
        "moon_phase": moon_phase,
        "analysis_hints": _generate_analysis_hints(lunar_date, tiangan_dizhi, solar_terms, moon_phase),
    }

    return result


def _get_season_cn(month: int) -> str:
    """Determine season from month."""
    if month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    elif month in (9, 10, 11):
        return "Autumn"
    else:
        return "Winter"


def _get_moon_phase(lunar_day: int) -> dict:
    """Determine moon phase from lunar day."""
    if lunar_day == 1:
        return {"phase": "New Moon", "hint": "New beginnings, good for launching"}
    elif 2 <= lunar_day <= 7:
        return {"phase": "Waxing Crescent", "hint": "Energy rising, good for expansion"}
    elif 8 <= lunar_day <= 14:
        return {"phase": "Waxing Gibbous", "hint": "Momentum building, maintain pace"}
    elif lunar_day == 15:
        return {"phase": "Full Moon", "hint": "Peak energy, watch for reversals"}
    elif 16 <= lunar_day <= 22:
        return {"phase": "Waning Gibbous", "hint": "Energy declining, good for wrapping up"}
    else:
        return {"phase": "Waning Crescent", "hint": "Quiet period, good for reflection and planning"}


def _generate_analysis_hints(date_info: dict, gz: dict, terms: dict, moon: dict) -> list[str]:
    """Generate analysis hints for the analytical engine (not shown in articles)."""
    hints = []
    hints.append(f"Moon phase: {moon['phase']} - {moon['hint']}")
    if terms.get("today_term"):
        hints.append(f"Solar term today: {terms['today_term']}, seasonal transition point")
    season = terms.get("season_cn", "")
    season_hints = {
        "Spring": "Growth season, good for new ventures and positioning",
        "Summer": "High energy but watch for overheating in markets",
        "Autumn": "Harvest time, watch for earnings realization",
        "Winter": "Consolidation period, good for deep research and value hunting",
    }
    if season in season_hints:
        hints.append(f"Season: {season} - {season_hints[season]}")
    hints.append(f"Day stems-branches: {gz.get('day_gz', '')}, for cycle analysis reference")
    return hints


def main():
    """Collect lunar calendar data and save to output directory."""
    import argparse
    parser = argparse.ArgumentParser(description="Lunar calendar data collection")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d")
        date_str = args.date
    else:
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")

    output_dir = ROOT / "output" / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Collecting] Lunar calendar data - {date_str}")
    lunar_info = get_lunar_info(today)

    output_file = output_dir / "raw_lunar.json"
    output_file.write_text(
        json.dumps(lunar_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if lunar_info.get("available"):
        print(f"[OK] Lunar data saved: {output_file}")
        print(f"     {lunar_info['date']['lunar_date_cn']}")
        print(f"     Stems-branches: {lunar_info['tiangan_dizhi']['day_gz']}")
        print(f"     Moon phase: {lunar_info['moon_phase']['phase']}")
        if lunar_info['solar_terms'].get('today_term'):
            print(f"     Solar term: {lunar_info['solar_terms']['today_term']}")
    else:
        print(f"[WARN] Lunar data unavailable: {lunar_info.get('error', 'unknown')}")

    return lunar_info


if __name__ == "__main__":
    main()
