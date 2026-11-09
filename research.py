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
    """2005 öncesini at; günlük fiyat sınırının çok üstündeki sıçramaları (düzeltilmemiş sermaye artırımı) nötrle."""
    fixed = {}
    for t, df in data.items():
        df = df.loc[START:].copy()
        df["Volume"] = df["Volume"].astype(float)
        if len(df) < 2:
            continue
        r = df["Close"].pct_change()
        for day in r.index[r.abs() > JUMP]:
            # Sıçramadan önceki tüm fiyatları ölçekle: o günkü getiri 0 olur
            k = df.loc[day, "Close"] / df["Close"].shift(1).loc[day]
            cols = ["Open", "High", "Low", "Close"]
            df.loc[df.index < day, cols] *= k
            df.loc[df.index < day, "Volume"] /= k
            if not quiet:
                print(f"  düzeltildi: {t} {day.date()} ({(k - 1) * 100:+.0f}%)")
        fixed[t] = df
    return fixed


WIDE = os.path.join(bot.OUT_DIR, ".cache", "wide.pkl")


def pit_membership(data: dict[str, pd.DataFrame], cal: pd.DatetimeIndex, n: int = 30) -> pd.DataFrame:
    """
    Noktasal (point-in-time) evren: her çeyrek başında, önceki 3 ayın ortalama işlem hacmine (TL) göre
    en büyük `n` hisse o çeyreğin evrenidir. Yalnızca o güne kadarki veri kullanılır.
    """
    tv = pd.DataFrame({t: (df["Close"] * df["Volume"]) for t, df in data.items()}).reindex(cal)
    avg = tv.rolling(63, min_periods=40).mean().shift(1)
    age = tv.notna().cumsum()
    mem = pd.DataFrame(False, index=cal, columns=tv.columns)
    q = pd.Series(cal, index=cal).dt.to_period("Q")
    starts = q[q != q.shift(1)].index
    for i, day in enumerate(starts):
        row = avg.loc[day].where(age.loc[day] >= 126).dropna()
        top = row.nlargest(n).index
        end = starts[i + 1] if i + 1 < len(starts) else cal[-1] + pd.Timedelta(days=1)
        mem.loc[(cal >= day) & (cal < end), top] = True
    return mem


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
    a = ap.parse_args()
    main_pit() if a.pit else main(a.refresh)
