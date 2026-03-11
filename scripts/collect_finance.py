#!/usr/bin/env python3
"""
Finance data collection script: yfinance (US stocks) + AKShare (China A-shares + funds).

All data sources are free and require no API keys.
- yfinance: https://github.com/ranaroussi/yfinance
- AKShare: https://akshare.akfamily.xyz/

Output: output/YYYY-MM-DD/raw_finance.json
"""

import json
import os
import re
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")

import requests

# Project root directory
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))


# ============================================================
# Tencent Finance API (free, unlimited, works globally)
# Fallback when AKShare Eastmoney source is rate-limited
# ============================================================

def _tencent_code(code: str, is_index: bool = False) -> str:
    """Convert a numeric code to Tencent API format (sh/sz prefix)."""
    if is_index:
        sz_indices = {"399001", "399006", "399005", "399300"}
        return f"sz{code}" if code in sz_indices else f"sh{code}"
    first = code[0]
    return f"sz{code}" if first in ("0", "3") else f"sh{code}"


def _fetch_tencent_quotes(codes: list[str]) -> list[dict]:
    """
    Fetch real-time quotes from Tencent Finance API.
    codes: List of sh/sz prefixed codes like ['sh000001', 'sz399001']
    """
    if not codes:
        return []
    url = f"https://qt.gtimg.cn/q={','.join(codes)}"
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = "gbk"
        results = []
        for line in resp.text.strip().split(";"):
            line = line.strip()
            if not line or '="' not in line:
                continue
            data_str = line.split('="', 1)[1].rstrip('"')
            if not data_str:
                continue
            fields = data_str.split("~")
            if len(fields) < 5:
                continue
            name = fields[1]
            code = fields[2]
            try:
                price = float(fields[3])
                prev_close = float(fields[4])
                if prev_close == 0:
                    continue
                change_pct = (price - prev_close) / prev_close * 100
            except (ValueError, ZeroDivisionError):
                continue
            results.append({
                "code": code,
                "name": name,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
            })
        return results
    except Exception as e:
        print(f"[WARN] Tencent quotes API failed: {e}")
        return []


# Major A-share stocks for Tencent API fallback
_MAJOR_A_SHARES = [
    "sh600519", "sz000858", "sz000568",   # Consumer
    "sh601318", "sh600036", "sh601166", "sh601398", "sh600030",  # Finance
    "sz300750", "sz002594", "sz002415",   # Tech/EV
    "sh600276", "sz300015", "sz000661",   # Healthcare
    "sh600887", "sz000333", "sh600309",   # Manufacturing
    "sh601012", "sh600900", "sh601888",   # Industrial
    "sh600585", "sh601857", "sh600028",   # Energy
]


# ============================================================
# US market data (yfinance - completely free, no API key)
# ============================================================

