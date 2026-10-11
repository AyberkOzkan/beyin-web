# İlk çalıştırma rehberi

beyin-web, Obsidian vault'unuzdaki Markdown dosyalarını tarayıcıda okumanızı sağlar. Vault, notlarınızın bulunduğu klasördür. Bu adımlar notlarınızı değiştirmez; Obsidian açık kalabilir.

## 1. Python'u denetleyin

Linux ve macOS'ta Terminal'i, Windows'ta Başlat menüsünden PowerShell'i açın. WSL kullanıyorsanız WSL terminalini açın.

| Ortam | Komut | Beklenen çıktı |
|---|---|---|
| Linux ve macOS | `python3 --version` | `Python 3.11.x` veya daha yeni bir sürüm, örneğin `Python 3.12.10`. |
| Windows | `py -3 --version` | `Python 3.11.x` veya daha yeni bir sürüm. `py` yoksa `python --version` deneyin. |
| WSL | `python3 --version` | WSL içinde kurulu Python'un `Python 3.11.x` veya daha yeni sürümü. |

Komut bulunamıyorsa önce Python 3.11 ya da üstünü kurun. Windows'ta kurulumda Python'u PATH'e ekleme seçeneğini işaretleyin, ardından terminali yeniden açın. WSL, Windows'taki Python kurulumundan ayrı bir ortamdır. Uygulama için pip paketi veya Node kurulumu gerekmez. Güncel Edge, Chrome ya da Firefox kullanın.

## 2. Depoyu edinin ve klasöre girin

Bu deponun sayfasındaki **Code → Download ZIP** ile dosyaları indirin ve ZIP'i açın; Git kullanıyorsanız kendi depo adresinizden klonlayabilirsiniz. İçinde `README.md`, `beyin_web` ve `scripts` bulunan klasörü bulun. Örnekler klasörü `projects/beyin-web` olarak yerleştirdiğinizi varsayar; başka yere açtıysanız yolu değiştirin.

Linux ve macOS:

```sh
cd "$HOME/projects/beyin-web"
```

Windows PowerShell:

```powershell
cd "$HOME\projects\beyin-web"
```

WSL'den Windows'taki depoya erişim:

```sh
cd "/mnt/c/Users/KULLANICI/projects/beyin-web"
```

`KULLANICI` örnek bir yer tutucudur; kendi Windows kullanıcı klasörünüzün adını yazın. Başlatıcılar kurulum yapmaz, dosya yazmaz ve WSL'i başlatmaz.

## 3. Vault yolunu bulun ve açın

Obsidian'da bir notun bulunduğu klasörü Dosya Gezgini/Finder ile açın ve vault'un en üst klasörünü bulun. Bu klasörde genellikle gizli `.obsidian` klasörü ve not klasörleriniz vardır. Tek bir `.md` dosyasını veya onun alt klasörünü seçmeyin. Klasörün tam yolunu kopyalayın; boşluk veya Türkçe harf varsa da tırnak içinde kullanın.

Linux ve macOS:

```sh
scripts/beyin-web --vault "$HOME/Documents/Beyin" --open
```

Windows PowerShell veya Komut İstemi:

```text
scripts\beyin-web.cmd --vault "C:\Users\KULLANICI\Documents\Beyin" --open
```

WSL terminali, vault Windows'taysa:

```sh
scripts/beyin-web --vault "/mnt/c/Users/KULLANICI/Documents/Beyin" --open
```

Beyin'in çalışma zamanı başka ortamdaysa `--no-beyin` ekleyin. Örneğin Beyin yalnız WSL'de çalışıyorsa Windows komutu şöyle olur:

```text
scripts\beyin-web.cmd --vault "C:\Users\KULLANICI\Documents\Beyin" --open --no-beyin
```

Terminal açık kalır ve şu biçimde bir satır gösterir:

```text
beyin-web adresi: http://127.0.0.1:7373/?t=…
```

Bu, kendi bilgisayarınızdaki uygulamanın adresidir. `…` burada örnektir; terminaldeki gerçek adresi bütünüyle kullanın. Port değişebilir. `--open` tarayıcıyı açar; açmazsa adresi kopyalayıp tarayıcıya yapıştırın.

`?t=…` kısmı giriş belirtecidir. Sunucu bunu denetleyip tarayıcıya bir oturum çerezi koyar, sonra adres çubuğundan kaldırır. Böylece aynı bilgisayarda belirteci bilmeyen bir kullanıcı veya başka bir web sayfası notlarınıza erişemez. **Belirteçli adresi başkasıyla paylaşmayın.** Belirteç vault dışında, ayar klasöründeki `token` dosyasında tutulur; uygulama bu dosyayı ilk çalıştırmada oluşturur.

## 4. Kapatın veya boşta kapanmayı seçin

Sunucunun çalıştığı terminale dönüp **Ctrl+C** basın. Yalnız tarayıcı sekmesini kapatmak sunucuyu kapatmaz.

