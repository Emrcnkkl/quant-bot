#!/usr/bin/env python3
"""
Ekonomi ve finans paneli için piyasa verisi toplayıcı → markets.json

Kaynaklar (ücretsiz): Yahoo Finance (endeksler, döviz, altın, emtia, dünya borsaları, kripto; gün içinde
~15 dk gecikmeli) ve Borsa İstanbul resmî günlük bülteni (tüm hisselerin kapanışı: yükselenler, düşenler,
en çok işlem görenler, piyasa genişliği).

Kullanım:  python3 panel.py          (gün içinde 30 dakikada bir ve akşam bot ile birlikte çalışır)
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pandas as pd

import bot

EPOCH = pd.Timestamp("2000-01-01")   # grafik tarihleri bu günden itibaren gün sayısı olarak saklanır (dosya küçük kalsın)
GRAM = "GRAM"           # gram altın = ons altın × USD/TRY ÷ 31,1035
# (grup kimliği, başlık, [(sembol, ad, ondalık, birim, tür)])  tür: "pct" yüzde değişim, "bp" puan farkı
GROUPS = [
    ("tr", "Türkiye", [("XU100.IS", "BIST 100", 0, "", "pct"), ("XU030.IS", "BIST 30", 0, "", "pct"),
                       ("XBANK.IS", "BIST Banka", 0, "", "pct"), ("XUSIN.IS", "BIST Sınai", 0, "", "pct")]),
    ("fx", "Döviz", [("USDTRY=X", "Dolar / TL", 4, "₺", "pct"), ("EURTRY=X", "Euro / TL", 4, "₺", "pct"),
                     ("GBPTRY=X", "Sterlin / TL", 4, "₺", "pct"), ("EURUSD=X", "Euro / Dolar", 4, "$", "pct"),
                     ("DX-Y.NYB", "Dolar endeksi (DXY)", 2, "", "pct")]),
    ("metal", "Altın ve gümüş", [(GRAM, "Gram altın", 2, "₺", "pct"), ("GC=F", "Ons altın", 2, "$", "pct"),
                                 ("SI=F", "Ons gümüş", 2, "$", "pct")]),
    ("emtia", "Emtia", [("BZ=F", "Brent petrol (varil)", 2, "$", "pct"), ("CL=F", "WTI petrol (varil)", 2, "$", "pct"),
                        ("NG=F", "Doğal gaz", 3, "$", "pct"), ("HG=F", "Bakır (libre)", 3, "$", "pct")]),
    ("world", "Dünya borsaları", [("^GSPC", "S&P 500 · ABD", 0, "", "pct"), ("^IXIC", "Nasdaq · ABD", 0, "", "pct"),
                                  ("^DJI", "Dow Jones · ABD", 0, "", "pct"), ("^GDAXI", "DAX · Almanya", 0, "", "pct"),
                                  ("^FTSE", "FTSE 100 · İngiltere", 0, "", "pct"),
                                  ("^STOXX50E", "Euro Stoxx 50 · Avrupa", 0, "", "pct"),
                                  ("^N225", "Nikkei 225 · Japonya", 0, "", "pct")]),
    ("rates", "Faiz ve risk", [("^TNX", "ABD 10 yıllık tahvil faizi", 2, "%", "bp"),
                               ("^VIX", "VIX (korku endeksi)", 2, "", "pct")]),
    ("crypto", "Kripto", [("BTC-USD", "Bitcoin", 0, "$", "pct"), ("ETH-USD", "Ethereum", 0, "$", "pct")]),
]


def rnd(x, dec):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), dec)


def series_stats(c: pd.Series, dec: int, kind: str) -> dict:
    """Son değer, değişimler (gün, hafta, ay, yıl başı, 1 yıl), küçük grafik ve geçmiş."""
    c = c.dropna()
    c = c[c > 0] if kind == "pct" else c
    last_d = c.index[-1]

    def back(days=None, ytd=False):
        ref = c[c.index <= (pd.Timestamp(last_d.year - 1, 12, 31) if ytd else last_d - pd.Timedelta(days=days))]
        if not len(ref):
            return None
        a, b = c.iloc[-1], ref.iloc[-1]
        return rnd(a - b, 3) if kind == "bp" else rnd((a / b - 1) * 100, 2)
    one_y = c[c.index > last_d - pd.Timedelta(days=366)]
    weekly = c[c.index > last_d - pd.Timedelta(days=5 * 366)].resample("W-FRI").last().dropna()
    return {
        "last": rnd(c.iloc[-1], dec), "date": str(last_d.date()),
        "chg": (rnd(c.iloc[-1] - c.iloc[-2], 3) if kind == "bp" else rnd((c.iloc[-1] / c.iloc[-2] - 1) * 100, 2))
        if len(c) > 1 else None,
        "chg1w": back(7), "chg1m": back(30), "chgytd": back(ytd=True), "chg1y": back(365),
        "hi1y": rnd(one_y.max(), dec), "lo1y": rnd(one_y.min(), dec),
        "spark": [rnd(v, dec + 1) for v in c.iloc[-66:]],
        "hist": {"d": [(i - EPOCH).days for i in one_y.index], "c": [rnd(v, dec + 1) for v in one_y]},
        "long": {"d": [(i - EPOCH).days for i in weekly.index], "c": [rnd(v, dec + 1) for v in weekly]},
    }


def fetch_markets() -> list[dict]:
    import yfinance as yf
    syms = [s for _, _, items in GROUPS for s, *_ in items if s != GRAM]
    raw = None
    for attempt in range(3):
        try:
            raw = yf.download(syms, period="5y", interval="1d", auto_adjust=True, progress=False,
                              threads=True, group_by="column")["Close"]
            break
        except Exception as e:  # noqa: BLE001
            print(f"  ! Yahoo: {type(e).__name__}", file=sys.stderr)
    if raw is None:
        raise RuntimeError("Yahoo'dan piyasa verisi alınamadı")
    raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
    raw = raw[~raw.index.duplicated(keep="last")]
    cols = {s: raw[s] for s in syms if s in raw}
    if "GC=F" in cols and "USDTRY=X" in cols:
        g, u = cols["GC=F"].dropna(), cols["USDTRY=X"].dropna()
        cols[GRAM] = (g * u.reindex(g.index).ffill() / 31.1035).dropna()
    out = []
    for gid, title, items in GROUPS:
        rows = []
        for s, name, dec, unit, kind in items:
            c = cols.get(s)
            if c is None or c.dropna().size < 30:
                print(f"  ! {s}: veri yok", file=sys.stderr)
                continue
            rows.append({"sym": s, "name": name, "dec": dec, "unit": unit, "kind": kind, **series_stats(c, dec, kind)})
        out.append({"id": gid, "title": title, "items": rows})
    return out


def bist_today(max_back: int = 7) -> dict | None:
    """Borsa İstanbul'da son işlem günü: tüm hisselerin değişimi (resmî bültenden)."""
    today = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None).normalize()
    for d in pd.bdate_range(today - pd.Timedelta(days=max_back + 3), today)[::-1]:
        b = bot.fetch_bulletin(d)
        if b is not None and len(b) > 100:
            break
    else:
        return None
    b = b[(b["PrevClose"] > 0) & (b["Close"] > 0)].copy()
    b["chg"] = (b["Close"] / b["PrevClose"] - 1) * 100
    try:
        with open(os.path.join(bot.OUT_DIR, "names.json"), encoding="utf-8") as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    def nm(t, raw):
        return bot.NAMES.get(t) or cache.get(t) or str(raw).title()

    def rows(df):
        return [{"t": t, "name": nm(t, r["Name"]), "close": rnd(r["Close"], 2), "chg": rnd(r["chg"], 2),
                 "vol_tl": rnd(r["TLVolume"] / 1e6, 1)} for t, r in df.iterrows()]
    liquid = b[b["TLVolume"] >= 5e6]          # çok sığ hisseleri sıralamalara alma (5 milyon TL altı)
    return {
        "date": str(d.date()), "total": int(len(b)),
        "adv": int((b["chg"] > 0.005).sum()), "dec": int((b["chg"] < -0.005).sum()),
        "unch": int((b["chg"].abs() <= 0.005).sum()),
        "vol_bn": rnd(b["TLVolume"].sum() / 1e9, 1),
        "gainers": rows(liquid.nlargest(10, "chg")), "losers": rows(liquid.nsmallest(10, "chg")),
        "active": rows(b.nlargest(10, "TLVolume")),
    }


def run() -> None:
    now = pd.Timestamp.now(tz="Europe/Istanbul")
    print(f"Panel verisi — {now:%Y-%m-%d %H:%M}")
    groups = fetch_markets()
    try:
        bist = bist_today()
    except Exception as e:  # noqa: BLE001
        print(f"  ! Borsa İstanbul bülteni: {type(e).__name__}: {e}", file=sys.stderr)
        bist = None
    out = {"generated_at": now.strftime("%Y-%m-%dT%H:%M%z"), "epoch": str(EPOCH.date()), "groups": groups, "bist": bist,
           "disclaimer": "Fiyatlar 15 dakikaya kadar gecikmeli olabilir; yatırım tavsiyesi değildir."}
    with open(os.path.join(bot.OUT_DIR, "markets.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    n = sum(len(g["items"]) for g in groups)
    print(f"  ✓ {n} gösterge" + (f" · BIST {bist['date']}: {bist['adv']} yükselen, {bist['dec']} düşen" if bist else ""))


if __name__ == "__main__":
    run()
