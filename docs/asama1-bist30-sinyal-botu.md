# Aşama 1 — BIST30 Sinyal Botu (9 Kasım 2026)

Kararlar: günlük veri (yfinance .IS), çoklu indikatör skoru, çıktılar = bot.py + signals.json + backtest.json + index.html.
Dosyalar: Masaüstü/YENİ PROJE (bot.py, index.html, README.md, requirements.txt, bot.yml → .github/workflows/).

BIST30 listesi (Eki–Ara 2026; TRMET girdi, DSTKF çıktı): AEFES AKBNK ASELS ASTOR BIMAS EKGYO ENKAI EREGL FROTO GARAN GUBRF ISCTR KCHOL KRDMD MGROS PETKM PGSUS SAHOL SASA SISE TAVHL TCELL THYAO TOASO TRALT TRMET TTKOM TUPRS VAKBN YKBNK. Ocak 2027'de güncellenmeli.

Skor (−100…+100): EMA200 ±15, EMA20/50 ±15, ADX/DI ±10, RSI ±15, MACD hist ±15, hacim ±10, 20g kırılım ±10, XU030'a göre 63g göreli güç ±10.
Sinyal: ≥+40 AL, ≤−40 SAT, arası TUT. Stop 2.5×ATR (iz süren), hedef 4×ATR.
Backtest: long-only, ertesi gün açılışta işlem, %0.10 komisyon + %0.05 kayma, skor<0 çıkış, son %30 OOS, portföy 1/30 eşit ağırlık.

Durum: Kod sentetik veriyle (--demo) test edildi; oturumdan Yahoo'ya erişim olmadığı için gerçek veri testi kullanıcının makinesinde yapılacak.
Bilinen sınırlamalar: hayatta kalma yanlılığı (bugünkü liste), nakitte faiz yok, parametreler optimize edilmedi.
