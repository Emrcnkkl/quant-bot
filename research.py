#!/usr/bin/env python3
"""
Uzun dönem araştırması (2005–bugün) ve kayan pencereli (walk-forward) test.

Sorular:
  1. Mevcut strateji 20 yıllık veride, farklı piyasa dönemlerinde nasıl davranıyor?
  2. "En güçlüleri seç" (rotasyon) stratejisi işe yarıyor mu?
  3. Her yıl başında yalnızca o güne kadarki veriye bakarak kural seçseydik ne olurdu?

Kıyaslar: XU030 (gerçek endeks), faiz, bugünkü 30 hisseye eşit ağırlıklı al-bekle
(bu sonuncusu "bugünkü listeyle test etme" yanlılığının büyüklüğünü gösterir).

Kullanım:
    python3 research.py            # .cache/long.pkl yoksa veriyi indirir
    python3 research.py --refresh  # veriyi yeniden indir
Çıktı: research.json + konsolda tablolar.
"""
from __future__ import annotations

import argparse
import os
import pickle

import numpy as np
import pandas as pd

import bot

START = "2005-01-04"          # 1 Ocak 2005'te TL'den 6 sıfır atıldı; öncesi eski TL
JUMP = 0.25                   # günlük fiyat sınırının çok üstündeki sıçramalar veri hatası sayılır
CACHE = os.path.join(bot.OUT_DIR, ".cache", "long.pkl")
COST = bot.CFG["commission"] + bot.CFG["slippage"]
FIRST_WF_YEAR = 2009          # kayan pencerede ilk seçim yılı (öncesi 3 yıl öğrenme verisi)


# --------------------------------------------------------------------------- #
#  Veri
# --------------------------------------------------------------------------- #
def load(refresh: bool) -> dict[str, pd.DataFrame]:
    if not refresh and os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            data = pickle.load(f)
    else:
        import yfinance as yf
        data = {}
        for t in list(bot.BIST30) + [bot.BENCHMARK]:
            raw = yf.download(f"{t}.IS", start="2004-01-01", interval="1d", auto_adjust=True,
                              progress=False, threads=False)
            if raw is not None and not raw.empty:
                data[t] = bot._clean(raw)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "wb") as f:
            pickle.dump(data, f)
    return fix(data)


def fix(data: dict[str, pd.DataFrame], quiet: bool = False) -> dict[str, pd.DataFrame]:
    """bot.fix_jumps ile aynı (2005 öncesini at, veri hatası sıçramalarını nötrle)."""
    return bot.fix_jumps(data, START, quiet)


WIDE = os.path.join(bot.OUT_DIR, ".cache", "wide.pkl")


def pit_membership(data: dict[str, pd.DataFrame], cal: pd.DatetimeIndex, n: int = 30) -> pd.DataFrame:
    """bot.pit_membership ile aynı (her çeyrek önceki 3 ayın işlem hacmine göre ilk n)."""
    return bot.pit_membership(data, cal, n)


# --------------------------------------------------------------------------- #
#  Stratejiler
# --------------------------------------------------------------------------- #
def slot_strategy(prep, cal, cash, over: dict, mem: pd.DataFrame | None = None) -> pd.Series:
    """Mevcut yapı: her hisseye 1/30 pay, bot.backtest kurallarıyla; boş pay faizde.
    `mem` verilirse hisseye yalnızca evrendeyken girilir ve portföy o günün evren üyelerinden oluşur."""
    base = dict(bot.CFG)
    bot.CFG.update(over)
    try:
        cols = {t: bot.backtest(d, sc, cash.reindex(d.index).fillna(0),
                                entry_mask=None if mem is None else mem[t])["daily"] for t, (d, sc) in prep.items()}
    finally:
        bot.CFG.clear()
        bot.CFG.update(base)
    df = pd.DataFrame(cols).reindex(cal)
    if mem is not None:
        # 30 pay: o günün evren üyeleri kendi strateji getirisini, boş paylar faizi kazanır.
        # Yaklaşıklık: evrenden çıkan hissedeki pozisyon maliyetsiz kapanmış sayılır.
        M = mem.reindex(index=cal, columns=df.columns).fillna(False)
        filled = df.apply(lambda c: c.fillna(cash))
        return (filled.where(M).sum(axis=1) + (30 - M.sum(axis=1)).clip(lower=0) * cash) / 30
    df = df.apply(lambda c: c.fillna(cash))
    # Bugünkü listede olup henüz işlem görmeyen hisselerin payı da faizde (30 pay)
    missing = len(bot.BIST30) - df.shape[1]
    return (df.sum(axis=1) + missing * cash) / len(bot.BIST30)


