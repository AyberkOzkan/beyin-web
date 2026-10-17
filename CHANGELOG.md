# Değişiklikler

## 0.2.1 (2026-10-17)

- Giriş çerezi artık geçici bir oturum değeri taşır; yeniden açma çalışan arayüzü kilit dosyasından bulur ve kalıcı belirteci başka portlara göndermez.
- Giriş belirteci bir kez yenilenir: 0.2.0'ın `token` dosyası ve kalıcı belirteci taşıyan 30 günlük çerezi ilk açılışta silinir, belirteç artık `login-token` dosyasında durur.
- Hedefler, yalnızca `goals/` altındaki hedef ve alışkanlıkları değiştirebilir; diğer klasörlerdeki notlar görünmeye devam eder.
- Ajan kurulum rehberinde (`beyin-web.md`) kendiliğinden kapanmanın sekmeler kapandıktan ya da tarayıcı arka plana alındıktan sonra işlediği açıklandı.
- Beyin başlatıcısı indirmeleri resmî HTTPS adresleri ve üç yönlendirmeyle sınırlar; durum denetimi kurulu kodu çalıştırmaz.

Güvenlik incelemesi ve önerileri için bakımcıya teşekkürler.

## 0.2.0 (2026-10-13)

Yeni sayfalar ve dil:

- **Hedefler sayfası.** Uzun vadeli hedefler, yıl hedefleri, yılın teması, odak alanları ve alışkanlık takibi. Arayüzün vault'a yazan tek sayfasıdır: hedef ve alışkanlık eklenir, adımlar ve günler işaretlenir, silinen not vault'un `.trash` klasörüne taşınır ve sayfadaki Çöp Kutusu'ndan geri alınır. `--read-only` yazmayı kapatır.
- **Raporlar sayfası.** Haftalık özet, son 30 gün, proje ilerlemeleri, bilgi birikimi ve haftanın öğrenilenleri; yalnızca vault'taki kayıtlardan hesaplanır.
- **İngilizce arayüz.** Dil, Ayarlar'dan seçilir; `--lang en` ya da `config.json`'da `"language": "en"` varsayılanı değiştirir. Tarih, sayı ve çoğul biçimleri dile uyar.

Kurulum ve kullanım:

- **Tek komutla kurulum.** `--install` arayüzün bir kopyasını kullanıcı klasörüne alır, vault yolunu ayarlara yazar ve bir kısayol bırakır (Windows'ta Başlat menüsü ve masaüstü, Linux'ta uygulama menüsü, macOS'ta masaüstü; WSL'de Windows kısayolu). Sonrası çift tık; vault'a dosya konmaz. `--uninstall` geri alır.
- **Koyu imleç.** Açık zeminde kaybolan beyaz imlecin yerine arayüzde koyu bir imleç kullanılır; Ayarlar'dan sistemin imlecine dönülebilir.
- **Ayarlar çekmecesi.** Dişli düğmesi artık çalışıyor: dil seçimi (üst çubukta ayrı bir dil düğmesi yoktur), imleç seçimi, Beyin'in Yakala, tercihler ve güncelleme rehberlerine bağlantılar ve **Arayüzü kapat**.
- İkinci kez başlatılan arayüz yeni sunucu açmaz, çalışanı gösterir (`--reuse`).
- Yeni kurulmuş, henüz güncelleme denetimi yapmamış bir Beyin'de üst köşede "Yalın kip" yazıyordu; sürüm artık vault'taki `.beyin-version`'dan okunuyor.
- README'nin başındaki ekran görüntüsünün yerine arayüzü gezen kısa bir GIF kondu (uydurma kişi ve projeler).
- **Asistana kurdurma.** `beyin-web.md`, Beyin'in `beyin.md`'si gibi bir ajan kurulum rehberidir: asistana verilince Python'u bulur, depoyu indirir, kurar ve vault'a dokunulmadığını denetler.
- Linux ve macOS başlatıcısı 3.11'den eski bir `python3`'ü atlar, `python3.11` gibi sürümlü adları kendisi bulur (Ubuntu 22.04'te `python3` 3.10'dur). Windows'ta çıktı bir programa aktarılırken Türkçe harfte çöken komut satırı düzeltildi.
- **Kısayol simgesi.** Kısayol kâğıt zemin üstünde karakalem bir beyinle görünür; küçük boylar için ayrıca, daha kalın çizilmiş bir sürüm vardır. Yan menüdeki adın yanında da aynı beyin durur.
- **Ad.** Arayüz kendini "Beyin" diye adlandırır; vault'un klasör adı yan menünün altında görünmeye devam eder.
- **Beyin için başlatıcı (önizleme).** `upstream/beyin_v3_web.py`, `yakala` düzeninde `kur | ac | durum | kaldir`; `scripts/build_release.py` her makinede aynı sürüm paketini ve SHA-256 özetini üretir.

Çizimler:

- **Kenar karalamaları.** Kâğıdın kenarına çiziktirilmiş gibi 16 küçük karalama, sayfanın boş kalan yerlerinde belirir; içeriğin üstüne gelmez, tıklamayı engellemez.
- **31 karakalem çizim.** Ana Sayfa karşılamasında, yan menünün altında, sayfa başlıklarında, "Bilgi Kasam" kartında ve boş kutularda; her yer kendi çizimlerinden birini rastgele gösterir. Çizimler kutu içinde küçük resimler değil, sayfanın parçasıdır: karşılamadaki çizim satırından taşar, karttaki çizim sayaçların altına uzanır, yan menüdeki çizim kenardan kenara yayılır. Kendi çiziminizi `static/img/` altına yuvanın adıyla koyabilirsiniz.

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
