# CLAUDE.md — BIST30 Teknik Sinyal Botu

Bu dosya, projeye Claude Code ile devam ederken bağlam sağlamak içindir.
Kullanıcıyla iletişim, arayüz metinleri ve kod yorumları **Türkçe**dir.

## Proje özeti
BIST 30 hisseleri için günlük veriyle teknik analiz yapan, her hisseye −100…+100 arası
skor verip **AL / TUT / SAT** sinyali üreten, geriye dönük test (backtest) raporu çıkaran
ve sonuçları statik bir web sayfasında gösteren bir bot. Şu an **Aşama 1** tamamlandı.

## Durum (9 Kasım 2026)
- Bot gerçek veriyle çalışıyor: GitHub Actions hafta içi 18:40'ta çalışıp JSON'ları commit ediyor; GitHub Pages açık
  (https://emrcnkkl.github.io/quant-bot/). Repo: Emrcnkkl/quant-bot, ana dal `claude/laughing-dijkstra-j1eqmj`.
- Cloud oturumları için `quant-bot` ortamı Yahoo Finance hostlarına izinli → `python3 bot.py` oturumdan da çalışır.
- Algoritma tarafı (nakit faizi, duyarlılık analizi, reel faiz filtresi) tamamlandı; **odak web sitesi**.
- Sitede yapılanlar: faiz ortamı kutusu (reel faiz), satıra tıklayınca hisse grafiği (fiyat+EMA, alış/satış işaretleri,
  skor şeridi, 3A/6A/1Y/2Y, üzerine gelince ayrıntı), yıl yıl getiri tablosu.
- Site arkadaşlara açılacak → genel kitleye yönelik: koyu tema varsayılan (açık tema `prefers-color-scheme: light`),
  üstte sabit menü (Bugün / Sinyaller / Performans / Nasıl çalışır / SSS), "yatırım tavsiyesi değildir" bandı,
  "100.000 ₺ ile başlasaydı" özet kartı (endeks ve faizle dürüst kıyas), sade dil (Puan, Zarar-kes, modelde...).
  Tasarım referansı kullanıcının diğer projesi (emrcnkkl.github.io/anlik_bot).
- Sinyal geçmişi: "Son sinyal değişiklikleri" (Sinyaller bölümü, `#gecmis`) — son 30 işlem günündeki AL/TUT/SAT geçişleri,
  geçmiş fiyatlardan yeniden hesaplanır (`signal_changes()`); history.json'a bağlı değil.
- Bulgular: strateji test döneminde endeksle başa baş, düşüşü ~1/3; ama 2024 sonrası faizin gerisinde
  (`docs/duyarlilik-analizi.md`, `docs/reel-faiz-filtresi.md`).

## Dosya yapısı
```
YENİ PROJE/
├── CLAUDE.md          # bu dosya
├── README.md          # kullanıcıya yönelik kurulum/çalıştırma
├── bot.py             # tüm mantık: veri, indikatörler, skor, backtest, JSON yazımı (tek dosya)
├── index.html         # tek dosyalık statik sayfa (inline CSS/JS, kütüphane yok); JSON'ları fetch eder
├── fonts/             # Inter değişken yazı tipi (woff2, latin + latin-ext; OFL lisansı OFL-Inter.txt)
├── requirements.txt   # yfinance, pandas, numpy
├── .github/workflows/bot.yml  # GitHub Actions workflow
├── signals.json       # güncel sinyaller (bot üretir)
├── backtest.json      # backtest raporu (bot üretir)
├── stocks/TICKER.json # hisse detay grafiği verisi, son 500 gün (bot üretir)
├── sensitivity.py     # parametre duyarlılık analizi (bot.py fonksiyonlarını kullanır, veriyi .cache/ altına kaydeder)
├── sensitivity.json   # analiz çıktısı
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
- Portföy: 30 hisseye eşit 1/N, sinyal yokken pay nakitte ve **TCMB politika faizi** kazanır (`POLICY_RATES` tablosu, `cash_returns()`, takvim günü bazında bileşik). Verisi kısa olan hissenin payı da o günlerde nakitte. XU030 al-tut ve saf nakit ile kıyaslanır.
- Sharpe, nakit getirisinin üzerindeki fazla getiriyle hesaplanır (`metrics(..., rf=cash)`); nakdin kendi Sharpe'ı `None`.
- `state` alanı backtest durum makinesinden gelir: `POZİSYONDA`, `GİRİŞ` (yarın al), `ÇIKIŞ` (yarın sat), `BEKLE`.

### Tüm ayarlar
`bot.py` başındaki `CFG` sözlüğü: history_period, warmup_days, buy/sell_threshold, exit_score,
stop_atr, target_atr, commission, slippage, oos_fraction, min_bars, cash_rate_factor (0 = faiz yok), changes_days (30),
real_rate_max (None = kapalı; reel faiz bunun üstündeyse yeni alım yok — `entry_allowed()`, `macro_frame()`).

`POLICY_RATES` (TCMB 1 hafta repo, yürürlük tarihi) ve `CPI_YOY` (yıllık TÜFE) yerleşik tablolar; gerçek çalıştırmada
`fetch_macro()` ikisini de tcmb.gov.tr'den canlı çekip günceller (urllib + regex, ek bağımlılık yok). Başarısızsa yerleşik tablo kalır,
`regime.source` bunu gösterir. Yerleşik tabloları ara ara canlı veriyle eşitle.

## JSON şemaları (index.html bunlara bağımlı — alan adı değiştirirken sayfayı da güncelle)
**signals.json**: `generated_at, data_date, demo, universe, thresholds{buy,sell}, disclaimer, regime{policy_rate,cpi_yoy,real_rate,policy_date,cpi_month,source,filter_max,blocking}, counts{AL,TUT,SAT}, signals[], changes_days, changes_dates[], changes[]`
- `changes[]`: `date, ticker, name, from, to, score, close, since_pct` (yeniden eskiye)
- `signals[]`: `ticker, name, date, close, change_pct, score, signal, state, score_5d_ago, components{ema200,...}, rsi, adx, atr_pct, stop, target, position{entry_date,entry_price,last_price,stop,pnl_pct,days}|null, reasons[]`

**backtest.json**: meta alanları + `settings, period{start,end,oos_start}, portfolio{full,oos,benchmark_full,benchmark_oos,cash_full,cash_oos}, equity_curve[{date,strategy,benchmark,cash}] (haftalık), yearly[{year,from,to,partial,strategy,benchmark,cash}], stocks[{ticker,name,strategy,oos,buy_hold_pct}], recent_trades[]`
- metrik alanları (`metrics()`): `total_return_pct, cagr_pct, sharpe, max_drawdown_pct, exposure_pct` (+ işlem listesi verilirse `trades, win_rate_pct, avg_trade_pct, profit_factor, avg_days`)

**history.json**: `[{date, signals: {TICKER: [signal, score, close]}}]`

**stocks/TICKER.json**: `ticker, name, dates[], close[], ema20[], ema50[], ema200[], score[], trades[], open` (kompakt JSON)

## Kod kuralları
- `bot.py` tek dosya kalsın, ta ki belirgin şekilde büyüyene kadar; Python 3.10 uyumlu olmalı (kullanıcının makinesi 3.10).
- JSON `allow_nan=False` ile yazılır → NaN değerleri `r2()` ile `None`'a çevir.
- `index.html` dışa bağımlılık içermez (yazı tipi `fonts/` altında, depodan yüklenir); koyu tema `:root`'ta, açık tema `@media (prefers-color-scheme: light)` içinde.
- "Premium" tema: arka planda ışık + ızgara, yarı saydam kart yüzeyleri (`--surface`), gradyan kenarlı hero, sayaç animasyonu,
  hisse simgeleri (`who()` / `.av`, renk `hue(ticker)`), kaydırınca belirme (`.rv`), `prefers-reduced-motion` destekli.
- Mobilde (≤520px) sinyal tablosunda simge ve puan çubuğu gizlenir, şirket adı kısaltılır — tablo 360px'e sığmalı.
- Sayfa metinleri teknik bilgisi olmayan okura göre yazılır; jargon gerekiyorsa `title` ipucu ya da SSS ile açıklanır.
- Sayılar `tr-TR` formatında gösterilir.

## Bilinen sınırlamalar
- **Hayatta kalma yanlılığı**: backtest bugünkü BIST30 listesiyle yapılıyor.
- Nakit getirisi politika faizi kabul ediliyor; gerçekte para piyasası fonu getirisi vergi/masraf nedeniyle biraz düşük olabilir (`cash_rate_factor` ile ayarlanır).
- Portföy `exposure_pct` metriği anlamlı değil (günlük ortalama getiri ≠ 0 olduğu sürece ~%100 çıkar); sayfada gösterilmiyor.
- Aynı gün stop olunca o günün kapanışındaki yeni giriş sinyali atlanıyor (küçük etki).
- yfinance BIST verisinde zaman zaman eksik gün/bölünme hatası olabilir; gerçek veride kontrol edilmeli.
- Demo veri rastgeledir; demo backtest sonuçları hiçbir şey ifade etmez.

## Sıradaki adımlar
1. **Gerçek veriyle ilk çalıştırma** — `python3 bot.py`; eksik/hatalı hisse var mı, skor dağılımı makul mü (hepsi TUT ya da hepsi AL değil mi), backtest sayıları mantıklı mı kontrol et.
2. GitHub Pages kurulumu; Actions'a yazma izni ver (Settings → Actions → General → Read and write), `workflow_dispatch` ile manuel test et. Repo: Emrcnkkl/quant-bot.
3. ~~Nakit getirisi~~ — yapıldı (TCMB politika faizi). 2026 PPK kararlarını `POLICY_RATES`'e ekle.
4. Hayatta kalma yanlılığını azaltmak için geçmiş çeyreklerin BIST30 listeleriyle tarihsel evren.
5. ~~Duyarlılık analizi~~ — yapıldı (`sensitivity.py`, sonuç `docs/duyarlilik-analizi.md`): sonuç ayarlara duyarsız, ayar oynamak OOS'u iyileştirmiyor, hiçbir ayar OOS'ta faizi geçmiyor → mevcut ayarlar korunuyor.
6. ~~Reel faiz filtresi~~ — kodda var, varsayılan kapalı (`docs/reel-faiz-filtresi.md`). Haftalık trend / XU030 EMA200 rejim filtresi denenmedi.
7. Sinyal değişimlerinde Telegram bildirimi (yalnızca AL↔TUT↔SAT değişince).
8. ~~Hisse detay grafiği~~ ve ~~sinyal geçmişi listesi~~ — yapıldı.
9. Ocak 2027'de BIST30 listesini güncelle.
