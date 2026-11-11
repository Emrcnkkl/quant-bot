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


class TestDegerlemeKaydi(unittest.TestCase):
    def test_yalnizca_eklenir(self):
        items = [{"ticker": "BBB", "close": 10, "pe": 5.0, "pb": None}, {"ticker": "AAA", "close": 2, "pe": None}]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "v.csv")
            self.assertTrue(bot.append_valuation_history(items, "2026-11-09", p))
            before = open(p, encoding="utf-8").read()
            # Aynı gün ya da daha eski gün tekrar yazılmaz, mevcut satırlar değişmez
            self.assertFalse(bot.append_valuation_history([{"ticker": "AAA", "close": 99}], "2026-11-09", p))
            self.assertFalse(bot.append_valuation_history(items, "2026-11-06", p))
            self.assertEqual(open(p, encoding="utf-8").read(), before)
            self.assertTrue(bot.append_valuation_history(items, "2026-11-10", p))
            lines = open(p, encoding="utf-8").read().splitlines()
            self.assertEqual(lines[0].split(",")[:3], ["date", "ticker", "close"])
            self.assertEqual(len(lines), 5)
            self.assertTrue(lines[1].startswith("2026-11-09,AAA,2,"))
            self.assertTrue("".join(open(p, encoding="utf-8").read()).startswith(before))


class TestResmiKaynak(unittest.TestCase):
    def _df(self, dates, close):
        return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0},
                            index=pd.DatetimeIndex(dates))

    def test_bulten_eksik_gunu_tamamlar_ve_hatayi_duzeltir(self):
        d1, d2 = pd.Timestamp("2026-11-06"), pd.Timestamp("2026-11-09")
        data = {"AAA": self._df([d1], [10.0]),               # Yahoo'da son gün yok
                "BBB": self._df([d1, d2], [20.0, 21.0]),     # Yahoo son gün yanlış (21 ≠ 22)
                "CCC": self._df([d1, d2], [30.0, 31.0]),     # doğru
                bot.BENCHMARK: self._df([d1], [100.0])}      # endeks bültende yok, dokunulmaz
        b = pd.DataFrame({"Open": [10.5, 21.5, 30.5], "High": [11.2, 22.4, 31.5], "Low": [10.1, 21.0, 30.0],
                          "Close": [11.0, 22.0, 31.0], "Volume": [5.0, 6.0, 7.0], "PrevClose": [10.0, 20.0, 30.0]},
                         index=["AAA", "BBB", "CCC"])
        bot.OFFICIAL.clear(); bot.MISMATCH.clear(); bot.PATCHED.clear()
        bot.official_fill(data, bulletins={d2: b})
        self.assertEqual(data["AAA"].index[-1], d2)
        self.assertEqual(data["AAA"]["Close"].iloc[-1], 11.0)
        self.assertEqual(data["AAA"]["Open"].iloc[-1], 10.5)
        self.assertEqual(data["BBB"]["Close"].iloc[-1], 22.0)
        self.assertEqual(len(data["BBB"]), 2)
        self.assertEqual(data["CCC"]["Volume"].iloc[-1], 1.0)        # fark yoksa Yahoo kalır
        self.assertEqual(data[bot.BENCHMARK].index[-1], d1)
        self.assertEqual([m.split()[0] for m in bot.MISMATCH], ["BBB"])
        self.assertEqual(bot.OFFICIAL, {"AAA", "BBB"})

    def test_bilanco_verisiyle_fk(self):
        sig = [{"ticker": "AAA", "name": "A", "close": 10.0, "signal": "TUT"}]
        fund = {"AAA": {"net_ttm": 50.0, "equity": 200.0, "currency": "USD", "eps": 99, "book": 99,
                        "fin_period": "2026/09"}}
        it = bot.valuation(sig, fund, {"USD": 40.0}, shares={"AAA": 100.0})["items"][0]
        self.assertEqual(it["pe"], 20.0)        # 1000 / 50
        self.assertEqual(it["pb"], 5.0)         # 1000 / 200
        self.assertEqual(it["source"], "isyatirim")
        self.assertFalse(it["fx_converted"])


