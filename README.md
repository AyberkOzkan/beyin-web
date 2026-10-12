# beyin-web 0.1.0

Beyin vault'unu sade bir web arayüzünde gösteren yerel, salt okunur bir uygulama. Obsidian'ın ayrıntılarıyla uğraşmadan notlarını, projelerini ve asistanının hafızasını okumak isteyenler içindir. Veriler Markdown dosyalarından gelir; Beyin olmadan da kullanılabilir.

| Sayfa | Ne gösterir? |
|---|---|
| Ana Sayfa | Son oturum, açık işler, yakın etkinlik ve yaklaşan tarihler. |
| Projeler | Proje notu, görevler, bilgiler ve son receipt'ler (işlem kayıtları). |
| Bilgi | Konulara ve projelere göre bilgi notları, içerik ve bağlantılar. |
| Günlükler | Receipt'ler, oturum kartları, gün görünümü, seçili günün özeti, etkinlik ısı haritası ve yaklaşanlar. |
| Grafik | Notlar arasındaki bağlantılar ve seçili notun bağlamı. |
| Arama | Yerel kelime araması ve Beyin varsa bağlam araması. |
| Hafıza | Vault'taki kimlik, kurallar, son oturum ve açık konular. |
| Raporlar | Haftalık özet, son 30 gün, proje ilerlemeleri, bilgi birikimi ve haftanın öğrenilenleri; yalnızca vault'taki kayıtlardan hesaplanır. |

![Ana Sayfa: karşılama, bilgi kasası, son oturum, son notlar, projeler ve açık başlıklar](docs/img/home.png)

Görüntü, testlerde kullanılan sentetik örnek vault'la alınmıştır; içindeki notlar gerçek değildir.

## Beş dakikada çalıştırma

Python **3.11 ya da üstü** ve güncel Edge, Chrome ya da Firefox yeterlidir. Kullanım için başka kurulum, pip paketi veya derleme gerekmez. Bu depoyu indirin, ZIP indirdiyseniz açın ve terminalde depo klasörüne girin. Örneklerde vault yolunu kendi Obsidian klasörünüzle değiştirin.

Linux ve macOS:

```sh
scripts/beyin-web --vault "$HOME/Documents/Beyin" --open
```

Windows (PowerShell veya Komut İstemi):

```text
scripts\beyin-web.cmd --vault "C:\Users\KULLANICI\Documents\Beyin" --open
```

WSL, Windows'taki vault `/mnt/c/…` altındaysa (WSL terminalinde):

```sh
scripts/beyin-web --vault "/mnt/c/Users/KULLANICI/Documents/Beyin" --open
```

Beyin'in çalışma zamanı başka ortamdaysa komuta `--no-beyin` ekleyin; örneğin Beyin yalnız WSL'de çalışıyorsa Windows'tan başlatırken kullanın. Başlatıcı WSL'i kendiliğinden açmaz. Tarayıcı açılmazsa terminaldeki `beyin-web adresi: …` satırında verilen adresi elle açın. Kapatmak için terminalde `Ctrl+C` kullanın.

Ayrıntılar: [Kurulum rehberi](docs/INSTALL.md).

## Seçenekler ve ayarlar

| Seçenek | Anlamı |
|---|---|
| `--vault YOL` | Okunacak vault klasörü; boşluk içeren yolları tırnaklayın. |
| `--port SAYI` | Başlangıç portu; varsayılan 7373. Doluysa sonraki 20 porta kadar boş port aranır. `0` boş port seçtirir. |
| `--open` | Tarayıcıyı giriş adresiyle açar. |
| `--idle-exit DAKİKA` | Pozitif tam sayı; bu süre boyunca istek gelmezse kapanır. Varsayılan kapalıdır. Açık sekme istek gönderebilir. |
| `--no-token` | Belirteç ve çerez denetimini kapatır; yalnız tek kullanıcılı makine için. |
| `--no-beyin` | Yalın kipi zorlar; Beyin CLI'ı çağrılmaz. |
| `--version` | `beyin-web 0.1.0` yazdırıp çıkar. |

Vault keşif sırası: `--vault` → `BEYIN_VAULT` → `config.json` içindeki `vault` → bulunulan klasör (içinde `beyin.py` veya `.obsidian` varsa). Göreli yollar bulunulan klasöre göre çözülür; başlatıcı çalışma klasörünü değiştirmez. Öncelikli yol geçersizse sonraki aday denenmez.

