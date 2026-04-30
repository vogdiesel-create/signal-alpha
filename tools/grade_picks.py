#!/usr/bin/env python3
"""
Grade SignalAlpha picks against actual market prices.
Checks if picks hit target or stop loss.
Updates track record automatically.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("pip install yfinance")
    exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"
PICKS_DIR = DATA_DIR / "picks"
HISTORY_DIR = DATA_DIR / "history"


def grade_pick(pick, start_date):
    """Check if a pick hit target or stop since entry date."""
    ticker = pick["ticker"]
    entry = float(pick["entry"])
    target = float(pick["target"])
    stop = float(pick["stop"])
    direction = pick["direction"]

    stock = yf.Ticker(ticker)
    hist = stock.history(start=start_date, end=datetime.now().strftime("%Y-%m-%d"))

    if hist.empty:
        return {"status": "open", "current": None}

    current_price = float(hist["Close"].iloc[-1])

    for idx, row in hist.iterrows():
        high = float(row["High"])
        low = float(row["Low"])
        close = float(row["Close"])

        if direction == "long":
            if high >= target:
                return {
                    "status": "win",
                    "exit_price": target,
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "return_pct": f"+{((target - entry) / entry * 100):.1f}%",
                    "current": current_price,
                }
            if low <= stop:
                return {
                    "status": "loss",
                    "exit_price": stop,
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "return_pct": f"{((stop - entry) / entry * 100):.1f}%",
                    "current": current_price,
                }
        elif direction == "short":
            if low <= target:
                return {
                    "status": "win",
                    "exit_price": target,
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "return_pct": f"+{((entry - target) / entry * 100):.1f}%",
                    "current": current_price,
                }
            if high >= stop:
                return {
                    "status": "loss",
                    "exit_price": stop,
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "return_pct": f"{((entry - stop) / entry * 100):.1f}%",
                    "current": current_price,
                }

    return {
        "status": "open",
        "current": current_price,
        "unrealized": f"{((current_price - entry) / entry * 100):+.1f}%"
        if direction == "long"
        else f"{((entry - current_price) / entry * 100):+.1f}%",
    }


def grade_all():
    """Grade all picks from all daily files."""
    results = []
    pick_files = sorted(PICKS_DIR.glob("*.json"))

    for pf in pick_files:
        if pf.name == "latest.json":
            continue
        data = json.loads(pf.read_text())
        date = data["date"]
        for pick in data.get("picks", []):
            result = grade_pick(pick, date)
            results.append(
                {
                    "date": date,
                    "ticker": pick["ticker"],
                    "direction": pick["direction"],
                    "entry": pick["entry"],
                    "target": pick["target"],
                    "stop": pick.get("stop", ""),
                    "result": result["status"].upper(),
                    "returnPct": result.get("return_pct", result.get("unrealized", "N/A")),
                    "exit_date": result.get("exit_date", ""),
                }
            )

    return results


def update_latest_with_history():
    """Update latest.json with grading history."""
    latest_path = PICKS_DIR / "latest.json"
    if not latest_path.exists():
        return

    data = json.loads(latest_path.read_text())
    history = grade_all()

    # Update stats
    graded = [h for h in history if h["result"] in ["WIN", "LOSS"]]
    wins = [h for h in graded if h["result"] == "WIN"]
    total = len(history)

    data["history"] = history[-20:]  # Last 20 entries
    data["stats"]["totalPicks"] = str(total)
    data["stats"]["winRate"] = f"{len(wins)/len(graded)*100:.0f}%" if graded else "N/A"
    data["stats"]["activePicks"] = str(len([h for h in history if h["result"] == "OPEN"]))

    latest_path.write_text(json.dumps(data, indent=4))
    print(f"Updated: {total} picks, {len(graded)} graded, {len(wins)} wins")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "update":
        update_latest_with_history()
    else:
        results = grade_all()
        for r in results:
            print(f"{r['date']} {r['ticker']} {r['direction']} -> {r['result']} {r['returnPct']}")
