# Kural deneyleri: al-bekle'yi geçen hisse sayısı (9 Kasım 2026)

`python3 experiments.py` — 9 kural seti, önceden belirlendi. Eğitim: 13 Eyl 2021 – 21 Nis 2025, test: 22 Nis 2025 – 6 Kas 2026.
"Yener" = o dönemde stratejinin (nakit faiziyle birlikte) hissenin kendi al-bekle getirisini geçtiği hisse sayısı (30 hisse).

| Kural | Yener eğitim | **Yener test** | Yener tüm | Yıllık eğitim | Yıllık test | Test maks. düşüş | Piyasada |
|---|---|---|---|---|---|---|---|
| **mevcut** (skor ≥40 gir, <0 çık, 2.5 ATR) | 4 | **18** | 6 | %55.6 | **%25.8** | **−%6.6** | %52 |
| gevşek (skor <−20 çık, 4 ATR) | 4 | 13 | 6 | %63.0 | %21.5 | −%9.5 | %61 |
| sat_cik (yalnız SAT'ta çık, stop yok) | 7 | 12 | 8 | %74.0 | %15.6 | −%15.1 | %71 |
| ema50 (kapanış < EMA50 çık) | 6 | 14 | 5 | %62.9 | %24.6 | −%9.3 | %56 |
| kesişim (EMA20 < EMA50 çık) | **8** | 12 | **9** | %70.6 | %20.1 | −%12.2 | %68 |
| kesişim + 4 ATR stop | 5 | 13 | 6 | %61.5 | %19.8 | −%11.1 | %60 |
| ema200 (kapanış < EMA200 çık) | 7 | 12 | 7 | %72.2 | %18.0 | −%12.6 | %74 |
| rejim (endeks yükselişte kesişim, değilse skor) | 2 | 17 | 6 | %53.9 | %26.3 | −%7.3 | %52 |
| klasik 200 gün kuralı | 7 | 6 | 6 | %76.2 | %12.1 | −%17.2 | %80 |
| XU030 al-bekle | – | – | – | %69.1 | %27.0 | −%22.3 | %100 |
| Faiz | – | – | – | %26.4 | %39.9 | 0 | – |

## Bulgular
- **"6/30" tablosu dönemin başındaki boğa piyasasından geliyor.** Mevcut strateji eğitim döneminde 4/30, ama **test döneminde 18/30** hissede al-bekle'yi geçiyor.
- Daha uzun piyasada kalan kurallar eğitimde (2022–23 yükselişi) daha çok hissede kazanıyor (en iyi: kesişim 8/30), ama testte geriliyor (12/30) ve portföy getirisi düşüyor (%20 vs %26).
- Yani "al-bekle'yi geçen hisse sayısı" piyasa rejimine bağlı: güçlü yükselişte piyasada az kalan her strateji kaybeder, yatay/düşen piyasada kazanır. Hiçbir kural iki dönemi birden iyileştirmiyor.
- Eğitime göre seçilecek kural (kesişim) testte mevcut kuraldan kötü → kural değiştirmek geçmişe uydurma olur.

## Karar
Mevcut kural korunuyor. Yeni seçenekler (`exit_rule`, `entry_rule`, `stop_atr=None`) kodda kaldı, varsayılan değişmedi.
