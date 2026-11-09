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

---

# Ek: Noktasal evrenle yeniden test (`python3 research.py --pit`)

Evren: 181 adaydan Yahoo'da verisi olan 156 hisse (borsadan çıkmış 25 hisse — Finansbank, Petrol Ofisi, Trakya Cam,
Asya Katılım vb. — Yahoo'da yok). Her çeyrek başında önceki 3 ayın ortalama TL işlem hacmine göre ilk 30 hisse o çeyreğin evreni.
2005'ten beri 100 farklı hisse en az bir kez evrene girdi; çeyrek başına ortalama 4.4 hisse değişiyor.
Bugünkü evren gerçek BIST30 ile 25/30 örtüşüyor → yöntem gerçek endeks seçimine yakın.

**Doğrulama:** Evrenin eşit ağırlıklı al-bekle'si yıllık %25.9, gerçek XU030 %23.4. Fark ~15 puandan ~2.5 puana indi
(kalan fark: eşit ağırlık + borsadan çıkmış hisselerin eksikliği). Yanlılık büyük ölçüde temizlendi.

## 2009–2026
| Strateji | Yıllık | En büyük düşüş | Sharpe | Endeksi geçtiği yıl | Evreni geçtiği yıl |
|---|---|---|---|---|---|
| mevcut | %20.9 | −%24.1 | 0.43 | 9/18 | 8/18 |
| kesişim | %23.0 | −%22.5 | 0.46 | 9/18 | 8/18 |
| rotasyon: skora göre en iyi 8 | %12.1 | −%53.8 | 0.00 | 6/18 | 2/18 |
| rotasyon: momentum en iyi 5 | %26.3 | −%57.7 | 0.44 | 9/18 | 9/18 |
| rotasyon: momentum en iyi 8 | %26.5 | −%53.2 | 0.46 | 7/18 | 10/18 |
| rotasyon: momentum en iyi 10 | %26.8 | −%49.8 | 0.47 | 10/18 | 8/18 |
| kayan pencereli seçim | %20.8 | −%24.1 | 0.37 | 8/18 | 8/18 |
| evren eşit ağırlık al-bekle | %25.9 | −%39.2 | 0.46 | 8/18 | – |
| XU030 | %23.4 | −%35.7 | 0.39 | – | 10/18 |
| Faiz | %15.3 | 0 | – | 7/18 | 8/18 |

## Sonuç
1. **Momentum rotasyonunun %47'lik getirisinin neredeyse tamamı yanlılıktı.** Doğru evrenle %26–27; al-bekle ile aynı, düşüşü −%50–58 (daha kötü).
   Bota eklenmeyecek.
2. **Mevcut strateji gerçekçi testte:** yıllık %21, düşüş −%24 (al-bekle −%39, endeks −%36). Risk başına getirisi (Sharpe 0.43–0.46)
   al-bekle ile aynı; yani **getiri üstünlüğü yok, değeri düşüşleri yarıya indirmesi** (2008: +%4, evren −%60).
3. Kesişim çıkışı uzun dönemde biraz daha iyi (%23 / −%22.5) ama son 1.5 yılda mevcut kuraldan kötü ve fark küçük → kural değişmiyor.
4. Kayan pencereli seçim sabit kuraldan iyi değil → geçmişe göre kural değiştirmek değer katmıyor.

Bot ayarları değişmedi. Sitedeki geriye dönük test hâlâ bugünkü listeyle yapılıyor (yanlılık uyarısı sitede var).

---

# Ek 2: Pozisyon büyüklüğü (`python3 research.py --sizing`, noktasal evren)

Önceden belirlenen 8 çeşit: temel pay 1× / 1.5× / 2× / 3× (sermayenin m/30'u), her biri oynaklık ayarlı ve ayarsız.
Oynaklık ayarı: pay × (evren medyan ATR% / hissenin ATR%), 1/3–2 arası; toplam hisse payı %100'ü aşmaz (kaldıraç yok).
Karar kuralı (önceden): eğitimde (2009–2020) düşüşü evren al-bekle'den (−%39) derin olmayanlar arasında en yüksek eğitim getirisi.

| Çeşit | Ort. hisse payı | Eğitim yıllık / düşüş / Sharpe | Test (2021–26) yıllık / düşüş / Sharpe |
|---|---|---|---|
| 1× (eski) | %46 | %13.4 / −%15.1 / 0.41 | %38.1 / −%24.1 / 0.48 |
| **oynaklık 1×** | %46 | **%14.4 / −%14.2 / 0.51** | **%40.2 / −%24.5 / 0.58** |
| 1.5× | %64 | %13.8 / −%26.2 / 0.36 | %35.1 / −%32.9 / 0.32 |
| oynaklık 1.5× (kuralın seçimi) | %63 | %14.9 / −%22.8 / 0.45 | %38.3 / −%32.4 / 0.43 |
| 2× / 3× | %73 / %82 | daha kötü | daha kötü |
| evren al-bekle | %100 | %19.2 / −%39.2 / 0.48 | %41.0 / −%28.3 / 0.43 |

- **Oynaklık ayarı her iki dönemde de iyileştirdi** (Sharpe 0.41→0.51 ve 0.48→0.58, getiri arttı, düşüş aynı) → **bota eklendi** (`vol_sizing=True`).
- **Payı büyütmek işe yaramadı:** kuralın seçtiği oynaklık 1.5× testte oynaklık 1×'ten hem az kazandırdı hem derin düştü → eklenmedi.
  Sinyaller aynı anda geldiği için pay büyüyünce risk getiriden hızlı artıyor; faizdeki para da kaybediliyor.

# Botun geriye dönük testi artık noktasal evrenle (2006–bugün)
`bot.py` her gün 156 aday hisseyi indirir, her çeyrek en büyük 30'u seçer, oynaklık ayarlı pozisyonla 2006'dan test eder.
İlk sonuç (9 Kasım 2026): model yıllık %20.0 / en büyük düşüş −%24.5; XU030 %17.7 / −%63.5; büyük 30 al-bekle %18.5 / −%68.0; faiz %15.5.
