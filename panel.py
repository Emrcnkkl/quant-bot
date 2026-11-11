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
import re
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


# --------------------------------------------------------------------------- #
#  HABERLER (RSS başlıkları; yalnızca başlık, saat ve bağlantı — metin kopyalanmaz)
# --------------------------------------------------------------------------- #
NEWS_FEEDS = [
    ("Habertürk", "https://www.haberturk.com/rss/ekonomi.xml"),
    ("Bloomberg HT", "https://www.bloomberght.com/rss"),
    ("AA", "https://www.aa.com.tr/tr/rss/default?cat=ekonomi"),
    ("TRT Haber", "https://www.trthaber.com/ekonomi_articles.rss"),
    ("Dünya Gazetesi", "https://www.dunya.com/rss"),
    ("Ekonomim", "https://www.ekonomim.com/rss"),
]
# Anahtar kelimeler kelime başına göre eşleşir ("faiz" → "faizi", "faizler"); "=" ile bitenler tam kelime,
# boşluk içerenler metin içinde aranır. ("çin" → "için" ile eşleşmez.)
NEWS_CATS = [
    ("Borsa", ["borsa", "bist", "hisse", "endeks", "halka arz", "temettü", "kap=", "wall street"]),
    ("Faiz", ["faiz", "merkez bankası", "tcmb", "fed=", "fed'", "ecb=", "ppk=", "para politika", "tahvil", "politika faizi"]),
    ("Enflasyon", ["enflasyon", "tüfe", "üfe=", "fiyat artış", "zam=", "zamlı", "zammı"]),
    ("Döviz", ["dolar", "euro=", "euro'", "döviz", "kur=", "kuru=", "kurda", "kurlar", "sterlin"]),
    ("Altın", ["altın", "gümüş", "ons=", "onsu"]),
    ("Enerji", ["petrol", "brent", "doğal gaz", "doğalgaz", "akaryakıt", "benzin", "motorin", "elektrik", "enerji", "opec"]),
    ("Kripto", ["bitcoin", "kripto", "ethereum"]),
    ("Küresel", ["abd", "avrupa", "çin=", "çin'", "almanya", "rusya", "trump", "japonya", "ingiltere", "iran=", "iran'", "israil",
               "ukrayna", "fransa", "küresel"]),
]
NEWS_SKIP = ["şans topu", "sayısal loto", "süper loto", "on numara", "milli piyango", "burç", "maç sonucu", "canlı izle"]


def _fold(t: str) -> str:
    return t.replace("İ", "i").replace("I", "ı").lower()


def fetch_news(hours: int = 48, limit: int = 250) -> dict:
    import html as html_
    from email.utils import parsedate_to_datetime
    now = pd.Timestamp.now(tz="UTC")
    items, seen, sources = [], set(), []
    for src, url in NEWS_FEEDS:
        body = bot._http(url, timeout=20)
        if not body:
            print(f"  ! Haber akışı alınamadı: {src}", file=sys.stderr)
            continue
        txt = body.decode("utf-8", "ignore")
        n = 0
        for it in re.findall(r"<item[\s>].*?</item>|<entry[\s>].*?</entry>", txt, re.S):
            def tag(name):
                m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", it, re.S)
                return html_.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", tag("title")))
            link = tag("link") or (re.search(r'<link[^>]+href="([^"]+)"', it) or [None, ""])[1]
            when = tag("pubDate") or tag("published") or tag("updated") or tag("dc:date")
            try:
                ts = pd.Timestamp(parsedate_to_datetime(when)) if "," in when[:5] else pd.Timestamp(when)
                ts = ts.tz_localize("Europe/Istanbul") if ts.tzinfo is None else ts
                ts = ts.tz_convert("UTC")
            except Exception:  # noqa: BLE001
                ts = None
            if not title or not link.startswith("http") or (ts is not None and (now - ts).total_seconds() > hours * 3600):
                continue
            f = _fold(title)
            if any(k in f for k in NEWS_SKIP):
                continue
            key = re.sub(r"[^a-zçğıöşü0-9]", "", f)[:60]
            if key in seen:
                continue
            seen.add(key)
            words = re.findall(r"[a-zçğıöşüâî0-9']+", f)
            def hit(k):
                if " " in k:
                    return k in f
                if k.endswith("="):
                    return k[:-1] in words or any(w.split("'")[0] == k[:-1] for w in words)
                return any(w.startswith(k) for w in words)
            cats = [c for c, kws in NEWS_CATS if any(hit(k) for k in kws)]
            items.append({"title": title, "link": link, "src": src,
                          "ts": ts.strftime("%Y-%m-%dT%H:%MZ") if ts is not None else None, "cats": cats})
            n += 1
        sources.append({"name": src, "n": n})
    items.sort(key=lambda x: x["ts"] or "", reverse=True)
    return {"items": items[:limit], "sources": sources, "hours": hours}


