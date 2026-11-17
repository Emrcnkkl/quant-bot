"""Kâr büyümesi / bilanço sürprizi araştırması (17 Kasım 2026). Noktasal: bilanço dönem sonundan 75 gün (yıl sonu 100 gün)
sonra bilinir sayılır, karar dünkü bilgiyle. Ölçüler (o günün evreninde yüzdelik sıra, bankalar ayrı):
  • ceyrek: (son çeyrek net kâr − geçen yılın aynı çeyreği) / piyasa değeri   ("kâr sürprizi", fiyata göre)
  • yillik: (son 12 ay net kâr − bir yıl önceki son 12 ay) / piyasa değeri
Fiyata bölmek hem zararı/işaret sorununu hem de enflasyon etkisini (aynı gün herkes aynı enflasyonu yaşar) yumuşatır.
Güncel model (100 hisse, temel pay 1/50, ucuzluk filtresi + ucuza/puana pay, faiz filtresi) ile karşılaştırılır.
Çalıştırma: python3 research_growth.py"""
import pickle

import numpy as np
import pandas as pd

import bot
import research
import research_value as rv


def growth_frames(raw: dict, cal: pd.DatetimeIndex, tickers: list[str]):
    Q, Y = {}, {}
    for t in tickers:
        rec = raw.get(t)
        if not rec or not rec["statements"] or rec["mcap"] is None or not len(rec["mcap"]):
            continue
        st = rec["statements"]
        def q(y, m):                       # çeyreklik net kâr (birikimliden)
            a = st.get((y, m))
            if not a or a[0] is None:
                return None
            if m == 3:
                return a[0]
            b = st.get((y, m - 3))
            return a[0] - b[0] if b and b[0] is not None else None
        def ttm(y, m):
            v = [q(y, mm) for mm in (3, 6, 9, 12) if mm <= m] + [q(y - 1, mm) for mm in (3, 6, 9, 12) if mm > m]
            return None if any(x is None for x in v) else sum(v)
        dq, dy = {}, {}
        for (y, m) in st:
            avail = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0) + pd.Timedelta(days=100 if m == 12 else 75)
            a, b = q(y, m), q(y - 1, m)
            if a is not None and b is not None:
                dq[avail] = a - b
            a, b = ttm(y, m), ttm(y - 1, m)
            if a is not None and b is not None:
                dy[avail] = a - b
        mc = rec["mcap"]; mc = mc[mc > 0]; mc = mc[~mc.index.duplicated(keep="last")].reindex(cal).ffill(limit=5)
        for D, out in ((dq, Q), (dy, Y)):
            s = pd.Series(D).sort_index()
            s = s[~s.index.duplicated(keep="last")].reindex(cal.union(s.index)).ffill(limit=400).reindex(cal)
            out[t] = s / mc
    return pd.DataFrame(Q), pd.DataFrame(Y)


def rank_in_universe(X, FIN, M):
    cols = [c for c in X.columns if c in M.columns]
    out = pd.DataFrame(np.nan, index=X.index, columns=cols)
    for fin in (True, False):
        g = [c for c in cols if bool(FIN.get(c)) == fin]
        if g:
            out[g] = X[g].where(M[g]).rank(axis=1, pct=True)
    return out