class TestTakvim(unittest.TestCase):
    def test_takvim_suzme_ve_gruplama(self):
        disc = [
            {"publishDate": "05.11.2026 18:30:00", "stockCodes": "AAA", "kapTitle": "A A.Ş.", "disclosureClass": "FR",
             "subject": "Finansal Rapor", "year": 2026, "ruleType": "9 Aylık", "disclosureIndex": 1},
            {"publishDate": "05.11.2026 18:31:00", "stockCodes": "AAA", "kapTitle": "A A.Ş.", "disclosureClass": "FR",
             "subject": "Finansal Rapor", "year": 2026, "ruleType": "9 Aylık", "disclosureIndex": 2},   # aynı dönem: tek
            {"publishDate": "06.11.2026 09:00:00", "stockCodes": "BBB", "kapTitle": "B A.Ş.", "disclosureClass": "ODA",
             "subject": "Payların Geri Alınmasına İlişkin Bildirim", "summary": "Pay Geri Alım İşlemleri", "disclosureIndex": 3},
            {"publishDate": "06.11.2026 10:00:00", "stockCodes": "BBB", "kapTitle": "B A.Ş.", "disclosureClass": "ODA",
             "subject": "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", "summary": "Kâr payı", "disclosureIndex": 4},
            {"publishDate": "06.11.2026 11:00:00", "stockCodes": "ZZZ", "kapTitle": "Z A.Ş.", "disclosureClass": "ODA",
             "subject": "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", "summary": "evren dışı", "disclosureIndex": 5}]
        exp = [{"kapTitle": "B A.Ş.", "stockCode": None, "ruleTypeTerm": "9 Aylık", "endDate": "30.11.2026", "year": 2026,
                "subject": "Finansal Rapor"}]
        cal = bot.build_calendar(["AAA", "BBB"], pd.Timestamp("2026-11-10"), disclosures=disc, expected=exp,
                                 ppk=["2026-12-10", "2025-01-01"])
        kinds = [(e["kind"], e.get("ticker"), e["title"]) for e in cal["events"]]
        self.assertEqual(sum(k == "bilanco" for k, _, _ in kinds), 1)
        self.assertIn(("kap", "BBB", "Temettü"), kinds)
        self.assertNotIn("Geri alım", [t for _, _, t in kinds])          # günlük geri alım raporu gösterilmez
        self.assertNotIn("ZZZ", [t for _, t, _ in kinds])
        self.assertIn(("sonbilanco", "BBB", "Bilanço için son gün"), kinds)  # şirket adıyla eşlendi
        self.assertIn(("ppk", None, "TCMB faiz kararı"), kinds)
        self.assertEqual([e["date"] for e in cal["events"] if e["kind"] == "tufe"][:3], ["2026-11-03", "2026-12-03", "2027-01-04"])
        self.assertEqual(cal["events"], sorted(cal["events"], key=lambda e: (e["date"], e.get("time", ""))))

    def test_enflasyon_gunu_hafta_sonu_kayar(self):
        d = bot.cpi_release_dates(pd.Timestamp("2027-01-01"), pd.Timestamp("2027-01-31"))
        self.assertEqual([str(x.date()) for x in d], ["2027-01-04"])   # 3 Ocak 2027 pazar → pazartesi


class TestPanel(unittest.TestCase):
    def test_piyasa_degisimleri(self):
        import panel
        idx = pd.bdate_range("2025-01-01", "2026-11-11")
        c = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
        st = panel.series_stats(c, 2, "pct")
        self.assertEqual(st["last"], 200.0)
        self.assertAlmostEqual(st["chg"], (200 / c.iloc[-2] - 1) * 100, places=2)
        ref = c[c.index <= pd.Timestamp("2025-12-31")].iloc[-1]
        self.assertAlmostEqual(st["chgytd"], (200 / ref - 1) * 100, places=2)   # yıl başı = önceki yılın son kapanışı
        self.assertEqual(len(st["spark"]), 66)
        self.assertEqual(len(st["hist"]["d"]), len(st["hist"]["c"]))
        t = panel.series_stats(pd.Series([4.0, 4.5], index=idx[-2:]).reindex(idx).bfill(), 2, "bp")
        self.assertEqual(t["chg"], 0.5)                                           # faizde puan farkı


