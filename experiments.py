#!/usr/bin/env python3
"""
Kural deneyleri: "kaç hisse al-bekle'yi geçiyor?" sorusuna farklı giriş/çıkış kurallarıyla bakar.

Kural setleri sonuçlara bakılmadan, önceden belirlendi (aşağıdaki VARIANTS).
Her set için dönem ikiye bölünür: ilk %70 eğitim (IS), son %30 test (OOS).
Karar yalnızca eğitim sonuçlarına göre verilmeli; test sonucu, kararın tutup tutmadığını gösterir.

Kullanım:
    python3 experiments.py            # veriyi .cache/ altından okur (yoksa indirir)
Çıktı: experiments.json + konsolda tablo.
"""
from __future__ import annotations

import pandas as pd

import bot
import sensitivity

# (ad, açıklama, CFG değişiklikleri)
VARIANTS = [
    ("mevcut", "Skor ≥40 gir, skor <0 çık, 2.5 ATR stop", {}),
    ("gevsek", "Skor <−20 çık, 4 ATR stop", {"exit_score": -20, "stop_atr": 4.0}),
    ("sat_cik", "Yalnızca SAT'ta (skor <−40) çık, stop yok", {"exit_score": -40, "stop_atr": None}),
    ("ema50", "Kapanış EMA50 altına inince çık, stop yok", {"exit_rule": "ema50", "stop_atr": None}),
    ("kesisim", "EMA20 EMA50 altına inince çık, stop yok", {"exit_rule": "cross", "stop_atr": None}),
    ("kesisim_stop", "EMA20<EMA50 çık + 4 ATR stop", {"exit_rule": "cross", "stop_atr": 4.0}),
    ("ema200", "Kapanış EMA200 altına inince çık, stop yok", {"exit_rule": "ema200", "stop_atr": None}),
    ("rejim", "Endeks yükselişteyken EMA20<EMA50 çık, değilse skor <0 + 2.5 ATR stop", {"exit_rule": "regime"}),
    ("klasik200", "Klasik: EMA200 üstü gir, altı çık (skor yok)",
     {"entry_rule": "ema200", "exit_rule": "ema200", "stop_atr": None}),
]


def comp(r: pd.Series) -> float:
    """Günlük getiri serisinden toplam getiri (%)."""
    return float(((1 + r.fillna(0)).prod() - 1) * 100)


def ann(r: pd.Series) -> float:
    return float(((1 + r.fillna(0)).prod() ** (252 / max(len(r), 1)) - 1) * 100)


def main() -> None:
    data = sensitivity.load(cached=True)
    bench = data.pop(bot.BENCHMARK)["Close"]
    prepared = {}
    for t in bot.BIST30:
        df = data.get(t)
        if df is None or len(df) < bot.CFG["min_bars"]:
            continue
        d = bot.add_indicators(df, bench)
        prepared[t] = (d, bot.score_frame(d)["score"], bot.cash_returns(d.index))

    base = dict(bot.CFG)
    # Ortak bölme tarihi: portföy takvimine göre
    idx = pd.DatetimeIndex(sorted(set().union(*[v[0].index[base["warmup_days"]:] for v in prepared.values()])))
    split_date = idx[int(len(idx) * (1 - base["oos_fraction"]))]
    cash_all = bot.cash_returns(idx)
    b = bench.reindex(idx).ffill().pct_change().fillna(0)

    rows, per_stock = [], {}
    for name, desc, over in VARIANTS:
        bot.CFG.clear()
        bot.CFG.update(base)
        bot.CFG.update(over)
        daily, beat, n_tr, held, days = {}, {"is": 0, "oos": 0, "full": 0}, 0, 0, 0
        ps = {}
        for t, (d, sc, cash_d) in prepared.items():
            bt = bot.backtest(d, sc, cash_d)
            r = bt["daily"]
            bh = d["Close"].pct_change().reindex(r.index)
            daily[t] = r
            n_tr += len(bt["trades"])
            held += sum(x["days"] for x in bt["trades"]) + (bt["open"]["days"] if bt["open"] else 0)
            days += len(r)
            res = {}
            for k, m in (("is", r.index < split_date), ("oos", r.index >= split_date), ("full", r.index == r.index)):
                s_, h_ = comp(r[m]), comp(bh[m])
                res[k] = (round(s_, 1), round(h_, 1))
                beat[k] += s_ > h_
            ps[t] = res
        per_stock[name] = ps
        port = pd.DataFrame(daily).reindex(idx)
        port = port.apply(lambda col: col.fillna(cash_all)).mean(axis=1)
        is_m, oos_m = port.index < split_date, port.index >= split_date
        rows.append({
            "kural": name, "aciklama": desc,
            "yener_egitim": beat["is"], "yener_test": beat["oos"], "yener_tum": beat["full"],
            "yillik_egitim": round(ann(port[is_m]), 1), "yillik_test": round(ann(port[oos_m]), 1),
            "maks_dusus": bot.metrics(port)["max_drawdown_pct"],
            "test_dusus": bot.metrics(port[oos_m])["max_drawdown_pct"],
            "piyasada_pct": round(held / days * 100, 1), "islem_hisse": round(n_tr / len(prepared), 1),
        })
    bot.CFG.clear()
    bot.CFG.update(base)

    refs = {"XU030 al-bekle": {"yillik_egitim": round(ann(b[idx < split_date]), 1),
                               "yillik_test": round(ann(b[idx >= split_date]), 1),
                               "maks_dusus": bot.metrics(b)["max_drawdown_pct"],
                               "test_dusus": bot.metrics(b[idx >= split_date])["max_drawdown_pct"]},
            "Faiz": {"yillik_egitim": round(ann(cash_all[idx < split_date]), 1),
                     "yillik_test": round(ann(cash_all[idx >= split_date]), 1)}}
    out = {"n_stocks": len(prepared), "period": {"start": str(idx[0].date()), "oos_start": str(split_date.date()),
                                                  "end": str(idx[-1].date())},
           "variants": rows, "references": refs, "per_stock": per_stock}
    bot.write("experiments.json", out)

    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).drop(columns="aciklama").to_string(index=False))
    print("\n", refs, "\nhisse sayısı:", len(prepared), "· test başlangıcı:", split_date.date())


if __name__ == "__main__":
    main()
