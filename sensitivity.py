#!/usr/bin/env python3
"""
Parametre duyarlılık (sağlamlık) analizi — optimizasyon DEĞİL.

Amaç: stratejinin sonucu birkaç makul ayar değişikliğinde tutarlı mı, yoksa
tek bir şanslı ayara mı bağlı? Bunu görmek için:
  1. Her ayar kombinasyonu için portföy backtest'i yapılır (bot.py'deki mantıkla).
  2. Dönem ikiye bölünür: ilk %70 "eğitim" (IS), son %30 "test" (OOS).
  3. Ayar YALNIZCA eğitim döneminde seçilir; test dönemindeki sonucu ayrıca raporlanır.

Kullanım:
    python3 sensitivity.py            # veriyi indirir (.cache/ altına kaydeder)
    python3 sensitivity.py --cached   # kayıtlı veriyle tekrar çalıştırır
Çıktı: sensitivity.json + konsolda tablo.
"""
from __future__ import annotations

import argparse
import itertools
import os
import pickle

import pandas as pd

import bot

GRID = {
    "buy_threshold": [30, 40, 50],   # AL eşiği
    "exit_score": [-20, 0, 20],      # pozisyondayken skor bunun altına inerse çık
    "stop_atr": [2.0, 2.5, 3.0, 4.0],  # iz süren stop mesafesi (ATR katı)
}
CACHE = os.path.join(bot.OUT_DIR, ".cache", "data.pkl")


def load(cached: bool) -> dict[str, pd.DataFrame]:
    if cached and os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    data = bot.fetch_real(list(bot.BIST30) + [bot.BENCHMARK])
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "wb") as f:
        pickle.dump(data, f)
    return data


def ann(daily: pd.Series) -> float:
    """Yıllık bileşik getiri, %."""
    eq = (1 + daily.fillna(0)).prod()
    return round((eq ** (252 / len(daily)) - 1) * 100, 1)


def main(cached: bool) -> None:
    data = load(cached)
    bench = data.pop(bot.BENCHMARK)["Close"]

    # İndikatörler ve skor ayarlardan bağımsız: bir kez hesapla
    prepared = {}
    for t in bot.BIST30:
        df = data.get(t)
        if df is None or len(df) < bot.CFG["min_bars"]:
            continue
        d = bot.add_indicators(df, bench)
        prepared[t] = (d, bot.score_frame(d)["score"], bot.cash_returns(d.index))

    base = dict(bot.CFG)
    rows = []
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(GRID, combo))
        bot.CFG.update(base)
        bot.CFG.update(params)
        daily, trades, held = {}, 0, 0
        for t, (d, sc, cash_d) in prepared.items():
            bt = bot.backtest(d, sc, cash_d)
            daily[t] = bt["daily"]
            trades += len(bt["trades"])
            held += sum(x["days"] for x in bt["trades"]) + (bt["open"]["days"] if bt["open"] else 0)
        port_df = pd.DataFrame(daily)
        cash = bot.cash_returns(port_df.index)
        port = port_df.apply(lambda col: col.fillna(cash)).mean(axis=1)
        split = int(len(port) * (1 - bot.CFG["oos_fraction"]))
        full = bot.metrics(port, rf=cash)
        rows.append({
            **params,
            "total_pct": full["total_return_pct"],
            "max_dd_pct": full["max_drawdown_pct"],
            "is_cagr": ann(port.iloc[:split]),
            "oos_cagr": ann(port.iloc[split:]),
            "is_sharpe": bot.metrics(port.iloc[:split], rf=cash)["sharpe"],
            "oos_sharpe": bot.metrics(port.iloc[split:], rf=cash)["sharpe"],
            "oos_dd": bot.metrics(port.iloc[split:])["max_drawdown_pct"],
            "trades_per_stock": round(trades / len(prepared), 1),
            "exposure_pct": round(held / sum(len(v[0]) - bot.CFG["warmup_days"] for v in prepared.values()) * 100, 1),
        })
    bot.CFG.update(base)

    # Kıyaslar (ayarlardan bağımsız)
    idx = port.index
    cash = bot.cash_returns(idx)
    b = bench.reindex(idx).ffill().pct_change().fillna(0)
    split = int(len(idx) * (1 - bot.CFG["oos_fraction"]))
    refs = {
        "XU030 al-tut": {"is_cagr": ann(b.iloc[:split]), "oos_cagr": ann(b.iloc[split:]),
                         "is_sharpe": bot.metrics(b.iloc[:split], rf=cash)["sharpe"],
                         "oos_sharpe": bot.metrics(b.iloc[split:], rf=cash)["sharpe"],
                         "oos_dd": bot.metrics(b.iloc[split:])["max_drawdown_pct"]},
        "Nakit (faiz)": {"is_cagr": ann(cash.iloc[:split]), "oos_cagr": ann(cash.iloc[split:])},
    }

    res = pd.DataFrame(rows)
    best_is = res.sort_values("is_sharpe", ascending=False).iloc[0].to_dict()
    current = res[(res.buy_threshold == base["buy_threshold"]) & (res.exit_score == base["exit_score"])
                  & (res.stop_atr == base["stop_atr"])].iloc[0].to_dict()
    summary = {
        "period": {"start": str(idx[0].date()), "oos_start": str(idx[split].date()), "end": str(idx[-1].date())},
        "grid": GRID,
        "references": refs,
        "current": current,
        "best_in_sample": best_is,
        "oos_cagr_range": [float(res.oos_cagr.min()), float(res.oos_cagr.median()), float(res.oos_cagr.max())],
        "oos_beats_index": int((res.oos_cagr > refs["XU030 al-tut"]["oos_cagr"]).sum()),
        "oos_beats_cash": int((res.oos_cagr > refs["Nakit (faiz)"]["oos_cagr"]).sum()),
        "rank_corr_is_oos": round(float(res.is_sharpe.rank().corr(res.oos_sharpe.rank())), 2),
        "rows": rows,
    }
    bot.write("sensitivity.json", summary)

    pd.set_option("display.width", 200)
    print(res.sort_values("is_sharpe", ascending=False).to_string(index=False))
    print("\nKıyas:", refs)
    print("Mevcut ayar:", current)
    print("Eğitimde en iyi:", best_is)
    for k in ("oos_cagr_range", "oos_beats_index", "oos_beats_cash", "rank_corr_is_oos"):
        print(k, summary[k], f"/ {len(res)}" if k.startswith("oos_beats") else "")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BIST30 botu parametre duyarlılık analizi")
    ap.add_argument("--cached", action="store_true", help=".cache/ altındaki kayıtlı veriyi kullan")
    main(ap.parse_args().cached)
