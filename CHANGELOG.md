# Değişiklikler

## 0.2.0 (2026-10-13)

Yeni sayfalar ve dil:

- **Hedefler sayfası.** Uzun vadeli hedefler, yıl hedefleri, yılın teması, odak alanları ve alışkanlık takibi. Arayüzün vault'a yazan tek sayfasıdır: hedef ve alışkanlık eklenir, adımlar ve günler işaretlenir, silinen not vault'un `.trash` klasörüne taşınır ve sayfadaki Çöp Kutusu'ndan geri alınır. `--read-only` yazmayı kapatır.
- **Raporlar sayfası.** Haftalık özet, son 30 gün, proje ilerlemeleri, bilgi birikimi ve haftanın öğrenilenleri; yalnızca vault'taki kayıtlardan hesaplanır.
- **İngilizce arayüz.** Üst çubukta dil düğmesi; `--lang en` ya da `config.json`'da `"language": "en"` varsayılanı değiştirir. Tarih, sayı ve çoğul biçimleri dile uyar.

Kurulum ve kullanım:

- **Tek komutla kurulum.** `--install` arayüzün bir kopyasını kullanıcı klasörüne alır, vault yolunu ayarlara yazar ve bir kısayol bırakır (Windows'ta Başlat menüsü ve masaüstü, Linux'ta uygulama menüsü, macOS'ta masaüstü; WSL'de Windows kısayolu). Sonrası çift tık; vault'a dosya konmaz. `--uninstall` geri alır.
- **Ayarlar çekmecesi.** Dişli düğmesi artık çalışıyor: dil seçimi, Beyin'in Yakala, tercihler ve güncelleme rehberlerine bağlantılar ve **Arayüzü kapat**.
- İkinci kez başlatılan arayüz yeni sunucu açmaz, çalışanı gösterir (`--reuse`).

Var olan sayfalar:

- Günlükler'e "Seçili Gün Özeti" ve "Yaklaşanlar" kutuları eklendi.
- Grafik koyu bir gökyüzü sahnesinde çiziliyor; düğümler yavaşça süzülüyor, üzerine gelinen notun bağlantıları öne çıkıyor.
- Hafıza bir seferde tek bölüm gösteriyor; kurallar tek satır, içlerinde arama var.
- Üst çubuğa "Obsidian'da Aç" düğmesi geldi; açık olan notu ya da vault'u Obsidian'da açar.
- İşlem kayıtları (receipt) özetlerinden çıkarılan başlıklarla gösteriliyor.
- Yerleşim sıkılaştırıldı: Ana Sayfa 1672 × 941 pencerede kaydırmadan görünüyor.
- İkincil metin ve bağlantı renkleri koyulaştırıldı (karşıtlık en az 4,5:1).
- Sayfa içi süzme kutuları üst çubuktaki aramayla aynı davranıyor: "api" "API"yi, "cinar" "Çınar"ı buluyor.

Hız:

- 2.000 notluk vault'ta ilk tarama WSL'de (`/mnt/c`) 31,3 saniyeden 0,54 saniyeye indi.

## 0.1.0 (2026-10-11)

İlk sürüm: Ana Sayfa, Projeler, Bilgi, Günlükler, Grafik, Arama ve Hafıza sayfaları; sağlık çekmecesi; klavye ve ekran okuyucu desteği; Linux, macOS ve Windows başlatıcıları. Salt okunur.
