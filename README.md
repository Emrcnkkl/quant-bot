# BIST30 Teknik Sinyal Botu (Aşama 1)

BIST 30 hisseleri için günlük veriyle çoklu indikatör skoru hesaplar, AL / TUT / SAT sinyali üretir ve geriye dönük test raporu çıkarır.

## Dosyalar
| Dosya | Açıklama |
|---|---|
| `bot.py` | Veri indirme, indikatörler, skor, backtest, JSON çıktıları |
| `index.html` | Sinyal ve backtest sayfası (JSON dosyalarını okur) |
| `signals.json` | Güncel sinyaller |
| `backtest.json` | Geçmiş performans raporu |
| `history.json` | Günlük sinyal geçmişi (gerçek veriyle her çalıştırmada eklenir) |
| `bot.yml` | GitHub Actions: hafta içi 18:40'ta otomatik çalıştırma. Repoda `.github/workflows/bot.yml` yoluna taşıyın |

## Çalıştırma (Mac Terminal)
```bash
cd ~/Desktop/"YENİ PROJE"
python3 -m pip install -r requirements.txt
python3 bot.py           # gerçek veri
python3 -m http.server   # sonra tarayıcıda http://localhost:8000
```
`python3 bot.py --demo` internet olmadan sentetik veriyle test eder.

> `index.html` dosyasını çift tıklayarak açarsanız tarayıcı JSON dosyalarını okuyamaz; yukarıdaki gibi yerel sunucu ya da GitHub Pages kullanın.

## Strateji özeti
- Skor −100…+100: Trend (EMA200, EMA20/50, ADX) 40 · Momentum (RSI, MACD) 30 · Hacim 10 · 20g kırılım 10 · XU030'a göre göreli güç 10
- Skor ≥ +40 → AL, ≤ −40 → SAT, arası TUT
- Backtest: sadece alış, ertesi gün açılışta işlem, %0.15 tek yön maliyet, 2.5×ATR iz süren stop, skor < 0 olunca çıkış, son %30 örneklem dışı
- Ayarlar `bot.py` başındaki `CFG` sözlüğünde; BIST30 listesi her çeyrek güncellenmeli (`BIST30` sözlüğü).

**Uyarı:** Çıktılar algoritmik teknik analizdir, yatırım tavsiyesi değildir.