`config.json` yeri:

- Windows: `%APPDATA%\beyin-web\config.json`; `APPDATA` yoksa `~/.config/beyin-web/config.json`.
- Linux, macOS ve WSL: `XDG_CONFIG_HOME` tanımlıysa `$XDG_CONFIG_HOME/beyin-web/config.json`, yoksa `~/.config/beyin-web/config.json`.

Dosyayı isteğe bağlı olarak kendiniz oluşturun. Desteklenen anahtarlar:

| Anahtar | Değer |
|---|---|
| `vault` | Vault yolu (metin). |
| `port` | 0–65535 arasında tam sayı; geçersizse 7373. `--port` önceliklidir. |
| `display_name` | Ana Sayfa selamlamasında kullanılan ad (metin). |
| `beyin` | `false` ise Beyin çağrıları kapatılır. |

```json
{
  "vault": "C:\\Users\\KULLANICI\\Documents\\Beyin",
  "port": 7373,
  "display_name": "Deniz",
  "beyin": false
}
```

## Güvenlik ve yalın kip

Sunucu yalnız `127.0.0.1` üzerinde dinler. İlk adres belirteç taşır; açılışta `HttpOnly; SameSite=Strict` çerez konur ve belirteç adres çubuğundan kaldırılır. Belirteç ayar klasöründeki `token` dosyasında tutulur; vault içinde ayar klasörü kullanılamaz. API yalnız GET ile okunur (HEAD de desteklenir); yazma uçları yoktur. Katı CSP uzak kaynakları ve satır içi betikleri engeller. Gizli (`visibility: private`) notlar veri katmanında elenir. Vault'a ve Beyin'in durum klasörüne yazılmaz; dışarı ağ isteği, telemetri veya CDN kullanılmaz. Belirteçli adresi paylaşmayın.

Beyin yokken notlar, projeler, görevler, günlükler, grafik ve yerel arama çalışır. Hafıza dosyaları varsa okunabilir; yoksa boş durum gösterilir. Beyin bağlam araması ve Beyin'in sağlık/sürüm bilgileri kullanılamaz; sağlık çekmecesinde arayüzün tarama uyarıları okunabilir. Beyin varsa yalnız `doctor` ve `context --no-sync` çağrılır.

## Sınırlar

Salt okunurdur; not düzenleme ve oluşturma yoktur. Koyu tema ve mobil düzen yoktur; en düşük genişlik **1.024 px**'dir. Arama `ı`/`i` ayrımı yapmaz. Dekoratif çizimler henüz eklenmemiştir; notların bağlantı grafiği çalışır.

## Geliştirme ve ölçüm

```sh
python -m unittest discover -s tests -t .
node --test tests/js
```

`tests/e2e/` altındaki tarayıcı testleri aynı Python keşif komutuna dahildir. Ayrı çalıştırmak için:

```sh
python -m unittest discover -s tests/e2e -t .
```

Linux/macOS/WSL'de gerektiğinde `python` yerine `python3`, Windows'ta `py -3` kullanın. Tarayıcı testleri geliştirme ortamında Selenium ve yerel Edge sürücüsü gerektirir; bulunmazsa atlanır. Testler gerçek vault'u okumaz ve dışarı ağ isteği yapmaz.

Salt okunur performans ölçümü (kendi vault yolunuzla):

```sh
python scripts/measure.py VAULT
python scripts/measure.py VAULT --api --no-beyin --repeat 20 --idle 60
```

İlk komut `cold_ms`, `warm_ms`, türlere göre sayılar, `warnings` ve belleği yazdırır. İkincisi yerel API'nin ilk, ortanca ve en büyük sürelerini ve boşta işlemci yüzdesini ekler. Veri veya Beyin gerektiren ölçümler karşılıkları yoksa `atlandı` olur. Bellek yalnız `/proc/self/status` üzerinden ölçülür; diğer ortamlarda `rss_mb: unavailable` yazılır. Beyin çağrılarını da ölçmek için `--no-beyin` seçeneğini kaldırın.

[Mimari ve PLAN](docs/PLAN.md) · [Kurulum](docs/INSTALL.md) · [Performans raporu](docs/PERFORMANCE.md) · [Ajan kuralları](AGENTS.md)

Lisans: [MIT](LICENSE).
