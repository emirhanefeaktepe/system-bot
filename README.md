# System Bot · BIST hayali portföy sistemi

System Bot, Borsa İstanbul'da BIST 30 hisselerini tarayan, 5.000 TL hayali parayla
kendi kurallarına göre sanal alım-satım yapan ve her şeyi Telegram'dan bildiren bir sistemdir.

Gerçek para kullanmaz, aracı kuruma bağlanmaz. Amacı, hangi kuralların gerçekten
işe yaradığını risksiz şekilde ölçmektir. Yatırım tavsiyesi değildir.

## Nasıl çalışır

| Saat (TR) | Ne olur |
|---|---|
| 10:20 - 17:50, 30 dakikada bir | Dün seçilen hisseler sanal olarak alınır. Stop ve hedefler kontrol edilir. Elindeki hisse %4'ten fazla oynarsa haber verilir. |
| 18:40 | Gün sonu: süre ve trend çıkışları, 30 hissenin taranması, yarın alınacakların seçilmesi, rapor. |
| Cuma 18:40 | Gün sonu raporuna haftalık karne eklenir. |

Veriler Yahoo Finance'ten gelir ve yaklaşık 15 dakika gecikmelidir. Saniyelik veri yoktur.

## Vadeler ve stratejiler

**Güncel durum:** 1 haftalık strateji kapalı (2024-2026 testinde zarar ettirdi). Para açık 4 stratejiye bölünür.
**Piyasa filtresi (kapalı):** BIST 30 kendi 200 günlük ortalamasının altındayken yeni alım yapmama kuralı denendi, 2024-2026 testinde sonucu kötüleştirdiği için kapatıldı. Açık pozisyonlar kendi kurallarıyla yönetilmeye devam eder. İkisi de `config.py` içinden açılıp kapatılabilir.

Her strateji kendi bölmesiyle işlem yapar.
Böylece hangi vadenin işe yaradığı ayrı ayrı görülür.

| Vade | Strateji | Alım kuralı | Çıkış |
|---|---|---|---|
| 1 hafta | Kısa vadeli tepki | Yükseliş trendinde (fiyat > 50 > 100 günlük ort.) RSI(3) 15'in altına düşerse | 5 günlük ortalamanın üstünde kapanış, stop 2 ATR, hedef 2 ATR, en fazla 5 gün |
| 10 gün | Hacimli kırılım | 20 günlük zirve, normalin 1,5 katı hacimle kırılırsa | Stop 2 ATR, hedef 3 ATR, en fazla 10 gün |
| 20 gün | Trend içi geri çekilme | 20 > 50 > 100 günlük ort. sıralıyken fiyat 20 günlüğe değip yukarı dönerse | Stop 2,5 ATR, hedef 4 ATR, en fazla 20 gün |
| 50 gün | Orta vade momentum | Son 3 ayın en güçlü 5 hissesinden trendi bozulmamış olanlar | 50 günlük ortalamanın altında kapanış, stop 3 ATR, en fazla 50 gün |
| 100 gün | Uzun vade trend | 200 günlük ortalamanın üstünde, son 6 ayın en güçlü 5 hissesi | 100 günlük ortalamanın altında kapanış, stop 4 ATR, en fazla 100 gün |

ATR, hissenin günlük ortalama oynaklığıdır. Stop mesafesi her hissenin kendi oynaklığına göre ayarlanır.

## Kurulum

### 1. Telegram botu
1. Telegram'da **@BotFather**'ı aç, `/newbot` yaz, bota bir isim ver.
2. Verdiği **token**'ı kaydet (`123456:ABC...` gibi).
3. Kendi botunu bul ve ona herhangi bir mesaj gönder.
4. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini aç. `"chat":{"id": ...}` içindeki sayı senin **chat id**'n.

### 2. GitHub
1. github.com'da ücretsiz hesap aç ve `system-bot` adında yeni bir depo (repository) oluştur.
2. Bu klasördeki dosyaları depoya yükle.
3. Depoda **Settings → Secrets and variables → Actions → New repository secret** ile iki sır ekle:
   - `TELEGRAM_TOKEN`: BotFather'ın verdiği token
   - `TELEGRAM_CHAT_ID`: getUpdates'teki sayı
   - (İsteğe bağlı) `ANTHROPIC_API_KEY`: gün sonu raporuna Claude yorumu eklemek için. Ücretlidir, şart değil.

### 3. İlk çalıştırma
1. Depoda **Actions** sekmesine gir, iş akışlarını etkinleştir.
2. **System Bot → Run workflow** ile önce `telegram` seç. Telegram'a "System Bot bağlandı" mesajı gelmeli.
3. Sonra `backtest` çalıştır. Kuralların son 3 yıldaki sonucu Telegram'a gelir.
4. Bundan sonrası otomatik: hafta içi her gün çalışır.

### 4. Durum sayfası (isteğe bağlı)
**Settings → Pages → Deploy from a branch → main / docs**. Portföy, açık pozisyonlar ve fırsat
listesi bir web sayfasında görünür. Not: depo herkese açık değilse GitHub Pages ücretli plan ister.

## Ayarlar
Her şey `config.py` içinde: hisse listesi, başlangıç parası, pozisyon sayısı, risk oranı, uyarı eşiği.
BIST 30 listesi 3 ayda bir değişir; liste 1 Ekim - 31 Aralık 2026 dönemine göredir.

## Bilgisayarda denemek
```
pip install -r requirements.txt
python run.py backtest --demo --dry   # rastgele veriyle, mesaj göndermeden
python run.py eod --dry               # gerçek veriyle gün sonu, ekrana yazar
```

## Sınırlar
- Veri 15 dakika gecikmeli ve ücretsiz kaynaktan. Yahoo bazen sunucuları sınırlayabilir; o gün çalışma atlanır.
- GitHub zamanlanmış işleri birkaç dakika geç başlatabilir.
- Geçmiş testte iyi görünen kural gelecekte de iyi çalışmayabilir. En az 20-30 sanal işlem birikmeden sonuca güvenme.
- 5.000 TL beşe bölündüğünde pahalı hisselerden ancak 1-2 lot alınabilir; bütçe yetmeyen sinyal atlanır.