class TestHaberVeHalkaArz(unittest.TestCase):
    def test_rss_ayrisma_ve_suzme(self):
        import panel
        now = pd.Timestamp.now(tz="UTC")
        rss = ("<rss><channel>"
               f"<item><title><![CDATA[Merkez Bankası faizi sabit tuttu]]></title><link>https://a.example/1</link><pubDate>{now:%a, %d %b %Y %H:%M:%S} +0000</pubDate></item>"
               f"<item><title>Merkez Bankası faizi sabit tuttu</title><link>https://a.example/2</link><pubDate>{now:%a, %d %b %Y %H:%M:%S} +0000</pubDate></item>"
               f"<item><title>Şans Topu sonuçları açıklandı</title><link>https://a.example/3</link><pubDate>{now:%a, %d %b %Y %H:%M:%S} +0000</pubDate></item>"
               "<item><title>Eski haber: dolar rekor kırdı</title><link>https://a.example/4</link><pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate></item>"
               "</channel></rss>").encode()
        old_http, old_feeds = bot._http, panel.NEWS_FEEDS
        try:
            bot._http = lambda url, timeout=30: rss
            panel.NEWS_FEEDS = [("Deneme", "https://a.example/rss")]
            out = panel.fetch_news()
        finally:
            bot._http, panel.NEWS_FEEDS = old_http, old_feeds
        self.assertEqual([x["title"] for x in out["items"]], ["Merkez Bankası faizi sabit tuttu"])   # tekrar, piyango ve eski haber yok
        self.assertIn("Faiz", out["items"][0]["cats"])

    def test_halka_arz_yeni_kod_eklenir(self):
        import panel
        def bul(codes):
            return pd.DataFrame({"Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 11.0, "Volume": 1.0, "PrevClose": 10.0,
                                 "TLVolume": 1e7, "Name": "ORNEK"}, index=codes)
        base = [f"K{i:03d}" for i in range(120)]
        days = {pd.Timestamp("2026-11-10"): bul(base), pd.Timestamp("2026-11-11"): bul(base + ["YENI"])}
        old = bot.fetch_bulletin
        try:
            bot.fetch_bulletin = lambda d: days.get(pd.Timestamp(d).normalize())
            st = {"last_date": "2026-11-10", "known": base, "ipos": []}
            new = panel.update_ipo_state(st, pd.Timestamp("2026-11-11"))
            again = panel.update_ipo_state(new, pd.Timestamp("2026-11-11"))
        finally:
            bot.fetch_bulletin = old
        self.assertEqual([x["t"] for x in new["ipos"]], ["YENI"])
        self.assertEqual(new["ipos"][0]["first_day"], "2026-11-11")
        self.assertEqual(new["ipos"][0]["first_open"], 10.0)
        self.assertEqual(again["ipos"], new["ipos"])                                    # tekrar çalıştırmada değişmez

    def test_halka_arz_ilk_kurulum_tatillerle_biter(self):
        import panel
        def bul(codes):
            return pd.DataFrame({"Open": 5.0, "High": 5.5, "Low": 5.0, "Close": 5.5, "Volume": 1.0, "PrevClose": float("nan"),
                                 "TLVolume": 1e7, "Name": "ORNEK"}, index=codes)
        base = [f"K{i:03d}" for i in range(120)]
        cal = pd.bdate_range("2026-09-01", "2026-11-11")
        holidays = set(cal[30:45]) | set(cal[-4:-1])        # uzun tatil + son günlerden hemen önce boşluk
        first = {"AAA": cal[10], "BBB": cal[46], "CCC": cal[-1]}
        def fake(d):
            d = pd.Timestamp(d).normalize()
            if d not in set(cal) or d in holidays:
                return None
            return bul(base + [t for t, f in first.items() if d >= f])
        old = bot.fetch_bulletin
        try:
            bot.fetch_bulletin = fake
            panel._codes_only.__globals__["bot"].fetch_bulletin = fake
            orig_codes = panel._codes_only
            panel._codes_only = lambda day, cache: (None if fake(day) is None else set(fake(day).index))
            st = panel.update_ipo_state(None, pd.Timestamp("2026-11-11"), back_days=75)
        finally:
            bot.fetch_bulletin = old
            panel._codes_only = orig_codes
        self.assertEqual({x["t"]: x["first_day"] for x in st["ipos"]},
                         {t: str(f.date()) for t, f in first.items()})


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
