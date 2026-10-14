# Beyin'e (avenoxbeyin) ekleme yolu

Bu belge, beyin-web'in [avenoxbeyin](https://github.com/avenoxai/avenoxbeyin) deposuna nasıl bağlanabileceğini anlatır: bugünkü durum, ölçümler, üç seçenek, öneri ve bakımcıya açılacak konunun taslağı. Karar avenoxbeyin'in bakımcısınındır; burada yazılanlar öneridir.

## Bugünkü durum

beyin-web ayrı bir depodur ve Beyin'e bağımlıdır, tersi değil: Beyin'in dosyalarını okur, kodunu değiştirmez. Kullanıcı depoyu indirir, `scripts/beyin-web --install --vault …` ile bir kez kurar ve masaüstündeki ya da uygulama menüsündeki kısayoldan açar. Beyin'in `update` komutu bu arayüzü bilmez.

## Ölçümler (2026-10-13)

avenoxbeyin, `main` `7527cdf`, sürüm 3.10.0:

- **Sürüm paketi dar.** `scripts/build_v3_release.py` pakete yalnızca şunları alır: `scripts/` altından üç dosya (`install_v3.py`, `beyin_v3.py`, `beyin_entry.py`), `template/.claude/scripts/beyin_v3*.py` kalıbına uyan Python dosyaları ve üç skill dosyası. HTML, CSS, JavaScript ya da yazı tipi taşıyan bir klasörün pakette yeri yok.
- **İsteğe bağlı araç örneği var: `yakala`.** Tek dosyadır (`beyin_v3_yakala.py`, 159 KB). `beyin_entry.py` içinde `yakala` alt komutu indeks ve eşitleme motoru yüklenmeden doğrudan bu modüle yönlendirilir; komutlar `beyin.py yakala kur | durum | kaldir` biçimindedir. Belgesi `docs/v3/YAKALA.md`, README'de "İsteğe bağlı" başlığı altında tek paragraftır.
- **Ağdan indirme örneği var.** `beyin_v3_update.py` yeni sürümü GitHub'dan indirir ve SHA-256 ile doğrular.
- **Katkı düzeni:** `CONTRIBUTING` belgesi yok; katkılar fork ve PR ile geliyor, başlıklar `feat(kapsam): …` ve `fix(kapsam): …` biçiminde, Türkçe ya da İngilizce. Testler `tests/` altında; CI Linux ve Windows'ta koşuyor.
- **Arayüzle ilgili açık bir konu ya da PR yok** (GitHub araması: web, arayüz, dashboard, ui).

beyin-web, sürüm 0.2.0:

