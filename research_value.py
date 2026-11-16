#!/usr/bin/env python3
"""
Ucuzluk (değer) araştırması — veri toplama ve test.

Veri (İş Yatırım, ücretsiz, resmî API değil): her hisse için 2008'den günlük piyasa değeri (HisseTekil → PD) ve
çeyreklik bilanço (MaliTablo → net kâr 3Z/3ZA, özkaynak 2O). Önbellek: .cache/value_raw.pkl (yarıda kalırsa kaldığı yerden devam).

Noktasal kullanım (geleceği bilmeden): bir çeyreğin bilançosu, çeyrek sonundan 75 gün (yıl sonu bilançosu 100 gün) sonra
"bilinir" kabul edilir. F/K yerine kazanç verimi (son 12 ay net kâr / piyasa değeri), PD/DD yerine defter/piyasa kullanılır
(zarar edenler en pahalı sayılır).

Kullanım:
    python3 research_value.py --veri     # veriyi indir (≈30 dk, kaldığı yerden devam eder)
    python3 research_value.py --test     # deneyler
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

import bot

RAW = os.path.join(".cache", "value_raw.pkl")
GROUPS = ("XI_29", "UFRS_K", "UFRS")


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def fetch_statements(t: str, years=range(2008, 2027)) -> tuple[str | None, dict]:
    """Tüm yılların çeyreklik net kâr (yıl başından birikimli) ve özkaynağı. Grup ilk dolu yıla göre seçilir."""
    out, group = {}, None
    for y in years:
        tried = [group] if group else list(GROUPS)
        for g in tried:
            q = "&".join(f"year{i}={y}&period{i}={m}" for i, m in enumerate((3, 6, 9, 12), 1))
            body = bot._http(f"{bot.ISY_URL}MaliTablo?companyCode={t}&exchange=TRY&financialGroup={g}&{q}", timeout=30)
            try:
                v = json.loads(body).get("value") if body else None
            except ValueError:
                v = None
            if not v:
                continue
            got = False
            for i, m in enumerate((3, 6, 9, 12), 1):
                row = {x["itemCode"]: _num(x.get(f"value{i}")) for x in v}
                eq = row.get("2O")
                net = row.get("3ZA") if g != "XI_29" and row.get("3ZA") else row.get("3Z")
                if eq and eq > 0:
                    out[(y, m)] = (net, eq)
                    got = True
            if got:
                group = g
                break
        time.sleep(0.15)
    return group, out


def fetch_mcap(t: str) -> pd.Series | None:
    p = bot.isy_prices(t, pd.Timestamp("2008-01-01"), pd.Timestamp.today().normalize())
    return None if p is None else p["MCap"].dropna()


def main_data(workers: int = 4) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with open(os.path.join(".cache", "wide.pkl"), "rb") as f:
        tickers = sorted(pickle.load(f).keys())
    tickers = [t for t in tickers if t != bot.BENCHMARK]
    try:
        with open(RAW, "rb") as f:
            raw = pickle.load(f)
    except FileNotFoundError:
        raw = {}
    todo = [t for t in tickers if t not in raw]

    def one(t):
        g, st = fetch_statements(t)
        return t, {"group": g, "statements": st, "mcap": fetch_mcap(t)}
    with ThreadPoolExecutor(workers) as ex:          # İş Yatırım'ı yormamak için en fazla 4 eşzamanlı istek
        for k, fut in enumerate(as_completed([ex.submit(one, t) for t in todo]), 1):
            t, rec = fut.result()
            raw[t] = rec
            mc = rec["mcap"]
            print(f"  [{len(raw)}/{len(tickers)}] {t}: grup {rec['group']}, {len(rec['statements'])} çeyrek, "
                  f"piyasa değeri {0 if mc is None else len(mc)} gün", flush=True)
            if k % 8 == 0:
                with open(RAW, "wb") as f:
                    pickle.dump(raw, f)
    with open(RAW, "wb") as f:
        pickle.dump(raw, f)
    print("Tamam:", len(raw), "hisse")


def value_frames(raw: dict, cal: pd.DatetimeIndex, tickers: list[str]):
    """Günlük, noktasal kazanç verimi (son 12 ay net kâr / piyasa değeri) ve defter/piyasa tabloları."""
    EY, BP, FIN = {}, {}, {}
    for t in tickers:
        rec = raw.get(t)
        if not rec or not rec["statements"] or rec["mcap"] is None or not len(rec["mcap"]):
            continue
        st = rec["statements"]
        ttm, eq = {}, {}
        for (y, m), (net, e) in st.items():
            q_end = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)
            avail = q_end + pd.Timedelta(days=100 if m == 12 else 75)   # bilançonun açıklanmış sayıldığı gün
            if m == 12:
                v = net
            else:
                a, b = st.get((y - 1, 12)), st.get((y - 1, m))
                v = net + a[0] - b[0] if a and b and None not in (net, a[0], b[0]) else None
            if v is not None:
                ttm[avail] = v
            eq[avail] = e
        mc = rec["mcap"]
        mc = mc[mc > 0].reindex(cal).ffill(limit=5)
        lim = 400                                              # 400 günden eski bilanço kullanılmaz
        T = pd.Series(ttm).sort_index()
        E = pd.Series(eq).sort_index()
        T = T[~T.index.duplicated(keep="last")].reindex(cal.union(T.index)).ffill(limit=lim).reindex(cal)
        E = E[~E.index.duplicated(keep="last")].reindex(cal.union(E.index)).ffill(limit=lim).reindex(cal)
        EY[t], BP[t] = T / mc, E / mc
        FIN[t] = rec["group"] != "XI_29"
    return pd.DataFrame(EY), pd.DataFrame(BP), pd.Series(FIN)


def value_score(EY, BP, FIN, M) -> pd.DataFrame:
    """0–1 ucuzluk puanı (1 = en ucuz): o günün evrenindeki hisseler arasında kazanç verimi ve defter/piyasa sıralamasının
    ortalaması; bankalar/sigortacılar ve diğer şirketler ayrı sıralanır. Zarar eden şirketin kazanç verimi negatif → pahalı."""
    cols = [c for c in EY.columns if c in M.columns]
    EY, BP, Mm = EY[cols], BP[cols], M[cols]
    out = pd.DataFrame(np.nan, index=EY.index, columns=cols)
    for fin in (True, False):
        g = [c for c in cols if bool(FIN.get(c)) == fin]
        if not g:
            continue
        r1 = EY[g].where(Mm[g]).rank(axis=1, pct=True)
        r2 = BP[g].where(Mm[g] & (BP[g] > 0)).rank(axis=1, pct=True)
        out[g] = pd.concat([r1, r2]).groupby(level=0).mean().reindex(EY.index)[g]
    return out


def main_test() -> None:
    import research
    cal, cash, mem, comps = research.bot_setup()
    with open(RAW, "rb") as f:
        raw = pickle.load(f)
    tick = list(comps)
    M = mem.reindex(index=cal, columns=tick).fillna(False)
    EY, BP, FIN = value_frames(raw, cal, tick)
    V = value_score(EY, BP, FIN, M).reindex(columns=tick).shift(1)         # dünün bilgisiyle
    cover = (V.notna() & M).sum(axis=1) / M.sum(axis=1)
    print(f"Ucuzluk verisi kapsamı (evrendeki hisselerin oranı): 2009 %{cover['2009'].mean() * 100:.0f}, "
          f"2015 %{cover['2015'].mean() * 100:.0f}, 2025 %{cover['2025'].mean() * 100:.0f}")
    n = bot.CFG["universe_size"]

    def run(entry_extra=None):
        rets, held, atrp, score = {}, {}, {}, {}
        for t, (d, sc) in comps.items():
            em = mem[t]
            if entry_extra is not None:
                em = em & entry_extra[t].reindex(em.index).fillna(True)    # verisi olmayan gün filtre uygulanmaz
            bt = bot.backtest(d, sc["score"], cash.reindex(d.index).fillna(0), entry_mask=em)
            rets[t], held[t] = bt["daily"], bt["held"]
            atrp[t] = (d["atr"] / d["Close"]).shift(1)
            score[t] = sc["score"].shift(1)
        R = pd.DataFrame(rets).reindex(cal).fillna(0)
        H = pd.DataFrame(held).reindex(cal).fillna(False).astype(bool) & M
        A = pd.DataFrame(atrp).reindex(cal)
        volf = A.pow(-1).mul(A.where(M).median(axis=1), axis=0).clip(1 / 3, 2).fillna(1)
        return R, H, volf, pd.DataFrame(score).reindex(cal)

    def port(R, Wt):
        Wt = Wt.div(Wt.sum(axis=1).clip(lower=1), axis=0)
        e = Wt.sum(axis=1)
        return (Wt * R).sum(axis=1) + (1 - e) * cash, e

    R0, H0, vol0, SC0 = run()
    Vf = V.reindex(index=cal, columns=tick)
    vt = (0.5 + Vf).fillna(1)                                               # 0.5 (pahalı) … 1.5 (ucuz)
    stilt = (SC0 / 40).clip(0.75, 1.5).fillna(1)
    variants = {"mevcut model": port(R0, H0.astype(float) / n * vol0),
                "puana gore agirlik": port(R0, H0.astype(float) / n * vol0 * stilt),
                "ucuza buyuk pay": port(R0, H0.astype(float) / n * vol0 * vt)}
    for lab, thr in (("AL + ucuz yari", 0.5), ("AL + en ucuz ucte bir", 2 / 3)):
        R1, H1, vol1, SC1 = run({t: (Vf[t] >= thr) | Vf[t].isna() for t in tick})
        variants[lab] = port(R1, H1.astype(float) / n * vol1)
        if thr == 0.5:
            variants["AL + ucuz yari + ucuza pay + puana pay"] = port(R1, H1.astype(float) / n * vol1 * vt * (SC1 / 40).clip(0.75, 1.5).fillna(1))
    # Saf ucuzluk: her ay başı en ucuz 15 (evrende, verisi olan), eşit ağırlık; maliyet: değişen pay × %0,15
    px = pd.DataFrame({t: d["Close"] for t, (d, _) in comps.items()}).reindex(cal)
    ret = px.pct_change().fillna(0)
    ema200 = pd.DataFrame({t: d["ema200"] for t, (d, _) in comps.items()}).reindex(cal).shift(1)
    mstart = pd.Series(cal.to_period("M"), index=cal).ne(pd.Series(cal.to_period("M"), index=cal).shift())
    for lab, trend in (("saf ucuzluk (en ucuz 15)", False), ("saf ucuzluk + trend (EMA200 ustu)", True)):
        W = pd.DataFrame(0.0, index=cal, columns=tick)
        cur = pd.Series(0.0, index=tick)
        cost = pd.Series(0.0, index=cal)
        for i, day in enumerate(cal):
            if mstart.iloc[i]:
                v = Vf.loc[day].where(M.loc[day]).dropna()
                pick = v.nlargest(15).index
                new = pd.Series(0.0, index=tick); new[pick] = 1 / 15
                cost[day] = (new - cur).abs().sum() * 0.0015
                cur = new
            w = cur.copy()
            if trend:
                ok = (px.loc[day] > ema200.loc[day]).reindex(tick).fillna(False)
                w = w.where(ok, 0)
            W.loc[day] = w.values
        e = W.sum(axis=1)
        variants[lab] = ((W * ret).sum(axis=1) + (1 - e) * cash - cost, e)
    rows = []
    for k, (r, e) in variants.items():
        st = research.period_stats(r, cash, cal)
        rows.append({"yontem": k, **{f"{p}_{x}": v for p, t3 in st.items() for x, v in zip(("yil", "dd", "sh"), t3)},
                     "hisse_payi": round(float(e.mean()) * 100)})
    df = pd.DataFrame(rows)
    ref = df.iloc[0]
    df["egitim_fark"] = (df.egitim_yil - ref.egitim_yil).round(1)
    df["test_fark"] = (df.test_yil - ref.test_yil).round(1)
    df["kurali_gecti"] = (df.egitim_fark >= 3) & (df.test_fark >= 3) & (df.tum_dd >= -35)
    bot.write("research_deger.json", {"rows": df.to_dict("records"),
                                       "not": "Ucuzluk verisi 2008 ortasından itibaren; öncesinde filtre uygulanmaz."})
    pd.set_option("display.width", 260)
    print(df.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.veri:
        main_data()
    elif a.test:
        main_test()
