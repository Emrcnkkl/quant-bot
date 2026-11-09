# CLAUDE.md — BIST30 Teknik Sinyal Botu

Bu dosya, projeye Claude Code ile devam ederken bağlam sağlamak içindir.
Kullanıcıyla iletişim, arayüz metinleri ve kod yorumları **Türkçe**dir.

## Proje özeti
BIST 30 hisseleri için günlük veriyle teknik analiz yapan, her hisseye −100…+100 arası
skor verip **AL / TUT / SAT** sinyali üreten, geriye dönük test (backtest) raporu çıkaran
ve sonuçları statik bir web sayfasında gösteren bir bot. Şu an **Aşama 1** tamamlandı.

## Durum (9 Kasım 2026)
- `bot.py`, `index.html`, workflow ve README yazıldı.
- Kod yalnızca **sentetik veriyle** (`python3 bot.py --demo`) test edildi; hem Python 3.10/pandas 2.3
  hem Python 3.12/pandas 3.0'da hatasız çalışıyor. Sayfa Playwright ile masaüstü ve mobilde kontrol edildi.
- **Gerçek veriyle henüz hiç çalıştırılmadı** (geliştirme ortamından Yahoo Finance'e erişim yoktu).
  Klasördeki `signals.json` / `backtest.json` DEMO çıktısıdır (`"demo": true`, sayfada uyarı bandı çıkar).
  İlk iş: `python3 bot.py` ile gerçek veriyi çalıştırıp çıktıları doğrulamak.

## Dosya yapısı
```
YENİ PROJE/
├── CLAUDE.md          # bu dosya
├── README.md          # kullanıcıya yönelik kurulum/çalıştırma
├── bot.py             # tüm mantık: veri, indikatörler, skor, backtest, JSON yazımı (tek dosya)
├── index.html         # tek dosyalık statik sayfa (inline CSS/JS, kütüphane yok); JSON'ları fetch eder
├── requirements.txt   # yfinance, pandas, numpy
├── .github/workflows/bot.yml  # GitHub Actions workflow
├── signals.json       # güncel sinyaller (bot üretir)
├── backtest.json      # backtest raporu (bot üretir)
└── history.json       # günlük sinyal geçmişi (yalnızca gerçek veriyle çalışınca oluşur/eklenir, son 500 gün)
```

## Çalıştırma
```bash
python3 -m pip install -r requirements.txt
python3 bot.py           # gerçek veri (yfinance, internet gerekir)
python3 bot.py --demo    # sentetik veri, internetsiz test (history.json'a yazmaz)
python3 -m http.server   # http://localhost:8000 — index.html file:// ile açılınca JSON okuyamaz
```

## Verilen kararlar
| Konu | Karar |
|---|---|
| Zaman dilimi | Günlük mumlar |
| Veri kaynağı | yfinance, semboller `XXXXX.IS`, `auto_adjust=True`, 6 yıl; benchmark `XU030.IS` |
| Strateji tipi | Çoklu indikatör birleşik skoru (tek strateji, parametre optimizasyonu YOK — aşırı uyumdan kaçınmak için) |
| Yön | Sadece long (açığa satış yok). SAT = çık / uzak dur anlamında |
| Çıktılar | Python bot + signals.json, backtest raporu, basit web sayfası |
| Otomasyon | GitHub Actions, hafta içi 18:40 TR (`40 15 * * 1-5` UTC), JSON'ları repoya commit eder |
| Hukuki | Her çıktıda "yatırım tavsiyesi değildir" uyarısı (SPK); disclaimer metni `bot.py` → `meta["disclaimer"]` |

### Evren — BIST 30 (1 Ekim–31 Aralık 2026 dönemi)
TRMET girdi, DSTKF çıktı. `bot.py` içindeki `BIST30` sözlüğü:
AEFES AKBNK ASELS ASTOR BIMAS EKGYO ENKAI EREGL FROTO GARAN GUBRF ISCTR KCHOL KRDMD MGROS
PETKM PGSUS SAHOL SASA SISE TAVHL TCELL THYAO TOASO TRALT TRMET TTKOM TUPRS VAKBN YKBNK
**Her çeyrek başında Borsa İstanbul duyurusuna göre güncellenmeli (sıradaki: Ocak 2027).**

### Skor (−100…+100) — `score_frame()`, ağırlıklar `W` sözlüğünde
| Bileşen | Puan | Kural |
|---|---|---|
| ema200 | ±15 | Kapanış EMA200 üstü/altı |
| ema_cross | ±15 | EMA20 > / < EMA50 |
| adx | ±10 | DI+/DI− yönü × ADX gücü (ADX 15→0, 30+→tam) |
| rsi | +15/0/−15/−5/+5 | 55–78 / 45–55 / 25–45 / >78 aşırı alım / <25 aşırı satım |
| macd | ±15 | Histogram işareti ±10, eğimi ±5 |
| volume | ±10 | Hacim > 1.5× 20g ort. ise günün yönünde |
| breakout | ±10 | Dünkü 20g zirve üstü / dip altı kapanış |
| relative | ±10 | 63g getiri − XU030 63g getirisi, ±%15'te tavan |

Sinyal: skor ≥ +40 → AL, ≤ −40 → SAT, arası TUT (`CFG["buy_threshold"]`, `CFG["sell_threshold"]`).
Bilgi amaçlı stop = kapanış − 2.5×ATR, hedef = kapanış + 4×ATR. Pozisyondaysa iz süren stop gösterilir.

### Backtest kuralları — `backtest()`
- Sinyal t günü kapanışında; işlem **t+1 açılışında** (ileriye bakma yanlılığı yok).
- Giriş: skor ≥ 40. Çıkış: skor < 0 (ertesi açılış) **veya** 2.5×ATR iz süren stop gün içinde (fiyat = min(açılış, stop)).
- Maliyet tek yön %0.10 komisyon + %0.05 kayma.
- İlk 210 gün ısınma (EMA200). Son %30 örneklem dışı (OOS) ayrı raporlanır.
- Portföy: 30 hisseye eşit 1/N, sinyal yokken pay nakitte (faiz yok). XU030 al-tut ile kıyaslanır.
- `state` alanı backtest durum makinesinden gelir: `POZİSYONDA`, `GİRİŞ` (yarın al), `ÇIKIŞ` (yarın sat), `BEKLE`.

### Tüm ayarlar
`bot.py` başındaki `CFG` sözlüğü: history_period, warmup_days, buy/sell_threshold, exit_score,
stop_atr, target_atr, commission, slippage, oos_fraction, min_bars.

## JSON şemaları (index.html bunlara bağımlı — alan adı değiştirirken sayfayı da güncelle)
**signals.json**: `generated_at, data_date, demo, universe, thresholds{buy,sell}, disclaimer, counts{AL,TUT,SAT}, signals[]`
- `signals[]`: `ticker, name, date, close, change_pct, score, signal, state, score_5d_ago, components{ema200,...}, rsi, adx, atr_pct, stop, target, position{entry_date,entry_price,last_price,stop,pnl_pct,days}|null, reasons[]`

**backtest.json**: meta alanları + `settings, period{start,end,oos_start}, portfolio{full,oos,benchmark_full,benchmark_oos}, equity_curve[{date,strategy,benchmark}] (haftalık), stocks[{ticker,name,strategy,oos,buy_hold_pct}], recent_trades[]`
- metrik alanları (`metrics()`): `total_return_pct, cagr_pct, sharpe, max_drawdown_pct, exposure_pct` (+ işlem listesi verilirse `trades, win_rate_pct, avg_trade_pct, profit_factor, avg_days`)

**history.json**: `[{date, signals: {TICKER: [signal, score, close]}}]`

## Kod kuralları
- `bot.py` tek dosya kalsın, ta ki belirgin şekilde büyüyene kadar; Python 3.10 uyumlu olmalı (kullanıcının makinesi 3.10).
- JSON `allow_nan=False` ile yazılır → NaN değerleri `r2()` ile `None`'a çevir.
- `index.html` dışa bağımlılık içermez; açık/koyu tema CSS değişkenleriyle (`:root` + `prefers-color-scheme`).
- Sayılar `tr-TR` formatında gösterilir.

## Bilinen sınırlamalar
- **Hayatta kalma yanlılığı**: backtest bugünkü BIST30 listesiyle yapılıyor.
- Nakitte bekleyen paraya faiz yok (Türkiye'de yüksek faiz ortamında stratejiyi olduğundan kötü gösterir).
- Portföy `exposure_pct` metriği anlamlı değil (günlük ortalama getiri ≠ 0 olduğu sürece ~%100 çıkar); sayfada gösterilmiyor.
- Aynı gün stop olunca o günün kapanışındaki yeni giriş sinyali atlanıyor (küçük etki).
- yfinance BIST verisinde zaman zaman eksik gün/bölünme hatası olabilir; gerçek veride kontrol edilmeli.
- Demo veri rastgeledir; demo backtest sonuçları hiçbir şey ifade etmez.

## Sıradaki adımlar
1. **Gerçek veriyle ilk çalıştırma** — `python3 bot.py`; eksik/hatalı hisse var mı, skor dağılımı makul mü (hepsi TUT ya da hepsi AL değil mi), backtest sayıları mantıklı mı kontrol et.
2. GitHub Pages kurulumu; Actions'a yazma izni ver (Settings → Actions → General → Read and write), `workflow_dispatch` ile manuel test et. Repo: Emrcnkkl/quant-bot.
3. Nakit getirisi (örn. TCMB politika faizi / para piyasası fonu) ile portföy backtest'ini düzelt.
4. Hayatta kalma yanlılığını azaltmak için geçmiş çeyreklerin BIST30 listeleriyle tarihsel evren.
5. Eşik/parametre duyarlılık analizi (örn. AL eşiği 30/40/50, stop 2/2.5/3 ATR) — optimizasyon değil, sağlamlık kontrolü.
6. Haftalık trend filtresi (opsiyonel), rejim filtresi (XU030 EMA200 altındayken yeni giriş yok).
7. Sinyal değişimlerinde Telegram bildirimi (yalnızca AL↔TUT↔SAT değişince).
8. Sayfaya hisse detay grafiği (fiyat + EMA + sinyal noktaları), history.json'dan sinyal geçmişi.
9. Ocak 2027'de BIST30 listesini güncelle.
