"""Sinyal gecikmesi araştırması (17 Kasım 2026): AL sinyaline ne kadar geç kalıyoruz?
  • Olay çalışması: AL'a geçişten önceki ve sonraki ortalama getiri (hareketin ne kadarı sinyalden önce olmuş?).
  • Portföy: bugünkü kural (sinyal kapanışta, işlem ertesi açılışta) ile 0 gecikme (sinyal günü kapanışında işlem,
    teorik), +1 ve +2 gün gecikme ve daha erken giriş eşikleri (30, 35) karşılaştırılır. Güncel model: 100 hisse,
    temel pay 1/50, ucuzluk filtresi + ucuza/puana pay, faiz filtresi.
Çalıştırma: python3 research_lag.py   (önbellek: .cache/wide.pkl, .cache/value_raw.pkl)"""
import pickle

import numpy as np
import pandas as pd

import bot
import research
import research_value as rv


def main() -> None:
    cal, cash, mem, comps = research.bot_setup()
    tick = list(comps)
    M = mem.reindex(index=cal, columns=tick).fillna(False)
    with open(rv.RAW, "rb") as f:
        raw = pickle.load(f)
    EY, BP, FIN = rv.value_frames(raw, cal, tick)
    V = rv.value_score(EY, BP, FIN, M).reindex(index=cal, columns=tick).shift(1)
    ok = (V >= 0.5) | V.isna()

    # ---- Olay çalışması: AL'a geçiş günleri (evrendeyken) ----
    ev = {k: [] for k in ("-20", "-5", "gun", "gap", "+5", "+21", "+63")}
    for t, (d, sc) in comps.items():
        s = sc["score"]
        start = (s >= 40) & (s.shift(1) < 40)
        m = mem[t].reindex(d.index).fillna(False)
        c, o = d["Close"].to_numpy(), d["Open"].to_numpy()
        for i in np.flatnonzero((start & m).to_numpy()):
            if i < 21 or i + 64 >= len(d):
                continue
            ev["-20"].append(c[i - 1] / c[i - 21] - 1)        # sinyalden önceki 20 gün
            ev["-5"].append(c[i - 1] / c[i - 6] - 1)
            ev["gun"].append(c[i] / c[i - 1] - 1)              # sinyal günü
            ev["gap"].append(o[i + 1] / c[i] - 1)              # sinyal kapanışından ertesi açılışa
            ev["+5"].append(c[i + 5] / o[i + 1] - 1)           # bizim girişimizden sonra
            ev["+21"].append(c[i + 21] / o[i + 1] - 1)
            ev["+63"].append(c[i + 63] / o[i + 1] - 1)
    print(f"AL'a geçiş sayısı: {len(ev['gun'])}")
    for k, v in ev.items():
        a = np.array(v)
        print(f"  {k:>4}: ort. %{a.mean() * 100:+.2f}  medyan %{np.median(a) * 100:+.2f}  pozitif %{(a > 0).mean() * 100:.0f}")
    # Kıyas: rastgele bir günden 21 gün sonrası (evrendeyken)
    base = []
    for t, (d, sc) in comps.items():
        m = mem[t].reindex(d.index).fillna(False).to_numpy()
        c, o = d["Close"].to_numpy(), d["Open"].to_numpy()
        idx = np.flatnonzero(m[:-22])
        base.extend(c[idx + 21] / o[idx + 1] - 1)
    print(f"  kıyas (herhangi bir gün, +21): ort. %{np.mean(base) * 100:+.2f}")

    # ---- Portföy varyantları ----
    def port(lag=0, thr=40, same_close=False):
        old = bot.CFG["buy_threshold"]
        bot.CFG["buy_threshold"] = thr
        rets, held, atrp, score = {}, {}, {}, {}
        for t, (d, sc) in comps.items():
            s = sc["score"].shift(lag) if lag else sc["score"]
            # same_close: sinyal günü kapanışında (kapanış seansında) al-sat; stoplar yine gerçek açılış/gün içi fiyatla
            em = mem[t] & ok[t].reindex(mem.index).fillna(True)
            bt = bot.backtest(d, s, cash.reindex(d.index).fillna(0), entry_mask=em,
                              exec_px=d["Close"].shift(1) if same_close else None)
            rets[t], held[t] = bt["daily"], bt["held"]
            atrp[t] = (d["atr"] / d["Close"]).shift(1)
            score[t] = s.shift(1)
        bot.CFG["buy_threshold"] = old
        R = pd.DataFrame(rets).reindex(cal).fillna(0)
        H = pd.DataFrame(held).reindex(cal).fillna(False).astype(bool) & M
        A = pd.DataFrame(atrp).reindex(cal)
        SC = pd.DataFrame(score).reindex(cal)
        volf = A.pow(-1).mul(A.where(M).median(axis=1), axis=0).clip(1 / 3, 2).fillna(1)
        Wt = H.astype(float) / 50 * volf * (0.5 + V).fillna(1) * (SC / 40).clip(0.75, 1.5).fillna(1)
        Wt = Wt.div(Wt.sum(axis=1).clip(lower=1), axis=0)
        e = Wt.sum(axis=1)
        return (Wt * R).sum(axis=1) + (1 - e) * cash

    rows = []
    for lab, kw in (("bugunku: kapanista sinyal, ertesi acilista islem", {}),
                    ("0 gecikme: sinyal gunu kapanisinda islem (teorik)", {"same_close": True}),
                    ("+1 gun gec", {"lag": 1}), ("+2 gun gec", {"lag": 2}),
                    ("erken giris: esik 35", {"thr": 35}), ("erken giris: esik 30", {"thr": 30})):
        st = research.period_stats(port(**kw), cash, cal)
        rows.append({"yontem": lab, **{f"{p}_{x}": v for p, t3 in st.items() for x, v in zip(("yil", "dd", "sh"), t3)}})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    bot.write("research_lag.json", {"events": {k: {"n": len(v), "avg_pct": round(float(np.mean(v)) * 100, 2),
                                                   "pos_pct": round(float((np.array(v) > 0).mean()) * 100)} for k, v in ev.items()},
                                    "base21_pct": round(float(np.mean(base)) * 100, 2), "rows": df.to_dict("records")})
    pd.set_option("display.width", 220)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