| Parça | Boyut |
|---|---:|
| Python (`beyin_web/`) | 150 KB |
| JavaScript | 205 KB |
| CSS | 47 KB |
| Arayüz metinleri (Türkçe, İngilizce) | 57 KB |
| Üçüncü taraf dosyalar (markdown-it, d3-force, ikonlar, yazı tipleri) | 678 KB (487 KB'ı yazı tipi) |
| **Toplam** | **yaklaşık 1,1 MB, 107 dosya** |

Yalnızca standart kütüphane kullanır; derleme adımı ve pip paketi yoktur. Beyin'den `doctor` ve `context --no-sync` dışında komut çağırmaz; durum klasörüne yazmaz.

## Üç seçenek

### 1. Bağlantı

avenoxbeyin'in README'sinde, "İsteğe bağlı" başlığı altında bu depoya bir paragraf ve bağlantı.

- Beyin'e yük: yok. Kod girmez, bakım gerekmez.
- Kullanıcıya: depoyu ayrıca indirip vault yolunu kendisi vermesi gerekir. Güncellemeyi kendisi izler.

### 2. İnce başlatıcı (öneri)

Beyin'e yalnızca küçük bir modül girer: `template/.claude/scripts/beyin_v3_web.py` (tahmin: birkaç yüz satır). `yakala` ile aynı düzen:

| Komut | Yaptığı |
|---|---|
| `beyin.py web kur` | beyin-web'in belirli bir sürümünün ZIP'ini GitHub'dan indirir, modülde yazılı SHA-256 ile doğrular, durum klasöründe `web/<sürüm>/` altına açar. |
| `beyin.py web ac` | Kurulu sürümü `beyin.py`'nin zaten bildiği vault ile başlatır ve tarayıcıyı açar. Kullanıcı vault yolu yazmaz. |
| `beyin.py web durum` | Kurulu mu, hangi sürüm, çalışıyor mu. |
| `beyin.py web kaldir` | Durum klasöründeki kopyayı siler. Vault'a dokunmaz. |

- Beyin'e yük: küçük ve okunabilir bir dosya, `beyin_entry.py`'de `yakala`'daki gibi üç satırlık yönlendirme, bir belge sayfası (`docs/v3/WEB.md`), testler. Arayüzün kodu Beyin'in deposuna girmez; incelemesi ve hataları bu depoda kalır.
- Kullanıcıya: tek komutla kurulum, vault yolu yok, sürüm sabit ve doğrulanmış. Beyin'in kurulu olduğu ortamda çalıştığı için yalın kip sorunu da kalkar.
- Sürüm sabitleme: modül beyin-web'in bir sürümünü ve özetini taşır; yeni sürüm, Beyin'e gelen küçük bir PR ile (iki satır) alınır. Böylece Beyin kullanıcılarına bakımcının görmediği kod gitmez.
- Kurmayan için hiçbir şey değişmez; `kur` çağrılmadıkça ağ isteği yapılmaz.

### 3. Tek dosya

Bu depodaki bir betik, Python paketini ve bütün ön uç dosyalarını gömerek tek bir `beyin_v3_web.py` üretir; dosya Beyin'in paket kalıbına doğrudan girer ve `beyin.py update` ile herkese ulaşır.

- Beyin'e yük: en çok. Yazı tipleri çıkarılsa bile 0,7–0,9 MB'lık (gömme biçimine göre), üretilmiş ve satır satır incelenemeyen bir dosya Beyin'in deposuna ve her kullanıcının vault'una girer (bugün en büyük modül 159 KB). Her arayüz değişikliği Beyin'e yeni bir PR demektir.
- Kullanıcıya: en kolay; ayrı kurulum yok.

## Öneri

**Önce 1, sonra 2.** Bağlantı hemen yapılabilir ve kimseye yük getirmez. İnce başlatıcı, `yakala`'nın açtığı yolu izler (isteğe bağlı araç, kendi alt komutu, `kur | durum | kaldir`) ve Beyin'in deposunu küçük tutar. Tek dosya seçeneği, bakımcı arayüzü Beyin'in çekirdeğine almak isterse konuşulur.

İnce başlatıcı için bu depoda yapılacaklar (bakımcı olumlu bakarsa):

1. Depoyu herkese açık yayınlamak ve sürüm etiketi atmak (`v0.2.0`), ZIP'i sürüm sayfasına koymak.
2. Yapıldı (2026-10-14): başlatıcının taslağı `upstream/beyin_v3_web.py` (yaklaşık 300 satır, yalnızca standart kütüphane). Durum klasörünü `yakala` ile aynı yoldan bulur (`.beyin-runtime.json`'daki sabit yol, yoksa vault yolunun özeti); kısayolu kurulan kopyanın kendi kodu yazar, bu yüzden Windows, WSL, Linux ve macOS ayrıntısı Beyin'e girmez. Bugün `--vault` ile tek başına çalışır; Beyin'e alınırsa `beyin_entry.py`'de `yakala`'daki gibi bir yönlendirme yeter.
3. Yapıldı (2026-10-14): `scripts/build_release.py` ZIP'i ve `.sha256` dosyasını üretir, sürümü ve özeti başlatıcıya işler. ZIP yalnızca `beyin_web/`, `LICENSE`, `README.md` ve `CHANGELOG.md` içerir; sıkıştırmasız, sabit tarih ve izinlerle yazıldığı için Windows'ta ve Linux'ta aynı özeti verir (ölçüm). `kur`, paketteki her yolu denetler: `beyin_web/` dışına, üst klasöre ya da mutlak yola yazan ve bağlantı (symlink) taşıyan paket reddedilir.
4. `beyin.py`'nin verdiği vault ve durum klasörüyle başlatmayı Beyin'in test düzeninde (`tests/v3_*_test.py`) sınayan bir test; bu depodaki karşılığı `tests/test_release.py`.

## Bakımcıya açılacak konunun taslağı

Başlık: `feat(web): isteğe bağlı web arayüzü (beyin-web) için öneri`

> Merhaba. Beyin'in vault'unda biriken kayıtları (projeler, görevler, receipt'ler, oturum kartları, kurallar, bilgi notları) Obsidian'ı bilmeyen birinin de okuyabileceği sadelikte gösteren yerel bir web arayüzü yazdım: **beyin-web** (MIT, bağlantı: …). Ekran görüntüleri aşağıda.
>
> Beyin'e dokunmaz: veriyi vault'taki Markdown dosyalarından okur, Beyin'den yalnızca `doctor` ve `context --no-sync` çağırır, durum klasörüne yazmaz. Yalnızca standart kütüphane kullanır; pip paketi, derleme adımı, dışarı ağ isteği yoktur. `visibility: private` notlar hiçbir sayfada görünmez. Vault'a yazan tek yer Hedefler sayfasıdır (`kind: goal` ve `kind: habit` notları, `goals/` klasörüne); `--read-only` onu da kapatır.
>
> Beyin'e nasıl bağlanabileceği konusunda üç yol görüyorum ve görüşünüzü almak istiyorum:
>
> 1. **Bağlantı:** README'de "İsteğe bağlı" altında bir paragraf.
> 2. **İnce başlatıcı:** `yakala` düzeninde küçük bir `beyin_v3_web.py`; `beyin.py web kur` arayüzün sabitlenmiş bir sürümünü indirip SHA-256 ile doğrular, `beyin.py web ac` vault'u bilerek başlatır. Arayüzün kodu Beyin'in deposuna girmez.
> 3. **Tek dosya:** arayüzün tamamı gömülü tek bir modül olarak pakete girer (0,7–0,9 MB).
>
> Benim önerim önce 1, uygun görürseniz 2. Hangisini isterseniz PR'ını hazırlarım; hiçbirini istemezseniz arayüz ayrı depoda yaşamaya devam eder.

Konuyu açmadan önce yapılacaklar: depoyu yayınlamak, taslaktaki bağlantıyı doldurmak, ekran görüntülerini eklemek. Yayın ve konu depo sahibinin onayıyla yapılır.