def main() -> None:
    cal, cash, mem, comps = research.bot_setup()
    tick = list(comps)
    M = mem.reindex(index=cal, columns=tick).fillna(False)
    with open(rv.RAW, "rb") as f:
        raw = pickle.load(f)
    EY, BP, FIN = rv.value_frames(raw, cal, tick)
    V = rv.value_score(EY, BP, FIN, M).reindex(index=cal, columns=tick).shift(1)
    GQ, GY = growth_frames(raw, cal, tick)
    GQ = rank_in_universe(GQ, FIN, M).reindex(index=cal, columns=tick).shift(1)
    GY = rank_in_universe(GY, FIN, M).reindex(index=cal, columns=tick).shift(1)
    cover = (GQ.notna() & M).sum(axis=1) / M.sum(axis=1)
    print(f"Büyüme verisi kapsamı: 2010 %{cover['2010'].mean() * 100:.0f}, 2018 %{cover['2018'].mean() * 100:.0f}, 2025 %{cover['2025'].mean() * 100:.0f}")

    # Tek başına bilgi: büyüme sırasına göre sonraki 21 günlük getiri (evren içi, beşte birlik dilimler)
    px = pd.DataFrame({t: d["Close"] for t, (d, _) in comps.items()}).reindex(cal)
    fwd = px.shift(-21) / px - 1
    for lab, G in (("ceyrek", GQ), ("yillik", GY)):
        res = []
        for lo in (0, .2, .4, .6, .8):
            m = (G > lo) & (G <= lo + .2) & M
            res.append(fwd.where(m).stack().mean() * 100)
        print(f"  {lab}: 21 gün sonraki ort. getiri, en düşük → en yüksek büyüme beşte biri: " + " · ".join(f"%{x:.2f}" for x in res))

    def run(ok):
        rets, held, atrp, score = {}, {}, {}, {}
        for t, (d, sc) in comps.items():
            em = mem[t] & ok[t].reindex(mem.index).fillna(True)
            bt = bot.backtest(d, sc["score"], cash.reindex(d.index).fillna(0), entry_mask=em)
            rets[t], held[t] = bt["daily"], bt["held"]
            atrp[t] = (d["atr"] / d["Close"]).shift(1)
            score[t] = sc["score"].shift(1)
        R = pd.DataFrame(rets).reindex(cal).fillna(0)
        H = pd.DataFrame(held).reindex(cal).fillna(False).astype(bool) & M
        A = pd.DataFrame(atrp).reindex(cal)
        volf = A.pow(-1).mul(A.where(M).median(axis=1), axis=0).clip(1 / 3, 2).fillna(1)
        return R, H, volf, pd.DataFrame(score).reindex(cal)

    def port(R, H, volf, SC, tilt):
        Wt = H.astype(float) / 50 * volf * tilt.fillna(1) * (SC / 40).clip(0.75, 1.5).fillna(1)
        Wt = Wt.div(Wt.sum(axis=1).clip(lower=1), axis=0)
        e = Wt.sum(axis=1)
        return (Wt * R).sum(axis=1) + (1 - e) * cash

    okV = (V >= 0.5) | V.isna()
    base = run(okV)
    variants = {"bugunku model (ucuzluk)": port(*base, 0.5 + V)}
    for lab, G in (("ceyrek", GQ), ("yillik", GY)):
        variants[f"{lab}: ucuza+buyumeye pay"] = port(*base, (0.5 + V).fillna(1) * (0.5 + G).fillna(1))
        both = (V + G.fillna(V)) / 2                                     # büyüme yoksa yalnız ucuzluk
        okB = (both >= 0.5) | both.isna()
        variants[f"{lab}: guclu AL = (ucuzluk+buyume)/2 >= 0.5"] = port(*run(okB), 0.5 + both)
        okVG = okV & ((G >= 0.5) | G.isna())
        variants[f"{lab}: ucuz VE buyuyen"] = port(*run(okVG), 0.5 + V)
        okVorG = okV | (G >= 0.8)
        variants[f"{lab}: ucuz YA DA cok buyuyen (ust %20)"] = port(*run(okVorG), (0.5 + V).fillna(1) * (0.5 + G).fillna(1))
    rows = []
    for k, r in variants.items():
        st = research.period_stats(r, cash, cal)
        rows.append({"yontem": k, **{f"{p}_{x}": v for p, t3 in st.items() for x, v in zip(("yil", "dd", "sh"), t3)}})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    ref = df.iloc[0]
    df["egitim_fark"] = (df.egitim_yil - ref.egitim_yil).round(1)
    df["test_fark"] = (df.test_yil - ref.test_yil).round(1)
    df["iki_donem_iyi"] = (df.egitim_fark > 0) & (df.test_fark > 0) & (df.tum_dd >= -35)
    bot.write("research_buyume.json", {"rows": df.to_dict("records")})
    pd.set_option("display.width", 260)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