def rotation(R, key, eligible, cash, n: int) -> pd.Series:
    """
    En güçlüleri seç: her cuma kapanışında `key`e göre en yüksek `n` uygun hisse seçilir,
    her birine 1/n ağırlık verilir (uygun hisse azsa kalan pay faizde).
    İşlem ertesi işlem gününün kapanışında yapılır (1 gün gecikme, ileriye bakma yok).
    """
    cal = R.index
    fri = pd.Series(cal, index=cal)
    rebal = fri.groupby(fri.dt.to_period("W-FRI")).transform("max") == fri   # haftanın son işlem günü
    target = pd.DataFrame(np.nan, index=cal, columns=R.columns)
    k = key.where(eligible)
    for day in cal[rebal.to_numpy()]:
        row = k.loc[day].dropna()
        w = pd.Series(0.0, index=R.columns)
        if len(row):
            w[row.nlargest(n).index] = 1.0 / n
        target.loc[day] = w
    # Sinyal günü s → işlem s+1 kapanışında → getiriye s+2'den itibaren etki
    W = target.shift(1).ffill().fillna(0.0)
    turnover = W.diff().abs().sum(axis=1).fillna(W.abs().sum(axis=1))
    eff = W.shift(1).fillna(0.0)
    r = (eff * R.fillna(0)).sum(axis=1) + (1 - eff.sum(axis=1)) * cash - turnover * COST
    return r


# --------------------------------------------------------------------------- #
#  Ölçüm
# --------------------------------------------------------------------------- #
def yearly(r: pd.Series) -> pd.Series:
    return (r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1) * 100).round(1)


def summary(r: pd.Series, cash: pd.Series) -> dict:
    m = bot.metrics(r, rf=cash)
    return {"cagr": m["cagr_pct"], "max_dd": m["max_drawdown_pct"], "sharpe": m["sharpe"], "total": m["total_return_pct"]}


def walk_forward(series: dict[str, pd.Series], cash: pd.Series) -> tuple[pd.Series, dict]:
    """Her yıl başında, o güne kadarki tüm veride (faizin üstünde) Sharpe'ı en yüksek kuralı seç, o yıl uygula."""
    years = sorted(set(cash.index.year))
    out, picks = [], {}
    for y in years:
        if y < FIRST_WF_YEAR:
            continue
        past = cash.index.year < y
        best = max(series, key=lambda k: bot.metrics(series[k][past], rf=cash[past])["sharpe"])
        picks[y] = best
        out.append(series[best][cash.index.year == y])
    return pd.concat(out), picks


