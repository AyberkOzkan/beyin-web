# beyin-web: ajan kurulum rehberi

Bu dosya, kullanıcının şu isteğini yerine getirmek için kurulum tarifidir:

> Beyin vault'uma beyin-web arayüzünü kur. Kuruluysa güncelle. Gerekli indirme ve
> kurulum adımlarını sen yap; sonunda kısayoldan açılıp açılmadığına birlikte bakalım.

Kullanıcı depo indirmek, Python sürümü aramak ya da komut yazmak zorunda değildir; bunları
ajan yapar. Kullanıcıya kalanlar yalnızca şunlardır: yönetici parolası (Python kurmak
gerekirse), GitHub girişi (depo özelken) ve ilk açılışta kısayola tıklamak.

## Değişmez kurallar

1. **Vault'a dokunma.** Kurulum vault'a hiçbir dosya yazmaz, taşımaz, silmez. Arayüzün
   kopyası, ayar dosyası ve kısayol vault'un dışına gider. Depoyu da vault'un içine indirme.
2. **Beyin'in durumuna dokunma.** Kurulum için `beyin.py sync`, `receipt`, `note-create`
   gibi yazan komutları çalıştırma. Beyin'in durum klasörüne (indeks, yedekler) yazma.
3. **Sistemin `python3`'ünü değiştirme.** `update-alternatives`, `/usr/bin/python3`'ün
   bağını değiştirmek ya da `python3`'ü başka sürüme yönlendirmek yok: Ubuntu'nun kendi
   araçları (`apt`, ağ ve masaüstü betikleri) sistemin `python3`'üne bağlıdır. Daha yeni bir
   Python gerekiyorsa onu yanına kur ve tam adıyla çağır (`python3.11`).
4. **Giriş belirtecini gösterme.** Arayüz, tarayıcıyı içeri bir giriş belirteciyle (token)
   alır. Bu değeri, belirteçli adresi ya da ayar klasöründeki `token` dosyasının
   içeriğini terminal çıktısına, sohbete veya dış bir servise yazma. Doğrulamak için
   sunucuyu elle başlatma; 5. adımdaki denetimler yeterlidir.
5. **Yalnızca bu depo.** Kod `AyberkOzkan/beyin-web` deposundan alınır. Başka bir kopya,
   çatal ya da üçüncü taraf paket kullanma. pip, npm ya da başka bir bağımlılık gerekmez.
6. **Bitmeden "kuruldu" deme.** Kurulum komutunun çıkış kodunu, kurulan kopyanın sürümünü,
   ayar dosyasını ve kısayolu 5. adımdaki gibi denetle.

## 1. Vault'u ve Beyin'i bul

