"""FCN 每日監控網頁產生器（6檔專屬版）。

商品資料與判斷邏輯與 Colab notebook `fcn_6products_only_report.ipynb` 一致，
輸出 docs/index.html 給 GitHub Pages 使用。
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))

# ki=None 代表沒有獨立 KI 價，監控時以 strike(轉換價) 做為參考下限
PRODUCTS = [
    {"id": "01985364", "ccy": "USD", "coupon": 12.12, "strike_pct": 80, "ko_pct": 88,
     "trade": "2026/08/21", "issue": "2026/08/28", "fixing": "2026/12/28", "maturity": "2026/12/31",
     "ko_start": "2026/09/28", "ko_end": "2026/12/28",
     "legs": [{"ticker": "AVGO", "strike": 294.7600, "ki": 276.3375, "ko": 324.2360},
              {"ticker": "AMAT", "strike": 393.8560, "ki": 369.2400, "ko": 433.2416},
              {"ticker": "ORCL", "strike": 117.1760, "ki": 109.8525, "ko": 128.8936}]},

    {"id": "01985369", "ccy": "AUD", "coupon": 27.37, "strike_pct": 85, "ko_pct": 85,
     "trade": "2026/08/21", "issue": "2026/08/28", "fixing": "2026/12/28", "maturity": "2026/12/31",
     "ko_start": "2026/09/28", "ko_end": "2026/12/28",
     "legs": [{"ticker": "COHR", "strike": 246.0920, "ki": 193.9784, "ko": 246.0920},
              {"ticker": "MU", "strike": 821.7630, "ki": 647.7426, "ko": 821.7630},
              {"ticker": "SNDK", "strike": 1356.6680, "ki": 1069.3736, "ko": 1356.6680}]},

    {"id": "01915911", "ccy": "USD", "coupon": 10.0, "strike_pct": 85, "ko_pct": 95,
     "trade": "2026/08/21", "issue": "2026/08/28", "fixing": "2026/12/28", "maturity": "2026/12/31",
     "ko_start": "2026/09/28", "ko_end": "2026/12/28",
     "legs": [{"ticker": "TSM", "strike": 356.1075, "ki": None, "ko": 398.0025},
              {"ticker": "GOOG", "strike": 290.4875, "ki": None, "ko": 324.6625},
              {"ticker": "AVGO", "strike": 313.1825, "ki": None, "ko": 350.0275}]},

    {"id": "01915778", "ccy": "USD", "coupon": 17.35, "strike_pct": 80, "ko_pct": 85,
     "trade": "2026/08/06", "issue": "2026/08/13", "fixing": "2026/12/14", "maturity": "2026/12/17",
     "ko_start": "2026/09/14", "ko_end": "2026/12/14",
     "legs": [{"ticker": "AVGO", "strike": 336.4520, "ki": None, "ko": 357.4803},
              {"ticker": "TSLA", "strike": 255.6240, "ki": None, "ko": 271.6005},
              {"ticker": "AMAT", "strike": 421.9840, "ki": None, "ko": 448.3580}]},

    {"id": "01915777", "ccy": "USD", "coupon": 15.81, "strike_pct": 80, "ko_pct": 90,
     "trade": "2026/08/06", "issue": "2026/08/13", "fixing": "2026/12/14", "maturity": "2026/12/17",
     "ko_start": "2026/09/14", "ko_end": "2026/12/14",
     "legs": [{"ticker": "SOXX", "strike": 426.0160, "ki": None, "ko": 479.2680},
              {"ticker": "ADBE", "strike": 208.1920, "ki": None, "ko": 234.2160},
              {"ticker": "AVGO", "strike": 336.4520, "ki": None, "ko": 378.5085}]},

    {"id": "01681089", "ccy": "USD", "coupon": 12.77, "strike_pct": 75, "ko_pct": 86,
     "trade": "2026/09/23", "issue": "2026/09/30", "fixing": "2027/02/01", "maturity": "2027/02/04",
     "ko_start": "2026/10/30", "ko_end": "2027/02/01",
     "legs": [{"ticker": "MRVL", "strike": 195.6750, "ki": 182.6300, "ko": 224.3740},
              {"ticker": "AMAT", "strike": 355.7850, "ki": 332.0660, "ko": 407.9668},
              {"ticker": "MU", "strike": 803.9100, "ki": 750.3160, "ko": 921.8168}]},
]

# 客戶庫存資料
HOLDINGS = {
    "01985364": [],
    "01985369": [],
    "01915911": [],
    "01915778": [{"customer": "合計", "amount": 250000, "units": 25}],
    "01915777": [{"customer": "合計", "amount": 200000, "units": 20}],
    "01681089": [{"customer": "合計", "amount": 250000, "units": 25}],
}

STATUS_RANK = {"ki_breached": 0, "critical_ki": 1, "near_ki": 2, "pre_obs": 3, "normal": 4, "unknown": 5}
STATUS_LABEL = {"ki_breached": ("跌破KI", "#c0392b"), "critical_ki": ("KI警戒", "#e67e22"),
                "near_ki": ("接近KI", "#f1c40f"), "pre_obs": ("觀察期前", "#7f8c8d"),
                "normal": ("正常", "#2ecc71"), "unknown": ("無資料", "#95a5a6")}
KO_ALL_LABEL = ("已全部提前出場", "#c9a84c")


def parse_date(s):
    return datetime.strptime(s, "%Y/%m/%d").date()


def get_current_price(ticker):
    import yfinance as yf
    t = yf.Ticker(ticker)
    # 1) 當日分鐘K線最後一筆  2) fast_info  3) 最近交易日收盤價
    try:
        closes = t.history(period="1d", interval="1m")["Close"].dropna()
        if not closes.empty:
            return float(closes.iloc[-1]), closes.index[-1]
    except Exception:
        pass
    try:
        val = t.fast_info["last_price"]
        if val is not None:
            return float(val), None
    except Exception:
        pass
    try:
        closes = t.history(period="5d")["Close"].dropna()
        return float(closes.iloc[-1]), closes.index[-1]
    except Exception:
        return None, None


def get_prices(tickers):
    prices, timestamps = {}, []
    for t in tickers:
        price, ts = get_current_price(t)
        prices[t] = price
        print(f"  {t}: {price}  (資料時間: {ts})")
        if ts is not None:
            timestamps.append(ts)
    return prices, timestamps


def leg_status(spot, strike, ki, ko, ko_started):
    ki_ref = ki if ki is not None else strike
    if spot is None:
        return "unknown", "無法取得報價", False, False

    reached_ko = spot >= ko
    near_ko = (not reached_ko) and spot >= ko * 0.97

    if spot <= ki_ref:
        code, desc = "ki_breached", "已跌破 KI 參考價"
    else:
        buf = (spot - ki_ref) / ki_ref
        if buf <= 0.05:
            code, desc = "critical_ki", "距 KI 參考價 5% 內"
        elif buf <= 0.10:
            code, desc = "near_ki", "距 KI 參考價 10% 內"
        elif not ko_started:
            code, desc = "pre_obs", "尚未進入 KO 觀察期"
        else:
            code, desc = "normal", "安全區間"

    if reached_ko:
        desc += "；已達KO價"
    elif near_ko:
        desc += "；接近KO價（3%內）"
    return code, desc, reached_ko, near_ko


def build_report_data(prices, today):
    out = []
    for p in PRODUCTS:
        ko_start, ko_end = parse_date(p["ko_start"]), parse_date(p["ko_end"])
        started = today >= ko_start
        legs, worst_code, ko_count = [], None, 0
        for leg in p["legs"]:
            spot = prices.get(leg["ticker"])
            code, desc, reached_ko, near_ko = leg_status(spot, leg["strike"], leg["ki"], leg["ko"], started)
            ki_ref = leg["ki"] if leg["ki"] is not None else leg["strike"]
            ko_count += reached_ko
            legs.append({
                "ticker": leg["ticker"], "spot": spot, "strike": leg["strike"],
                "ki": ki_ref, "ki_note": "" if leg["ki"] is not None else "*", "ko": leg["ko"],
                "ki_buf": (spot - ki_ref) / ki_ref * 100 if spot is not None else None,
                "ko_buf": (spot / leg["ko"] - 1) * 100 if spot is not None else None,
                "reached_ko": reached_ko, "near_ko": near_ko,
                "label": STATUS_LABEL[code][0], "color": STATUS_LABEL[code][1], "desc": desc,
            })
            if worst_code is None or STATUS_RANK[code] < STATUS_RANK[worst_code]:
                worst_code = code

        all_ko = started and ko_count == len(p["legs"])
        label, color = KO_ALL_LABEL if all_ko else STATUS_LABEL[worst_code]
        holdings = HOLDINGS.get(p["id"], [])
        out.append({
            **p, "legs": legs, "worst_status": worst_code, "label": label, "color": color,
            "all_ko": all_ko, "ko_count": ko_count, "total_legs": len(p["legs"]),
            "days": (parse_date(p["maturity"]) - today).days,
            "holdings": holdings, "holdings_total": sum(h["amount"] for h in holdings),
        })
    return out


def fmt(v, spec, suffix=""):
    return format(v, spec) + suffix if v is not None else "-"


def badge(text, color):
    return f'<span class="badge" style="background:{color}">{text}</span>'


def make_html(products, upd, price_asof):
    alerts = ""
    groups = [
        ("ako", "✅ 已全部提前出場", [p for p in products if p["all_ko"]]),
        ("aki", "🚨 跌破KI", [p for p in products if p["worst_status"] == "ki_breached"]),
        ("anr", "⚠️ KI警戒 / 接近KI", [p for p in products if p["worst_status"] in ("critical_ki", "near_ki")]),
    ]
    for cls, title, ps in groups:
        if ps:
            alerts += f'<div class="al {cls}">{title}：{", ".join(p["id"] for p in ps)}</div>'
    if not alerts:
        alerts = '<div class="al aok">✅ 無異常，所有產品正常觀察中</div>'

    ov = ""
    for p in products:
        prog = "" if p["all_ko"] else f'<div class="sub">KO進度 {p["ko_count"]}/{p["total_legs"]}</div>'
        ov += (f"<tr><td><b>{p['id']}</b></td><td>{p['ccy']}</td><td class='cp'>{p['coupon']}%</td>"
               f"<td>{p['ko_start']} ~ {p['ko_end']}</td><td>{p['maturity']}</td><td>{p['days']}</td>"
               f"<td>{badge(p['label'], p['color'])}{prog}</td></tr>")

    cards = ""
    for p in products:
        trs = ""
        for l in p["legs"]:
            kic = "bd" if l["ki_buf"] is not None and l["ki_buf"] <= 10 else ""
            if l["reached_ko"]:
                kob = badge("已達KO", "#c9a84c")
            elif l["near_ko"]:
                kob = badge("接近KO", "#27ae60")
            else:
                kob = badge("未達KO", "#95a5a6")
            trs += (f"<tr><td><b>{l['ticker']}</b></td><td>{fmt(l['spot'], '.2f')}</td>"
                    f"<td>{l['ki']:.4f}{l['ki_note']}</td>"
                    f"<td class='{kic}'>{fmt(l['ki_buf'], '+.2f', '%')}</td>"
                    f"<td>{l['ko']:.4f}</td><td>{fmt(l['ko_buf'], '+.2f', '%')}</td><td>{kob}</td>"
                    f"<td>{badge(l['label'], l['color'])}</td><td class='desc'>{l['desc']}</td></tr>")
        hold = ""
        if p["holdings"]:
            rows = "".join(f"<tr><td>{h['customer']}</td><td>{h['amount']:,.0f}</td><td>{h['units']}</td></tr>"
                           for h in p["holdings"])
            hold = (f'<div class="hl">客戶庫存（合計 {p["ccy"]} {p["holdings_total"]:,.0f}）</div>'
                    f'<table class="dt"><thead><tr><th>客戶代號</th><th>投資金額({p["ccy"]})</th><th>單位數</th></tr></thead>'
                    f'<tbody>{rows}</tbody></table>')
        prog = "" if p["all_ko"] else f' <span class="kop">KO進度 {p["ko_count"]}/{p["total_legs"]}</span>'
        cards += (f'<div class="card"><div class="chd"><div><span class="cid">{p["id"]}</span>'
                  f'<span style="margin-left:8px">{badge(p["label"], p["color"])}</span>{prog}</div>'
                  f'<div class="cmt">{p["ccy"]} · 年化 {p["coupon"]}% · 轉換價 {p["strike_pct"]}% · KO {p["ko_pct"]}%'
                  f' · 到期 {p["maturity"]} · 剩 {p["days"]} 天</div></div>'
                  f'<div class="cbd"><table class="dt"><thead><tr><th>標的</th><th>現價</th><th>轉換價/KI參考</th>'
                  f'<th>距KI緩衝</th><th>KO價</th><th>距KO</th><th>是否達KO</th><th>KI狀態</th><th>說明</th></tr></thead>'
                  f'<tbody>{trs}</tbody></table>'
                  f'<div class="fn">KO觀察期：{p["ko_start"]} ~ {p["ko_end"]}　|　期末定價日：{p["fixing"]}　|　到期日：{p["maturity"]}</div>'
                  f'{hold}</div></div>')

    return f'''<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>FCN監控</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,"PingFang TC","Noto Sans TC",sans-serif;background:#F0F2F5;font-size:13px;color:#222}}
.hd{{background:linear-gradient(135deg,#1a3a6e,#2E4A7A);color:#fff;padding:16px}}.hd h1{{font-size:17px}}.hd p{{font-size:11px;color:#c9a84c;margin-top:4px}}
.wrap{{max-width:1000px;margin:0 auto;padding:12px}}.sec{{font-size:13px;font-weight:bold;color:#1a3a6e;border-left:3px solid #c9a84c;padding-left:8px;margin:16px 0 8px}}
.al{{padding:8px 12px;border-radius:6px;margin-bottom:6px;font-weight:bold;font-size:12px}}
.aok{{background:#E8F5E9;color:#2E7D32;border-left:4px solid #2E7D32}}.ako{{background:#FBF5E6;color:#8a6d1f;border-left:4px solid #c9a84c}}
.aki{{background:#FFEBEE;color:#C62828;border-left:4px solid #C62828}}.anr{{background:#FFF3E0;color:#E65100;border-left:4px solid #E65100}}
.ow{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
.ov{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.08)}}
.ov thead tr{{background:#1a3a6e;color:#fff}}.ov th{{padding:8px 10px;text-align:center;font-size:11px;white-space:nowrap}}
.ov td{{padding:7px 10px;text-align:center;font-size:12px;border-bottom:1px solid #EEE;white-space:nowrap}}.ov tbody tr:nth-child(even){{background:#F7F9FC}}
.cp{{color:#c9a84c;font-weight:bold}}.bd{{color:#C62828;font-weight:bold}}.sub{{font-size:10px;color:#666;margin-top:2px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold;white-space:nowrap;color:#fff}}
.card{{background:#fff;border-radius:8px;margin-bottom:12px;box-shadow:0 1px 6px rgba(0,0,0,.08);overflow:hidden}}
.chd{{background:#1a3a6e;padding:10px 14px}}.cid{{font-size:14px;font-weight:bold;color:#c9a84c}}.kop{{font-size:11px;color:#cfd8dc;margin-left:6px}}
.cmt{{font-size:11px;color:#90A4AE;margin-top:3px}}
.cbd{{padding:10px;overflow-x:auto;-webkit-overflow-scrolling:touch}}
.dt{{width:100%;border-collapse:collapse;font-size:11px}}.dt thead tr{{background:#3A5278;color:#fff}}
.dt th{{padding:6px 8px;text-align:center;white-space:nowrap}}.dt td{{padding:6px 8px;text-align:center;border-bottom:1px solid #EEE;white-space:nowrap}}
.dt tbody tr:nth-child(even){{background:#F7F9FC}}.desc{{text-align:left!important}}
.fn{{color:#888;font-size:10px;margin:6px 0}}.hl{{font-weight:bold;color:#1a3a6e;font-size:12px;margin:10px 0 4px}}
.ft{{color:#9E9E9E;font-size:10px;padding:16px 0 24px;line-height:1.6}}
</style></head><body>
<div class="hd"><h1>FCN 結構型商品　每日監控（6檔）</h1><p>更新：{upd} (台北) · 報價時間：{price_asof} · {len(products)}支商品</p></div>
<div class="wrap"><div class="sec">今日警示</div>{alerts}
<div class="sec">產品總覽</div><div class="ow"><table class="ov">
<thead><tr><th>商品編號</th><th>幣別</th><th>年化配息</th><th>KO觀察期</th><th>到期日</th><th>剩餘天</th><th>目前狀態</th></tr></thead>
<tbody>{ov}</tbody></table></div>
<div class="sec">各產品明細</div>{cards}
<div class="ft">* 表示合約未明訂獨立 KI 價，監控時以轉換價作為參考下限。「距KI緩衝」= (現價 - KI參考價) / KI參考價，數字愈小代表離KI愈近、風險愈高。「已全部提前出場」須所有連結標的當日皆達KO價，任一檔未達則商品尚未出場。資料來源：Yahoo Finance。以上資訊僅供內部參考，實際條件以正式合約為準。</div></div></body></html>'''


def main(out_path="docs/index.html"):
    now = datetime.now(TPE)
    tickers = sorted({leg["ticker"] for p in PRODUCTS for leg in p["legs"]})
    prices, timestamps = get_prices(tickers)
    price_asof = max(timestamps).strftime("%Y/%m/%d %H:%M %Z") if timestamps else "N/A"
    products = build_report_data(prices, now.date())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(make_html(products, now.strftime("%Y/%m/%d %H:%M"), price_asof))
    print("done:", os.path.getsize(out_path), "bytes")


if __name__ == "__main__":
    main(*sys.argv[1:])
