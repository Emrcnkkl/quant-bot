# Reel faiz filtresi (9 Kasım 2026)

Kural: reel faiz = o gün bilinen TCMB politika faizi − son açıklanan yıllık TÜFE.
Reel faiz `CFG["real_rate_max"]` eşiğinin üstündeyse **yeni alım yapılmaz**; açık pozisyonlar normal kurallarla kapanır.
TÜFE, ileriye bakmamak için ilgili aydan sonraki ayın 5'inden itibaren kullanılır.

| Eşik | Toplam | Eğitim (yıllık) | Test (yıllık) | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|
| Filtre yok (mevcut) | %598 | %55.8 | %25.5 | %124 | %15 | %39 | %18 | %26 |
| 0 | %792 | %58.9 | %40.5 | %124 | %15 | %41 | %43 | %32 |
| +5 | %723 | %55.8 | %39.7 | %124 | %15 | %39 | %34 | %32 |
| +10 | %578 | %55.8 | %23.1 | %124 | %15 | %39 | %15 | %26 |
| XU030 al-tut | %829 | %68.9 | %25.3 | %194 | %35 | %34 | %14 | %17 |
| Nakit (faiz) | %291 | %26.3 | %40.5 | %13 | %18 | %49 | %43 | %32 |

\* 2026 için politika faizi %38 ve TÜFE %30.89 (Aralık 2025) varsayıldı; 2026 verileri eklenmeli.

## Yorum
- Eşik 0 iken filtre Aralık 2024'ten beri neredeyse hiç alım yaptırmıyor; sonuç "o tarihten beri parayı faizde tut" ile aynı.
- Bu, 5 yıllık veride **tek bir rejim değişikliği** (negatif reel faizden pozitife geçiş) üzerine kurulu. Ekonomik mantığı var
  (pozitif reel faizde mevduat hisseye güçlü rakip), ama istatistiksel kanıt zayıf: geçmişe bakarak seçilmiş bir kural gibi davranabilir.
- Eşik +10 neredeyse hiç devreye girmiyor; +5 ile 0 arasındaki fark tek bir dönemin zamanlamasından geliyor.

## Karar
Filtre kodda hazır ama **varsayılan olarak kapalı** (`real_rate_max = None`). Güncel reel faiz `signals.json` → `regime`
alanında yayınlanıyor; sayfada bilgi olarak gösterilecek. Açıp açmamak kullanıcı kararı.
