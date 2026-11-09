#!/usr/bin/env python3
"""
BIST30 Teknik Analiz Sinyal Botu  (Aşama 1)
-------------------------------------------
- Günlük veri (yfinance, .IS uzantılı semboller)
- Çoklu indikatör skoru  (-100 ... +100)
    Trend      : EMA200, EMA20/EMA50, ADX/DI
    Momentum   : RSI14, MACD histogram
    Hacim      : 20 günlük ortalamaya göre hacim
    Kırılım    : 20 günlük en yüksek / en düşük
    Göreli güç : XU030 endeksine göre 3 aylık getiri farkı
- Sinyal     : skor >= +40 -> AL,  skor <= -40 -> SAT,  arası -> TUT
- Risk       : ATR tabanlı stop (2.5 ATR) ve hedef (4 ATR)
- Backtest   : sadece long, sinyal kapanışta oluşur, ERTESİ GÜN AÇILIŞTA işlem,
               komisyon + kayma dahil, ATR iz süren stop, örneklem dışı (OOS) dönem ayrı

Çıktılar (aynı klasöre):
    signals.json   -> güncel sinyaller (web sayfası okur)
    backtest.json  -> geçmiş performans raporu
    history.json   -> günlük sinyal geçmişi (her çalıştırmada eklenir)

Kullanım:
    pip install -r requirements.txt
    python bot.py            # gerçek veri (internet gerekir)
    python bot.py --demo     # sentetik veri ile test (internet gerekmez)

UYARI: Bu yazılımın ürettiği çıktılar yatırım tavsiyesi değildir.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
#  AYARLAR
# --------------------------------------------------------------------------- #
# BIST 30 bileşenleri: 1 Ekim - 31 Aralık 2026 dönemi (TRMET girdi, DSTKF çıktı)
# Her çeyrek başında Borsa İstanbul duyurusuna göre güncelleyin.
BIST30 = {
    "AEFES": "Anadolu Efes", "AKBNK": "Akbank", "ASELS": "Aselsan",
    "ASTOR": "Astor Enerji", "BIMAS": "BİM Mağazalar", "EKGYO": "Emlak Konut GYO",
    "ENKAI": "Enka İnşaat", "EREGL": "Ereğli Demir Çelik", "FROTO": "Ford Otosan",
    "GARAN": "Garanti BBVA", "GUBRF": "Gübre Fabrikaları", "ISCTR": "İş Bankası (C)",
    "KCHOL": "Koç Holding", "KRDMD": "Kardemir (D)", "MGROS": "Migros",
    "PETKM": "Petkim", "PGSUS": "Pegasus", "SAHOL": "Sabancı Holding",
    "SASA": "SASA Polyester", "SISE": "Şişecam", "TAVHL": "TAV Havalimanları",
    "TCELL": "Turkcell", "THYAO": "Türk Hava Yolları", "TOASO": "Tofaş",
    "TRALT": "Türk Altın İşletmeleri", "TRMET": "TR Anadolu Metal Madencilik",
    "TTKOM": "Türk Telekom", "TUPRS": "Tüpraş", "VAKBN": "VakıfBank",
    "YKBNK": "Yapı Kredi",
}
BENCHMARK = "XU030"   # Yahoo'da XU050 geçmişi yok; kıyas endeksi BIST30 (BIST50 ile çok benzer hareket eder)

# Şirket adları: BIST30 + sık listeye giren diğer büyük hisseler. Listede olmayan bir hisse evrene girerse
# adı Yahoo'dan alınır ve names.json'a kaydedilir (company_name).
NAMES = {
    **BIST30,
    "AKSEN": "Aksa Enerji", "ALARK": "Alarko Holding", "BJKAS": "Beşiktaş", "BRSAN": "Borusan Boru",
    "BTCIM": "Batıçim", "CCOLA": "Coca-Cola İçecek", "CRFSA": "CarrefourSA", "CWENE": "CW Enerji",
    "ENERY": "Enerya Enerji", "EUPWR": "Europower Enerji", "GESAN": "Girişim Elektrik", "HALKB": "Halkbank",
    "HEKTS": "Hektaş", "MIATK": "Mia Teknoloji", "ODAS": "Odaş Elektrik", "SELEC": "Selçuk Ecza",
    "SKBNK": "Şekerbank", "TKFEN": "Tekfen Holding", "TURSG": "Türkiye Sigorta", "ULKER": "Ülker",
    "CANTE": "Çan2 Termik", "ECILC": "Eczacıbaşı İlaç", "FENER": "Fenerbahçe", "KLRHO": "Kiler Holding",
    "KONTR": "Kontrolmatik", "OYAKC": "Oyak Çimento", "ARCLK": "Arçelik", "DOAS": "Doğuş Otomotiv",
    "OTKAR": "Otokar", "TTRAK": "Türk Traktör", "VESTL": "Vestel", "ISMEN": "İş Yatırım", "SOKM": "Şok Marketler",
    "MAVI": "Mavi Giyim", "AGHOL": "Anadolu Grubu Holding", "ENJSA": "Enerjisa", "AKSA": "Aksa Akrilik",
    "KONYA": "Konya Çimento", "CIMSA": "Çimsa", "EGEEN": "Ege Endüstri", "KORDS": "Kordsa", "ZOREN": "Zorlu Enerji",
    "SMRTG": "Smart Güneş", "GWIND": "Galata Wind", "ISGYO": "İş GYO", "TSKB": "TSKB", "ALBRK": "Albaraka Türk",
    "DOHOL": "Doğan Holding", "GLYHO": "Global Yatırım Holding", "AYGAZ": "Aygaz", "TMSN": "Tümosan",
    "KCAER": "Kocaer Çelik", "ISDMR": "İskenderun Demir Çelik", "QUAGR": "Qua Granite", "REEDR": "Reeder",
    "BERA": "Bera Holding", "CEMTS": "Çemtaş", "YYLGD": "Yayla Gıda", "GSRAY": "Galatasaray", "TSPOR": "Trabzonspor",
    "VESBE": "Vestel Beyaz Eşya", "BRYAT": "Borusan Yatırım", "AKSUE": "Akdeniz Su", "PASEU": "Pasifik Eurasia",
}

# Geriye dönük test için aday hisseler: bugünkü BIST100'ün büyük kısmı + geçmişte BIST30'da olmuş ve hâlâ
# Yahoo'da verisi bulunan hisseler. Her çeyrek bunların arasından işlem hacmine göre en büyük 30'u seçilir
# (noktasal evren) — bugünkü listeyle test etmenin "hayatta kalma yanlılığı"nı büyük ölçüde giderir.
# Borsadan çıkmış hisselerin (Finansbank, Petrol Ofisi, Trakya Cam...) Yahoo'da verisi yok.
CANDIDATES = """
    AEFES AFYON AGHOL AKBNK AKCNS AKENR AKFGY AKGRT AKMGY AKSA AKSEN ALARK ALBRK ALCTL ALFAS ALGYO
    ALKIM ANHYT ANSGR ARCLK ASELS ASTOR ASUZU AVOD AYDEM AYGAZ BAGFS BANVT BERA BIMAS BIOEN BIZIM
    BJKAS BRISA BRSAN BRYAT BTCIM BUCIM CANTE CCOLA CEMTS CIMSA CLEBI CRFSA CWENE DEVA DOAS DOGUB
    DOHOL DYOBY ECILC ECZYT EGEEN EKGYO EMKEL ENERY ENJSA ENKAI EREGL EUPWR EUREN FENER FORTE FROTO
    GARAN GENIL GESAN GLYHO GOODY GOZDE GSDHO GSRAY GUBRF GWIND HALKB HEKTS HURGZ IHEVA IHLAS INDES
    ISCTR ISDMR ISFIN ISGYO ISMEN IZMDC KARSN KARTN KCAER KCHOL KLRHO KONTR KONYA KORDS KRDMD KRSTL
    LOGO MAVI MGROS MIATK MPARK NETAS NTHOL NUHCM ODAS OTKAR OYAKC PARSN PETKM PGSUS PRKME QUAGR
    RAYSG REEDR SAHOL SARKY SASA SELEC SISE SKBNK SKTAS SMRTG SNGYO SOKM TATGD TAVHL TCELL THYAO
    TKFEN TKNSA TMSN TOASO TRALT TRCAS TRGYO TRMET TSKB TSPOR TTKOM TTRAK TUKAS TUPRS TURSG ULKER
    VAKBN VAKKO VERUS VESBE VESTL VKGYO YATAS YKBNK YUNSA YYLGD ZOREN ZRGYO
