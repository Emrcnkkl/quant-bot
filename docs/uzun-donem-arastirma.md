# Uzun dönem araştırması ve kayan pencereli test (9 Kasım 2026)

`python3 research.py` — 2005–2026 günlük veri (Yahoo), faiz 2003'ten (TCMB: 2010 öncesi gecelik borç alma, sonrası 1 hafta repo),
TÜFE 2005'ten. Değerlendirme dönemi 2009–2026 (18 yıl); 2006–2008 ilk seçim için öğrenme verisi.
Veri düzeltmesi: %25'i aşan tek günlük sıçramalar (MGROS 2009 +%304, PGSUS 2013 +%53, KCHOL 2007, GUBRF 2009, TCELL 2005)
düzeltilmemiş sermaye artırımı sayılıp nötrlendi.

## 2009–2026 özet
| Strateji | Yıllık | En büyük düşüş | Sharpe (faiz üstü) | Endeksi geçtiği yıl | Faizi geçtiği yıl |
|---|---|---|---|---|---|
| mevcut (skor gir / skor<0 çık / 2.5 ATR) | %24.7 | −%20.9 | 0.70 | 10/18 | 9/18 |
| kesişim (skor gir / EMA20<EMA50 çık) | %29.4 | −%21.5 | 0.79 | 11/18 | 10/18 |
| rotasyon: skora göre en iyi 5 | %15.2 | −%49.2 | 0.12 | 8/18 | 9/18 |
| rotasyon: skora göre en iyi 8 | %20.5 | −%38.3 | 0.31 | 9/18 | 10/18 |
| **rotasyon: 12-1 ay momentuma göre en iyi 5** | **%47.3** | −%40.6 | **0.97** | 15/18 | 13/18 |
| rotasyon: momentuma göre en iyi 8 | %41.3 | −%40.3 | 0.88 | 14/18 | 12/18 |
| kayan pencereli seçim (her yıl geçmişe göre en iyi) | %32.9 | −%32.0 | 0.79 | 12/18 | 10/18 |
| **bugünkü 30 hisse, eşit ağırlık al-bekle** | **%38.2** | −%32.8 | 0.84 | 17/18 | 12/18 |
| XU030 (gerçek endeks) | %23.4 | −%35.7 | 0.39 | – | 11/18 |
| Faiz | %15.3 | 0 | – | 7/18 | – |

Yıl yıl tablo `research.json` → `yearly` içinde.

## Bulgular
1. **Bugünkü listeyle test yapmak sonuçları çok şişiriyor.** Bugünkü 30 hisseyi geçmişte eşit ağırlıkla tutmak, gerçek endeksten
   yılda ~15 puan fazla getiriyor ve 18 yılın 17'sinde endeksi geçiyor. Bugün BIST30'da olanlar, geçmişte yükselmiş oldukları için oradalar.
   → Endeksle (XU030) kıyas yanıltıcı; adil kıyas aynı hisse evreninin eşit ağırlıklı al-bekle'si (%38.2).
   → Sitede gösterilen "100.000 ₺ → ~700.000 ₺" da bu yanlılığı içeriyor.
2. **Mevcut stratejinin asıl değeri düşüşten korumak:** 2008'de +%8 (endeks −%50), 2018'de −%3 (endeks −%20). Ama kendi evreninin
   al-bekle'sinden yılda ~13 puan az getiriyor.
3. **Skora göre sıralama işe yaramıyor:** skor, iyi bir "ne zaman" göstergesi ama hisseleri birbirine göre sıralamada kötü.
4. **12-1 ay momentumu rotasyonu en güçlü sonuç:** evrenin al-bekle'sini de geçiyor (%47 vs %38), Sharpe en yüksek. Ama düşüşü −%40
   ve bu sonuç **bugünkü listeden en çok etkilenecek strateji** (geçmişte en çok yükselenleri seçiyor; bugünkü liste de onlardan oluşuyor).
5. Kayan pencereli seçim çoğunlukla "kesişim"i seçti; sabit bir kuraldan belirgin iyi değil.

## Karar ve sıradaki adım
Bot ayarları değişmedi. Momentum rotasyonuna geçmeden önce **geçmiş dönemin gerçek hisse evreniyle** (her dönemde o zamanki büyük/likit
hisseler) test şart. Plan: geniş bir aday listesi (BIST100) içinden her çeyrek işlem hacmine göre en büyük 30'u seçen bir evren kurmak;
bu evrenin eşit ağırlıklı al-bekle'si XU030'a yaklaşıyorsa yanlılık büyük ölçüde giderilmiş demektir. Sonra rotasyon yeniden test edilir.
Sınırlama: Yahoo'da borsadan çıkmış hisselerin verisi genelde yok; yanlılık tamamen sıfırlanamaz.
