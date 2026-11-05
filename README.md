# QuantBIST — RSI · MACD · SuperTrend

BIST hisseleri için günlük sinyal panosu. Sayfa GitHub Pages'te yayınlanır; GitHub Actions günlük olarak signals.json dosyasını üretip depoya kaydeder.

## Yayınlama
1. Bu klasördeki dosyaları GitHub deposunun kök dizinine yükleyin; index.html kökte olmalı.
2. Settings → Pages bölümünde Deploy from a branch seçin; ana branch ve /(root) dizinini yayınlayın.
3. Settings → Actions → General bölümünde Workflow permissions için Read and write permissions seçin.
4. Actions sekmesinden Günlük RSI MACD SuperTrend sinyalleri iş akışını açıp Run workflow ile ilk taramayı başlatın. Sonrakiler hafta içi otomatik çalışır.
5. Tarama tamamlanınca siteyi açın. Adres biçimi: https://KULLANICI.github.io/DEPO/

GitHub Pages yayını ve sinyal üretimi ayrı çalışır. İlk taramaya kadar başlangıç JSON dosyası görünür. Veri alınamazsa bot hata verir ve var olan sinyal dosyasını korur.

## Strateji
- RSI: 7, 10 ve 14 periyot seçenekleri; 30 altı AL, 70 üstü SAT.
- MACD: 8/21 ve 12/26; sinyal periyodu 9.
- SuperTrend: (10, 3.0) ve (14, 2.0).
- Her model, %5, %8 ve %12 iz süren stop seçenekleriyle geçmiş günlük veride karşılaştırılır; en yüksek geçmiş getirili modelin son sinyali gösterilir.
- Yalnızca RSI, MACD ve SuperTrend kullanılır. Geçmiş getiri gelecek performansını göstermez; ekran yatırım tavsiyesi değildir.

## Yerelde çalıştırma
Python 3.11 ortamında python -m pip install -r requirements.txt ve ardından python quant_bot.py çalıştırın. Çıktı signals.json dosyasına yazılır.

Bu proje için API anahtarı veya Telegram sırrı gerekmez. Depo herkese açıksa site ve sinyaller herkesçe görülebilir.