""".split()

CFG = {
    "history_start": "2004-01-01",  # indirilecek verinin başlangıcı (2005 öncesi eski TL, atılır)
    "backtest_start": "2006-01-01", # portföy testinin başlangıcı (2008 krizi dahil)
    "universe_size": 50,        # sinyal ve test evreni: her çeyrek işlem hacmine göre en büyük N hisse ("BIST50 benzeri")
    "universe_window": 252,     # hacim ortalaması penceresi (gün); 12 ay -> kısa süreli spekülatif hacim listeye sokmaz
    "vol_sizing": True,         # oynaklığa göre pozisyon büyüklüğü (docs/uzun-donem-arastirma.md)
    "vol_cap": 2.0,             # bir pozisyon en fazla temel payın bu katı olabilir
    "jump_limit": 0.25,         # tek günde bundan büyük fiyat sıçraması veri hatası sayılır
    "warmup_days": 210,         # EMA200 için ısınma
    "buy_threshold": 40,        # skor >= bu -> AL
    "sell_threshold": -40,      # skor <= bu -> SAT
    "exit_score": 0,            # pozisyondayken skor bunun altına inerse çık
    "stop_atr": 2.5,            # iz süren stop mesafesi (ATR katı)
    "target_atr": 4.0,          # bilgi amaçlı hedef (ATR katı)
    "commission": 0.0010,       # tek yön komisyon (%0.10)
    "slippage": 0.0005,         # tek yön kayma (%0.05)
    "oos_fraction": 0.30,       # son %30'luk dönem örneklem dışı olarak raporlanır
    "min_bars": 260,
    "cash_rate_factor": 1.0,    # nakit getirisi = politika faizi × bu katsayı (0 -> faiz yok)
    "real_rate_max": 5.0,       # reel faiz %5'in üstündeyken yeni alım yok (docs/uzun-donem-arastirma.md, 20 yıl testi)
    "changes_days": 30,
    # Çıkış kuralı: "score" = skor < exit_score | "ema50" = kapanış < EMA50 |
    #               "cross" = EMA20 < EMA50 | "ema200" = kapanış < EMA200 |
    #               "regime" = endeks EMA200 üstündeyken "cross", altındayken "score"
    "exit_rule": "score",
    # Giriş kuralı: "score" = skor >= buy_threshold | "ema200" = kapanış > EMA200 (klasik 200 gün kuralı, kıyas için)
    "entry_rule": "score",         # sinyal geçmişi listesi: son kaç işlem günündeki değişiklikler      # reel faiz (politika − yıllık TÜFE) bunun üstündeyse yeni alım yok; None = filtre kapalı
}

# TCMB politika faizi, yıllık %. (yürürlük tarihi, oran)
# 20 Mayıs 2010 öncesi: gecelik (O/N) borç alma faizi (o dönemin politika faizi) — sabit, değişmez.
# Sonrası: bir hafta vadeli repo (borç verme).
# Kaynak: tcmb.gov.tr → Merkez Bankası Faiz Oranları → 1 Hafta Repo.
# Bot her gerçek çalıştırmada bu tabloyu TCMB sitesinden günceller (fetch_macro);
# siteye ulaşılamazsa aşağıdaki yerleşik tablo kullanılır.
POLICY_RATES_PRE2010 = [
    ("2003-10-15", 26.00), ("2004-02-05", 24.00), ("2004-03-17", 22.00),
    ("2004-09-08", 20.00), ("2004-12-20", 18.00), ("2005-01-11", 17.00),
    ("2005-02-09", 16.50), ("2005-03-09", 15.50), ("2005-04-11", 15.00),
    ("2005-05-10", 14.50), ("2005-06-09", 14.25), ("2005-10-11", 14.00),
    ("2005-11-09", 13.75), ("2005-12-09", 13.50), ("2006-01-02", 13.50),
    ("2006-04-28", 13.25), ("2006-06-08", 15.00), ("2006-06-26", 17.25),
    ("2006-06-28", 17.25), ("2006-07-21", 17.50), ("2007-09-14", 17.25),
    ("2007-10-17", 16.75), ("2007-11-15", 16.25), ("2007-12-14", 15.75),
    ("2008-01-18", 15.50), ("2008-02-15", 15.25), ("2008-05-16", 15.75),
    ("2008-06-17", 16.25), ("2008-07-18", 16.75), ("2008-10-23", 16.75),
    ("2008-11-20", 16.25), ("2008-12-19", 15.00), ("2009-01-16", 13.00),
    ("2009-02-20", 11.50), ("2009-03-20", 10.50), ("2009-04-17", 9.75),
    ("2009-05-15", 9.25), ("2009-06-17", 8.75), ("2009-07-17", 8.25),
    ("2009-08-19", 7.75), ("2009-09-18", 7.25), ("2009-10-16", 6.75),
    ("2009-11-20", 6.50),
]
POLICY_RATES = POLICY_RATES_PRE2010 + [
    ("2010-05-20", 7.00), ("2010-12-17", 6.50), ("2011-01-21", 6.25),
    ("2011-08-05", 5.75), ("2012-12-19", 5.50), ("2013-04-17", 5.00),
    ("2013-05-17", 4.50), ("2014-01-29", 10.00), ("2014-05-23", 9.50),
    ("2014-06-25", 8.75), ("2014-07-18", 8.25), ("2015-01-21", 7.75),
    ("2015-02-25", 7.50), ("2016-11-25", 8.00), ("2018-06-01", 16.50),
    ("2018-06-08", 17.75), ("2018-09-14", 24.00), ("2019-07-26", 19.75),
    ("2019-09-13", 16.50), ("2019-10-25", 14.00), ("2019-12-13", 12.00),
    ("2020-01-17", 11.25), ("2020-02-20", 10.75), ("2020-03-18", 9.75),
    ("2020-04-23", 8.75), ("2020-05-22", 8.25), ("2020-09-25", 10.25),
    ("2020-11-20", 15.00), ("2020-12-25", 17.00), ("2021-03-19", 19.00),
    ("2021-09-24", 18.00), ("2021-10-22", 16.00), ("2021-11-19", 15.00),
    ("2021-12-17", 14.00), ("2022-08-19", 13.00), ("2022-09-23", 12.00),
    ("2022-10-21", 10.50), ("2022-11-25", 9.00), ("2023-02-24", 8.50),
    ("2023-06-23", 15.00), ("2023-07-21", 17.50), ("2023-08-25", 25.00),
    ("2023-09-22", 30.00), ("2023-10-27", 35.00), ("2023-11-24", 40.00),
    ("2023-12-22", 42.50), ("2024-01-26", 45.00), ("2024-03-22", 50.00),
    ("2024-12-27", 47.50), ("2025-01-24", 45.00), ("2025-03-07", 42.50),
    ("2025-04-18", 46.00), ("2025-07-25", 43.00), ("2025-09-12", 40.50),
    ("2025-10-24", 39.50), ("2025-12-12", 38.00), ("2026-01-23", 37.00),
    ("2026-10-23", 36.00),
]

# TÜİK yıllık TÜFE (%), ay -> oran. Kaynak: tcmb.gov.tr → Enflasyon Verileri → Tüketici Fiyatları.
# Veri ayın bitiminden ~3 gün sonra açıklanır; ileriye bakmamak için her ay verisi
# bir sonraki ayın 5'inden itibaren kullanılır. fetch_macro() bu tabloyu da günceller.
CPI_YOY = {
    "2005-01": 9.24, "2005-02": 8.69, "2005-03": 7.94, "2005-04": 8.18, "2005-05": 8.70, "2005-06": 8.95,
    "2005-07": 7.82, "2005-08": 7.91, "2005-09": 7.99, "2005-10": 7.52, "2005-11": 7.61, "2005-12": 7.72,
    "2006-01": 7.93, "2006-02": 8.15, "2006-03": 8.16, "2006-04": 8.83, "2006-05": 9.86, "2006-06": 10.12,
    "2006-07": 11.69, "2006-08": 10.26, "2006-09": 10.55, "2006-10": 9.98, "2006-11": 9.86, "2006-12": 9.65,
    "2007-01": 9.93, "2007-02": 10.16, "2007-03": 10.86, "2007-04": 10.72, "2007-05": 9.23, "2007-06": 8.60,
    "2007-07": 6.90, "2007-08": 7.39, "2007-09": 7.12, "2007-10": 7.70, "2007-11": 8.40, "2007-12": 8.39,
    "2008-01": 8.17, "2008-02": 9.10, "2008-03": 9.15, "2008-04": 9.66, "2008-05": 10.74, "2008-06": 10.61,
    "2008-07": 12.06, "2008-08": 11.77, "2008-09": 11.13, "2008-10": 11.99, "2008-11": 10.76, "2008-12": 10.06,
    "2009-01": 9.50, "2009-02": 7.73, "2009-03": 7.89, "2009-04": 6.13, "2009-05": 5.24, "2009-06": 5.73,
    "2009-07": 5.39, "2009-08": 5.33, "2009-09": 5.27, "2009-10": 5.08, "2009-11": 5.53, "2009-12": 6.53,
    "2010-01": 8.19, "2010-02": 10.13, "2010-03": 9.56, "2010-04": 10.19, "2010-05": 9.10, "2010-06": 8.37,
    "2010-07": 7.58, "2010-08": 8.33, "2010-09": 9.24, "2010-10": 8.62, "2010-11": 7.29, "2010-12": 6.40,
    "2011-01": 4.90, "2011-02": 4.16, "2011-03": 3.99, "2011-04": 4.26, "2011-05": 7.17, "2011-06": 6.24,
    "2011-07": 6.31, "2011-08": 6.65, "2011-09": 6.15, "2011-10": 7.66, "2011-11": 9.48, "2011-12": 10.45,
    "2012-01": 10.61, "2012-02": 10.43, "2012-03": 10.43, "2012-04": 11.14, "2012-05": 8.28, "2012-06": 8.87,
    "2012-07": 9.07, "2012-08": 8.88, "2012-09": 9.19, "2012-10": 7.80, "2012-11": 6.37, "2012-12": 6.16,
    "2013-01": 7.31, "2013-02": 7.03, "2013-03": 7.29, "2013-04": 6.13, "2013-05": 6.51, "2013-06": 8.30,
    "2013-07": 8.88, "2013-08": 8.17, "2013-09": 7.88, "2013-10": 7.71, "2013-11": 7.32, "2013-12": 7.40,
    "2014-01": 7.75, "2014-02": 7.89, "2014-03": 8.39, "2014-04": 9.38, "2014-05": 9.66, "2014-06": 9.16,
    "2014-07": 9.32, "2014-08": 9.54, "2014-09": 8.86, "2014-10": 8.96, "2014-11": 9.15, "2014-12": 8.17,
    "2015-01": 7.24, "2015-02": 7.55, "2015-03": 7.61, "2015-04": 7.91, "2015-05": 8.09, "2015-06": 7.20,
    "2015-07": 6.81, "2015-08": 7.14, "2015-09": 7.95, "2015-10": 7.58, "2015-11": 8.10, "2015-12": 8.81,
    "2016-01": 9.58, "2016-02": 8.78, "2016-03": 7.46, "2016-04": 6.57, "2016-05": 6.58, "2016-06": 7.64,
    "2016-07": 8.79, "2016-08": 8.05, "2016-09": 7.28, "2016-10": 7.16, "2016-11": 7.00, "2016-12": 8.53,
    "2017-01": 9.22, "2017-02": 10.13, "2017-03": 11.29, "2017-04": 11.87, "2017-05": 11.72, "2017-06": 10.90,
    "2017-07": 9.79, "2017-08": 10.68, "2017-09": 11.20, "2017-10": 11.90, "2017-11": 12.98, "2017-12": 11.92,
    "2018-01": 10.35, "2018-02": 10.26, "2018-03": 10.23, "2018-04": 10.85, "2018-05": 12.15, "2018-06": 15.39,
    "2018-07": 15.85, "2018-08": 17.90, "2018-09": 24.52, "2018-10": 25.24, "2018-11": 21.62, "2018-12": 20.30,
    "2019-01": 20.35, "2019-02": 19.67, "2019-03": 19.71, "2019-04": 19.50, "2019-05": 18.71, "2019-06": 15.72,
    "2019-07": 16.65, "2019-08": 15.01, "2019-09": 9.26, "2019-10": 8.55, "2019-11": 10.56, "2019-12": 11.84,
    "2020-01": 12.15, "2020-02": 12.37, "2020-03": 11.86, "2020-04": 10.94, "2020-05": 11.39, "2020-06": 12.62,
    "2020-07": 11.76, "2020-08": 11.77, "2020-09": 11.75, "2020-10": 11.89, "2020-11": 14.03, "2020-12": 14.60,
    "2021-01": 14.97, "2021-02": 15.61, "2021-03": 16.19, "2021-04": 17.14, "2021-05": 16.59, "2021-06": 17.53,
    "2021-07": 18.95, "2021-08": 19.25, "2021-09": 19.58, "2021-10": 19.89, "2021-11": 21.31, "2021-12": 36.08,
    "2022-01": 48.69, "2022-02": 54.44, "2022-03": 61.14, "2022-04": 69.97, "2022-05": 73.50, "2022-06": 78.62,
    "2022-07": 79.60, "2022-08": 80.21, "2022-09": 83.45, "2022-10": 85.51, "2022-11": 84.39, "2022-12": 64.27,
    "2023-01": 57.68, "2023-02": 55.18, "2023-03": 50.51, "2023-04": 43.68, "2023-05": 39.59, "2023-06": 38.21,
    "2023-07": 47.83, "2023-08": 58.94, "2023-09": 61.53, "2023-10": 61.36, "2023-11": 61.98, "2023-12": 64.77,
    "2024-01": 64.86, "2024-02": 67.07, "2024-03": 68.50, "2024-04": 69.80, "2024-05": 75.45, "2024-06": 71.60,
    "2024-07": 61.78, "2024-08": 51.97, "2024-09": 49.38, "2024-10": 48.58, "2024-11": 47.09, "2024-12": 44.38,
    "2025-01": 42.12, "2025-02": 39.05, "2025-03": 38.10, "2025-04": 37.86, "2025-05": 35.41, "2025-06": 35.05,
    "2025-07": 33.52, "2025-08": 32.95, "2025-09": 33.29, "2025-10": 32.87, "2025-11": 31.07, "2025-12": 30.89,
    "2026-01": 30.65, "2026-02": 31.53, "2026-03": 30.87, "2026-04": 32.37, "2026-05": 32.61, "2026-06": 32.11,
    "2026-07": 31.75, "2026-08": 31.51, "2026-09": 29.73, "2026-10": 29.77,
}
# Aylık TÜFE değişimi (%), ay -> oran: getirileri enflasyondan arındırmak için (fiyat endeksi buradan kurulur)
CPI_MOM = {
    "2005-01": 0.55, "2005-02": 0.02, "2005-03": 0.26, "2005-04": 0.71, "2005-05": 0.92, "2005-06": 0.10,
    "2005-07": -0.57, "2005-08": 0.85, "2005-09": 1.02, "2005-10": 1.79, "2005-11": 1.40, "2005-12": 0.42,
    "2006-01": 0.75, "2006-02": 0.22, "2006-03": 0.27, "2006-04": 1.34, "2006-05": 1.88, "2006-06": 0.34,
    "2006-07": 0.85, "2006-08": -0.44, "2006-09": 1.29, "2006-10": 1.27, "2006-11": 1.29, "2006-12": 0.23,
    "2007-01": 1.00, "2007-02": 0.43, "2007-03": 0.92, "2007-04": 1.21, "2007-05": 0.50, "2007-06": -0.24,
    "2007-07": -0.73, "2007-08": 0.02, "2007-09": 1.03, "2007-10": 1.81, "2007-11": 1.95, "2007-12": 0.22,
    "2008-01": 0.80, "2008-02": 1.29, "2008-03": 0.96, "2008-04": 1.68, "2008-05": 1.49, "2008-06": -0.36,
    "2008-07": 0.58, "2008-08": -0.24, "2008-09": 0.45, "2008-10": 2.60, "2008-11": 0.83, "2008-12": -0.41,
    "2009-01": 0.29, "2009-02": -0.34, "2009-03": 1.10, "2009-04": 0.02, "2009-05": 0.64, "2009-06": 0.11,
    "2009-07": 0.25, "2009-08": -0.30, "2009-09": 0.39, "2009-10": 2.41, "2009-11": 1.27, "2009-12": 0.53,
    "2010-01": 1.85, "2010-02": 1.45, "2010-03": 0.58, "2010-04": 0.60, "2010-05": -0.36, "2010-06": -0.56,
    "2010-07": -0.48, "2010-08": 0.40, "2010-09": 1.23, "2010-10": 1.83, "2010-11": 0.03, "2010-12": -0.30,
    "2011-01": 0.41, "2011-02": 0.73, "2011-03": 0.42, "2011-04": 0.87, "2011-05": 2.42, "2011-06": -1.43,
    "2011-07": -0.41, "2011-08": 0.73, "2011-09": 0.75, "2011-10": 3.27, "2011-11": 1.73, "2011-12": 0.58,
    "2012-01": 0.56, "2012-02": 0.56, "2012-03": 0.41, "2012-04": 1.52, "2012-05": -0.21, "2012-06": -0.90,
    "2012-07": -0.23, "2012-08": 0.56, "2012-09": 1.03, "2012-10": 1.96, "2012-11": 0.38, "2012-12": 0.38,
    "2013-01": 1.65, "2013-02": 0.30, "2013-03": 0.66, "2013-04": 0.42, "2013-05": 0.15, "2013-06": 0.76,
    "2013-07": 0.31, "2013-08": -0.10, "2013-09": 0.77, "2013-10": 1.80, "2013-11": 0.01, "2013-12": 0.46,
    "2014-01": 1.98, "2014-02": 0.43, "2014-03": 1.13, "2014-04": 1.34, "2014-05": 0.40, "2014-06": 0.31,
    "2014-07": 0.45, "2014-08": 0.09, "2014-09": 0.14, "2014-10": 1.90, "2014-11": 0.18, "2014-12": -0.44,
    "2015-01": 1.10, "2015-02": 0.71, "2015-03": 1.19, "2015-04": 1.63, "2015-05": 0.56, "2015-06": -0.51,
    "2015-07": 0.09, "2015-08": 0.40, "2015-09": 0.89, "2015-10": 1.55, "2015-11": 0.67, "2015-12": 0.21,
    "2016-01": 1.82, "2016-02": -0.02, "2016-03": -0.04, "2016-04": 0.78, "2016-05": 0.58, "2016-06": 0.47,
    "2016-07": 1.16, "2016-08": -0.29, "2016-09": 0.18, "2016-10": 1.44, "2016-11": 0.52, "2016-12": 1.64,
    "2017-01": 2.46, "2017-02": 0.81, "2017-03": 1.02, "2017-04": 1.31, "2017-05": 0.45, "2017-06": -0.27,
    "2017-07": 0.15, "2017-08": 0.52, "2017-09": 0.65, "2017-10": 2.08, "2017-11": 1.49, "2017-12": 0.69,
    "2018-01": 1.02, "2018-02": 0.73, "2018-03": 0.99, "2018-04": 1.87, "2018-05": 1.62, "2018-06": 2.61,
    "2018-07": 0.55, "2018-08": 2.30, "2018-09": 6.30, "2018-10": 2.67, "2018-11": -1.44, "2018-12": -0.40,
    "2019-01": 1.06, "2019-02": 0.16, "2019-03": 1.03, "2019-04": 1.69, "2019-05": 0.95, "2019-06": 0.03,
    "2019-07": 1.36, "2019-08": 0.86, "2019-09": 0.99, "2019-10": 2.00, "2019-11": 0.38, "2019-12": 0.74,
    "2020-01": 1.35, "2020-02": 0.35, "2020-03": 0.57, "2020-04": 0.85, "2020-05": 1.36, "2020-06": 1.13,
    "2020-07": 0.58, "2020-08": 0.86, "2020-09": 0.97, "2020-10": 2.13, "2020-11": 2.30, "2020-12": 1.25,
    "2021-01": 1.68, "2021-02": 0.91, "2021-03": 1.08, "2021-04": 1.68, "2021-05": 0.89, "2021-06": 1.94,
    "2021-07": 1.80, "2021-08": 1.12, "2021-09": 1.25, "2021-10": 2.39, "2021-11": 3.51, "2021-12": 13.58,
    "2022-01": 11.10, "2022-02": 4.81, "2022-03": 5.46, "2022-04": 7.25, "2022-05": 2.98, "2022-06": 4.95,
    "2022-07": 2.37, "2022-08": 1.46, "2022-09": 3.08, "2022-10": 3.54, "2022-11": 2.88, "2022-12": 1.18,
    "2023-01": 6.65, "2023-02": 3.15, "2023-03": 2.29, "2023-04": 2.39, "2023-05": 0.04, "2023-06": 3.92,
    "2023-07": 9.49, "2023-08": 9.09, "2023-09": 4.75, "2023-10": 3.43, "2023-11": 3.28, "2023-12": 2.93,
    "2024-01": 6.70, "2024-02": 4.53, "2024-03": 3.16, "2024-04": 3.18, "2024-05": 3.37, "2024-06": 1.64,
    "2024-07": 3.23, "2024-08": 2.47, "2024-09": 2.97, "2024-10": 2.88, "2024-11": 2.24, "2024-12": 1.03,
    "2025-01": 5.03, "2025-02": 2.27, "2025-03": 2.46, "2025-04": 3.00, "2025-05": 1.53, "2025-06": 1.37,
    "2025-07": 2.06, "2025-08": 2.04, "2025-09": 3.23, "2025-10": 2.55, "2025-11": 0.87, "2025-12": 0.89,
    "2026-01": 4.84, "2026-02": 2.96, "2026-03": 1.94, "2026-04": 4.18, "2026-05": 1.71, "2026-06": 0.99,
    "2026-07": 1.78, "2026-08": 1.84, "2026-09": 1.84, "2026-10": 2.58,
}
MACRO_SOURCE = "yerleşik tablo"   # fetch_macro başarılı olursa "TCMB (canlı)" olur

TCMB = "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/"
TCMB_REPO_URL = TCMB + "Temel+Faaliyetler/Para+Politikasi/Merkez+Bankasi+Faiz+Oranlari/1+Hafta+Repo"
TCMB_CPI_URL = TCMB + "Istatistikler/Enflasyon+Verileri/Tuketici+Fiyatlari"

TR_TZ = timezone(timedelta(hours=3))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
#  VERİ
# --------------------------------------------------------------------------- #
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)[["Open", "High", "Low", "Close", "Volume"]]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[(df["Close"] > 0) & (df["Open"] > 0)]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def company_name(t: str) -> str:
    """Hisse adı: NAMES, yoksa names.json önbelleği, o da yoksa Yahoo (bir kez sorulur, önbelleğe yazılır)."""
    if t in NAMES:
        return NAMES[t]
    path = os.path.join(OUT_DIR, "names.json")
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    if t not in cache:
        name = t
        try:
            import yfinance as yf
            info = yf.Ticker(f"{t}.IS").info
            raw = info.get("longName") or info.get("shortName") or t
            name = re.sub(r"\s+(A\.?\s?[SŞ]\.?|Anonim\s+[SŞ]irketi|T\.?A\.?S\.?)\s*$", "", raw, flags=re.I).strip()
        except Exception:  # noqa: BLE001
            pass
        cache[t] = name
        write("names.json", cache, quiet=True)
    NAMES[t] = cache[t]
    return cache[t]


def fetch_real(tickers: list[str], verbose: bool = True) -> dict[str, pd.DataFrame]:
    import time

    import yfinance as yf

    data: dict[str, pd.DataFrame] = {}
    for t in tickers:
        sym = f"{t}.IS"
        for attempt in range(3):          # Yahoo ara sıra geçici hata verir
            try:
                raw = yf.download(sym, start=CFG["history_start"], interval="1d",
                                  auto_adjust=True, progress=False, threads=False)
                if raw is not None and not raw.empty:
                    data[t] = _clean(raw)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"  ! {t}: {e}", file=sys.stderr)
                time.sleep(2)
        if t not in data:
            print(f"  ! {t}: veri yok", file=sys.stderr)
        elif verbose:
            print(f"  ✓ {t}: {len(data[t])} gün, son {data[t].index[-1].date()}")
    return data


def fix_jumps(data: dict[str, pd.DataFrame], start: str = "2005-01-04", quiet: bool = True) -> dict[str, pd.DataFrame]:
    """1 Ocak 2005'te TL'den 6 sıfır atıldı: öncesini at. Günlük fiyat sınırının çok üstündeki tek günlük
    sıçramaları (Yahoo'da düzeltilmemiş sermaye artırımı) nötrle: önceki fiyatlar ölçeklenir, o günkü getiri 0 olur."""
    out = {}
    for t, df in data.items():
        df = df.loc[start:].copy()
        df["Volume"] = df["Volume"].astype(float)
        if len(df) < 2:
            continue
        r = df["Close"].pct_change()
        for day in r.index[r.abs() > CFG["jump_limit"]]:
            k = df.loc[day, "Close"] / df["Close"].shift(1).loc[day]
            df.loc[df.index < day, ["Open", "High", "Low", "Close"]] *= k
            df.loc[df.index < day, "Volume"] /= k
            if not quiet:
                print(f"  düzeltildi: {t} {day.date()} ({(k - 1) * 100:+.0f}%)")
        out[t] = df
    return out


def dedupe(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Aynı seriyi iki farklı kodla tutan kayıtları ayıkla (yeniden adlandırılan şirketler)."""
    seen, out = set(), {}
    for t in sorted(data, key=lambda x: (x not in BIST30, x)):   # bugünkü kod öncelikli
        df = data[t]
        key = (str(df.index[0].date()), round(float(df["Close"].iloc[-1]), 4), len(df))
        if key not in seen:
            seen.add(key)
            out[t] = df
    return out


def pit_membership(data: dict[str, pd.DataFrame], cal: pd.DatetimeIndex, n: int, window: int | None = None) -> pd.DataFrame:
    """Noktasal evren: her çeyrek başında, önceki 3 ayın ortalama TL işlem hacmine göre en büyük `n` hisse
    (en az 6 aylık geçmişi olanlar) o çeyreğin evrenidir. Yalnızca o güne kadarki veri kullanılır."""
    tv = pd.DataFrame({t: df["Close"] * df["Volume"] for t, df in data.items()}).reindex(cal)
    w = window or CFG.get("universe_window", 63)
    avg = tv.rolling(w, min_periods=int(w * 0.65)).mean().shift(1)
    age = tv.notna().cumsum()
    mem = pd.DataFrame(False, index=cal, columns=tv.columns)
    q = pd.Series(cal, index=cal).dt.to_period("Q")
    starts = q[q != q.shift(1)].index
    for i, day in enumerate(starts):
        top = avg.loc[day].where(age.loc[day] >= 126).dropna().nlargest(n).index
        end = starts[i + 1] if i + 1 < len(starts) else cal[-1] + pd.Timedelta(days=1)
        mem.loc[(cal >= day) & (cal < end), top] = True
    return mem


def sized_portfolio(prep: dict, cal: pd.DatetimeIndex, cash: pd.Series, mem: pd.DataFrame,
                    mult: float = 1.0, vol: bool = True, cap: float = 2.0, weights: bool = False):
    """
    Portföy: her pozisyon temel olarak sermayenin mult/N'i (N = evren büyüklüğü). Hisseye yalnızca evrendeyken girilir.
    vol=True: oynak hissede küçük, sakin hissede büyük pozisyon (temel pay × evren medyan ATR% / hissenin ATR%'si,
    1/3 ile `cap` arası). Toplam hisse payı %100'ü aşarsa hepsi orantılı küçültülür (kaldıraç yok). Boş pay faizde.
    Yaklaşıklık: ağırlıklar günlük yeniden dengelenir; evrenden çıkan hissedeki pozisyon maliyetsiz kapanmış sayılır.
    Döner: (günlük getiri, günlük hisse payı, hisse bazında backtest sonuçları[, günlük ağırlık tablosu])
    """
    n = CFG["universe_size"]
    rets, held, atrp, bts = {}, {}, {}, {}
    for t, (d, sc) in prep.items():
        bt = backtest(d, sc, cash.reindex(d.index).fillna(0), entry_mask=mem[t])
        bts[t] = bt
        rets[t], held[t] = bt["daily"], bt["held"]
        atrp[t] = (d["atr"] / d["Close"]).shift(1)
    M = mem.reindex(index=cal, columns=list(prep)).fillna(False)
    R = pd.DataFrame(rets).reindex(cal)
    H = pd.DataFrame(held).reindex(cal).fillna(False).astype(bool) & M
    Wt = H.astype(float) * mult / n
    if vol:
        A = pd.DataFrame(atrp).reindex(cal)
        med = A.where(M).median(axis=1)
        Wt = Wt * A.pow(-1).mul(med, axis=0).clip(1 / 3, cap).fillna(1)
    Wt = Wt.div(Wt.sum(axis=1).clip(lower=1), axis=0)
    expo = Wt.sum(axis=1)
    port = (Wt * R.fillna(0)).sum(axis=1) + (1 - expo) * cash
    return (port, expo, bts, Wt) if weights else (port, expo, bts)


def fetch_demo(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Rejim değiştiren sentetik fiyat serileri (sadece kod testi için)."""
    rng = np.random.default_rng(42)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1500)
    market = rng.normal(0.0006, 0.017, len(idx))
    data = {}
    for i, t in enumerate(tickers):
        r = np.random.default_rng(1000 + i)
        regime = np.repeat(r.normal(0, 0.0012, len(idx) // 60 + 1), 60)[: len(idx)]
        ret = 0.8 * market + regime + r.normal(0, 0.016, len(idx))
        close = 20 * (1 + i % 7) * np.exp(np.cumsum(ret))
        gap = r.normal(0, 0.006, len(idx))
        open_ = np.r_[close[0], close[:-1]] * np.exp(gap)
        hi = np.maximum(open_, close) * (1 + np.abs(r.normal(0, 0.008, len(idx))))
        lo = np.minimum(open_, close) * (1 - np.abs(r.normal(0, 0.008, len(idx))))
        vol = r.lognormal(15, 0.4, len(idx)) * (1 + 3 * np.abs(ret))
        data[t] = pd.DataFrame({"Open": open_, "High": hi, "Low": lo,
                                "Close": close, "Volume": vol}, index=idx)
    return data


def _page_text(url: str) -> str:
    import html
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bist30-bot)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    raw = re.sub(r"(?s)<(script|style).*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def fetch_macro() -> None:
    """Politika faizi ve TÜFE tablolarını TCMB sitesinden günceller.
    Başarısız olursa (internet yok, sayfa yapısı değişti...) yerleşik tablolar kalır."""
    global POLICY_RATES, CPI_YOY, CPI_MOM, MACRO_SOURCE
    try:
        rows = re.findall(r"(\d{2})\.(\d{2})\.(\d{4}) - (\d+\.\d+)", _page_text(TCMB_REPO_URL))
        rates = POLICY_RATES_PRE2010 + sorted((f"{y}-{m}-{d}", float(v)) for d, m, y, v in rows)
        rows_cpi = re.findall(r"\b(\d{2})-(\d{4}) (-?\d+\.\d+) (-?\d+\.\d+)", _page_text(TCMB_CPI_URL))
        cpi = {f"{y}-{m}": float(v) for m, y, v, _ in rows_cpi}
        mom = {f"{y}-{m}": float(x) for m, y, _, x in rows_cpi}
        # Basit akıl sağlığı kontrolü: yerleşik tablodaki son kayıtları içermeli
        if len(rates) < 30 or POLICY_RATES[-1] not in rates or len(cpi) < 60 or max(cpi) < max(CPI_YOY):
            raise ValueError(f"beklenmeyen içerik ({len(rates)} faiz, {len(cpi)} TÜFE satırı)")
        POLICY_RATES, CPI_YOY, MACRO_SOURCE = rates, cpi, "TCMB (canlı)"
        CPI_MOM = dict(sorted(mom.items()))
        print(f"  ✓ TCMB: politika faizi %{rates[-1][1]} ({rates[-1][0]}), "
              f"TÜFE %{cpi[max(cpi)]} ({max(cpi)})")
    except Exception as e:  # noqa: BLE001
        print(f"  ! TCMB verisi alınamadı, yerleşik tablo kullanılıyor: {e}", file=sys.stderr)


# --------------------------------------------------------------------------- #
#  İNDİKATÖRLER
# --------------------------------------------------------------------------- #
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df: pd.DataFrame, bench_close: pd.Series | None) -> pd.DataFrame:
    d = df.copy()
    c, h, l, v = d["Close"], d["High"], d["Low"], d["Volume"]

    d["ema20"], d["ema50"], d["ema200"] = ema(c, 20), ema(c, 50), ema(c, 200)

    delta = c.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    rs = wilder(gain, 14) / wilder(loss, 14).replace(0, np.nan)
    d["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    macd = ema(c, 12) - ema(c, 26)
    d["macd_hist"] = macd - ema(macd, 9)

    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    d["atr"] = wilder(tr, 14)

    up, dn = h.diff(), -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr_w = wilder(tr, 14)
    d["di_plus"] = 100 * wilder(pd.Series(plus_dm, index=d.index), 14) / atr_w
    d["di_minus"] = 100 * wilder(pd.Series(minus_dm, index=d.index), 14) / atr_w
    dx = 100 * (d["di_plus"] - d["di_minus"]).abs() / (d["di_plus"] + d["di_minus"]).replace(0, np.nan)
    d["adx"] = wilder(dx.fillna(0), 14)

    d["vol_ratio"] = v / v.rolling(20).mean()
    d["hh20"] = h.rolling(20).max().shift(1)   # dünkü itibarıyla 20g zirve
    d["ll20"] = l.rolling(20).min().shift(1)
    d["ret63"] = c.pct_change(63)
    if bench_close is not None:
        b = bench_close.reindex(d.index).ffill()
        d["rel63"] = d["ret63"] - b.pct_change(63)
        d["bench_up"] = b > ema(b, 200)          # endeks uzun vadeli yükseliş trendinde mi
    else:
        d["rel63"] = 0.0
        d["bench_up"] = False
    return d


# --------------------------------------------------------------------------- #
#  SKOR
# --------------------------------------------------------------------------- #
# Bileşen ağırlıkları (maksimum mutlak puan). Toplam = 100.
W = {"ema200": 15, "ema_cross": 15, "adx": 10, "rsi": 15,
     "macd": 15, "volume": 10, "breakout": 10, "relative": 10}


def score_frame(d: pd.DataFrame) -> pd.DataFrame:
    """Her gün için bileşen puanları ve toplam skor (vektörel)."""
    s = pd.DataFrame(index=d.index)
    c = d["Close"]

    s["ema200"] = np.where(c > d["ema200"], W["ema200"], -W["ema200"])
    s["ema_cross"] = np.where(d["ema20"] > d["ema50"], W["ema_cross"], -W["ema_cross"])

    direction = np.sign(d["di_plus"] - d["di_minus"])
    strength = ((d["adx"] - 15) / 15).clip(0, 1)          # ADX 15->0, 30+->1
    s["adx"] = W["adx"] * direction * strength

    rsi = d["rsi"]
    s["rsi"] = np.select(
        [rsi >= 78, rsi >= 55, rsi >= 45, rsi > 25],
        [-5, W["rsi"], 0, -W["rsi"]],
        default=5,                                       # aşırı satım: tepki ihtimali
    )

    hist = d["macd_hist"]
    rising = hist > hist.shift(1)
    s["macd"] = np.where(hist > 0, 10, -10) + np.where(rising, 5, -5)

    up_day = c > c.shift(1)
    strong_vol = d["vol_ratio"] > 1.5
    s["volume"] = np.where(strong_vol & up_day, W["volume"],
                           np.where(strong_vol & ~up_day, -W["volume"], 0))

    s["breakout"] = np.where(c > d["hh20"], W["breakout"],
                             np.where(c < d["ll20"], -W["breakout"], 0))

    s["relative"] = (d["rel63"].fillna(0) / 0.15).clip(-1, 1) * W["relative"]

    s["score"] = s[list(W)].sum(axis=1).round(1)
    return s


def label(score: float) -> str:
    if score >= CFG["buy_threshold"]:
        return "AL"
    if score <= CFG["sell_threshold"]:
        return "SAT"
    return "TUT"


def reasons(row: pd.Series, comp: pd.Series) -> list[str]:
    r = []
    r.append("Fiyat EMA200 üzerinde (uzun vade yukarı)" if comp["ema200"] > 0
             else "Fiyat EMA200 altında (uzun vade aşağı)")
    r.append("EMA20 > EMA50 (kısa vade pozitif)" if comp["ema_cross"] > 0
             else "EMA20 < EMA50 (kısa vade negatif)")
    if row["adx"] >= 25:
        r.append(f"Güçlü trend (ADX {row['adx']:.0f}, "
                 f"{'alıcılar' if row['di_plus'] > row['di_minus'] else 'satıcılar'} baskın)")
    rsi = row["rsi"]
    if rsi >= 78:
        r.append(f"RSI {rsi:.0f}: aşırı alım bölgesi")
    elif rsi <= 25:
        r.append(f"RSI {rsi:.0f}: aşırı satım bölgesi")
    else:
        r.append(f"RSI {rsi:.0f}")
    r.append("MACD histogramı pozitif" if row["macd_hist"] > 0 else "MACD histogramı negatif")
    if comp["volume"] > 0:
        r.append(f"Yükselişte yüksek hacim (ort. {row['vol_ratio']:.1f}x)")
    elif comp["volume"] < 0:
        r.append(f"Düşüşte yüksek hacim (ort. {row['vol_ratio']:.1f}x)")
    if comp["breakout"] > 0:
        r.append("20 günlük zirve kırıldı")
    elif comp["breakout"] < 0:
        r.append("20 günlük dip kırıldı")
    rel = row.get("rel63", 0) or 0
    if abs(rel) > 0.05:
        r.append(f"3 ayda endeksten {'iyi' if rel > 0 else 'kötü'} (%{rel*100:+.1f})")
    return r


# --------------------------------------------------------------------------- #
#  BACKTEST
# --------------------------------------------------------------------------- #
def cash_returns(index: pd.DatetimeIndex) -> pd.Series:
    """Her işlem günü için nakit getirisi: önceki işlem gününden bu yana geçen
    takvim günleri kadar, o gün geçerli politika faiziyle bileşik faiz."""
    rates = pd.Series({pd.Timestamp(k): v for k, v in POLICY_RATES}).sort_index()
    annual = rates.reindex(rates.index.union(index)).ffill().reindex(index).fillna(0)
    annual = annual / 100 * CFG["cash_rate_factor"]
    gap = pd.Series(index, index=index).diff().dt.days.fillna(0)
    prev_rate = annual.shift(1).fillna(0)          # faiz önceki günün oranıyla işler
    return (1 + prev_rate) ** (gap / 365) - 1


def macro_frame(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Her gün için o gün BİLİNEN politika faizi, son açıklanan yıllık TÜFE ve reel faiz."""
    rates = pd.Series({pd.Timestamp(k): v for k, v in POLICY_RATES}).sort_index()
    cpi = pd.Series({pd.Timestamp(k + "-01") + pd.DateOffset(months=1, days=4): v
                     for k, v in CPI_YOY.items()}).sort_index()
    out = pd.DataFrame(index=index)
    for name, s in (("policy", rates), ("cpi", cpi)):
        out[name] = s.reindex(s.index.union(index)).ffill().reindex(index)
    out["real"] = out["policy"] - out["cpi"]
    return out


def entry_allowed(index: pd.DatetimeIndex) -> pd.Series:
    """Reel faiz filtresi: reel faiz eşiğin üstündeyken yeni alım yapılmaz."""
    lim = CFG["real_rate_max"]
    if lim is None:
        return pd.Series(True, index=index)
    real = macro_frame(index)["real"]
    return ~(real > lim)          # veri yoksa (NaN) alıma izin ver


def backtest(d: pd.DataFrame, sc: pd.Series, cash: pd.Series | None = None,
             entry_mask: pd.Series | None = None) -> dict:
    """
    Long-only. t günü kapanışında skor >= buy_threshold ise t+1 açılışta al.
    Çıkış: skor < exit_score (t+1 açılışta) veya iz süren stop (gün içi).
    Pozisyonda olunmayan günlerde para nakitte durur ve `cash` getirisini kazanır.
    Döner: günlük strateji getirisi serisi, işlemler, pozisyon durumu.
    """
    o, h, l, c, atr = (d[k].to_numpy() for k in ("Open", "High", "Low", "Close", "atr"))
    score = sc.to_numpy()
    cash_r = cash.reindex(d.index).fillna(0).to_numpy() if cash is not None else np.zeros(len(d))
    allow = entry_allowed(d.index).to_numpy()
    if entry_mask is not None:            # örn. hisse o gün evrende mi (araştırma için)
        allow = allow & entry_mask.reindex(d.index).fillna(False).to_numpy(dtype=bool)
    rule = CFG["exit_rule"]
    if rule == "score":
        exit_sig = score < CFG["exit_score"]
    elif rule == "ema50":
        exit_sig = (d["Close"] < d["ema50"]).to_numpy()
    elif rule == "cross":
        exit_sig = (d["ema20"] < d["ema50"]).to_numpy()
    elif rule == "ema200":
        exit_sig = (d["Close"] < d["ema200"]).to_numpy()
    elif rule == "regime":
        # Endeks EMA200 üstündeyken (boğa) trend çıkışı, altındayken skor çıkışı
        up = d["bench_up"].fillna(False).to_numpy(dtype=bool)
        exit_sig = np.where(up, (d["ema20"] < d["ema50"]).to_numpy(), score < CFG["exit_score"])
    else:
        raise ValueError(f"bilinmeyen exit_rule: {rule}")
    if CFG["entry_rule"] == "ema200":
        entry_sig = (d["Close"] > d["ema200"]).to_numpy()
    else:
        entry_sig = score >= CFG["buy_threshold"]
    use_stop = CFG["stop_atr"] is not None
    n = len(d)
    cost = CFG["commission"] + CFG["slippage"]
    start = CFG["warmup_days"]

    daily = np.zeros(n)
    held = np.zeros(n, dtype=bool)   # o günün getirisi hisseden mi geldi (değilse faizden)
    in_pos = False
    entry_px = stop = 0.0
    entry_i = -1
    trades = []
    pending = None  # "buy" / "sell" -> ertesi açılışta uygulanacak

    for i in range(start, n):
        # 1) Bir önceki kapanışta verilen emri açılışta uygula
        if pending == "buy" and not in_pos:
            entry_px = o[i] * (1 + cost)
            stop = o[i] - CFG["stop_atr"] * atr[i - 1] if use_stop else -np.inf
            in_pos, entry_i = True, i
            held[i] = True
            day_ret = c[i] / entry_px - 1
            pending = None
            # aynı gün stop
            if l[i] <= stop:
                exit_px = min(o[i], stop) * (1 - cost)
                daily[i] = exit_px / entry_px - 1
                trades.append(_trade(d, entry_i, i, entry_px, exit_px, "stop"))
                in_pos = False
                continue
            daily[i] = day_ret
        elif pending == "sell" and in_pos:
            held[i] = True
            exit_px = o[i] * (1 - cost)
            daily[i] = exit_px / c[i - 1] - 1
            trades.append(_trade(d, entry_i, i, entry_px, exit_px, "sinyal"))
            in_pos = False
            pending = None
        elif in_pos:
            held[i] = True
            # 2) Gün içi stop kontrolü
            if l[i] <= stop:
                exit_px = min(o[i], stop) * (1 - cost)
                daily[i] = exit_px / c[i - 1] - 1
                trades.append(_trade(d, entry_i, i, entry_px, exit_px, "stop"))
                in_pos = False
            else:
                daily[i] = c[i] / c[i - 1] - 1
        else:
            pending = None
            daily[i] = cash_r[i]          # bütün gün nakitte

        # 3) Kapanışta: stopu yukarı taşı ve yarın için emir üret
        if in_pos:
            if use_stop:
                stop = max(stop, c[i] - CFG["stop_atr"] * atr[i])
            if exit_sig[i]:
                pending = "sell"
        elif entry_sig[i] and allow[i]:
            pending = "buy"

    open_trade = None
    if in_pos:
        open_trade = {
            "entry_date": str(d.index[entry_i].date()),
            "entry_price": round(float(entry_px), 2),
            "last_price": round(float(c[-1]), 2),
            "stop": round(float(stop), 2) if use_stop else None,
            "pnl_pct": round((c[-1] / entry_px - 1) * 100, 2),
            "days": int(n - 1 - entry_i),
        }
    return {
        "daily": pd.Series(daily, index=d.index).iloc[start:],
        "held": pd.Series(held, index=d.index).iloc[start:],
        "trades": trades,
        "open": open_trade,
        "pending": pending,
    }


def _trade(d, i0, i1, p0, p1, why):
    return {"entry_date": str(d.index[i0].date()), "exit_date": str(d.index[i1].date()),
            "entry": round(float(p0), 2), "exit": round(float(p1), 2),
            "ret_pct": round((p1 / p0 - 1) * 100, 2), "days": int(i1 - i0), "exit_reason": why}


def metrics(daily: pd.Series, trades: list[dict] | None = None, rf: pd.Series | None = None) -> dict:
    """rf verilirse Sharpe, nakit (faiz) getirisinin üzerindeki fazla getiriyle hesaplanır."""
    daily = daily.fillna(0)
    if len(daily) < 2:
        return {}
    eq = (1 + daily).cumprod()
    years = len(daily) / 252
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else float("nan")
    excess = daily - rf.reindex(daily.index).fillna(0) if rf is not None else daily
    std = excess.std()
    sharpe = (excess.mean() / std * math.sqrt(252)) if std > 0 else 0.0
    dd = (eq / eq.cummax() - 1).min()
    out = {
        "total_return_pct": round(total * 100, 2),
        "cagr_pct": round(cagr * 100, 2) if not math.isnan(cagr) else None,
        "sharpe": round(float(sharpe), 2),
        "max_drawdown_pct": round(float(dd) * 100, 2),
        "exposure_pct": round(float((daily != 0).mean()) * 100, 1),
    }
    if trades is not None:
        rets = [t["ret_pct"] for t in trades]
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]
        out.update({
            "trades": len(rets),
            "win_rate_pct": round(len(wins) / len(rets) * 100, 1) if rets else None,
            "avg_trade_pct": round(float(np.mean(rets)), 2) if rets else None,
            "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
            "avg_days": round(float(np.mean([t["days"] for t in trades])), 1) if trades else None,
        })
    return out


# --------------------------------------------------------------------------- #
#  ANA AKIŞ
# --------------------------------------------------------------------------- #
def r2(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 2)


def run(demo: bool, telegram_test: bool = False) -> None:
    tickers = list(BIST30)
    print(f"BIST50 sinyal botu — {'DEMO (sentetik veri)' if demo else 'gerçek veri'}")
    if not demo:
        fetch_macro()
    if demo:
        data = fetch_demo(tickers + [BENCHMARK])
    else:
        universe = sorted(set(tickers) | set(CANDIDATES))
        print(f"  {len(universe)} hisse + endeks indiriliyor (2004'ten beri)...")
        data = fetch_real(universe + [BENCHMARK], verbose=False)
        print(f"  {len(data)} seri indirildi")
        data = fix_jumps(data)
    usdtry = None
    if not demo:
        try:
            import yfinance as yf
            fx = _clean(yf.download("TRY=X", start=CFG["history_start"], interval="1d", auto_adjust=True,
                                    progress=False, threads=False))
            usdtry = fx["Close"].loc["2005-01-03":]
            print(f"  ✓ USD/TRY: {usdtry.iloc[-1]:.2f} ({usdtry.index[-1].date()})")
        except Exception as e:  # noqa: BLE001
            print(f"  ! USD/TRY alınamadı, dolar bazlı getiri atlanacak: {e}", file=sys.stderr)
    bench = data.pop(BENCHMARK, None)
    bench_close = bench["Close"] if bench is not None else None
    if bench is None:
        sys.exit("XU030 verisi alınamadı; evren seçimi ve portföy testi yapılamıyor.")

    # --- Evren: her çeyrek işlem hacmine göre en büyük N hisse. Sinyaller bugünkü üyeler için üretilir.
    cand = dedupe(data)
    full_cal = bench.index
    mem_full = pit_membership(cand, full_cal, CFG["universe_size"])
    tickers = sorted(mem_full.columns[mem_full.iloc[-1]])
    print(f"  Evren: işlem hacmine göre en büyük {len(tickers)} hisse")

    signals, per_stock, all_daily, recent_trades = [], [], {}, []
    changes, change_dates = [], set()
    prepared = {}           # hesaplanmış indikatör/skorlar (portföy testinde yeniden kullanılır)

    for t in tickers:
        df = data.get(t)
        if df is None or len(df) < CFG["min_bars"]:
            print(f"  ! {t}: yetersiz veri, atlandı", file=sys.stderr)
            continue
        d = add_indicators(df, bench_close)
        sc = score_frame(d)
        prepared[t] = (d, sc["score"])
        cash_d = cash_returns(d.index)
        bt = backtest(d, sc["score"], cash_d)

        last, comp = d.iloc[-1], sc.iloc[-1]
        prev_close = d["Close"].iloc[-2]
        score = float(comp["score"])
        sig = label(score)
        atr = float(last["atr"])
        close = float(last["Close"])

        # Pozisyon bilgisine göre durum açıklaması
        if bt["open"]:
            state = "POZİSYONDA"
            if bt["pending"] == "sell":
                state = "ÇIKIŞ"          # yarın açılışta çık sinyali
        else:
            state = "GİRİŞ" if bt["pending"] == "buy" else "BEKLE"

        signals.append({
            "ticker": t, "name": company_name(t),
            "date": str(d.index[-1].date()),
            "close": r2(close),
            "change_pct": r2((close / prev_close - 1) * 100),
            "score": round(score, 1),
            "signal": sig,
            "state": state,
            "score_5d_ago": round(float(sc["score"].iloc[-6]), 1),
            "components": {k: round(float(comp[k]), 1) for k in W},
            "rsi": r2(last["rsi"]), "adx": r2(last["adx"]),
            "atr_pct": r2(atr / close * 100),
            "stop": r2(close - CFG["stop_atr"] * atr) if sig != "SAT" else None,
            "target": r2(close + CFG["target_atr"] * atr) if sig != "SAT" else None,
            "position": bt["open"],
            "reasons": reasons(last, comp),
        })

        daily = bt["daily"]
        split = int(len(daily) * (1 - CFG["oos_fraction"]))
        oos_start = daily.index[split]
        bh = d["Close"].iloc[CFG["warmup_days"]:]
        per_stock.append({
            "ticker": t, "name": company_name(t),
            "strategy": metrics(daily, bt["trades"], rf=cash_d),
            "oos": metrics(daily.iloc[split:], [x for x in bt["trades"] if x["entry_date"] >= str(oos_start.date())],
                           rf=cash_d),
            "buy_hold_pct": r2((bh.iloc[-1] / bh.iloc[0] - 1) * 100),
        })
        for tr_ in bt["trades"][-5:]:
            recent_trades.append({"ticker": t, **tr_})
        write_stock_chart(t, d, sc["score"], bt)
        changes += signal_changes(t, d, sc["score"])
        change_dates.update(str(x.date()) for x in d.index[-(CFG["changes_days"] + 1):])

    if not signals:
        sys.exit("Hiç veri işlenemedi. İnternet bağlantısını ve yfinance kurulumunu kontrol edin.")

    # --- Portföy testi: noktasal evren (her çeyrek o zamanki en büyük 30 hisse) + oynaklığa göre pozisyon
    first = max(pd.Timestamp(CFG["backtest_start"]), full_cal[min(CFG["warmup_days"], len(full_cal) - 1)])
    cal = full_cal[full_cal >= first]
    mem = mem_full.reindex(cal).fillna(False)
    prep = {}
    for t, df in cand.items():
        if len(df) < CFG["min_bars"] or not mem[t].any():
            continue
        if t in prepared:
            prep[t] = prepared[t]
        else:
            d_ = add_indicators(df, bench_close)
            prep[t] = (d_, score_frame(d_)["score"])
    mem = mem[list(prep)]
    cash = cash_returns(cal)
    port, expo, _, weights = sized_portfolio(prep, cal, cash, mem, 1.0, CFG["vol_sizing"], CFG["vol_cap"], weights=True)
    # Adil kıyas: aynı evrenin (her gün o günün üyeleri) eşit ağırlıklı al-bekle'si
    closes = pd.DataFrame({t: d_["Close"] for t, (d_, _) in prep.items()}).reindex(cal)
    rets = closes.pct_change().where(closes.notna() & closes.shift(1).notna() & mem)
    uni = rets.mean(axis=1).fillna(cash)
    universe_note = (f"Her çeyrek, önceki {round(CFG['universe_window'] / 21)} ayın işlem hacmine göre en büyük {CFG['universe_size']} hisse "
                     f"({len(cand)} aday, {len(prep)} farklı hisse en az bir kez evrende)")
    print(f"  Portföy testi: {cal[0].date()} – {cal[-1].date()} · {universe_note} · ortalama hisse payı %{expo.mean() * 100:.0f}")
    split = int(len(port) * (1 - CFG["oos_fraction"]))
    port_eq = (1 + port).cumprod()
    bench_eq = None
    if bench_close is not None:
        b = bench_close.reindex(port.index).ffill()
        bench_eq = b / b.iloc[0]
    cash_eq = (1 + cash).cumprod()
    # Enflasyon ve dolar: aynı getirileri TÜFE'ye ve USD/TRY'ye göre de raporla
    cpi_l = cpi_level(port.index)
    usd_l = usdtry.reindex(port.index).ffill().bfill() if usdtry is not None else None
    cpi_eq = cpi_l / cpi_l.iloc[0]
    usd_eq = usd_l / usd_l.iloc[0] if usd_l is not None else None
    uni_eq = (1 + uni).cumprod()
    weekly = port_eq.resample("W-FRI").last().dropna()   # tamamen tatil olan haftaları atla
    curve = [{"date": str(i.date()), "strategy": round(float(v), 4),
              "benchmark": round(float(bench_eq.asof(i)), 4) if bench_eq is not None else None,
              "cash": round(float(cash_eq.asof(i)), 4), "universe": round(float(uni_eq.asof(i)), 4),
              "cpi": round(float(cpi_eq.asof(i)), 4),
              "usd": round(float(usd_eq.asof(i)), 4) if usd_eq is not None else None}
             for i, v in weekly.items()]

    live = update_live(port, weights, bench_close, demo)
    unit_src = {"strategy": port, "cash": cash, "universe": uni}
    if bench_eq is not None:
        unit_src["benchmark"] = bench_eq.pct_change().fillna(0)
    now = datetime.now(TR_TZ)
    order = {"AL": 0, "TUT": 1, "SAT": 2}
    signals.sort(key=lambda x: (order[x["signal"]], -x["score"]))
    counts = {k: sum(1 for s in signals if s["signal"] == k) for k in order}
    meta = {
        "generated_at": now.isoformat(timespec="minutes"),
        "data_date": max(s["date"] for s in signals),
        "demo": demo,
        "universe": f"BIST50 benzeri: işlem hacmine göre en büyük {CFG['universe_size']} hisse (her çeyrek güncellenir)",
        "thresholds": {"buy": CFG["buy_threshold"], "sell": CFG["sell_threshold"]},
        "disclaimer": "Buradaki bilgiler algoritmik teknik analiz çıktısıdır; yatırım tavsiyesi değildir. "
                      "Yatırım danışmanlığı hizmeti, SPK lisanslı kuruluşlar tarafından kişiye özel sunulur.",
    }
    # Makro durum: bugün bilinen politika faizi, son TÜFE ve reel faiz (sayfada bilgi olarak gösterilir)
    today = pd.DatetimeIndex([pd.Timestamp(meta["data_date"])])
    mf = macro_frame(today).iloc[0]
    regime = {
        "policy_rate": r2(mf["policy"]), "cpi_yoy": r2(mf["cpi"]), "real_rate": r2(mf["real"]),
        "policy_date": POLICY_RATES[-1][0], "cpi_month": max(CPI_YOY), "source": MACRO_SOURCE,
        "filter_max": CFG["real_rate_max"],
        "blocking": bool(CFG["real_rate_max"] is not None and mf["real"] > CFG["real_rate_max"]),
    }
    changes.sort(key=lambda x: (x["date"], x["to"] == "AL", x["score"]), reverse=True)
    notify_args = (meta, regime, counts)
    # Evrenden çıkan hisselerin grafik dosyalarını sil
    sdir = os.path.join(OUT_DIR, "stocks")
    if os.path.isdir(sdir):
        keep = {f"{x['ticker']}.json" for x in signals}
        for fn in os.listdir(sdir):
            if fn.endswith(".json") and fn not in keep:
                os.remove(os.path.join(sdir, fn))
    write("signals.json", {**meta, "regime": regime, "counts": counts, "signals": signals,
                           "changes_days": CFG["changes_days"],
                           "changes_dates": sorted(change_dates)[-(CFG["changes_days"] + 1):], "changes": changes})

    write("backtest.json", {
        **meta,
        "backtest_universe": universe_note,
        "avg_exposure_pct": r2(expo.mean() * 100),
        "settings": {k: CFG[k] for k in ("buy_threshold", "exit_score", "stop_atr", "vol_sizing", "universe_size",
                                          "commission", "slippage", "oos_fraction",
                                          "cash_rate_factor", "real_rate_max")},
        "cash_rate_last_pct": POLICY_RATES[-1][1],
        "cash_rate_last_date": POLICY_RATES[-1][0],
        "period": {"start": str(port.index[0].date()), "end": str(port.index[-1].date()),
                   "oos_start": str(port.index[split].date())},
        "portfolio": {
            "full": metrics(port, rf=cash),
            "oos": metrics(port.iloc[split:], rf=cash),
            "benchmark_full": metrics(bench_eq.pct_change().fillna(0), rf=cash) if bench_eq is not None else None,
            "benchmark_oos": metrics(bench_eq.pct_change().fillna(0).iloc[split:], rf=cash) if bench_eq is not None else None,
            # Nakdin oynaklığı ~0 olduğu için Sharpe anlamsız -> None
            "cash_full": {**metrics(cash), "sharpe": None},
            "cash_oos": {**metrics(cash.iloc[split:]), "sharpe": None},
            "universe_full": metrics(uni, rf=cash),
            "universe_oos": metrics(uni.iloc[split:], rf=cash),
        },
        "equity_curve": curve,
        "yearly": yearly_table(port, bench_eq.pct_change().fillna(0) if bench_eq is not None else None, cash, uni,
                               cpi_l, usd_l),
        "fx_start": r2(usd_l.iloc[0]) if usd_l is not None else None,
        "units": {
            "real": unit_metrics(unit_src, cpi_l, split),
            **({"usd": unit_metrics(unit_src, usd_l, split)} if usd_l is not None else {}),
        },
        "stocks": sorted(per_stock, key=lambda x: -(x["strategy"].get("total_return_pct") or 0)),
        "recent_trades": sorted(recent_trades, key=lambda x: x["exit_date"], reverse=True)[:40],
    })

    # --- Telegram bildirimi (AL'a giren / çıkan hisseler, model portföy işlemleri)
    notify(*notify_args, changes, live, demo, test=telegram_test)

    # --- Geçmiş (her çalıştırma, aynı veri günü tekrar yazılmaz)
    hist_path = os.path.join(OUT_DIR, "history.json")
    try:
        with open(hist_path, encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    if not demo:
        history = [h for h in history if h.get("date") != meta["data_date"]]
        history.append({"date": meta["data_date"],
                        "signals": {s["ticker"]: [s["signal"], s["score"], s["close"]] for s in signals}})
        write("history.json", history[-500:])

    print(f"\nTamam: {counts['AL']} AL, {counts['TUT']} TUT, {counts['SAT']} SAT  "
          f"(veri tarihi {meta['data_date']})")
    pf, cf = metrics(port, rf=cash), metrics(cash)
    print(f"Nakit (politika faizi) aynı dönemde: toplam %{cf['total_return_pct']}")
    print(f"Backtest portföy: toplam %{pf['total_return_pct']}, MaxDD %{pf['max_drawdown_pct']}, "
          f"Sharpe {pf['sharpe']}")


def signal_changes(t: str, d: pd.DataFrame, score: pd.Series) -> list[dict]:
    """Son `changes_days` işlem gününde sinyalin (AL/TUT/SAT) değiştiği günler.
    Puan yalnızca o güne kadarki fiyatlardan hesaplandığı için geçmiş sinyaller birebir yeniden üretilebilir."""
    n = CFG["changes_days"]
    lab = score.iloc[-(n + 1):].map(label)
    close = d["Close"].iloc[-(n + 1):]
    out = []
    for i in range(1, len(lab)):
        if lab.iloc[i] != lab.iloc[i - 1]:
            c0 = float(close.iloc[i])
            out.append({
                "date": str(lab.index[i].date()), "ticker": t, "name": company_name(t),
                "from": lab.iloc[i - 1], "to": lab.iloc[i],
                "score": round(float(score.iloc[len(score) - len(lab) + i]), 1),
                "close": r2(c0),
                "since_pct": r2((float(close.iloc[-1]) / c0 - 1) * 100),   # o günden bugüne fiyat değişimi
            })
    return out


SITE_URL = "https://emrcnkkl.github.io/quant-bot/"


def telegram_send(text: str) -> bool:
    """Telegram kanalına mesaj gönderir. Token ve kanal ID'si ortam değişkenlerinden okunur
    (GitHub → Settings → Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). Yoksa sessizce atlar."""
    import urllib.error
    import urllib.parse
    import urllib.request
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("  · Telegram ayarlı değil (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID yok), bildirim atlandı")
        return False
    body = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=body, timeout=30) as r:
            ok = json.load(r).get("ok", False)
        print(f"  {'✓' if ok else '!'} Telegram mesajı {'gönderildi' if ok else 'gönderilemedi'}")
        return ok
    except urllib.error.HTTPError as e:
        # Telegram'ın açıklaması (ör. "chat not found") token içermez; URL ise içerdiği için yazdırılmaz
        try:
            desc = json.load(e).get("description", "")
        except Exception:  # noqa: BLE001
            desc = ""
        hint = {400: "kanal ID'sini kontrol edin (kanallar için -100 ile başlar)",
                401: "token hatalı", 403: "bot kanalda yönetici değil ya da mesaj izni yok"}.get(e.code, "")
        print(f"  ! Telegram hatası {e.code}: {desc} {('→ ' + hint) if hint else ''}", file=sys.stderr)
        return False
    except Exception as e:  # noqa: BLE001  (token hata mesajına karışmasın diye yalnızca tür yazılır)
        print(f"  ! Telegram hatası: {type(e).__name__}", file=sys.stderr)
        return False


def notify(meta: dict, regime: dict, counts: dict, changes: list[dict], live: dict | None,
           demo: bool, test: bool = False) -> None:
    """Son bildirimden bu yana AL'a girenler / AL'dan çıkanlar ve model portföy işlemleri için Telegram mesajı.
    Durum notify.json'da tutulur; aynı gün için iki kez gönderilmez. İlk çalıştırmada geçmişi göndermez."""
    if demo:
        return
    path = os.path.join(OUT_DIR, "notify.json")
    try:
        with open(path, encoding="utf-8") as f:
            last = json.load(f).get("last_date")
    except (FileNotFoundError, json.JSONDecodeError):
        last = None
    today = meta["data_date"]
    if last is None and not test:
        write("notify.json", {"last_date": today})
        print("  · Telegram: ilk çalıştırma, başlangıç tarihi kaydedildi (geçmiş gönderilmez)")
        return
    if last == today and not test:
        return
    since = last if (last and last != today) else str(pd.Timestamp(today) - pd.Timedelta(days=1))[:10]
    new = [c for c in changes if c["date"] > since]
    ins = [c for c in new if c["to"] == "AL"]
    outs = [c for c in new if c["from"] == "AL"]
    ev = [e for e in (live or {}).get("events", []) if e["date"] > since]
    if not (ins or outs or ev or test):
        write("notify.json", {"last_date": today})
        print("  · Telegram: AL değişikliği yok, mesaj gönderilmedi")
        return

    def fmt_ch(c):
        return f"<b>{c['ticker']}</b> ({c['score']:+.0f})"
    day = pd.Timestamp(today)
    months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    lines = [f"📊 <b>BIST50 Sinyal</b> · {day.day} {months[day.month - 1]} {day.year} kapanışı"]
    if test and not (ins or outs or ev):
        lines.append("🔔 Deneme mesajı: bildirimler çalışıyor.")
    if ins:
        lines.append("🟢 AL'a girenler: " + ", ".join(fmt_ch(c) for c in ins))
    if outs:
        lines.append("🟠 AL'dan çıkanlar: " + ", ".join(f"<b>{c['ticker']}</b> → {c['to']}" for c in outs))
    if ev:
        buys = [e["ticker"] for e in ev if e["type"] == "alış"]
        sells = [e["ticker"] for e in ev if e["type"] == "satış"]
        if buys:
            lines.append("🛒 Model portföy aldı: " + ", ".join(buys))
        if sells:
            lines.append("💼 Model portföy sattı: " + ", ".join(sells))
    if regime.get("blocking"):
        lines.append(f"⏸ Reel faiz %{regime['real_rate']:+.1f} (eşik %{regime['filter_max']:.0f}): model yeni alım yapmıyor.")
    lines.append(f"Toplam: {counts['AL']} AL · {counts['TUT']} TUT · {counts['SAT']} SAT")
    if live and len(live["points"]) > 1:
        p0, p1 = live["points"][0], live["points"][-1]
        lines.append(f"Canlı portföy ({p0['date']}'den beri): %{(p1['value'] / p0['value'] - 1) * 100:+.1f} · "
                     f"BIST30 %{(p1['bench'] / p0['bench'] - 1) * 100:+.1f}")
    lines.append(f'<a href="{SITE_URL}">Siteye git</a> · <i>Yatırım tavsiyesi değildir.</i>')
    if telegram_send("\n".join(lines)) or not test:
        write("notify.json", {"last_date": today})


def update_live(port: pd.Series, weights: pd.DataFrame, bench_close: pd.Series, demo: bool) -> dict | None:
    """
    Canlı model portföy kaydı (live.json). İlk çalıştırmada 100.000 ₺ ile başlar; sonraki her çalıştırmada
    yalnızca son kayıttan SONRAKİ günler eklenir — geçmiş kayıtlar asla yeniden yazılmaz.
    Böylece geriye dönük testten bağımsız, sonradan değiştirilemeyen bir performans kaydı birikir.
    """
    if demo:
        return None
    path = os.path.join(OUT_DIR, "live.json")
    try:
        with open(path, encoding="utf-8") as f:
            live = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        live = None

    def holdings(day):
        w = weights.loc[day]
        w = w[w > 1e-6].sort_values(ascending=False)
        return [{"ticker": t, "name": company_name(t), "weight_pct": r2(v * 100)} for t, v in w.items()]

    last_day = port.index[-1]
    b_last = float(bench_close.asof(last_day))
    if live is None:
        live = {"start_date": str(last_day.date()), "start_value": 100000.0, "start_bench": b_last,
                "note": "Her gün yalnızca yeni günün getirisi eklenir; geçmiş kayıtlar değiştirilmez.",
                "points": [{"date": str(last_day.date()), "value": 100000.0, "bench": 100000.0,
                            "stock_pct": r2(weights.loc[last_day].sum() * 100)}],
                "events": []}
    else:
        prev = pd.Timestamp(live["points"][-1]["date"])
        value = live["points"][-1]["value"]
        prev_set = {h["ticker"] for h in live.get("holdings", [])}
        for day in port.index[port.index > prev]:
            value *= 1 + float(port.loc[day])
            bench_v = live["start_value"] * float(bench_close.asof(day)) / live["start_bench"]
            live["points"].append({"date": str(day.date()), "value": round(value, 2), "bench": round(bench_v, 2),
                                   "stock_pct": r2(weights.loc[day].sum() * 100)})
            cur = set(weights.columns[weights.loc[day] > 1e-6])
            for t in sorted(cur - prev_set):
                live["events"].append({"date": str(day.date()), "ticker": t, "name": company_name(t), "type": "alış"})
            for t in sorted(prev_set - cur):
                live["events"].append({"date": str(day.date()), "ticker": t, "name": company_name(t), "type": "satış"})
            prev_set = cur
        live["events"] = live["events"][-100:]
    live["holdings"] = holdings(last_day)
    live["updated"] = str(last_day.date())
    write("live.json", live)
    return live


def cpi_level(index: pd.DatetimeIndex) -> pd.Series:
    """Günlük TÜFE seviyesi (aylık değişimlerden kurulur, ay içinde geometrik ara değer).
    Henüz açıklanmamış aylar için son 3 ayın ortalama aylık değişimi varsayılır."""
    mom = pd.Series({pd.Period(k, "M"): v / 100 for k, v in CPI_MOM.items()}).sort_index()
    last = mom.index[-1]
    need = pd.period_range(mom.index[0], max(index[-1].to_period("M"), last), freq="M")
    mom = mom.reindex(need).fillna(mom.iloc[-3:].mean())
    lvl_end = (1 + mom).cumprod()                       # ay sonu seviyesi
    lvl_start = lvl_end / (1 + mom)                     # ay başı seviyesi
    per = index.to_period("M")
    frac = (index.day - 1) / index.days_in_month
    out = lvl_start.reindex(per).to_numpy() * (1 + mom.reindex(per).to_numpy()) ** frac
    return pd.Series(out, index=index)


def unit_metrics(series: dict[str, pd.Series], deflator: pd.Series, split: int) -> dict:
    """Getirileri bir ölçüye (TÜFE seviyesi ya da USD/TRY kuru) bölerek yıllık getiri ve toplam getiri."""
    out = {}
    d = deflator / deflator.iloc[0]
    for k, r in series.items():
        eq = (1 + r.fillna(0)).cumprod() / d
        rr = eq.pct_change().fillna(eq.iloc[0] - 1)
        out[k] = {"full": {"cagr_pct": metrics(rr)["cagr_pct"], "total_return_pct": r2((eq.iloc[-1] - 1) * 100),
                           "max_drawdown_pct": metrics(rr)["max_drawdown_pct"]},
                  "oos": {"cagr_pct": metrics(rr.iloc[split:])["cagr_pct"],
                          "total_return_pct": r2((eq.iloc[-1] / eq.iloc[split - 1] - 1) * 100),
                          "max_drawdown_pct": metrics(rr.iloc[split:])["max_drawdown_pct"]}}
    return out


def yearly_table(port: pd.Series, bench: pd.Series | None, cash: pd.Series, uni: pd.Series | None = None,
                 cpi: pd.Series | None = None, usd: pd.Series | None = None) -> list[dict]:
    """Takvim yılı bazında strateji / XU030 / nakit getirisi (%). Eksik yıllar `partial` işaretli."""
    out = []
    for year, p in port.groupby(port.index.year):
        def ret(s):
            return None if s is None else r2(((1 + s.loc[p.index].fillna(0)).prod() - 1) * 100)
        out.append({
            "year": int(year), "from": str(p.index[0].date()), "to": str(p.index[-1].date()),
            "partial": bool(p.index[0].month > 1 or p.index[0].day > 10 or p.index[-1].month < 12),
            "strategy": ret(p), "benchmark": ret(bench), "cash": ret(cash), "universe": ret(uni),
            # o yıl TÜFE ve USD/TRY değişimi (%): sayfa reel / dolar bazlı yıllık getiriyi bundan hesaplar
            "cpi_pct": None if cpi is None else r2(((1 + cpi.pct_change().loc[p.index].fillna(0)).prod() - 1) * 100),
            "usd_pct": None if usd is None else r2(((1 + usd.pct_change().loc[p.index].fillna(0)).prod() - 1) * 100),
        })
    return out


def write_stock_chart(t: str, d: pd.DataFrame, score: pd.Series, bt: dict, days: int = 500) -> None:
    """Sayfadaki hisse detay grafiği için son ~2 yılın fiyat, EMA, skor ve işlem verisi."""
    w = d.iloc[-days:]
    start = str(w.index[0].date())
    col = lambda s: [r2(x) for x in s]  # noqa: E731
    write(f"stocks/{t}.json", {
        "ticker": t, "name": company_name(t),
        "dates": [str(x.date()) for x in w.index],
        "close": col(w["Close"]), "ema20": col(w["ema20"]), "ema50": col(w["ema50"]),
        "ema200": col(w["ema200"]), "score": [round(float(x), 1) for x in score.iloc[-days:]],
        "trades": [x for x in bt["trades"] if x["exit_date"] >= start],
        "open": bt["open"],
    }, quiet=True)


def write(name: str, obj, quiet: bool = False) -> None:
    path = os.path.join(OUT_DIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None if quiet else 1,
                  separators=(",", ":") if quiet else None, allow_nan=False)
    if not quiet:
        print(f"  → {name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BIST30 teknik analiz sinyal botu")
    ap.add_argument("--demo", action="store_true", help="sentetik veri ile çalıştır")
    ap.add_argument("--telegram-test", action="store_true", help="değişiklik olmasa da Telegram'a deneme mesajı gönder")
    a = ap.parse_args()
    run(a.demo, a.telegram_test)