def main(refresh: bool) -> None:
    bot.fetch_macro()
    data = load(refresh)
    bench = data.pop(bot.BENCHMARK)
    cal = bench.index[bot.CFG["warmup_days"]:]
    cash = bot.cash_returns(cal)
    b = bench["Close"].reindex(cal).pct_change().fillna(0)

    prep, closes, scores, mom = {}, {}, {}, {}
    for t, df in data.items():
        if len(df) < bot.CFG["min_bars"]:
            continue
        d = bot.add_indicators(df, bench["Close"])
        sc = bot.score_frame(d)["score"]
        prep[t] = (d, sc)
        closes[t] = d["Close"]
        # Yeterli geçmişi olmayan günlerde skor/momentum kullanılmaz
        ok = pd.Series(np.arange(len(d)) >= bot.CFG["min_bars"], index=d.index)
        scores[t] = sc.where(ok)
        mom[t] = (d["Close"].shift(21) / d["Close"].shift(252) - 1).where(ok)   # 12-1 ay momentum
    C = pd.DataFrame(closes).reindex(cal)
    R = C.pct_change()
    SC = pd.DataFrame(scores).reindex(cal)
    MO = pd.DataFrame(mom).reindex(cal)
    listed = C.notna() & C.shift(1).notna()

    strategies = {
        "mevcut": slot_strategy(prep, cal, cash, {}),
        "kesisim": slot_strategy(prep, cal, cash, {"exit_rule": "cross", "stop_atr": None}),
        "rot_skor_5": rotation(R, SC, listed & (SC >= 40), cash, 5),
        "rot_skor_8": rotation(R, SC, listed & (SC >= 40), cash, 8),
        "rot_skor0_5": rotation(R, SC, listed & (SC >= 0), cash, 5),
        "rot_mom_5": rotation(R, MO, listed & (MO > 0), cash, 5),
        "rot_mom_8": rotation(R, MO, listed & (MO > 0), cash, 8),
    }
    refs = {
        "XU030": b,
        "faiz": cash,
        "esit_30_al_bekle": (R.where(listed).mean(axis=1)).fillna(0),
    }
    wf, picks = walk_forward(strategies, cash)

    allser = {**strategies, "kayan_secim": wf, **refs}
    ytab = pd.DataFrame({k: yearly(v) for k, v in allser.items()})
    wf_idx = wf.index
    summ = {k: {"tum": summary(v, cash), "wf_donemi": summary(v.reindex(wf_idx).fillna(0), cash.reindex(wf_idx))}
            for k, v in allser.items()}
    beat = {k: int((ytab[k] > ytab["XU030"]).loc[ytab.index >= FIRST_WF_YEAR].sum()) for k in allser}
    beat_cash = {k: int((ytab[k] > ytab["faiz"]).loc[ytab.index >= FIRST_WF_YEAR].sum()) for k in allser}

    bot.write("research.json", {
        "period": {"start": str(cal[0].date()), "end": str(cal[-1].date()), "wf_start": FIRST_WF_YEAR},
        "n_stocks": len(prep), "yearly": {str(y): row.dropna().to_dict() for y, row in ytab.iterrows()},
        "summary": summ, "wf_picks": picks, "years_beat_index": beat, "years_beat_cash": beat_cash,
    })
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print("\nYıllık getiri (%):")
    print(ytab.to_string())
    n_years = int((ytab.index >= FIRST_WF_YEAR).sum())
    print(f"\nÖzet ({FIRST_WF_YEAR}–{cal[-1].year}, {n_years} yıl):")
    rows = [{"strateji": k, **s["wf_donemi"], "endeksi_gecen_yil": beat[k], "faizi_gecen_yil": beat_cash[k]}
            for k, s in summ.items()]
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nKayan pencere seçimleri:", picks)


def sized(prep, cal, cash, mem, over: dict, mult: float, vol: bool, cap: float = 2.0) -> tuple[pd.Series, pd.Series]:
    """bot.sized_portfolio ile aynı; `over` ile CFG geçici olarak değiştirilebilir."""
    base = dict(bot.CFG)
    bot.CFG.update(over)
    try:
        port, expo, _ = bot.sized_portfolio(prep, cal, cash, mem, mult, vol, cap)
    finally:
        bot.CFG.clear()
        bot.CFG.update(base)
    return port, expo


