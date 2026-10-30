"""
用法：python breakout/scan.py AAPL NVDA MSFT --start 2022-01-01 --min-dollar-vol 5
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy import load_yfinance, run_breakout_strategy  # noqa: E402

SHOW_COLS = ["Date", "Close", "PivotPrice", "BaseWidthPct", "BreakoutVolRatio", "BreakoutPct", "ClosePos"]


def main():
    p = argparse.ArgumentParser(description="美股盤整突破訊號掃描")
    p.add_argument("tickers", nargs="+")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--min-dollar-vol", type=float, default=5.0, help="百萬美元")
    p.add_argument("--min-price", type=float, default=10.0)
    args = p.parse_args()

    pd.set_option("display.width", 200)
    for ticker in args.tickers:
        print(f"正在下載 {ticker} 的歷史日 K 線數據...")
        data = load_yfinance(ticker, start=args.start)
        if data.empty:
            print(f"{ticker}: 無資料\n")
            continue
        res = run_breakout_strategy(data, min_dollar_vol=args.min_dollar_vol, min_price=args.min_price)
        sig = res[res["Signal"]]
        print(f"在 {len(data)} 個交易日中，共找出 {len(sig)} 個 {ticker} 的突破訊號：")
        print(sig[SHOW_COLS].to_string(index=False) if not sig.empty else "目前時間區間內無符合所有嚴格篩選條件的訊號。")
        print()


if __name__ == "__main__":
    main()