# --------------------------------------------------------------------------- #
#  HALKA ARZLAR (Borsa İstanbul bülteninde ilk kez görünen hisseler)
# --------------------------------------------------------------------------- #
def _bulletin_codes(day: pd.Timestamp, cache: dict):
    """O günün bülteni (tam tablo). Tatil ya da henüz yayımlanmamışsa None."""
    if day not in cache:
        b = bot.fetch_bulletin(day)
        cache[day] = b if b is not None and len(b) > 100 else None
    return cache[day]


def _codes_only(day: pd.Timestamp, cache: dict):
    """Arama için hafif sürüm: yalnızca hisse kodları (tüm sütunları okumaktan ~20 kat hızlı)."""
    import io
    import zipfile
    key = ("codes", day)
    if key not in cache:
        if day in cache:
            cache[key] = None if cache[day] is None else set(cache[day].index)
        else:
            body = bot._http(bot.BULLETIN_URL.format(y=day.year, m=day.month, d=day.day))
            codes = None
            if body:
                try:
                    with zipfile.ZipFile(io.BytesIO(body)) as z:
                        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                        col = pd.read_csv(z.open(name), sep=";", usecols=[1], dtype=str, encoding="latin-1").iloc[:, 0]
                    codes = {c[:-2] for c in col.dropna() if c.endswith(".E")}
                except Exception:  # noqa: BLE001
                    codes = None
            cache[key] = codes if codes and len(codes) > 100 else None
    return cache[key]


