"""
盤整突破 (Base Breakout) 策略 —— 純 pandas 實作

輸入：日 K 線 DataFrame，需含欄位 Date, Open, High, Low, Close, Volume
輸出：原資料加上各項指標欄位與布林欄位 Signal

訊號條件（全部成立才為 True）：
  1. 流動性：近 N 日平均成交金額 >= min_dollar_vol（單位：百萬美元）
  2. 股價  ：收盤價 >= min_price
  3. 趨勢  ：Close > SMA50 且 SMA50 > SMA200
  4. 盤整  ：突破前 base_len 日的區間寬度 BaseWidthPct <= max_base_width
  5. 突破  ：收盤價站上 PivotPrice（盤整區最高價），且漲幅不超過 max_extension（避免追高）
  6. 量能  ：當日成交量 / 前 N 日均量 >= min_vol_ratio
  7. 收盤位置：ClosePos = (Close-Low)/(High-Low) >= min_close_pos（收在當日高檔）
  8. 冷卻期：前 cooldown 日內未出現過訊號（避免同一波突破重複觸發）
"""

import numpy as np
import pandas as pd

REQUIRED_COLS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def run_breakout_strategy(
    df: pd.DataFrame,
    min_dollar_vol: float = 20.0,   # 百萬美元
    min_price: float = 10.0,
    base_len: int = 20,             # 盤整區間天數
    max_base_width: float = 15.0,   # 盤整區最大寬度 (%)
    max_extension: float = 5.0,     # 突破幅度上限 (%)
    min_vol_ratio: float = 1.5,     # 突破量 / 均量
    min_close_pos: float = 0.6,     # 收盤位於當日區間位置 (0~1)
    vol_avg_len: int = 50,          # 均量 / 均成交金額天數
    use_trend_filter: bool = True,
    cooldown: int = 10,
) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要欄位: {missing}")

    out = df.copy().sort_values("Date").reset_index(drop=True)
    high, low, close, vol = out["High"], out["Low"], out["Close"], out["Volume"]

    # 1. 流動性（用前一日為止的均值，避免突破當日的爆量灌水）
    dollar_vol = close * vol / 1e6
    out["AvgDollarVol"] = dollar_vol.rolling(vol_avg_len).mean().shift(1)
    avg_vol = vol.rolling(vol_avg_len).mean().shift(1)

    # 3. 趨勢均線
    out["SMA50"] = close.rolling(50).mean()
    out["SMA200"] = close.rolling(200).mean()

    # 4. 盤整區：不含當日的前 base_len 根 K 棒
    base_high = high.rolling(base_len).max().shift(1)
    base_low = low.rolling(base_len).min().shift(1)
    out["PivotPrice"] = base_high
    out["BaseWidthPct"] = (base_high - base_low) / base_high * 100

    # 5~7. 突破幅度、量比、收盤位置
    out["BreakoutPct"] = (close / base_high - 1) * 100
    out["BreakoutVolRatio"] = vol / avg_vol
    day_range = (high - low).replace(0, np.nan)
    out["ClosePos"] = ((close - low) / day_range).fillna(1.0)

    cond = (
        (out["AvgDollarVol"] >= min_dollar_vol)
        & (close >= min_price)
        & (out["BaseWidthPct"] <= max_base_width)
        & (out["BreakoutPct"] > 0)
        & (out["BreakoutPct"] <= max_extension)
        & (out["BreakoutVolRatio"] >= min_vol_ratio)
        & (out["ClosePos"] >= min_close_pos)
    )
    if use_trend_filter:
        cond &= (close > out["SMA50"]) & (out["SMA50"] > out["SMA200"])
    cond = cond.fillna(False).to_numpy()

    # 8. 冷卻期
    signal = np.zeros(len(out), dtype=bool)
    last = -cooldown - 1
    for i in np.flatnonzero(cond):
        if i - last > cooldown:
            signal[i] = True
            last = i
    out["Signal"] = signal

    round_cols = ["PivotPrice", "BaseWidthPct", "BreakoutPct", "BreakoutVolRatio", "ClosePos"]
    out[round_cols] = out[round_cols].round(2)
    return out


def load_yfinance(ticker: str, start: str = "2022-01-01") -> pd.DataFrame:
    """下載 yfinance 日 K，並整理成 run_breakout_strategy 需要的格式。"""
    import yfinance as yf

    data = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    data = data.reset_index()
    data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]
    return data[REQUIRED_COLS]