- Vault, kullanıcının verdiği klasör ya da çalışma klasörüdür. Mutlak yolu kullan.
- Kökünde `beyin.py` ve içi `3.` ile başlayan `.beyin-version` bulunmalıdır. Yoksa dur:
  önce Beyin kurulmalıdır (Beyin'in kendi `beyin.md` rehberi). beyin-web Beyin'in
  eklentisidir; tek başına işe yaramaz.
- Beyin'in sağlığına bak (salt okunur): `<python> beyin.py doctor --human`.

## 2. Python 3.11 ya da üstünü bul

Her adayı gerçekten çalıştırıp sürümüne bak; adına güvenme:

```text
<aday> -c "import sys; print(sys.version)"
```

- **Linux, macOS, WSL:** sırayla `python3.14`, `python3.13`, `python3.12`, `python3.11`,
  `python3`, `python`. Ubuntu 22.04'te `python3` 3.10'dur; 3.11 kuruluysa `python3.11`
  adıyla yanındadır.
- **Windows:** önce `py -3`, sonra `python`.

Uygun Python yoksa işletim sisteminin paket yöneticisiyle kur. Yönetici izni gerekiyorsa
yalnızca o noktada kısa ve açık biçimde kullanıcıdan iste:

| Sistem | Komut |
|---|---|
| Ubuntu, Debian | `sudo apt install python3.11` |
| Fedora | `sudo dnf install python3.11` |
| macOS | `brew install python@3.12` (Homebrew yoksa python.org'daki kurulum paketi) |
| Windows | `winget install Python.Python.3.12` |

Kurduktan sonra 3. kuralı hatırla: yeni Python `python3`'ün yerine geçirilmez.

## 3. Kodu al

Depoyu vault'un dışında geçici bir klasöre indir:

```text
git clone --depth 1 https://github.com/AyberkOzkan/beyin-web.git <geçici-klasör>/beyin-web
```

- Depo özelse `git clone` GitHub girişi ister. Kullanıcıdan `gh auth login` ile ya da kendi
  SSH anahtarıyla giriş yapmasını iste; parolayı ya da anahtarı sohbete yazdırma.
- `git` yoksa GitHub'ın depo sayfasındaki ZIP'i indirip aç; ZIP'i açarken mutlak yol,
  `..` ile kaçış ya da sembolik bağ içeren üyeyi reddet.
- Klasörde `beyin_web/__main__.py` ve `scripts/beyin-web` bulunmalıdır.

## 4. Kur

Komutu depo klasöründe çalıştır. Kurulu bir sürüm varsa aynı komut onu günceller; ayarlar
korunur.

Linux, macOS ve WSL:

```text
scripts/beyin-web --install --vault "<mutlak-vault-yolu>"
```

Windows (PowerShell):

```text
& .\scripts\beyin-web.cmd --install --vault "<mutlak-vault-yolu>"
```

- Başlatıcı 2. adımdaki sırayla 3.11 ya da üstü bir Python arar. Uygun olanı bulamazsa
  "Python 3.11 ya da üstü bulunamadı" der ve 127 ile çıkar; 2. adıma dön.
- Python'u kendin seçmek istersen başlatıcının yaptığını elle yap:
  `PYTHONPATH="<depo-klasörü>" <python> -P -m beyin_web --install --vault "<vault>"`.
  `-P`, çalışma klasöründeki başka bir `beyin_web`'in araya girmesini önler.
- Kullanıcı İngilizce arayüz isterse sona `--lang en` ekle; seçim ayar dosyasına yazılır.
- Kurulum, kısayolu onu kuran Python'un tam yoluyla yazar. Bu yüzden kısayol, sistemin
  `python3`'ü eski olsa da doğru Python'la açılır.
- Başarılı kurulum 0 ile çıkar ve kısayolların yerini yazar.

## 5. Doğrula

Sunucuyu başlatmadan şunlara bak:

1. **Sürüm:** kurulan kopya sürümünü söylemeli (`beyin-web X.Y.Z`):

   ```text
   PYTHONPATH="<kopya>" <python> -P -m beyin_web --version
   ```

2. **Ayar:** `config.json` içindeki `vault` değeri 1. adımdaki yol olmalı. İçeriği
   gösterirken yalnızca `vault` ve `language` değerlerini yaz.
3. **Kısayol:** dosya yerinde olmalı.
4. **Vault:** kurulumdan önce vault'un dışında bir işaret dosyası oluştur; kurulumdan sonra
   vault'ta ondan yeni dosya olmamalı (Obsidian açıksa `.obsidian/` klasörünü sayma):

   ```text
   find "<vault>" -newer <işaret-dosyası> -not -path "*/.obsidian/*" -type f
   ```

| | Kopya | Ayar klasörü | Kısayol |
|---|---|---|---|
| Linux | `~/.local/share/beyin-web/app` | `~/.config/beyin-web` | `~/.local/share/applications/beyin-web.desktop` |
| macOS | `~/Library/Application Support/beyin-web/app` | `~/.config/beyin-web` | `~/Desktop/Beyin Web.command` |
| Windows | `%LOCALAPPDATA%\beyin-web\app` | `%APPDATA%\beyin-web` | Başlat menüsünde ve masaüstünde `Beyin Web.lnk` |
| WSL | Linux'taki gibi (WSL içinde) | Linux'taki gibi | Windows'un Başlat menüsünde ve masaüstünde `Beyin Web.lnk` |

`XDG_DATA_HOME` ya da `XDG_CONFIG_HOME` tanımlıysa Linux'taki yollar onların altındadır.

Sonra geçici depo klasörünü sil; kurulu kopya ondan bağımsızdır.

## 6. Kullanıcıyla ilk açılış

Kullanıcıya şunları kısaca söyle ve kısayola tıklamasını iste:

- **Açmak:** uygulama menüsünde (Windows'ta Başlat menüsünde ve masaüstünde) **Beyin Web**.
  Tarayıcı açılır, Ana Sayfa görünür. İkinci tıklama yeni bir sunucu başlatmaz, açık olanı
  gösterir.
- **Kapatmak:** sağ üstteki dişli → **Arayüzü kapat**. Unutulursa 30 dakika kullanılmayınca
  kendiliğinden kapanır.
- **Vault'a yazan tek yer Hedefler sayfasıdır** (`goals/` klasörü). Gerisi yalnızca okur.

Kullanıcı Ana Sayfa'yı görmeden "kurulum doğrulandı" deme.

## Güncelleme ve kaldırma

- **Güncellemek:** 3. ve 4. adımları yeniden uygula. Arayüz açıksa önce kapatılmasını iste:
  açık sunucu eski kopyadan çalışır ve kısayol onu gösterir.
- **Kaldırmak:** depo klasöründe `scripts/beyin-web --uninstall` (Windows'ta
  `scripts\beyin-web.cmd --uninstall`). Kısayolu ve kopyayı siler; ayarlara ve vault'a
  dokunmaz.

## Sorun giderme

- **`Unknown option: -P`:** komut Python 3.10 ya da daha eskisiyle çalıştı. 2. adıma dön;
  `python3`'ü değiştirme, 3.11'i tam adıyla çağır.
- **Linux'ta menüde görünmüyor:** bazı masaüstleri menüyü oturum açılışında okur.
  `update-desktop-database ~/.local/share/applications` dene ya da oturumu kapatıp aç.
- **Kısayol tarayıcı yerine bir klasör açıyor (WSL):** eski bir sürüm kurulu olabilir;
  güncelle.