def update_ipo_state(state: dict | None, today: pd.Timestamp, back_days: int = 730) -> dict:
    """
    Halka arz listesi (kalıcı durum, ipo_state.json). İlk çalıştırmada son ~2 yılın bültenleri taranır: bugün işlem
    gören ama dönem başında olmayan her hissenin ilk işlem günü ikili aramayla bulunur. Sonraki çalıştırmalarda yalnızca
    yeni bülten(ler)deki yeni kodlar eklenir. İlk gün açılış/kapanış bültenden alınır (halka arz fiyatı bültende yok).
    """
    cache = {}
    days = list(pd.bdate_range(today - pd.Timedelta(days=12), today)[::-1])
    latest_d = next((d for d in days if _bulletin_codes(d, cache) is not None), None)
    if latest_d is None:
        return state or {}
    latest = _bulletin_codes(latest_d, cache)

    def first_row(t, d):
        r = _bulletin_codes(d, cache).loc[t]
        return {"t": t, "raw_name": str(r["Name"]), "first_day": str(d.date()),
                "first_open": rnd(r["Open"], 2), "first_close": rnd(r["Close"], 2)}
    if not state or not state.get("known"):
        cal = [d for d in pd.bdate_range(today - pd.Timedelta(days=back_days), latest_d)]
        start_i = next(i for i, d in enumerate(cal) if _codes_only(d, cache) is not None)
        base = _codes_only(cal[start_i], cache)
        new = sorted(set(latest.index) - base)
        print(f"  · Halka arz geçmişi taranıyor: {len(new)} yeni kod ({cal[start_i].date()} – {latest_d.date()})")
        ipos = []
        for t in new:
            lo, hi = start_i, len(cal) - 1
            while lo < hi:
                m = (lo + hi) // 2
                k = m                              # tatilse sonraki ilk bülten gününe kay
                while k < hi and _codes_only(cal[k], cache) is None:
                    k += 1
                codes = _codes_only(cal[k], cache)
                if codes is None or t in codes:
                    # m..k-1 arası bülten yok (tatil); sınırın her adımda daralması için k == hi ise m'ye çek
                    hi = k if (codes is not None and k < hi) else m
                else:
                    lo = k + 1
            while lo < len(cal) - 1 and _codes_only(cal[lo], cache) is None:
                lo += 1
            if _codes_only(cal[lo], cache) is not None and t in _codes_only(cal[lo], cache) \
                    and _bulletin_codes(cal[lo], cache) is not None:
                ipos.append(first_row(t, cal[lo]))
        return {"last_date": str(latest_d.date()), "known": sorted(latest.index), "ipos": ipos}
    known = set(state["known"])
    ipos = list(state.get("ipos", []))
    if str(latest_d.date()) > state.get("last_date", ""):
        # Son kayıttan bu yana yayımlanan bültenler (genelde tek gün)
        for d in pd.bdate_range(pd.Timestamp(state["last_date"]) + pd.Timedelta(days=1), latest_d):
            b = _bulletin_codes(d, cache)
            if b is None:
                continue
            for t in sorted(set(b.index) - known):
                ipos.append(first_row(t, d))
                print(f"  ✓ Yeni işlem görmeye başlayan hisse: {t} ({d.date()})")
            known |= set(b.index)
    return {"last_date": str(max(latest_d.date().isoformat(), state.get("last_date", ""))),
            "known": sorted(known), "ipos": ipos}


