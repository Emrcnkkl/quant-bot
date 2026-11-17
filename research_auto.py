"""Aday listesi araştırması (17 Kasım 2026): evren, elle yazılmış 156 adaydan mı yoksa Borsa İstanbul'daki tüm hisselerden mi
seçilmeli? Son 12 ayın hacmine göre ilk 100'ün 44'ü eski aday listesinde yoktu.
Aday setleri (önbellek .cache/): wide.pkl (eski 156) · wide_auto.pkl (+ bugün hacimde ilk 200'de olanlar; geriye bakış yanlılığı
taşır) · wide_all.pkl (son 1 yılda bültende görünen tüm hisseler; hangi hisselerin büyüyeceğini bilmediği için en dürüstü).
Her sette: güncel model ve "ucuz VE kârı büyüyen" (research_growth.py) varyantı.
Çalıştırma: python3 research_auto.py --veri (evrene hiç girmiş hisselerin bilanço verisi) · python3 research_auto.py"""
import argparse
import os
import pickle
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import bot
import research
import research_growth as rg
import research_value as rv

SETS = (("eski 156 aday", ".cache/wide.pkl"), ("+ bugunku ilk 200", ".cache/wide_auto.pkl"), ("tum hisseler", ".cache/wide_all.pkl"))


def setup(path):
    research.WIDE = path
    return research.bot_setup()


def main_data() -> None:
    with open(rv.RAW, "rb") as f:
        raw = pickle.load(f)
    cal, cash, mem, comps = setup(SETS[-1][1])
    need = [t for t in comps if t not in raw]
    print(f"Evrene en az bir kez girmiş {len(comps)} hisse; bilançosu eksik {len(need)}", flush=True)

    def one(t):                         # yalnızca hissenin işlem gördüğü yıllar (öncesi boş sorgu, çok yavaş)
        g, st = rv.fetch_statements(t, years=range(max(2008, comps[t][0].index[0].year - 1), 2027))
        return t, {"group": g, "statements": st, "mcap": rv.fetch_mcap(t)}
    with ThreadPoolExecutor(4) as ex:
        for k, (t, rec) in enumerate(ex.map(one, need), 1):
            raw[t] = rec
            print(f"  [{k}/{len(need)}] {t}: {rec['group']}, {len(rec['statements'])} çeyrek", flush=True)
            if k % 10 == 0:
                with open(rv.RAW, "wb") as f:
                    pickle.dump(raw, f)
    with open(rv.RAW, "wb") as f:
        pickle.dump(raw, f)


def main() -> None:
    with open(rv.RAW, "rb") as f:
        raw = pickle.load(f)
    rows = []
    for lab, path in SETS:
        if not os.path.exists(path):
            continue
        cal, cash, mem, comps = setup(path)
        tick = list(comps)
        M = mem.reindex(index=cal, columns=tick).fillna(False)
        EY, BP, FIN = rv.value_frames(raw, cal, tick)
        V = rv.value_score(EY, BP, FIN, M).reindex(index=cal, columns=tick).shift(1)
        GQ, _ = rg.growth_frames(raw, cal, tick)
        GQ = rg.rank_in_universe(GQ, FIN, M).reindex(index=cal, columns=tick).shift(1)
        cover = ((V.notna() & M).sum(axis=1) / M.sum(axis=1))
        print(f"{lab}: {len(tick)} hisse evrene girmiş; ucuzluk kapsamı 2015 %{cover['2015'].mean() * 100:.0f}, 2025 %{cover['2025'].mean() * 100:.0f}", flush=True)

        def run(ok, tilt):
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
            SC = pd.DataFrame(score).reindex(cal)
            volf = A.pow(-1).mul(A.where(M).median(axis=1), axis=0).clip(1 / 3, 2).fillna(1)
            Wt = H.astype(float) / 50 * volf * tilt.fillna(1) * (SC / 40).clip(0.75, 1.5).fillna(1)
            Wt = Wt.div(Wt.sum(axis=1).clip(lower=1), axis=0)
            e = Wt.sum(axis=1)
            return (Wt * R).sum(axis=1) + (1 - e) * cash

        okV = (V >= 0.5) | V.isna()
        okVG = okV & ((GQ >= 0.5) | GQ.isna())
        uni = mem.reindex(index=cal, columns=tick).fillna(False)
        px = pd.DataFrame({t: d["Close"] for t, (d, _) in comps.items()}).reindex(cal)
        ubh = px.pct_change().where(uni.shift(1).fillna(False)).mean(axis=1).fillna(0)   # evren al-bekle (eşit ağırlık)
        for vlab, r in (("model", run(okV, 0.5 + V)), ("model + kar buyumesi", run(okVG, 0.5 + V)), ("evren al-bekle", ubh)):
            st = research.period_stats(r, cash, cal)
            rows.append({"adaylar": lab, "yontem": vlab, **{f"{p}_{x}": v for p, t3 in st.items() for x, v in zip(("yil", "dd", "sh"), t3)}})
            print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    bot.write("research_aday.json", {"rows": df.to_dict("records")})
    pd.set_option("display.width", 220)
    print(df.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--veri", action="store_true")
    a = ap.parse_args()
    main_data() if a.veri else main()