def main_sizing() -> None:
    """Pozisyon büyüklüğü deneyleri (noktasal evren)."""
    bot.fetch_macro()
    data, bench, cal, cash, mem, prep = pit_setup()
    b = bench["Close"].reindex(cal).pct_change().fillna(0)
    C = pd.DataFrame({t: d["Close"] for t, (d, _) in prep.items()}).reindex(cal)
    R = C.pct_change()
    ew = R.where(C.notna() & C.shift(1).notna() & mem).mean(axis=1).fillna(0)
    yrs = cal.year
    IS, OOS = (yrs >= FIRST_WF_YEAR) & (yrs <= 2020), yrs >= 2021
    ALL = yrs >= FIRST_WF_YEAR

    def stats(r, mask):
        m = bot.metrics(r[mask], rf=cash[mask])
        return m["cagr_pct"], m["max_drawdown_pct"], m["sharpe"]

    rows = []
    variants = [(m_, v) for v in (False, True) for m_ in (1.0, 1.5, 2.0, 3.0)]
    series = {}
    for m_, v in variants:
        name = f"{'oynaklik_' if v else ''}{m_:g}x"
        r, e = sized(prep, cal, cash, mem, {}, m_, v)
        series[name] = r
        rows.append({"cesit": name, "ort_hisse_payi": round(float(e[ALL].mean()) * 100),
                     **{f"{k}_{lab}": val for lab, msk in (("egitim", IS), ("test", OOS), ("tum", ALL))
                        for k, val in zip(("yillik", "dusus", "sharpe"), stats(r, msk))}})
    for name, r in (("evren_al_bekle", ew), ("XU030", b), ("faiz", cash)):
        series[name] = r
        rows.append({"cesit": name, "ort_hisse_payi": 100 if name != "faiz" else 0,
                     **{f"{k}_{lab}": val for lab, msk in (("egitim", IS), ("test", OOS), ("tum", ALL))
                        for k, val in zip(("yillik", "dusus", "sharpe"), stats(r, msk))}})
    df = pd.DataFrame(rows)
    # Önceden belirlenen karar kuralı: eğitimde düşüşü evren al-bekle'den derin olmayanlar arasında en yüksek yıllık getiri
    lim = df.loc[df.cesit == "evren_al_bekle", "dusus_egitim"].iloc[0]
    cand = df[(df.cesit.str.contains("x")) & (df.dusus_egitim >= lim)]
    pick = cand.sort_values("yillik_egitim", ascending=False).iloc[0]["cesit"]
    ytab = pd.DataFrame({k: yearly(v) for k, v in series.items()})
    bot.write("research_sizing.json", {"rows": rows, "pick": pick, "dd_limit_is": lim,
                                       "yearly": {str(y): r.dropna().to_dict() for y, r in ytab.iterrows()}})
    pd.set_option("display.width", 250)
    print(df.to_string(index=False))
    print(f"\nKarar kuralı (eğitim düşüşü ≥ {lim}% olanlar içinde en yüksek eğitim getirisi): {pick}")
    print(ytab.loc[FIRST_WF_YEAR:, [pick, "1x", "evren_al_bekle", "XU030", "faiz"]].to_string())


