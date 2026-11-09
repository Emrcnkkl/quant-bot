# Parametre duyarlılık analizi (9 Kasım 2026)

`python3 sensitivity.py` — 36 ayar kombinasyonu (AL eşiği 30/40/50 × çıkış skoru −20/0/+20 × stop 2/2.5/3/4 ATR).
Dönem 2021-09-13 – 2026-11-06; ilk %70 eğitim (IS), 2025-04-21 sonrası test (OOS). Nakit = TCMB politika faizi (2026 için %38 varsayıldı).

| | Yıllık getiri eğitim | Yıllık getiri test | Test maks. düşüş |
|---|---|---|---|
| Mevcut ayar (40 / 0 / 2.5) | %55.8 | %25.5 | −%6.6 |
| Eğitimde en iyi ayar (30 / 0 / 2.0) | %60.0 | %24.6 | −%7.1 |
| 36 ayarın test aralığı | %49–65 | %20.4 – %27.8 (medyan %25.2) | −%5 … −%10 |
| XU030 al-tut | %68.9 | %25.3 | −%22.3 |
| Nakit (faiz) | %26.3 | %40.5 | 0 |

## Bulgular
- **Sonuç ayarlara duyarlı değil:** 36 ayarın hepsi test döneminde %20–28 bandında. Tek bir şanslı ayara bağlı bir sonuç yok.
- **Ayar oynamak işe yaramıyor:** Eğitimde iyi olan ayar testte iyi olmuyor (sıralama korelasyonu −0.15). Eğitimde en iyi ayar testte mevcut ayardan biraz kötü.
- **Endeksle başa baş, çok daha az düşüşle:** Test döneminde 36 ayarın 16'sı endeksi geçiyor; düşüşler endeksin üçte biri civarında.
- **Hiçbir ayar faizi geçmiyor (0/36):** Test döneminde BIST30'un kendisi faizin altında kaldı. Sadece alım yapan bir hisse stratejisi, ayarı ne olursa olsun bunu telafi edemez.
- Tüm dönemde de hiçbir ayar endeks al-tut'u geçmiyor (en iyi %710, endeks %829); fark 2022–2023 negatif reel faiz döneminden geliyor.

## Karar
Mevcut ayarlar (40 / 0 / 2.5) korunuyor. İyileştirme parametrede değil, "ne zaman hisse, ne zaman nakit" kararında aranmalı (rejim / reel faiz filtresi).
