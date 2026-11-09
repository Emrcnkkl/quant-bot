#!/usr/bin/env python3
"""
BIST30 Teknik Analiz Sinyal Botu  (Aşama 1)
-------------------------------------------
- Günlük veri (yfinance, .IS uzantılı semboller)
- Çoklu indikatör skoru  (-100 ... +100)
    Trend      : EMA200, EMA20/EMA50, ADX/DI
    Momentum   : RSI14, MACD histogram
    Hacim      : 20 günlük ortalamaya göre hacim
    Kırılım    : 20 günlük en yüksek / en düşük
    Göreli güç : XU030 endeksine göre 3 aylık getiri farkı
- Sinyal     : skor >= +40 -> AL,  skor <= -40 -> SAT,  arası -> TUT
- Risk       : ATR tabanlı stop (2.5 ATR) ve hedef (4 ATR)
- Backtest   : sadece long, sinyal kapanışta oluşur, ERTESİ GÜN AÇILIŞTA işlem,
               komisyon + kayma dahil, ATR iz süren stop, örneklem dışı (OOS) dönem ayrı

Çıktılar (aynı klasöre):
    signals.json   -> güncel sinyaller (web sayfası okur)
    backtest.json  -> geçmiş performans raporu
    history.json   -> günlük sinyal geçmişi (her çalıştırmada eklenir)

Kullanım:
    pip install -r requirements.txt
    python bot.py            # gerçek veri (internet gerekir)
    python bot.py --demo     # sentetik veri ile test (internet gerekmez)

UYARI: Bu yazılımın ürettiği çıktılar yatırım tavsiyesi değildir.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
#  AYARLAR
# --------------------------------------------------------------------------- #
# BIST 30 bileşenleri: 1 Ekim - 31 Aralık 2026 dönemi (TRMET girdi, DSTKF çıktı)
# Her çeyrek başında Borsa İstanbul duyurusuna göre güncelleyin.
BIST30 = {
    "AEFES": "Anadolu Efes", "AKBNK": "Akbank", "ASELS": "Aselsan",
    "ASTOR": "Astor Enerji", "BIMAS": "BİM Mağazalar", "EKGYO": "Emlak Konut GYO",
    "ENKAI": "Enka İnşaat", "EREGL": "Ereğli Demir Çelik", "FROTO": "Ford Otosan",
    "GARAN": "Garanti BBVA", "GUBRF": "Gübre Fabrikaları", "ISCTR": "İş Bankası (C)",
    "KCHOL": "Koç Holding", "KRDMD": "Kardemir (D)", "MGROS": "Migros",
    "PETKM": "Petkim", "PGSUS": "Pegasus", "SAHOL": "Sabancı Holding",
    "SASA": "SASA Polyester", "SISE": "Şişecam", "TAVHL": "TAV Havalimanları",
    "TCELL": "Turkcell", "THYAO": "Türk Hava Yolları", "TOASO": "Tofaş",
    "TRALT": "Türk Altın İşletmeleri", "TRMET": "TR Anadolu Metal Madencilik",
    "TTKOM": "Türk Telekom", "TUPRS": "Tüpraş", "VAKBN": "VakıfBank",
    "YKBNK": "Yapı Kredi",
}
BENCHMARK = "XU030"

CFG = {
    "history_period": "6y",     # indirilecek veri uzunluğu
    "warmup_days": 210,         # EMA200 için ısınma
    "buy_threshold": 40,        # skor >= bu -> AL
    "sell_threshold": -40,      # skor <= bu -> SAT
    "exit_score": 0,            # pozisyondayken skor bunun altına inerse çık
    "stop_atr": 2.5,            # iz süren stop mesafesi (ATR katı)
    "target_atr": 4.0,          # bilgi amaçlı hedef (ATR katı)
    "commission": 0.0010,       # tek yön komisyon (%0.10)
    "slippage": 0.0005,         # tek yön kayma (%0.05)
    "oos_fraction": 0.30,       # son %30'luk dönem örneklem dışı olarak raporlanır
    "min_bars": 260,
}

TR_TZ = timezone(timedelta(hours=3))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
#  VERİ
# --------------------------------------------------------------------------- #
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["Close"] > 0) & (df["Open"] > 0)]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_real(tickers: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    data: dict[str, pd.DataFrame] = {}
    for t in tickers:
        sym = f"{t}.IS"
        try:
            raw = yf.download(sym, period=CFG["history_period"], interval="1d",
                              auto_adjust=True, progress=False, threads=False)
            if raw is None or raw.empty:
                print(f"  ! {t}: veri yok", file=sys.stderr)
                continue
            data[t] = _clean(raw)
            print(f"  ✓ {t}: {len(data[t])} gün, son {data[t].index[-1].date()}")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {t}: {e}", file=sys.stderr)
    return data


def fetch_demo(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Rejim değiştiren sentetik fiyat serileri (sadece kod testi için)."""
    rng = np.random.default_rng(42)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1500)
    market = rng.normal(0.0006, 0.017, len(idx))
    data = {}
    for i, t in enumerate(tickers):
        r = np.random.default_rng(1000 + i)
        regime = np.repeat(r.normal(0, 0.0012, len(idx) // 60 + 1), 60)[: len(idx)]
        ret = 0.8 * market + regime + r.normal(0, 0.016, len(idx))
        close = 20 * (1 + i % 7) * np.exp(np.cumsum(ret))
        gap = r.normal(0, 0.006, len(idx))
        open_ = np.r_[close[0], close[:-1]] * np.exp(gap)
        hi = np.maximum(open_, close) * (1 + np.abs(r.normal(0, 0.008, len(idx))))
        lo = np.minimum(open_, close) * (1 - np.abs(r.normal(0, 0.008, len(idx))))
        vol = r.lognormal(15, 0.4, len(idx)) * (1 + 3 * np.abs(ret))
        data[t] = pd.DataFrame({"Open": open_, "High": hi, "Low": lo,
                                "Close": close, "Volume": vol}, index=idx)
    return data


# --------------------------------------------------------------------------- #
#  İNDİKATÖRLER
# --------------------------------------------------------------------------- #
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df: pd.DataFrame, bench_close: pd.Series | None) -> pd.DataFrame:
    d = df.copy()
    c, h, l, v = d["Close"], d["High"], d["Low"], d["Volume"]

    d["ema20"], d["ema50"], d["ema200"] = ema(c, 20), ema(c, 50), ema(c, 200)

    delta = c.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    rs = wilder(gain, 14) / wilder(loss, 14).replace(0, np.nan)
    d["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    macd = ema(c, 12) - ema(c, 26)
    d["macd_hist"] = macd - ema(macd, 9)

    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    d["atr"] = wilder(tr, 14)

    up, dn = h.diff(), -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr_w = wilder(tr, 14)
    d["di_plus"] = 100 * wilder(pd.Series(plus_dm, index=d.index), 14) / atr_w
    d["di_minus"] = 100 * wilder(pd.Series(minus_dm, index=d.index), 14) / atr_w
    dx = 100 * (d["di_plus"] - d["di_minus"]).abs() / (d["di_plus"] + d["di_minus"]).replace(0, np.nan)
    d["adx"] = wilder(dx.fillna(0), 14)

    d["vol_ratio"] = v / v.rolling(20).mean()
    d["hh20"] = h.rolling(20).max().shift(1)   # dünkü itibarıyla 20g zirve
    d["ll20"] = l.rolling(20).min().shift(1)
    d["ret63"] = c.pct_change(63)
    if bench_close is not None:
        b = bench_close.reindex(d.index).ffill()
        d["rel63"] = d["ret63"] - b.pct_change(63)
    else:
        d["rel63"] = 0.0
    return d


# --------------------------------------------------------------------------- #
#  SKOR
# --------------------------------------------------------------------------- #
# Bileşen ağırlıkları (maksimum mutlak puan). Toplam = 100.
W = {"ema200": 15, "ema_cross": 15, "adx": 10, "rsi": 15,
     "macd": 15, "volume": 10, "breakout": 10, "relative": 10}


def score_frame(d: pd.DataFrame) -> pd.DataFrame:
    """Her gün için bileşen puanları ve toplam skor (vektörel)."""
    s = pd.DataFrame(index=d.index)
    c = d["Close"]

    s["ema200"] = np.where(c > d["ema200"], W["ema200"], -W["ema200"])
    s["ema_cross"] = np.where(d["ema20"] > d["ema50"], W["ema_cross"], -W["ema_cross"])

    direction = np.sign(d["di_plus"] - d["di_minus"])
    strength = ((d["adx"] - 15) / 15).clip(0, 1)          # ADX 15->0, 30+->1
    s["adx"] = W["adx"] * direction * strength

    rsi = d["rsi"]
    s["rsi"] = np.select(
        [rsi >= 78, rsi >= 55, rsi >= 45, rsi > 25],
        [-5, W["rsi"], 0, -W["rsi"]],
        default=5,                                       # aşırı satım: tepki ihtimali
    )

    hist = d["macd_hist"]
    rising = hist > hist.shift(1)
    s["macd"] = np.where(hist > 0, 10, -10) + np.where(rising, 5, -5)

    up_day = c > c.shift(1)
    strong_vol = d["vol_ratio"] > 1.5
    s["volume"] = np.where(strong_vol & up_day, W["volume"],
                           np.where(strong_vol & ~up_day, -W["volume"], 0))

    s["breakout"] = np.where(c > d["hh20"], W["breakout"],
                             np.where(c < d["ll20"], -W["breakout"], 0))

    s["relative"] = (d["rel63"].fillna(0) / 0.15).clip(-1, 1) * W["relative"]

    s["score"] = s[list(W)].sum(axis=1).round(1)
    return s


def label(score: float) -> str:
    if score >= CFG["buy_threshold"]:
        return "AL"
    if score <= CFG["sell_threshold"]:
        return "SAT"
    return "TUT"


def reasons(row: pd.Series, comp: pd.Series) -> list[str]:
    r = []
    r.append("Fiyat EMA200 üzerinde (uzun vade yukarı)" if comp["ema200"] > 0
             else "Fiyat EMA200 altında (uzun vade aşağı)")
    r.append("EMA20 > EMA50 (kısa vade pozitif)" if comp["ema_cross"] > 0
             else "EMA20 < EMA50 (kısa vade negatif)")
    if row["adx"] >= 25:
        r.append(f"Güçlü trend (ADX {row['adx']:.0f}, "
                 f"{'alıcılar' if row['di_plus'] > row['di_minus'] else 'satıcılar'} baskın)")
    rsi = row["rsi"]
    if rsi >= 78:
        r.append(f"RSI {rsi:.0f}: aşırı alım bölgesi")
    elif rsi <= 25:
        r.append(f"RSI {rsi:.0f}: aşırı satım bölgesi")
    else:
        r.append(f"RSI {rsi:.0f}")
    r.append("MACD histogramı pozitif" if row["macd_hist"] > 0 else "MACD histogramı negatif")
    if comp["volume"] > 0:
        r.append(f"Yükselişte yüksek hacim (ort. {row['vol_ratio']:.1f}x)")
    elif comp["volume"] < 0:
        r.append(f"Düşüşte yüksek hacim (ort. {row['vol_ratio']:.1f}x)")
    if comp["breakout"] > 0:
        r.append("20 günlük zirve kırıldı")
    elif comp["breakout"] < 0:
        r.append("20 günlük dip kırıldı")
    rel = row.get("rel63", 0) or 0
    if abs(rel) > 0.05:
        r.append(f"3 ayda endeksten {'iyi' if rel > 0 else 'kötü'} (%{rel*100:+.1f})")
    return r


# --------------------------------------------------------------------------- #
#  BACKTEST
# --------------------------------------------------------------------------- #
def backtest(d: pd.DataFrame, sc: pd.Series) -> dict:
    """
    Long-only. t günü kapanışında skor >= buy_threshold ise t+1 açılışta al.
    Çıkış: skor < exit_score (t+1 açılışta) veya iz süren stop (gün içi).
    Döner: günlük strateji getirisi serisi, işlemler, pozisyon durumu.
    """
    o, h, l, c, atr = (d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "atr"))
    score = sc.to_numpy()
    n = len(d)
    cost = CFG["commission"] + CFG["slippage"]
    start = CFG["warmup_days"]

    daily = np.zeros(n)
    in_pos = False
    entry_px = stop = 0.0
    entry_i = -1
    trades = []
    pending = None  # "buy" / "sell" -> ertesi açılışta uygulanacak

    for i in range(start, n):
        # 1) Bir önceki kapanışta verilen emri açılışta uygula
        if pending == "buy" and not in_pos:
            entry_px = o[i] * (1 + cost)
            stop = o[i] - CFG["stop_atr"] * atr[i - 1]
            in_pos, entry_i = True, i
            day_ret = c[i] / entry_px - 1
            pending = None
            # aynı gün stop
            if l[i] <= stop:
                exit_px = min(o[i], stop) * (1 - cost)
                daily[i] = exit_px / entry_px - 1
                trades.append(_trade(d, entry_i, i, entry_px, exit_px, "stop"))
                in_pos = False
                continue
            daily[i] = day_ret
        elif pending == "sell" and in_pos:
            exit_px = o[i] * (1 - cost)
            daily[i] = exit_px / c[i - 1] - 1
            trades.append(_trade(d, entry_i, i, entry_px, exit_px, "sinyal"))
            in_pos = False
            pending = None
        elif in_pos:
            # 2) Gün içi stop kontrolü
            if l[i] <= stop:
                exit_px = min(o[i], stop) * (1 - cost)
                daily[i] = exit_px / c[i - 1] - 1
                trades.append(_trade(d, entry_i, i, entry_px, exit_px, "stop"))
                in_pos = False
            else:
                daily[i] = c[i] / c[i - 1] - 1
        else:
            pending = None

        # 3) Kapanışta: stopu yukarı taşı ve yarın için emir üret
        if in_pos:
            stop = max(stop, c[i] - CFG["stop_atr"] * atr[i])
            if score[i] < CFG["exit_score"]:
                pending = "sell"
        elif score[i] >= CFG["buy_threshold"]:
            pending = "buy"

    open_trade = None
    if in_pos:
        open_trade = {
            "entry_date": str(d.index[entry_i].date()),
            "entry_price": round(float(entry_px), 2),
            "last_price": round(float(c[-1]), 2),
            "stop": round(float(stop), 2),
            "pnl_pct": round((c[-1] / entry_px - 1) * 100, 2),
            "days": int(n - 1 - entry_i),
        }
    return {
        "daily": pd.Series(daily, index=d.index).iloc[start:],
        "trades": trades,
        "open": open_trade,
        "pending": pending,
    }


def _trade(d, i0, i1, p0, p1, why):
    return {"entry_date": str(d.index[i0].date()), "exit_date": str(d.index[i1].date()),
            "entry": round(float(p0), 2), "exit": round(float(p1), 2),
            "ret_pct": round((p1 / p0 - 1) * 100, 2), "days": int(i1 - i0), "exit_reason": why}


def metrics(daily: pd.Series, trades: list[dict] | None = None) -> dict:
    daily = daily.fillna(0)
    if len(daily) < 2:
        return {}
    eq = (1 + daily).cumprod()
    years = len(daily) / 252
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else float("nan")
    std = daily.std()
    sharpe = (daily.mean() / std * math.sqrt(252)) if std > 0 else 0.0
    dd = (eq / eq.cummax() - 1).min()
    out = {
        "total_return_pct": round(total * 100, 2),
        "cagr_pct": round(cagr * 100, 2) if not math.isnan(cagr) else None,
        "sharpe": round(float(sharpe), 2),
        "max_drawdown_pct": round(float(dd) * 100, 2),
        "exposure_pct": round(float((daily != 0).mean()) * 100, 1),
    }
    if trades is not None:
        rets = [t["ret_pct"] for t in trades]
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]
        out.update({
            "trades": len(rets),
            "win_rate_pct": round(len(wins) / len(rets) * 100, 1) if rets else None,
            "avg_trade_pct": round(float(np.mean(rets)), 2) if rets else None,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
            "avg_days": round(float(np.mean([t["days"] for t in trades])), 1) if trades else None,
        })
    return out