def ipo_report(state: dict, months: int = 24) -> dict:
    """Son halka arzların performansı (ilk işlem fiyatına göre), tavan serisi ve BIST 100 kıyası."""
    import yfinance as yf
    cutoff = str((pd.Timestamp.today() - pd.DateOffset(months=months)).date())
    ipos = [x for x in state.get("ipos", []) if x["first_day"] >= cutoff]
    if not ipos:
        return {"items": []}
    syms = [f"{x['t']}.IS" for x in ipos] + ["XU100.IS"]
    px = yf.download(syms, start=min(x["first_day"] for x in ipos), interval="1d", auto_adjust=True,
                     progress=False, threads=True, group_by="column")["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    try:
        with open(os.path.join(bot.OUT_DIR, "names.json"), encoding="utf-8") as f:
            names = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        names = {}
    # Bülten adları Türkçe karaktersiz; eksik adlar Yahoo'dan alınıp names.json'a yazılır (her çalıştırmada en fazla 15)
    asked = 0
    for x in ipos:
        if x["t"] not in names and x["t"] not in bot.NAMES and asked < 15:
            try:
                nm = bot.company_name(x["t"])
                if nm and nm != x["t"]:
                    names[x["t"]] = nm
            except Exception:  # noqa: BLE001
                pass
            asked += 1
    xu = px["XU100.IS"].dropna() if "XU100.IS" in px else pd.Series(dtype=float)
    items = []
    for x in ipos:
        s = f"{x['t']}.IS"
        c = px[s].dropna() if s in px else pd.Series(dtype=float)
        c = c[c.index >= pd.Timestamp(x["first_day"])]
        if len(c) < 1 or not x.get("first_open"):
            continue
        # Yahoo düzeltilmiş fiyatı bedelsizlerde geçmişi ölçekler: ilk günü Yahoo'nun ilk kapanışına göre oranla
        scale = x["first_close"] / c.iloc[0] if x.get("first_close") else 1.0
        cc = c * scale
        base = x["first_open"]
        r = cc.pct_change()
        # Tavan serisi: ikinci işlem gününden itibaren üst üste ~%10 yükseliş. İlk gün sayılmaz: halka arz fiyatı
        # bültende olmadığından ilk günün tavan olup olmadığı kesin bilinemez (çoğu hisse ilk güne tavanla başlar).
        tavan = 0
        for v in r.iloc[1:]:
            if v >= 0.095:
                tavan += 1
            else:
                break
        xb = xu[xu.index >= pd.Timestamp(x["first_day"])]
        bret = (xb.iloc[-1] / xb.iloc[0] - 1) * 100 if len(xb) > 1 else None
        ret = (cc.iloc[-1] / base - 1) * 100
        items.append({
            "t": x["t"], "name": bot.NAMES.get(x["t"]) or names.get(x["t"]) or x["raw_name"].title(),
            "first_day": x["first_day"], "first_open": base, "first_close": x.get("first_close"),
            "last": rnd(c.iloc[-1], 2),          # gerçek son fiyat (getiriler bedelsize göre düzeltilmiş seriden) "chg": rnd(r.iloc[-1] * 100, 2) if len(r) > 1 else None,
            "ret": rnd(ret, 1), "vs_bist": rnd(ret - bret, 1) if bret is not None else None,
            "peak": rnd((cc.max() / base - 1) * 100, 1), "from_peak": rnd((cc.iloc[-1] / cc.max() - 1) * 100, 1),
            "tavan": tavan, "days": int(len(cc)),
            "spark": [rnd(v, 2) for v in (cc.iloc[::max(1, len(cc) // 80)] if len(cc) > 80 else cc)],
        })
    items.sort(key=lambda i: i["first_day"], reverse=True)
    yr = [i for i in items if i["first_day"] >= str((pd.Timestamp.today() - pd.DateOffset(months=12)).date())]
    rets = [i["ret"] for i in yr if i["ret"] is not None]
    stats = {"n12": len(yr), "up12": sum(r > 0 for r in rets), "avg12": rnd(float(np.mean(rets)), 1) if rets else None,
             "med12": rnd(float(np.median(rets)), 1) if rets else None,
             "tavan12": sum(i["tavan"] > 0 for i in yr), "beat12": sum((i["vs_bist"] or 0) > 0 for i in yr)}
    return {"items": items, "stats": stats, "months": months}


def run_ipos() -> dict | None:
    path = os.path.join(bot.OUT_DIR, "ipo_state.json")
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = None
    today = pd.Timestamp.now(tz="Europe/Istanbul").tz_localize(None).normalize()
    new_state = update_ipo_state(state, today)
    if new_state and new_state != state:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_state, f, ensure_ascii=False, separators=(",", ":"))
    return ipo_report(new_state) if new_state else None


def _write_compact(name: str, obj) -> None:
    with open(os.path.join(bot.OUT_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


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
    stamp = now.strftime("%Y-%m-%dT%H:%M%z")
    try:
        news = fetch_news()
        _write_compact("news.json", {"generated_at": stamp, **news})
        print(f"  ✓ Haberler: {len(news['items'])} başlık, {sum(1 for x in news['sources'] if x['n'])} kaynak")
    except Exception as e:  # noqa: BLE001
        print(f"  ! Haberler: {type(e).__name__}: {e}", file=sys.stderr)
    try:
        ipo = run_ipos()
        if ipo is not None:
            _write_compact("ipos.json", {"generated_at": stamp, **ipo})
            print(f"  ✓ Halka arzlar: {len(ipo['items'])} hisse")
    except Exception as e:  # noqa: BLE001
        print(f"  ! Halka arzlar: {type(e).__name__}: {e}", file=sys.stderr)
    n = sum(len(g["items"]) for g in groups)
    print(f"  ✓ {n} gösterge" + (f" · BIST {bist['date']}: {bist['adv']} yükselen, {bist['dec']} düşen" if bist else ""))


if __name__ == "__main__":
    run()
