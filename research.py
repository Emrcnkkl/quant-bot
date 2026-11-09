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
    fixed = {}
    for t, df in data.items():
        df = df.loc[START:].copy()
        r = df["Close"].pct_change()
        for day in r.index[r.abs() > JUMP]:
            # Sıçramadan önceki tüm fiyatları ölçekle: o günkü getiri 0 olur
            k = df.loc[day, "Close"] / df["Close"].shift(1).loc[day]
            cols = ["Open", "High", "Low", "Close"]
            df.loc[df.index < day, cols] *= k
            print(f"  düzeltildi: {t} {day.date()} ({(k - 1) * 100:+.0f}%)")
        fixed[t] = df
    return fixed


# --------------------------------------------------------------------------- #
#  Stratejiler
# --------------------------------------------------------------------------- #
def slot_strategy(prep, cal, cash, over: dict) -> pd.Series:
    """Mevcut yapı: her hisseye 1/30 pay, bot.backtest kurallarıyla; boş pay faizde."""
    base = dict(bot.CFG)
    bot.CFG.update(over)
    try:
        cols = {t: bot.backtest(d, sc, cash.reindex(d.index).fillna(0))["daily"] for t, (d, sc) in prep.items()}
    finally:
        bot.CFG.clear()
        bot.CFG.update(base)
    df = pd.DataFrame(cols).reindex(cal)
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    main(ap.parse_args().refresh)