# --------------------------------------------------------------------------- #
#  ANA AKIŞ
# --------------------------------------------------------------------------- #
def r2(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 2)


def run(demo: bool) -> None:
    tickers = list(BIST30)
    print(f"BIST30 sinyal botu — {'DEMO (sentetik veri)' if demo else 'gerçek veri'}")
    fetch = fetch_demo if demo else fetch_real
    data = fetch(tickers + [BENCHMARK])
    bench = data.pop(BENCHMARK, None)
    bench_close = bench["Close"] if bench is not None else None
    if bench is None:
        print("  ! XU030 verisi alınamadı, göreli güç bileşeni 0 kabul edilecek", file=sys.stderr)

    signals, per_stock, all_daily, recent_trades = [], [], {}, []
    oos_daily = {}

    for t in tickers:
        df = data.get(t)
        if df is None or len(df) < CFG["min_bars"]:
            print(f"  ! {t}: yetersiz veri, atlandı", file=sys.stderr)
            continue
        d = add_indicators(df, bench_close)
        sc = score_frame(d)
        bt = backtest(d, sc["score"])

        last, comp = d.iloc[-1], sc.iloc[-1]
        prev_close = d["Close"].iloc[-2]
        score = float(comp["score"])
        sig = label(score)
        atr = float(last["atr"])
        close = float(last["Close"])

        # Pozisyon bilgisine göre durum açıklaması
        if bt["open"]:
            state = "POZİSYONDA"
            if bt["pending"] == "sell":
                state = "ÇIKIŞ"          # yarın açılışta çık sinyali
        else:
            state = "GİRİŞ" if bt["pending"] == "buy" else "BEKLE"

        signals.append({
            "ticker": t, "name": BIST30[t],
            "date": str(d.index[-1].date()),
            "close": r2(close),
            "change_pct": r2((close / prev_close - 1) * 100),
            "score": round(score, 1),
            "signal": sig,
            "state": state,
            "score_5d_ago": round(float(sc["score"].iloc[-6]), 1),
            "components": {k: round(float(comp[k]), 1) for k in W},
            "rsi": r2(last["rsi"]), "adx": r2(last["adx"]),
            "atr_pct": r2(atr / close * 100),
            "stop": r2(close - CFG["stop_atr"] * atr) if sig != "SAT" else None,
            "target": r2(close + CFG["target_atr"] * atr) if sig != "SAT" else None,
            "position": bt["open"],
            "reasons": reasons(last, comp),
        })

        daily = bt["daily"]
        all_daily[t] = daily
        split = int(len(daily) * (1 - CFG["oos_fraction"]))
        oos_start = daily.index[split]
        oos_daily[t] = daily.iloc[split:]
        bh = d["Close"].iloc[CFG["warmup_days"]:]
        per_stock.append({
            "ticker": t, "name": BIST30[t],
            "strategy": metrics(daily, bt["trades"]),
            "oos": metrics(daily.iloc[split:], [x for x in bt["trades"] if x["entry_date"] >= str(oos_start.date())]),
            "buy_hold_pct": r2((bh.iloc[-1] / bh.iloc[0] - 1) * 100),
        })
        for tr_ in bt["trades"][-5:]:
            recent_trades.append({"ticker": t, **tr_})

    if not signals:
        sys.exit("Hiç veri işlenemedi. İnternet bağlantısını ve yfinance kurulumunu kontrol edin.")

    # --- Portföy: tüm hisselere eşit ağırlık (1/N), günlük yeniden dengeleme
    port = pd.DataFrame(all_daily).fillna(0).mean(axis=1)
    split = int(len(port) * (1 - CFG["oos_fraction"]))
    port_eq = (1 + port).cumprod()
    bench_eq = None
    if bench_close is not None:
        b = bench_close.reindex(port.index).ffill()
        bench_eq = b / b.iloc[0]
    weekly = port_eq.resample("W-FRI").last()
    curve = [{"date": str(i.date()), "strategy": round(float(v), 4),
              "benchmark": round(float(bench_eq.asof(i)), 4) if bench_eq is not None else None}
             for i, v in weekly.items()]

    now = datetime.now(TR_TZ)
    order = {"AL": 0, "TUT": 1, "SAT": 2}
    signals.sort(key=lambda x: (order[x["signal"]], -x["score"]))
    counts = {k: sum(1 for s in signals if s["signal"] == k) for k in order}
    meta = {
        "generated_at": now.isoformat(timespec="minutes"),
        "data_date": max(s["date"] for s in signals),
        "demo": demo,
        "universe": "BIST 30 (Ekim-Aralık 2026)",
        "thresholds": {"buy": CFG["buy_threshold"], "sell": CFG["sell_threshold"]},
        "disclaimer": "Buradaki bilgiler algoritmik teknik analiz çıktısıdır; yatırım tavsiyesi değildir. "
                      "Yatırım danışmanlığı hizmeti, SPK lisanslı kuruluşlar tarafından kişiye özel sunulur.",
    }
    write("signals.json", {**meta, "counts": counts, "signals": signals})

    write("backtest.json", {
        **meta,
        "settings": {k: CFG[k] for k in ("buy_threshold", "exit_score", "stop_atr",
                                          "commission", "slippage", "oos_fraction")},
        "period": {"start": str(port.index[0].date()), "end": str(port.index[-1].date()),
                   "oos_start": str(port.index[split].date())},
        "portfolio": {
            "full": metrics(port),
            "oos": metrics(port.iloc[split:]),
            "benchmark_full": metrics(bench_eq.pct_change().fillna(0)) if bench_eq is not None else None,
            "benchmark_oos": metrics(bench_eq.pct_change().fillna(0).iloc[split:]) if bench_eq is not None else None,
        },
        "equity_curve": curve,
        "stocks": sorted(per_stock, key=lambda x: -(x["strategy"].get("total_return_pct") or 0)),
        "recent_trades": sorted(recent_trades, key=lambda x: x["exit_date"], reverse=True)[:40],
    })

    # --- Geçmiş (her çalıştırma, aynı veri günü tekrar yazılmaz)
    hist_path = os.path.join(OUT_DIR, "history.json")
    try:
        with open(hist_path, encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    if not demo:
        history = [h for h in history if h.get("date") != meta["data_date"]]
        history.append({"date": meta["data_date"],
                        "signals": {s["ticker"]: [s["signal"], s["score"], s["close"]] for s in signals}})
        write("history.json", history[-500:])

    print(f"\nTamam: {counts['AL']} AL, {counts['TUT']} TUT, {counts['SAT']} SAT  "
          f"(veri tarihi {meta['data_date']})")
    pf = metrics(port)
    print(f"Backtest portföy: toplam %{pf['total_return_pct']}, MaxDD %{pf['max_drawdown_pct']}, "
          f"Sharpe {pf['sharpe']}")


def write(name: str, obj) -> None:
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, allow_nan=False)
    print(f"  → {name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BIST30 teknik analiz sinyal botu")
    ap.add_argument("--demo", action="store_true", help="sentetik veri ile çalıştır")
    run(ap.parse_args().demo)