def collect_us_market_movers() -> dict:
    """Collect US stock gainers/losers using yfinance (free, no API key)."""
    try:
        import yfinance as yf
    except ImportError:
        print("[WARN] yfinance not installed, skipping US stock data")
        return {"gainers": [], "losers": []}

    symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "CRM",
        "JPM", "V", "MA", "BAC", "GS",
        "UNH", "JNJ", "PFE", "LLY", "ABBV",
        "XOM", "CVX", "WMT", "COST", "HD",
        "DIS", "INTC", "ORCL", "ADBE", "AVGO",
    ]
    all_stocks = []
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                hist = tickers.tickers[sym].history(period="2d")
                if len(hist) >= 2:
                    price = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2]
                    pct = (price - prev) / prev * 100
                    info = tickers.tickers[sym].info
                    all_stocks.append({
                        "symbol": sym,
                        "name": info.get("shortName", sym),
                        "price": round(price, 2),
                        "change_pct": round(pct, 2),
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] yfinance batch collection failed: {e}")

    all_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    gainers = [s for s in all_stocks if s["change_pct"] > 0][:10]
    losers = [s for s in all_stocks if s["change_pct"] < 0]
    losers.sort(key=lambda x: x["change_pct"])
    losers = losers[:10]

    print(f"[OK] US market movers: {len(gainers)} gainers, {len(losers)} losers")
    return {"gainers": gainers, "losers": losers}


def collect_us_top_quotes() -> list[dict]:
    """Collect real-time quotes for major US tech stocks via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return []

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "NFLX", "CRM"]
    result = []
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                t = tickers.tickers[sym]
                hist = t.history(period="2d")
                info = t.info
                if len(hist) >= 2:
                    price = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2]
                    pct = (price - prev) / prev * 100
                    result.append({
                        "symbol": sym,
                        "name": info.get("shortName", sym),
                        "price": round(price, 2),
                        "change_pct": round(pct, 2),
                        "day_high": round(hist["High"].iloc[-1], 2),
                        "day_low": round(hist["Low"].iloc[-1], 2),
                        "volume": int(hist["Volume"].iloc[-1]),
                        "market_cap": info.get("marketCap", 0),
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] yfinance top quotes collection failed: {e}")

    print(f"[OK] US top quotes: {len(result)} stocks")
    return result


# ============================================================
# A-share data (AKShare - completely free, no API key)
# ============================================================

def collect_a_share_hot() -> list[dict]:
    """
    Collect A-share hot stocks (top gainers + losers).
    Priority: AKShare Eastmoney -> Tencent Finance API fallback.
    """
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        df = df[["代码", "名称", "最新价", "涨跌幅", "成交额"]].copy()
        df["涨跌幅"] = df["涨跌幅"].astype(float)
        df["成交额"] = df["成交额"].astype(float)

        top_gainers = df.nlargest(10, "涨跌幅")
        top_losers = df.nsmallest(10, "涨跌幅")

        result = []
        for _, row in top_gainers.iterrows():
            result.append({
                "code": row["代码"], "name": row["名称"],
                "price": float(row["最新价"]) if row["最新价"] else 0,
                "change_pct": float(row["涨跌幅"]),
                "turnover": float(row["成交额"]), "direction": "gainer",
            })
        for _, row in top_losers.iterrows():
            result.append({
                "code": row["代码"], "name": row["名称"],
                "price": float(row["最新价"]) if row["最新价"] else 0,
                "change_pct": float(row["涨跌幅"]),
                "turnover": float(row["成交额"]), "direction": "loser",
            })

        print(f"[OK] A-share hot stocks (Eastmoney): {len(result)} items")
        return result
    except Exception as e:
        print(f"[WARN] A-share Eastmoney source failed: {e}, trying Tencent...")

    # Fallback: Tencent Finance API
    quotes = _fetch_tencent_quotes(_MAJOR_A_SHARES)
    if quotes:
        quotes.sort(key=lambda x: x["change_pct"], reverse=True)
        gainers = [dict(q, direction="gainer", turnover=0) for q in quotes if q["change_pct"] > 0][:10]
        losers_raw = [q for q in quotes if q["change_pct"] < 0]
        losers_raw.sort(key=lambda x: x["change_pct"])
        losers = [dict(q, direction="loser", turnover=0) for q in losers_raw][:10]
        result = gainers + losers
        print(f"[OK] A-share hot stocks (Tencent fallback): {len(result)} items")
        return result

    print("[ERROR] A-share data: all sources failed")
    return []


def collect_a_share_major_indices() -> list[dict]:
    """
    Collect A-share major indices (Shanghai, Shenzhen, ChiNext, etc.).
    Priority: AKShare Sina -> AKShare Eastmoney -> Tencent Finance API.
    """
    major_codes = ["000001", "399001", "399006", "000300", "000016", "000905"]
    major_names = {
        "000001": "Shanghai Composite", "399001": "Shenzhen Component",
        "399006": "ChiNext", "000300": "CSI 300",
        "000016": "SSE 50", "000905": "CSI 500",
    }

    # Method 1: AKShare Sina source
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_sina()
        df = df[df["代码"].isin(major_codes)]
        if not df.empty:
            result = []
            for _, row in df.iterrows():
                result.append({
                    "code": row["代码"],
                    "name": major_names.get(row["代码"], row["名称"]),
                    "price": float(row["最新价"]) if row["最新价"] else 0,
                    "change_pct": float(row["涨跌幅"]) if row["涨跌幅"] else 0,
                })
            print(f"[OK] A-share indices (Sina): {len(result)} items")
            return result
    except Exception as e:
        print(f"[WARN] A-share indices Sina failed: {e}, trying Eastmoney...")

    # Method 2: AKShare Eastmoney source
    try:
        import akshare as ak
        time.sleep(1)
        df = ak.stock_zh_index_spot_em()
        df = df[df["代码"].isin(major_codes)]
        if not df.empty:
            result = []
            for _, row in df.iterrows():
                result.append({
                    "code": row["代码"],
                    "name": major_names.get(row["代码"], row["名称"]),
                    "price": float(row["最新价"]) if row["最新价"] else 0,
                    "change_pct": float(row["涨跌幅"]) if row["涨跌幅"] else 0,
                })
            print(f"[OK] A-share indices (Eastmoney): {len(result)} items")
            return result
    except Exception as e:
        print(f"[WARN] A-share indices Eastmoney also failed: {e}, trying Tencent...")

    # Method 3: Tencent Finance API (ultimate fallback)
    tencent_codes = [_tencent_code(c, is_index=True) for c in major_codes]
    quotes = _fetch_tencent_quotes(tencent_codes)
    if quotes:
        for q in quotes:
            q["name"] = major_names.get(q["code"], q["name"])
        print(f"[OK] A-share indices (Tencent): {len(quotes)} items")
        return quotes

    print("[ERROR] A-share indices: all three sources failed")
    return []


def collect_top_funds(top_n: int = 10) -> list[dict]:
    """Collect top-performing mutual funds ranked by 1-year return."""
    try:
        import akshare as ak
    except ImportError:
        return []

    try:
        df = ak.fund_open_fund_rank_em(symbol="全部")
        if df.empty:
            return []

        df_top = df.head(top_n)
        result = []
        for _, row in df_top.iterrows():
            result.append({
                "code": str(row.get("基金代码", "")),
                "name": str(row.get("基金简称", "")),
                "nav": str(row.get("单位净值", "")),
                "return_1y": str(row.get("近1年", "")),
                "return_6m": str(row.get("近6月", "")),
                "return_3m": str(row.get("近3月", "")),
            })

        print(f"[OK] Top funds: {len(result)} items")
        return result
    except Exception as e:
        print(f"[ERROR] Fund ranking collection failed: {e}")
        return []


def collect_fund_holdings(fund_code: str) -> list[dict]:
    """Collect top 10 holdings for a specific fund."""
    try:
        import akshare as ak
    except ImportError:
        return []

    try:
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date="")
        if df.empty:
            return []

        result = []
        for _, row in df.head(10).iterrows():
            result.append({
                "stock_code": str(row.get("股票代码", "")),
                "stock_name": str(row.get("股票名称", "")),
                "hold_pct": str(row.get("占净值比例", "")),
                "hold_amount": str(row.get("持股数", "")),
                "hold_value": str(row.get("持仓市值", "")),
            })

        print(f"[OK] Fund {fund_code} holdings: {len(result)} stocks")
        return result
    except Exception as e:
        print(f"[ERROR] Fund {fund_code} holdings collection failed: {e}")
        return []


def collect_macro_indicators() -> dict:
    """Collect China macro indicators (CPI/PMI/M2)."""
    try:
        import akshare as ak
    except ImportError:
        return {}
    result = {}
    try:
        df = ak.macro_china_cpi()
        if not df.empty:
            result["cpi"] = [{"date": str(row.iloc[0]), "value": str(row.iloc[1])} for _, row in df.head(6).iterrows()]
    except Exception as e:
        print(f"[WARN] CPI collection failed: {e}")
    try:
        df = ak.macro_china_pmi()
        if not df.empty:
            result["pmi"] = [{"date": str(row.iloc[0]), "value": str(row.iloc[1])} for _, row in df.head(6).iterrows()]
    except Exception as e:
        print(f"[WARN] PMI collection failed: {e}")
    try:
        df = ak.macro_china_money_supply()
        if not df.empty:
            cols = df.columns.tolist()
            result["m2"] = [{"date": str(row[cols[0]]), "m2_value": str(row[cols[1]]) if len(cols) > 1 else ""} for _, row in df.head(6).iterrows()]
    except Exception as e:
        print(f"[WARN] M2 collection failed: {e}")
    print(f"[OK] Macro indicators: {list(result.keys())}")
    return result


def collect_sector_flow() -> list[dict]:
    """Collect sector-level capital flow data."""
    try:
        import akshare as ak
    except ImportError:
        return []
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        if df.empty:
            return []
        result = []
        cols = df.columns.tolist()
        for _, row in df.head(20).iterrows():
            result.append({
                "sector": str(row[cols[1]]) if len(cols) > 1 else "",
                "change_pct": str(row[cols[2]]) if len(cols) > 2 else "",
                "net_inflow": str(row[cols[3]]) if len(cols) > 3 else "",
            })
        print(f"[OK] Sector capital flow: {len(result)} items")
        return result
    except Exception as e:
        print(f"[WARN] Sector flow collection failed: {e}")
        return []


def collect_north_south_flow() -> dict:
    """Collect northbound/southbound capital flow (HK-China Stock Connect)."""
    try:
        import akshare as ak
    except ImportError:
        return {}
    result = {}
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        if not df.empty:
            north = df[df["资金方向"] == "北向"]
            south = df[df["资金方向"] == "南向"]
            if not north.empty:
                result["north_bound"] = [
                    {"date": str(row.get("交易日", "")), "board": str(row.get("板块", "")),
                     "net_buy": str(row.get("成交净买额", "")), "net_flow": str(row.get("资金净流入", ""))}
                    for _, row in north.iterrows()
                ]
            if not south.empty:
                result["south_bound"] = [
                    {"date": str(row.get("交易日", "")), "board": str(row.get("板块", "")),
                     "net_buy": str(row.get("成交净买额", "")), "net_flow": str(row.get("资金净流入", ""))}
                    for _, row in south.iterrows()
                ]
    except Exception as e:
        print(f"[WARN] Northbound/southbound flow collection failed: {e}")
    print(f"[OK] North/south capital flow: {list(result.keys())}")
    return result


def collect_us_sector_performance() -> list[dict]:
    """Collect US sector performance via SPDR Sector ETFs (yfinance, free)."""
    try:
        import yfinance as yf
    except ImportError:
        return []

    sector_etfs = {
        "Technology": "XLK", "Healthcare": "XLV", "Financials": "XLF",
        "Energy": "XLE", "Consumer Discretionary": "XLY", "Industrials": "XLI",
        "Real Estate": "XLRE", "Utilities": "XLU", "Materials": "XLB",
        "Communication Services": "XLC", "Consumer Staples": "XLP",
    }
    result = []
    try:
        tickers = yf.Tickers(" ".join(sector_etfs.values()))
        for name, ticker in sector_etfs.items():
            try:
                hist = tickers.tickers[ticker].history(period="5d")
                if len(hist) >= 2:
                    today_close = hist["Close"].iloc[-1]
                    prev_close = hist["Close"].iloc[-2]
                    pct = (today_close - prev_close) / prev_close * 100
                    result.append({
                        "sector": name,
                        "etf": ticker,
                        "change_pct": round(pct, 2),
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] US sector performance collection failed: {e}")

    result.sort(key=lambda x: x["change_pct"], reverse=True)
    print(f"[OK] US sector performance: {len(result)} items")
    return result


def collect_tracked_fund_nav() -> list[dict]:
    """
    Collect NAV trends for tracked funds configured in sources.json.
    Used in weekly/monthly reports for investment analysis.
    """
    try:
        import akshare as ak
    except ImportError:
        print("[WARN] akshare not installed, skipping fund NAV collection")
        return []

    # Read tracked funds from config (fallback to empty list)
    tracked = CONFIG.get("finance", {}).get("tracked_funds", [])
    if not tracked:
        print("[INFO] No tracked funds configured in sources.json")
        return []

    result = []
    for fund_info in tracked:
        code = fund_info["code"]
        name = fund_info["name"]
        theme = fund_info.get("theme", "")
        try:
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            if df.empty:
                continue
            recent = df.tail(30)
            nav_data = []
            for _, row in recent.iterrows():
                nav_data.append({
                    "date": str(row["净值日期"]),
                    "nav": float(row["单位净值"]),
                    "daily_return": float(row["日增长率"]) if "日增长率" in row.index else 0,
                })

            if len(nav_data) >= 2:
                latest_nav = nav_data[-1]["nav"]
                week_ago = nav_data[-min(5, len(nav_data))]["nav"]
                week_return = (latest_nav - week_ago) / week_ago * 100
                month_ago = nav_data[0]["nav"]
                month_return = (latest_nav - month_ago) / month_ago * 100
            else:
                week_return = 0
                month_return = 0

            result.append({
                "code": code,
                "name": name,
                "theme": theme,
                "latest_nav": nav_data[-1]["nav"] if nav_data else 0,
                "latest_date": nav_data[-1]["date"] if nav_data else "",
                "week_return_pct": round(week_return, 2),
                "month_return_pct": round(month_return, 2),
                "nav_trend": nav_data[-7:],
            })
        except Exception as e:
            print(f"[WARN] Fund {code}({name}) NAV collection failed: {e}")

    print(f"[OK] Tracked fund NAV: {len(result)} funds")
    return result


# ============================================================
# Main function
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Finance data collection")
    parser.add_argument("--date", default=None, help="Pipeline date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    output_dir = ROOT / "output" / today
    output_dir.mkdir(parents=True, exist_ok=True)

    us_movers = collect_us_market_movers()
    a_share_hot = collect_a_share_hot()
    a_share_indices = collect_a_share_major_indices()
    top_funds = collect_top_funds(10)

    fund_holdings = {}
    for fund in top_funds[:3]:
        code = fund["code"]
        holdings = collect_fund_holdings(code)
        if holdings:
            fund_holdings[code] = {
                "fund_name": fund["name"],
                "holdings": holdings,
            }

    us_sector = collect_us_sector_performance()
    macro = collect_macro_indicators()
    sector_flow = collect_sector_flow()
    north_south = collect_north_south_flow()
    tracked_funds = collect_tracked_fund_nav()

    result = {
        "collected_at": datetime.now().isoformat(),
        "date": today,
        "us_market": {
            "movers": us_movers,
            "sector_performance": us_sector,
            "top_quotes": collect_us_top_quotes(),
        },
        "a_share": {
            "indices": a_share_indices,
            "hot_stocks": a_share_hot,
            "sector_flow": sector_flow,
            "north_south_flow": north_south,
        },
        "macro": macro,
        "funds": {
            "top_ranked": top_funds,
            "holdings_detail": fund_holdings,
            "tracked_funds": tracked_funds,
        },
    }

    output_file = output_dir / "raw_finance.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Finance data saved to {output_file}")
    return result


if __name__ == "__main__":
    r = main()
    if r:
        indices = r.get("a_share", {}).get("indices", [])
        us_quotes = r.get("us_market", {}).get("top_quotes", [])
        if not indices and not us_quotes:
            print("[WARN] Finance collection: US + A-share indices both empty")
            sys.exit(1)
