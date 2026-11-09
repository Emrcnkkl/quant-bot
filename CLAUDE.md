# CLAUDE.md — BIST30 Teknik Sinyal Botu

Bu dosya, projeye Claude Code ile devam ederken bağlam sağlamak içindir.
Kullanıcıyla iletişim, arayüz metinleri ve kod yorumları **Türkçe**dir.

## Proje özeti
BIST 30 hisseleri için günlük veriyle teknik analiz yapan, her hisseye −100…+100 arası
skor verip **AL / TUT / SAT** sinyali üreten, geriye dönük test (backtest) raporu çıkaran
ve sonuçları statik bir web sayfasında gösteren bir bot. Şu an **Aşama 1** tamamlandı.

## Durum (10 Kasım 2026)
- Bot gerçek veriyle çalışıyor: GitHub Actions hafta içi 18:40 (+ yedek 19:25, 21:10) çalışıp JSON'ları commit ediyor; GitHub Pages
  açık (https://emrcnkkl.github.io/quant-bot/). Repo: Emrcnkkl/quant-bot, ana dal `claude/laughing-dijkstra-j1eqmj`.
- Cloud oturumları için `quant-bot` ortamı Yahoo Finance ve www.tcmb.gov.tr'ye izinli → `python3 bot.py` oturumdan da çalışır (~1 dk).
- **Portföy testi (sitedeki rakamlar)**: 2006'dan, noktasal evren (her çeyrek TL hacme göre en büyük 30), oynaklık ayarlı pozisyon,
  reel faiz filtresi (+5). Sonuç (Kasım 2026): model %21/yıl, düşüş −%25 · XU030 %17.7, −%64 · faiz %15.5.
  **Enflasyondan arındırılmış**: model +%1.7/yıl, XU030 −%1.2, faiz −%3.0. Dolar bazında model +%1.7, XU030 −%1.2.
- Modelin değeri getiri değil **düşüş koruması** (2008: endeks −%50, model +%7). Teknik göstergelerle al-bekle'yi getiride
  belirgin geçmek gerçekçi testte mümkün olmadı; aşağıdaki "Araştırma bulguları"na bakmadan yeni kural ekleme.
- **Canlı model portföy** (`live.json`): 9 Kasım 2026'da 100.000 ₺ ile başladı; her çalıştırmada yalnızca yeni günler eklenir,
  geçmiş kayıtlar ASLA yeniden yazılmaz (`update_live`). Model mantığı değişirse eski kayıtlar olduğu gibi kalır.
- **Telegram**: AL'a giren/çıkan hisseler ve model alım/satımları (`notify`, durum `notify.json`). Token/kanal ID GitHub
  Secrets'ta (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) — depoya ya da sohbete yazılmaz. Elle deneme: Actions → Run workflow →
  "telegram_test" kutusu, ya da `python3 bot.py --telegram-test`.
- Site: koyu premium tema, genel kitleye sade dil; Bugün (özet kartı, AL/TUT/SAT, faiz ortamı, canlı portföy) · Sinyaller (tablo,
  hisse grafiği, son sinyal değişiklikleri, faiz filtresi uyarısı) · Performans (TL / enflasyondan arındırılmış / dolar anahtarı,
  yıl yıl tablo) · Nasıl çalışır · SSS. Tasarım referansı kullanıcının diğer projesi (emrcnkkl.github.io/anlik_bot).

### Araştırma bulguları (ayrıntı `docs/`)
| Konu | Sonuç | Karar |
|---|---|---|
| Nakit faizi | Boştaki para politika faizi kazanmalı | eklendi |
| Parametre duyarlılığı (`sensitivity.py`) | sonuç ayarlara duyarsız; ayar oynamak işe yaramıyor | ayarlar sabit |
| Çıkış kuralları (`experiments.py`) | hiçbir kural iki dönemi birden iyileştirmedi | değişmedi |
| Bugünkü listeyle test | ~15 puan/yıl şişirme (hayatta kalma yanlılığı) | noktasal evren |
| Momentum rotasyonu | avantajı yanlılıktı; doğru evrende al-bekle kadar, düşüş −%50+ | eklenmedi |
| Oynaklığa göre pozisyon | iki dönemde de risk başına getiri arttı | **eklendi** (`vol_sizing`) |
| Payı büyütmek (1.5×+) | testte daha kötü | eklenmedi |
| Reel faiz filtresi 20 yıl (`research.py --faiz`) | +2.5…+7.5 arası eşikler iyileştiriyor; +5 iki dönemde de | **eklendi** (`real_rate_max=5`) |

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
├── live.json          # canlı model portföy kaydı (yalnızca eklenir, geçmişi değişmez)
├── notify.json        # son Telegram bildirimi tarihi
├── sensitivity.py     # parametre duyarlılık analizi (bot.py fonksiyonlarını kullanır, veriyi .cache/ altına kaydeder)
├── sensitivity.json   # analiz çıktısı
├── experiments.py     # giriş/çıkış kuralı deneyleri (al-bekle'yi geçen hisse sayısı), çıktı experiments.json
├── research.py        # 2005–bugün uzun dönem testi, momentum rotasyonu, kayan pencereli seçim; veri .cache/long.pkl, çıktı research.json
│                      # --pit noktasal evren · --sizing pozisyon büyüklüğü · --faiz reel faiz filtresi (research_*.json)
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
| Veri kaynağı | yfinance, semboller `XXXXX.IS`, `auto_adjust=True`, 2004'ten (2005 öncesi atılır, `fix_jumps`); benchmark `XU030.IS`; ~157 seri, Actions'ta ~1–2 dk |
| Strateji tipi | Çoklu indikatör birleşik skoru (tek strateji, parametre optimizasyonu YOK — aşırı uyumdan kaçınmak için) |
| Yön | Sadece long (açığa satış yok). SAT = çık / uzak dur anlamında |
| Çıktılar | Python bot + signals.json, backtest raporu, basit web sayfası |
| Otomasyon | GitHub Actions, hafta içi 18:40 TR (`40 15 * * 1-5` UTC) + yedek 19:25 ve 21:10; o günün verisi varsa yedekler atlanır. JSON'ları repoya commit eder (push öncesi `pull --rebase`) |
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
- Portföy (`sized_portfolio`): 2006'dan, noktasal evren (her çeyrek önceki 3 ayın TL hacmine göre ilk 30, `pit_membership`); temel pay 1/30,
  oynaklık ayarlı (× medyan ATR% / hisse ATR%, 1/3–2), toplam ≤ %100; hisseye yalnızca evrendeyken girilir. Sinyal yokken pay nakitte ve **TCMB politika faizi** kazanır (`POLICY_RATES` tablosu, `cash_returns()`, takvim günü bazında bileşik). Verisi kısa olan hissenin payı da o günlerde nakitte. XU030 al-tut ve saf nakit ile kıyaslanır.
- Sharpe, nakit getirisinin üzerindeki fazla getiriyle hesaplanır (`metrics(..., rf=cash)`); nakdin kendi Sharpe'ı `None`.
- `state` alanı backtest durum makinesinden gelir: `POZİSYONDA`, `GİRİŞ` (yarın al), `ÇIKIŞ` (yarın sat), `BEKLE`.

### Tüm ayarlar
`bot.py` başındaki `CFG` sözlüğü: warmup_days, buy/sell_threshold, exit_score,
stop_atr, target_atr, commission, slippage, oos_fraction, min_bars, cash_rate_factor (0 = faiz yok), changes_days (30),
history_start, backtest_start (2006), universe_size (30), vol_sizing (True), vol_cap (2), jump_limit (0.25),
real_rate_max (5.0; None = kapalı; reel faiz bunun üstündeyse yeni alım yok — `entry_allowed()`, `macro_frame()`),
exit_rule ("score" varsayılan | ema50 | cross | ema200 | regime), entry_rule ("score" | ema200), stop_atr=None → stop yok.

`POLICY_RATES` (2010-05 öncesi `POLICY_RATES_PRE2010` = gecelik borç alma, sonrası 1 hafta repo; 2003'ten) ve `CPI_YOY` (yıllık TÜFE, 2005'ten) yerleşik tablolar; gerçek çalıştırmada
`fetch_macro()` ikisini de tcmb.gov.tr'den canlı çekip günceller (urllib + regex, ek bağımlılık yok). Başarısızsa yerleşik tablo kalır,
`regime.source` bunu gösterir. Yerleşik tabloları ara ara canlı veriyle eşitle.

## JSON şemaları (index.html bunlara bağımlı — alan adı değiştirirken sayfayı da güncelle)
**signals.json**: `generated_at, data_date, demo, universe, thresholds{buy,sell}, disclaimer, regime{policy_rate,cpi_yoy,real_rate,policy_date,cpi_month,source,filter_max,blocking}, counts{AL,TUT,SAT}, signals[], changes_days, changes_dates[], changes[]`
- `changes[]`: `date, ticker, name, from, to, score, close, since_pct` (yeniden eskiye)
- `signals[]`: `ticker, name, date, close, change_pct, score, signal, state, score_5d_ago, components{ema200,...}, rsi, adx, atr_pct, stop, target, position{entry_date,entry_price,last_price,stop,pnl_pct,days}|null, reasons[]`

**backtest.json**: meta alanları + `backtest_universe, avg_exposure_pct, fx_start, units{real,usd}{strategy,benchmark,universe,cash}{full,oos}, settings, period{start,end,oos_start}, portfolio{full,oos,benchmark_full,benchmark_oos,cash_full,cash_oos}, portfolio{...,universe_full,universe_oos}, equity_curve[{date,strategy,benchmark,cash,universe,cpi,usd}] (haftalık), yearly[{year,from,to,partial,strategy,benchmark,cash,universe,cpi_pct,usd_pct}], stocks[{ticker,name,strategy,oos,buy_hold_pct}], recent_trades[]`
- metrik alanları (`metrics()`): `total_return_pct, cagr_pct, sharpe, max_drawdown_pct, exposure_pct` (+ işlem listesi verilirse `trades, win_rate_pct, avg_trade_pct, profit_factor, avg_days`)

**live.json**: `start_date, start_value, start_bench, points[{date,value,bench,stock_pct}], events[{date,ticker,name,type}], holdings[{ticker,name,weight_pct}], updated`

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
- Hayatta kalma yanlılığı büyük ölçüde giderildi (noktasal evren); borsadan çıkmış hisselerin Yahoo verisi yok → hafif iyimserlik kalabilir.
- Hisse bazında tablo (`stocks[]`) ve son işlemler hâlâ bugünkü 30 hisse için (2005'ten).
- Nakit getirisi politika faizi kabul ediliyor; gerçekte para piyasası fonu getirisi vergi/masraf nedeniyle biraz düşük olabilir (`cash_rate_factor` ile ayarlanır).
- Portföy `exposure_pct` metriği anlamlı değil (günlük ortalama getiri ≠ 0 olduğu sürece ~%100 çıkar); sayfada gösterilmiyor.
- Aynı gün stop olunca o günün kapanışındaki yeni giriş sinyali atlanıyor (küçük etki).
- yfinance BIST verisinde zaman zaman eksik gün/bölünme hatası olabilir; gerçek veride kontrol edilmeli.
- Demo veri rastgeledir; demo backtest sonuçları hiçbir şey ifade etmez.

## Sıradaki adımlar
1. ~~Telegram~~ — çalışıyor (9 Kasım 2026 deneme mesajı gönderildi; kullanıcının eski QuantBIST projesiyle aynı bot ve kanal).
2. Ocak 2027'de BIST30 listesini (`BIST30` sözlüğü) Borsa İstanbul duyurusuna göre güncelle; `CANDIDATES`'e yeni büyük hisseleri ekle.
3. Fikirler: puan bileşenlerini tek tek sınamak (eğitim/test ayrımıyla), endeks EMA200 rejim filtresi (20 yıl testi),
   değerleme verisi (F/K) — veri kaynağı gerekli. Canlı portföy birkaç ay biriktikten sonra geriye dönük testle kıyasla.
