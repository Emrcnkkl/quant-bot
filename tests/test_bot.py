"""
Botun temel hesaplarını kontrol eden testler. İnternet gerektirmez.
Çalıştırma:  python3 -m unittest discover -s tests -v
"""
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402


def demo_stock(n=600, seed=1):
    return bot.fetch_demo(["AAA"])["AAA"].iloc[-n:]


class TestHesaplar(unittest.TestCase):
    def test_nakit_faizi_yillik_oran(self):
        # Yıl boyu sabit %38 politika faizi ≈ %38 yıllık getiri vermeli
        idx = pd.bdate_range("2026-01-01", "2026-12-31")
        r = (1 + bot.cash_returns(idx)).prod() - 1
        self.assertAlmostEqual(r, 0.38 * 364 / 365, delta=0.02)

    def test_metrikler(self):
        r = pd.Series([0.01] * 252)
        m = bot.metrics(r)
        self.assertAlmostEqual(m["total_return_pct"], (1.01 ** 252 - 1) * 100, places=0)
        self.assertEqual(m["max_drawdown_pct"], 0.0)

    def test_puan_araligi(self):
        d = bot.add_indicators(demo_stock(), None)
        sc = bot.score_frame(d)["score"]
        self.assertLessEqual(sc.max(), 100.01)
        self.assertGreaterEqual(sc.min(), -100.01)
        self.assertEqual(set(bot.ACTIVE) <= set(bot.score_frame(d).columns), True)

    def test_ileriye_bakma_yok(self):
        # Sinyal t kapanışında oluşur; işlem en erken t+1'de olmalı
        d = bot.add_indicators(demo_stock(), None)
        sc = pd.Series(-100.0, index=d.index)
        t = d.index[300]
        sc.loc[t] = 100.0
        old = bot.CFG["real_rate_max"]
        bot.CFG["real_rate_max"] = None      # faiz filtresi bu testi etkilemesin
        try:
            bt = bot.backtest(d, sc, None)
        finally:
            bot.CFG["real_rate_max"] = old
        first_held = bt["held"][bt["held"]].index
        self.assertTrue(len(first_held) > 0)
        self.assertGreater(first_held[0], t)

    def test_veri_hatasi_duzeltme(self):
        idx = pd.bdate_range("2010-01-01", periods=10)
        df = pd.DataFrame({"Open": 10.0, "High": 10.0, "Low": 10.0, "Close": 10.0, "Volume": 100.0}, index=idx)
        df.iloc[5:, :4] = 40.0          # düzeltilmemiş sermaye artırımı gibi 4 kat sıçrama
        out = bot.fix_jumps({"X": df}, start="2010-01-01")["X"]
        self.assertAlmostEqual(out["Close"].pct_change().abs().max(), 0.0)

    def test_evren_buyuklugu(self):
        idx = pd.bdate_range("2015-01-01", periods=700)
        data = {f"T{i}": pd.DataFrame({"Close": 10.0, "Volume": float(i + 1)}, index=idx) for i in range(80)}
        mem = bot.pit_membership(data, idx, 50, 252)
        self.assertEqual(int(mem.iloc[-1].sum()), 50)
        self.assertTrue(mem.iloc[-1]["T79"])          # en yüksek hacim
        self.assertFalse(mem.iloc[-1]["T0"])

    def test_faiz_filtresi_alimi_engeller(self):
        d = bot.add_indicators(demo_stock(), None)
        sc = pd.Series(100.0, index=d.index)
        old = bot.CFG["real_rate_max"]
        try:
            bot.CFG["real_rate_max"] = -1000.0     # her gün "reel faiz eşiğin üstünde"
            bt = bot.backtest(d, sc, None)
            self.assertEqual(len(bt["trades"]), 0)
            self.assertFalse(bt["held"].any())
        finally:
            bot.CFG["real_rate_max"] = old


class TestUcuzluk(unittest.TestCase):
    def test_dolar_raporlayan_sirket_kurla_cevrilir(self):
        sig = [{"ticker": "AAA", "name": "A", "close": 310.0, "signal": "TUT"}]
        fund = {"AAA": {"eps": 2.0, "book": 16.85, "currency": "USD", "sector": "Industrials"}}
        v = bot.valuation(sig, fund, 50.0)["items"][0]
        # Yahoo özsermayeyi zaten TL vermişse (çevirince PD/DD saçma küçük olur) çevrilmez
        fund2 = {"AAA": {"eps": 20.0, "book": 200.0, "currency": "USD"}}
        self.assertAlmostEqual(bot.valuation(sig, fund2, 50.0)["items"][0]["pb"], 310 / 200, places=2)
        self.assertAlmostEqual(v["pb"], 310 / (16.85 * 50), places=2)
        self.assertAlmostEqual(v["pe"], 310 / (2.0 * 50), places=2)

    def test_zarar_eden_sirketin_fk_si_yok_ve_ucuz_olan_yuksek_puan(self):
        sig = [{"ticker": t, "name": t, "close": 100.0, "signal": "TUT"} for t in "ABCDE"]
        fund = {"A": {"eps": 20, "book": 200}, "B": {"eps": 10, "book": 100}, "C": {"eps": 5, "book": 50},
                "D": {"eps": 2, "book": 20}, "E": {"eps": -1, "book": 10}}
        items = {i["ticker"]: i for i in bot.valuation(sig, fund, None)["items"]}
        self.assertIsNone(items["E"]["pe"])
        self.assertTrue(items["E"]["loss"])
        self.assertGreater(items["A"]["score"], items["D"]["score"])   # A en düşük F/K ve PD/DD -> en ucuz


class TestCanliPortfoy(unittest.TestCase):
    def test_gecmis_kayitlar_degismez(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = bot.OUT_DIR
            bot.OUT_DIR = tmp
            try:
                idx = pd.bdate_range("2026-11-02", periods=3)
                port = pd.Series([0.01, 0.02, -0.01], index=idx)
                w = pd.DataFrame({"AAA": [0.1, 0.1, 0.0]}, index=idx)
                bench = pd.Series([100.0, 101.0, 102.0], index=idx)
                bot.update_live(port.iloc[:1], w.iloc[:1], bench, demo=False)
                first = json.load(open(os.path.join(tmp, "live.json")))["points"][0]
                # Sonraki gün, geçmiş getiri "değişmiş" olsa bile ilk kayıt aynı kalmalı
                port2 = port.copy()
                port2.iloc[0] = 0.5
                live = bot.update_live(port2, w, bench, demo=False)
                self.assertEqual(live["points"][0], first)
                self.assertEqual(len(live["points"]), 3)
                self.assertAlmostEqual(live["points"][-1]["value"], 100000 * 1.02 * 0.99, places=2)
            finally:
                bot.OUT_DIR = old


class TestUcuncuUc(unittest.TestCase):
    def test_demo_calistirma_gecerli_json(self):
        """Demo çalıştırma tüm dosyaları NaN içermeden yazmalı."""
        with tempfile.TemporaryDirectory() as tmp:
            old = bot.OUT_DIR
            bot.OUT_DIR = tmp
            try:
                bot.run(demo=True)
                for name in ("signals.json", "backtest.json"):
                    with open(os.path.join(tmp, name), encoding="utf-8") as f:
                        txt = f.read()
                    self.assertNotIn("NaN", txt)
                    json.loads(txt)
                s = json.load(open(os.path.join(tmp, "signals.json")))
                self.assertTrue(s["demo"])
                self.assertGreater(len(s["signals"]), 0)
            finally:
                bot.OUT_DIR = old


if __name__ == "__main__":
    unittest.main()