def main_faiz() -> None:
    """Reel faiz filtresi, 2006–bugün, noktasal evren + oynaklık ayarlı pozisyon (botun portföy testiyle aynı)."""
    bot.fetch_macro()
    data, bench, cal, cash, mem, prep = pit_setup()
    cal = cal[cal >= pd.Timestamp(bot.CFG["backtest_start"])]
    cash, mem = cash.reindex(cal), mem.reindex(cal)
    b = bench["Close"].reindex(cal).pct_change().fillna(0)
    periods = {"2006-08": (2006, 2008), "2009-17": (2009, 2017), "2018-20": (2018, 2020),
               "2021-24": (2021, 2024), "2025-26": (2025, 2026), "egitim_06-20": (2006, 2020),
               "test_21-26": (2021, 2026), "tum": (2006, 2026)}
    variants = {"filtre_yok": None, "esik_0": 0.0, "esik_+2.5": 2.5, "esik_+5": 5.0, "esik_+7.5": 7.5, "esik_+10": 10.0}
    rows, series = [], {}
    for name, lim in variants.items():
        r, e = sized(prep, cal, cash, mem, {"real_rate_max": lim}, 1.0, True)
        series[name] = (r, e)
    series["XU030"] = (b, pd.Series(1.0, index=cal))
    for name, (r, e) in series.items():
        row = {"cesit": name}
        for pn, (a_, z) in periods.items():
            m = (cal.year >= a_) & (cal.year <= z)
            met = bot.metrics(r[m], rf=cash[m])
            row[f"{pn}_yil"], row[f"{pn}_dd"], row[f"{pn}_sh"] = met["cagr_pct"], met["max_drawdown_pct"], met["sharpe"]
        row["hisse_payi"] = round(float(e.mean()) * 100)
        rows.append(row)
    df = pd.DataFrame(rows).set_index("cesit")
    bot.write("research_faiz.json", {"rows": df.reset_index().to_dict("records"),
                                     "yearly": {k: yearly(v[0]).to_dict() for k, v in series.items()}})
    pd.set_option("display.width", 250)
    for kind, lab in (("yil", "Yıllık getiri %"), ("dd", "En büyük düşüş %"), ("sh", "Sharpe (faiz üstü)")):
        print(f"\n{lab}:")
        print(df[[c for c in df.columns if c.endswith("_" + kind)]].rename(columns=lambda c: c.rsplit("_", 1)[0]).to_string())
    print("\nOrtalama hisse payı %:", df["hisse_payi"].to_dict())


def pit_setup():
    with open(WIDE, "rb") as f:
        wide = fix(pickle.load(f), quiet=True)
    with open(CACHE, "rb") as f:
        bench = fix(pickle.load(f), quiet=True)[bot.BENCHMARK]
    data = bot.dedupe(wide)
    cal = bench.index[bot.CFG["warmup_days"]:]
    cash = bot.cash_returns(cal)
    mem = pit_membership(data, bench.index).reindex(cal).fillna(False)
    prep = {}
    for t, df in data.items():
        if len(df) < bot.CFG["min_bars"] or not mem[t].any():
            continue
        d = bot.add_indicators(df, bench["Close"])
        prep[t] = (d, bot.score_frame(d)["score"])
    return data, bench, cal, cash, mem[list(prep)], prep