İstek gelmeyince 15 dakika sonra kapanması için (Windows'ta başlatıcı adını `scripts\beyin-web.cmd` ile değiştirin):

```sh
scripts/beyin-web --vault "$HOME/Documents/Beyin" --open --idle-exit 15
```

`--idle-exit` pozitif tam sayı olarak dakika alır; varsayılan olarak kapalıdır. Tarayıcı açıkken güncelleme istekleri gelebilir; boşta kapanmak için sekmeyi kapatın.

## 5. İsteğe bağlı kolaylıklar

Her seferinde `--vault` yazmamak için ortam değişkenini kendiniz tanımlayabilirsiniz. Bu komutlar yalnız o terminal oturumu için geçerlidir.

Linux, macOS ve WSL (WSL'de vault yolunu `/mnt/c/…` ile değiştirin):

```sh
export BEYIN_VAULT="$HOME/Documents/Beyin"
scripts/beyin-web --open
```

Windows PowerShell:

```powershell
$env:BEYIN_VAULT = "C:\Users\KULLANICI\Documents\Beyin"
scripts\beyin-web.cmd --open
```

Alternatif olarak `config.json` dosyasını kendiniz oluşturun:

- Windows: `%APPDATA%\beyin-web\config.json`; `APPDATA` yoksa kullanıcı ev klasöründeki `.config/beyin-web/config.json`.
- Linux, macOS ve WSL: `XDG_CONFIG_HOME` tanımlıysa onun altındaki `beyin-web/config.json`, yoksa `~/.config/beyin-web/config.json`.

Windows örneği (JSON içinde ters eğik çizgiler iki kez yazılır):

```json
{
  "vault": "C:\\Users\\KULLANICI\\Documents\\Beyin",
  "port": 7373,
  "display_name": "Deniz",
  "beyin": false
}
```

Linux/macOS için `vault` değerini `/home/KULLANICI/Documents/Beyin` veya `/Users/KULLANICI/Documents/Beyin`, WSL için `/mnt/c/Users/KULLANICI/Documents/Beyin` yapın. Tam yolu yazın; JSON içindeki `~` ve `$HOME` genişletilmez. Yalnız `vault`, `port`, `display_name` ve `beyin` anahtarları desteklenir. `beyin: false` yalın kipi seçer; Beyin'i kullanmak için bu anahtarı kaldırın veya `true` yapın. Ayar klasörünü vault'un içinde oluşturmayın.

Vault keşfi `--vault`, ardından `BEYIN_VAULT`, ardından `config.json` sırasındadır. Hiçbiri yoksa bulunulan klasörde `beyin.py` veya `.obsidian` aranır. Göreli yollar terminalin çalışma klasörüne göre çözülür; seçilmiş yol geçersizse diğer adaylara geçilmez.

POSIX sistemlerde başlatıcıya sembolik bağ oluşturmayı isterseniz kendiniz yapın. Örnek, depoyu `$HOME/projects/beyin-web` altında varsayar:

```sh
mkdir -p "$HOME/.local/bin"
ln -s "$HOME/projects/beyin-web/scripts/beyin-web" "$HOME/.local/bin/beyin-web"
"$HOME/.local/bin/beyin-web" --open
```

Son komut vault'un `BEYIN_VAULT` veya `config.json` ile ayarlanmasını gerektirir. `~/.local/bin` PATH'teyse yalnız `beyin-web --open` yazabilirsiniz. Sembolik bağ depoyu bulur ve bulunduğunuz klasörü değiştirmez.

Windows'ta masaüstünde sağ tıklayıp **Yeni → Kısayol** seçin. Hedef olarak kendi depo ve vault yollarınızla şunu yazın:

```text
"C:\Users\KULLANICI\projects\beyin-web\scripts\beyin-web.cmd" --vault "C:\Users\KULLANICI\Documents\Beyin" --open --no-beyin
```

Beyin Windows'ta çalışıyorsa `--no-beyin` seçeneğini kaldırın. Kısayol yalnız tıkladığınızda çalışır; WSL açmaz. Bu kolaylıkların hiçbirini başlatıcı sizin yerinize oluşturmaz.

## 6. Sık sorunlar

| Durum veya görünen metin | Çözüm |
|---|---|
| Port dolu | Varsayılan 7373 doluysa sıradaki boş port aranır (sonraki 20 porta kadar). Terminaldeki adresi kullanın. Gerekirse `--port 7400` verin. |
| `Vault bulunamadı. --vault ile var olan bir vault klasörü belirtin.` | Klasörün tam yolunu, tırnakları ve ortam değişkenini denetleyin. WSL'de `C:\…` yerine `/mnt/c/…` kullanın. |
| `Bu sayfayı açmak için terminalde gösterilen belirteçli adresi kullanın.` | Çerez yok veya geçersiz. Terminaldeki tam belirteçli adresi yeniden açın; yeni tarayıcı/profil de bu adresle giriş yapmalıdır. |
| Sayfa boş veya yazı tipi yok | Zorla yenileyin (`Ctrl+Shift+R`; macOS'ta `Cmd+Shift+R`). Gerekirse bu yerel adresin tarayıcı önbelleğini temizleyip terminaldeki adresi yeniden açın. |
| `Beyin bulunamadı; yalın kipte çalışıyor.` | Yerel notlar, projeler, günlükler, grafik ve kelime araması çalışır. Beyin başka ortamdaysa `--no-beyin` verin veya uygulamayı Beyin'in çalıştığı ortamda açın. |
| `Tarayıcı açılamadı. Terminaldeki adresi tarayıcıda açın.` veya WSL'de tarayıcı açılmıyor | Terminaldeki tam adresi Windows tarayıcısında elle açın. WSL'de `--open`, varsa `wslview`, yoksa `explorer.exe` kullanır. |
| `Python bulunamadı. Python 3.11 ya da üstünü kurun.` | Python'u ve PATH ayarını denetleyin, terminali yeniden açın. |
| `Sunucu başlatılamadı. Ayarları ve kullanılabilir portları kontrol edin.` | Ayar klasörünün vault dışında olduğunu ve seçilen port aralığının kullanılabildiğini denetleyin. |

Diğer seçenekler ve sınırlar için [README](../README.md), mimari için [PLAN](PLAN.md).
