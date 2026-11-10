# CLAUDE.md — BIST50 Teknik Sinyal Botu

Bu dosya, projeye Claude Code ile devam ederken bağlam sağlamak içindir.
Kullanıcıyla iletişim, arayüz metinleri ve kod yorumları **Türkçe**dir.

## Proje özeti
Borsa İstanbul'un en büyük 50 hissesi (işlem hacmine göre, "BIST50 benzeri") için günlük veriyle teknik analiz yapan, her hisseye −100…+100 arası
skor verip **AL / TUT / SAT** sinyali üreten, geriye dönük test (backtest) raporu çıkaran
ve sonuçları statik bir web sayfasında gösteren bir bot. Şu an **Aşama 1** tamamlandı.

## Durum (10 Kasım 2026)
- Bot gerçek veriyle çalışıyor: GitHub Actions hafta içi 18:40 (+ yedek 19:25, 21:10) çalışıyor; GitHub Pages
  (https://emrcnkkl.github.io/quant-bot/) **Actions'tan yayınlanır** (Source: GitHub Actions, `upload-pages-artifact` + `deploy-pages`).
  Depo şişmesin diye her gün yeniden üretilen `signals.json, backtest.json, valuation.json, stocks/` commit edilmez (.gitignore);
  workflow önce bunları yayındaki siteden indirir (eski veri koruması için), bot çalışır, yalnızca küçük kalıcı kayıtlar
  (`history.json, live.json, notify.json, names.json, fundamentals.json, valuation_history.csv`) commit edilir, site paketi
  (`index.html fonts img` + üretilenler + live.json) yayınlanır. `index.html/fonts/img` push'unda bot çalışmadan yeniden yayınlanır.
  Deploy işi, depoda kalmış eski üretilen dosyaları bir kez `git rm --cached` ile çıkarır. Repo: Emrcnkkl/quant-bot, ana dal `claude/laughing-dijkstra-j1eqmj`.
- Cloud oturumları için `quant-bot` ortamı Yahoo Finance ve www.tcmb.gov.tr'ye izinli → `python3 bot.py` oturumdan da çalışır (~1 dk).
- **10 Kasım 2026'da 30 → 50 hisseye geçildi.** Evren = her çeyrek son 12 ayın (252 gün) TL hacmine göre en büyük 50 hisse
  (`universe_size=50`, `universe_window=252`); sinyaller bugünkü üyeler için, liste otomatik — elle BIST listesi tutulmuyor.
  Kıyas endeksi XU030 kalır (Yahoo'da XU050 geçmişi yok). Şirket adları `NAMES`, yoksa Yahoo → `names.json`.
- **Portföy testi (sitedeki rakamlar)**: 2006'dan, noktasal evren, oynaklık ayarlı pozisyon, reel faiz filtresi (+5).
  Sonuç (6 bileşenli puanla, 10 Kasım 2026): model %23.6/yıl, düşüş −%16.7, Sharpe 0.71 · XU030 %17.7, −%64 · büyük 50 al-bekle
  %20.3, −%67 · faiz %15.5. **Enflasyondan arındırılmış**: model +%3.9/yıl, büyük 50 al-bekle +%1.0, XU030 −%1.2, faiz −%3.0.
- Veri koruması: Yahoo'dan gelen en yeni veri yayındakinden eskiyse bot hiçbir dosyayı değiştirmeden hata koduyla durur.
  `data_quality()`: eksik son gün, fiyat sınırını aşan hareket, geride kalan endeks, TCMB/kur alınamaması → signals.json `quality`,
  uyarı Telegram'a (`TELEGRAM_ADMIN_CHAT_ID` varsa oraya, yoksa kanala); evrenin %25'inden fazlası eksikse durur.
  Workflow: önce `tests/` (unittest), son deneme (21:10) ya da elle çalıştırma başarısızsa Telegram'a arıza uyarısı.
- Kıyaslar: XU030, büyük 50 al-bekle, faiz, **gram altın** (GC=F × USD/TRY ÷ 31,1035) ve **dolar**. 2006'dan altın TL'de %31.6/yıl
  ile modeli (%23.6) geçiyor (düşüşü −%34); sitede ve SSS'de açıkça gösteriliyor.
- **Sinyal isabeti** (`signal_accuracy`, signals.json `accuracy`): AL'dan 1 ay sonra ort. +%2.3 vs herhangi bir gün +%1.8;
  SAT +%0.9. Son 3 yılda fark ~0. Sinyallerin tek tek tahmin gücü zayıf; modelin değeri risk kontrolü.
- Paylaşım: og:image `img/og.png` (1200×630), ikonlar `img/`.
- **Veri kaynakları (10 Kasım 2026)**: geçmiş fiyat Yahoo (düzeltilmiş). Son günler `official_fill()` ile **Borsa İstanbul
  resmî günlük bülteni** (`thbYYYYMMDD1.zip`, ~18:25'te yayımlanır, `fetch_bulletin`) ile tamamlanır/kontrol edilir: Yahoo'da
  olmayan ya da saatlikten tahmin edilen (`PATCHED`) gün → resmî OHLCV; Yahoo son günü %0,5'ten farklıysa resmî değer (`MISMATCH`,
  6+ hissede uyarı). Son gün henüz düzeltilmediği için düzeltilmiş = ham fiyat. Bülten yoksa yedek `isy_fill()` (İş Yatırım
  `HisseTekil`; açılış yok, 18:30 öncesi bugünü kullanmaz). Endeks (XU030) bültende yok → saatlik tamamlama kalır.
  İş Yatırım/Borsa İstanbul resmî API değil; adresler değişirse bot Yahoo ile devam eder (hata durdurmaz).
  `quant-bot` cloud ortamında www.isyatirim.com.tr, www.borsaistanbul.com izinli.
- **Değerleme kaydı** (`append_valuation_history` → `valuation_history.csv`, 9 Kasım 2026'dan): her veri günü hisse başına
  close, eps, book (TL), pe, pb, div_yield, roe, mcap_bn, sector, score, signal, fund_date. Yalnızca eklenir (aynı/eski gün yazılmaz).
  Amaç: birkaç yıl sonra ucuzluk puanını noktasal veriyle test etmek (Yahoo geçmiş F/K vermiyor).
- **Ucuzluk endeksi** (bilgi amaçlı, modelden bağımsız, test edilmedi): asıl kaynak **İş Yatırım mali tabloları**
  (`isy_financials`: `MaliTablo`, exchange=TRY; grup XI_29 sanayi / UFRS_K banka+sigorta / UFRS; son 12 ay net kâr = son çeyrek +
  önceki yıl sonu − önceki yıl aynı çeyrek; net kâr 3Z ya da bankada 3ZA; özkaynak 2O) + hisse sayısı `isy_shares` (İş Yatırım
  piyasa değeri / kapanış, her gün). Haftada bir `fetch_fundamentals` → `fundamentals.json` (Yahoo .info da alınır: sektör,
  temettü verimi; ve İş Yatırım verisi yoksa yedek). `valuation()` → `valuation.json` (`source`: isyatirim|yahoo, `period`).
  Yahoo yedeğinde yabancı para raporlayanlar için çevrilmiş/çevrilmemiş PD/DD'den 0,1–15 aralığında olan seçilir. F/K>100 gösterilmez. Puan 0–100 = sektör içi (≥4 hisse, yoksa tümü) F/K ve PD/DD sıralaması ort.
- Workflow zamanlama: GitHub görevleri saatlerce geciktirebiliyor. "Beklenen veri günü" 18:00 (TR) öncesi bir önceki iş günü;
  Yahoo eski veri verirse bot hata vermeden çıkar; son denemede (21:10) veri hâlâ yoksa Telegram'a bilgi mesajı.
- Modelin değeri getiri değil **düşüş koruması** (2008: endeks −%50, model +%7). Teknik göstergelerle al-bekle'yi getiride
  belirgin geçmek gerçekçi testte mümkün olmadı; aşağıdaki "Araştırma bulguları"na bakmadan yeni kural ekleme.
- **Canlı model portföy** (`live.json`): 9 Kasım 2026'da 100.000 ₺ ile başladı; her çalıştırmada yalnızca yeni günler eklenir,
  geçmiş kayıtlar ASLA yeniden yazılmaz (`update_live`). Model mantığı değişirse eski kayıtlar olduğu gibi kalır.
- **Telegram**: AL'a giren/çıkan hisseler ve model alım/satımları (`notify`, durum `notify.json`). Token/kanal ID GitHub
  Secrets'ta (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) — depoya ya da sohbete yazılmaz. Elle deneme: Actions → Run workflow →
  "telegram_test" kutusu, ya da `python3 bot.py --telegram-test`.
- Site: koyu premium tema, genel kitleye sade dil. **Sekmeli** (tek index.html, `#…` ile yönlendirme: `route()`, `PAGES`,
  aynı anda tek sekme görünür; `#ucuzluk`/`#sss` gibi eski bağlantılar `ALIAS` ile çalışır, iç bağlantılar (#gecmis) ilgili sekmeyi açar):
  Bugün (özet kartı, AL/TUT/SAT, faiz ortamı, canlı portföy) · Sinyaller (tablo, hisse grafiği, son sinyal değişiklikleri, faiz
  filtresi uyarısı) · Performans (TL / enflasyondan arındırılmış / dolar anahtarı, yıl yıl tablo) · Değerleme · Nasıl çalışır + SSS ·
  **İletişim** (form → FormSubmit AJAX `formsubmit.co/ajax/<FORM_KEY>`; FORM_KEY FormSubmit'in rastgele anahtarı, form
  etkinleştirildi, e-posta adresi sayfada yazmaz; başarısızsa "tekrar deneyin" mesajı). Grafikler sekme açılınca yeniden çizilir (`redraw`). Tasarım referansı kullanıcının diğer projesi (emrcnkkl.github.io/anlik_bot).

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
| 30 → 50 hisse | Sharpe 0.34→0.54 (2006–20), 0.73→0.90 (2021–26); 31–50. sıradakilerde de çalışıyor | **eklendi** |
| Hacim penceresi 3 ay → 12 ay | aynı performans, liste çeyrekte 6.7 yerine 2.9 hisse değişiyor | **12 ay** |
| Bileşen testi (`research.py --bilesen`) | ema_cross ve relative çıkınca iki dönemde de iyileşiyor; macd, rsi, adx, breakout, volume gerekli; ema200 sınırda | **ema_cross + relative çıkarıldı** (`ACTIVE`) |
| Ağırlık yöntemleri (`research.py --agirlik`) | puana göre eğim: Sharpe 0.53→0.58 / 1.00→1.13 ama düşüş −16.7→−18.9 (2 puan sınırını az aştı); diğerleri fark yok/kötü | eklenmedi, kullanıcıya soruldu |

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
├── signals.json       # güncel sinyaller (bot üretir; depoda değil, Pages'e yüklenir)
├── backtest.json      # backtest raporu (bot üretir; depoda değil)
├── stocks/TICKER.json # hisse detay grafiği verisi, son 500 gün (bot üretir; depoda değil)
├── valuation_history.csv # günlük değerleme kaydı (yalnızca eklenir)
├── live.json          # canlı model portföy kaydı (yalnızca eklenir, geçmişi değişmez)
├── notify.json        # son Telegram bildirimi tarihi
├── names.json         # Yahoo'dan alınmış şirket adı önbelleği (NAMES'te olmayanlar için)
├── valuation.json     # ucuzluk endeksi (her gün) · fundamentals.json: temel veri önbelleği (haftalık)
├── tests/test_bot.py  # birim testler (python3 -m unittest discover -s tests); workflow her çalıştırmada koşar
├── img/               # og.png paylaşım görseli, ikonlar
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
| Veri kaynağı | yfinance (son gün Borsa İstanbul bülteniyle kontrol, yedek İş Yatırım; bilanço İş Yatırım), semboller `XXXXX.IS`, `auto_adjust=True`, 2004'ten (2005 öncesi atılır, `fix_jumps`); benchmark `XU030.IS`; ~157 seri, Actions'ta ~1–2 dk |
| Strateji tipi | Çoklu indikatör birleşik skoru (tek strateji, parametre optimizasyonu YOK — aşırı uyumdan kaçınmak için) |
| Yön | Sadece long (açığa satış yok). SAT = çık / uzak dur anlamında |
| Çıktılar | Python bot + signals.json, backtest raporu, basit web sayfası |
| Otomasyon | GitHub Actions, hafta içi 18:40 TR (`40 15 * * 1-5` UTC) + yedek 19:25 ve 21:10; o günün verisi varsa yedekler atlanır. Kalıcı kayıtları commit eder (push öncesi `pull --rebase --autostash`), siteyi Pages'e yükler |
| Hukuki | Her çıktıda "yatırım tavsiyesi değildir" uyarısı (SPK); disclaimer metni `bot.py` → `meta["disclaimer"]` |

### İsim kaynağı — `BIST30` sözlüğü (artık evreni belirlemiyor, yalnızca şirket adları için; Ekim–Aralık 2026 listesi)
AEFES AKBNK ASELS ASTOR BIMAS EKGYO ENKAI EREGL FROTO GARAN GUBRF ISCTR KCHOL KRDMD MGROS
PETKM PGSUS SAHOL SASA SISE TAVHL TCELL THYAO TOASO TRALT TRMET TTKOM TUPRS VAKBN YKBNK
Evren `pit_membership` ile otomatik belirlenir; `CANDIDATES` (156 aday) ara ara yeni büyük hisselerle genişletilmeli.

### Skor (−100…+100) — `score_frame()`, ağırlıklar `W`, puana girenler `ACTIVE` (kalanlar ×100/75 ölçeklenir)
| Bileşen | Puan | Kural |
|---|---|---|
| ema200 | ±15 | Kapanış EMA200 üstü/altı |
| ema_cross | (±15) | EMA20 > / < EMA50 — **puanda değil** (yalnızca gerekçe metni) |
| adx | ±10 | DI+/DI− yönü × ADX gücü (ADX 15→0, 30+→tam) |
| rsi | +15/0/−15/−5/+5 | 55–78 / 45–55 / 25–45 / >78 aşırı alım / <25 aşırı satım |
| macd | ±15 | Histogram işareti ±10, eğimi ±5 |
| volume | ±10 | Hacim > 1.5× 20g ort. ise günün yönünde |
| breakout | ±10 | Dünkü 20g zirve üstü / dip altı kapanış |
| relative | (±10) | 63g getiri − XU030 63g getirisi — **puanda değil** |

Sinyal: skor ≥ +40 → AL, ≤ −40 → SAT, arası TUT (`CFG["buy_threshold"]`, `CFG["sell_threshold"]`).
Bilgi amaçlı stop = kapanış − 2.5×ATR, hedef = kapanış + 4×ATR. Pozisyondaysa iz süren stop gösterilir.

### Backtest kuralları — `backtest()`
- Sinyal t günü kapanışında; işlem **t+1 açılışında** (ileriye bakma yanlılığı yok).
- Giriş: skor ≥ 40. Çıkış: skor < 0 (ertesi açılış) **veya** 2.5×ATR iz süren stop gün içinde (fiyat = min(açılış, stop)).
- Maliyet tek yön %0.10 komisyon + %0.05 kayma.
- İlk 210 gün ısınma (EMA200). Son %30 örneklem dışı (OOS) ayrı raporlanır.
- Portföy (`sized_portfolio`): 2006'dan, noktasal evren (her çeyrek son 12 ayın TL hacmine göre ilk 50, `pit_membership`); temel pay 1/50,
  oynaklık ayarlı (× medyan ATR% / hisse ATR%, 1/3–2), toplam ≤ %100; hisseye yalnızca evrendeyken girilir. Sinyal yokken pay nakitte ve **TCMB politika faizi** kazanır (`POLICY_RATES` tablosu, `cash_returns()`, takvim günü bazında bileşik). Verisi kısa olan hissenin payı da o günlerde nakitte. XU030 al-tut ve saf nakit ile kıyaslanır.
- Sharpe, nakit getirisinin üzerindeki fazla getiriyle hesaplanır (`metrics(..., rf=cash)`); nakdin kendi Sharpe'ı `None`.
- `state` alanı backtest durum makinesinden gelir: `POZİSYONDA`, `GİRİŞ` (yarın al), `ÇIKIŞ` (yarın sat), `BEKLE`.

### Tüm ayarlar
`bot.py` başındaki `CFG` sözlüğü: warmup_days, buy/sell_threshold, exit_score,
stop_atr, target_atr, commission, slippage, oos_fraction, min_bars, cash_rate_factor (0 = faiz yok), changes_days (30),
history_start, backtest_start (2006), universe_size (50), universe_window (252), vol_sizing (True), vol_cap (2), jump_limit (0.25),
real_rate_max (5.0; None = kapalı; reel faiz bunun üstündeyse yeni alım yok — `entry_allowed()`, `macro_frame()`),
exit_rule ("score" varsayılan | ema50 | cross | ema200 | regime), entry_rule ("score" | ema200), stop_atr=None → stop yok.

`POLICY_RATES` (2010-05 öncesi `POLICY_RATES_PRE2010` = gecelik borç alma, sonrası 1 hafta repo; 2003'ten) ve `CPI_YOY` (yıllık TÜFE, 2005'ten) yerleşik tablolar; gerçek çalıştırmada
`fetch_macro()` ikisini de tcmb.gov.tr'den canlı çekip günceller (urllib + regex, ek bağımlılık yok). Başarısızsa yerleşik tablo kalır,
`regime.source` bunu gösterir. Yerleşik tabloları ara ara canlı veriyle eşitle.

## JSON şemaları (index.html bunlara bağımlı — alan adı değiştirirken sayfayı da güncelle)
**signals.json**: `generated_at, data_date, demo, universe, thresholds{buy,sell}, disclaimer, quality{ok,warnings[],notes[],checked}, accuracy{since,recent_since,horizons,all|recent{AL,SAT,TUM}{5,21,63}{n,avg,median,pos},by_ticker{T:{n,avg21,pos21}}}, regime{policy_rate,cpi_yoy,real_rate,policy_date,cpi_month,source,filter_max,blocking}, counts{AL,TUT,SAT}, signals[], changes_days, changes_dates[], changes[]`
- `changes[]`: `date, ticker, name, from, to, score, close, since_pct` (yeniden eskiye)
- `signals[]`: `ticker, name, date, close, change_pct, score, signal, state, score_5d_ago, components{ema200,...}, rsi, adx, atr_pct, stop, target, position{entry_date,entry_price,last_price,stop,pnl_pct,days}|null, reasons[]`

**backtest.json**: meta alanları + `backtest_universe, avg_exposure_pct, fx_start, units{real,usd}{strategy,benchmark,universe,cash}{full,oos}, settings, period{start,end,oos_start}, portfolio{full,oos,benchmark_full,benchmark_oos,cash_full,cash_oos}, portfolio{...,universe_full,universe_oos,gold_full,gold_oos,dollar_full,dollar_oos}, equity_curve[{date,strategy,benchmark,cash,universe,cpi,usd,gold}] (haftalık), yearly[{year,from,to,partial,strategy,benchmark,cash,universe,cpi_pct,usd_pct,gold_pct}], stocks[{ticker,name,strategy,oos,buy_hold_pct}], recent_trades[]`
- metrik alanları (`metrics()`): `total_return_pct, cagr_pct, sharpe, max_drawdown_pct, exposure_pct` (+ işlem listesi verilirse `trades, win_rate_pct, avg_trade_pct, profit_factor, avg_days`)

**live.json**: `start_date, start_value, start_bench, points[{date,value,bench,stock_pct}], events[{date,ticker,name,type}], holdings[{ticker,name,weight_pct}], notes[{date,text}], updated`

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
- Hisse bazında tablo (`stocks[]`) ve son işlemler bugünkü 50 hisse için (2005'ten, noktasal değil).
- Nakit getirisi politika faizi kabul ediliyor; gerçekte para piyasası fonu getirisi vergi/masraf nedeniyle biraz düşük olabilir (`cash_rate_factor` ile ayarlanır).
- Portföy `exposure_pct` metriği anlamlı değil (günlük ortalama getiri ≠ 0 olduğu sürece ~%100 çıkar); sayfada gösterilmiyor.
- Aynı gün stop olunca o günün kapanışındaki yeni giriş sinyali atlanıyor (küçük etki).
- yfinance BIST verisinde zaman zaman eksik gün/bölünme hatası olabilir; gerçek veride kontrol edilmeli.
- Demo veri rastgeledir; demo backtest sonuçları hiçbir şey ifade etmez.

## Sıradaki adımlar
1. ~~Telegram~~ — çalışıyor (9 Kasım 2026 deneme mesajı gönderildi; kullanıcının eski QuantBIST projesiyle aynı bot ve kanal).
2. `CANDIDATES`'e yeni halka arz olmuş büyük hisseleri ara ara ekle (evren otomatik; elle BIST listesi tutulmuyor).
3. Fikirler: puan bileşenlerini tek tek sınamak (eğitim/test ayrımıyla), endeks EMA200 rejim filtresi (20 yıl testi),
   değerleme verisi (F/K) — veri kaynağı gerekli. Canlı portföy birkaç ay biriktikten sonra geriye dönük testle kıyasla.