def main_pit() -> None:
    """Noktasal evrenle aynı testler: her çeyrek, o zamanki en likit 30 hisse."""
    bot.fetch_macro()
    with open(WIDE, "rb") as f:
        wide = fix(pickle.load(f), quiet=True)
    with open(CACHE, "rb") as f:
        bench = fix(pickle.load(f), quiet=True)[bot.BENCHMARK]
    # Aynı seriyi iki farklı kodla tutan kayıtları ayıkla (yeniden adlandırılan şirketler)
    seen, data = {}, {}
    for t, df in sorted(wide.items()):
        key = (str(df.index[0].date()), round(float(df["Close"].iloc[-1]), 4), len(df))
        if key not in seen:
            seen[key] = t
            data[t] = df
    cal = bench.index[bot.CFG["warmup_days"]:]
    cash = bot.cash_returns(cal)
    b = bench["Close"].reindex(cal).pct_change().fillna(0)
    mem = pit_membership(data, bench.index).reindex(cal).fillna(False)

    prep, closes, scores, mom = {}, {}, {}, {}
    for t, df in data.items():
        if len(df) < bot.CFG["min_bars"] or not mem[t].any():
            continue
        d = bot.add_indicators(df, bench["Close"])
        sc = bot.score_frame(d)["score"]
        prep[t] = (d, sc)
        closes[t] = d["Close"]
        ok = pd.Series(np.arange(len(d)) >= bot.CFG["min_bars"], index=d.index)
        scores[t] = sc.where(ok)
        mom[t] = (d["Close"].shift(21) / d["Close"].shift(252) - 1).where(ok)
    mem = mem[list(prep)]
    C = pd.DataFrame(closes).reindex(cal)
    R = C.pct_change()
    SC = pd.DataFrame(scores).reindex(cal)
    MO = pd.DataFrame(mom).reindex(cal)
    listed = C.notna() & C.shift(1).notna() & mem

    # Evrenin eşit ağırlıklı al-bekle'si (her gün o günün üyeleri)
    ew = R.where(listed).mean(axis=1).fillna(0)
    strategies = {
        "mevcut": slot_strategy(prep, cal, cash, {}, mem),
        "kesisim": slot_strategy(prep, cal, cash, {"exit_rule": "cross", "stop_atr": None}, mem),
        "rot_skor_8": rotation(R, SC, listed & (SC >= 40), cash, 8),
        "rot_mom_5": rotation(R, MO, listed & (MO > 0), cash, 5),
        "rot_mom_8": rotation(R, MO, listed & (MO > 0), cash, 8),
        "rot_mom_10": rotation(R, MO, listed & (MO > 0), cash, 10),
    }
    refs = {"XU030": b, "faiz": cash, "evren_esit_al_bekle": ew}
    wf, picks = walk_forward(strategies, cash)
    allser = {**strategies, "kayan_secim": wf, **refs}
    ytab = pd.DataFrame({k: yearly(v) for k, v in allser.items()})
    wf_idx = wf.index
    summ = {k: summary(v.reindex(wf_idx).fillna(0), cash.reindex(wf_idx)) for k, v in allser.items()}
    sel = ytab.index >= FIRST_WF_YEAR
    beat = {k: int((ytab[k] > ytab["XU030"])[sel].sum()) for k in allser}
    beat_ew = {k: int((ytab[k] > ytab["evren_esit_al_bekle"])[sel].sum()) for k in allser}
    beat_cash = {k: int((ytab[k] > ytab["faiz"])[sel].sum()) for k in allser}
    # Evren istatistikleri
    turnover = (mem.astype(int).diff().abs().sum(axis=1) / 2)
    q_changes = turnover[turnover > 0]
    bot.write("research_pit.json", {
        "period": {"start": str(cal[0].date()), "end": str(cal[-1].date()), "wf_start": FIRST_WF_YEAR},
        "n_candidates": len(data), "n_ever_member": len(prep),
        "avg_quarterly_changes": round(float(q_changes.mean()), 1),
        "current_members": sorted(mem.columns[mem.iloc[-1]].tolist()),
        "yearly": {str(y): row.dropna().to_dict() for y, row in ytab.iterrows()},
        "summary": summ, "wf_picks": picks,
        "years_beat_index": beat, "years_beat_universe": beat_ew, "years_beat_cash": beat_cash,
    })
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    print(f"\nAday: {len(data)} · en az bir kez evrende: {len(prep)} · çeyrek başına ortalama değişen hisse: {q_changes.mean():.1f}")
    cur = set(mem.columns[mem.iloc[-1]]); real = set(bot.BIST30)
    print(f"Bugünkü evren ile gerçek BIST30 kesişimi: {len(cur & real)}/30 · fazla: {sorted(cur - real)} · eksik: {sorted(real - cur)}")
    print("\nYıllık getiri (%):")
    print(ytab.to_string())
    print(f"\nÖzet ({FIRST_WF_YEAR}–{cal[-1].year}):")
    print(pd.DataFrame([{"strateji": k, **v, "endeksi_gecen": beat[k], "evreni_gecen": beat_ew[k], "faizi_gecen": beat_cash[k]}
                        for k, v in summ.items()]).to_string(index=False))
    print("\nKayan pencere seçimleri:", picks)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--pit", action="store_true", help="noktasal (o dönemin en likit 30 hissesi) evrenle test")
    ap.add_argument("--sizing", action="store_true", help="pozisyon büyüklüğü deneyleri (noktasal evren)")
    ap.add_argument("--faiz", action="store_true", help="reel faiz filtresi, 2006–bugün")
    a = ap.parse_args()
    if a.faiz:
        main_faiz()
    else:
        main_sizing() if a.sizing else main_pit() if a.pit else main(a.refresh)
