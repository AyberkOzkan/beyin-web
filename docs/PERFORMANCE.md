# Performans raporu (0.1.0)

`docs/PLAN.md` bölüm 10'daki her hedefin ölçülen değeri. Hepsi ölçümdür; tahmin ya da yuvarlanmış beklenti yoktur.

- **Tarih:** 2026-10-11, commit `d7920fe` (sürüm 0.1.0).
- **Vault:** gerçek vault, 124 Markdown dosyası (taramada 115 kayıt; frontmatter türüne göre 63 `receipt`, 20 `fact`, 13 `task`, 10 `receipt-index`, 9 `note`), Windows diskinde.
- **Arka uç ölçümleri:** WSL 2 Ubuntu, Python 3.12.3, vault `/mnt/c/…` üzerinden; Beyin açık.
- **Tarayıcı ölçümleri:** Windows 11, Python 3.12.10, başsız Edge, 1672×941; Beyin kapalı (çalışma zamanı yalnızca WSL'de).
- Ölçümler vault'u ve Beyin'in durum klasörünü değiştirmedi: öncesi ve sonrası 459 dosyanın zamanı ve boyutu aynı (vault ve `~/.local/state/beyin-v3`; `.git` ve `.obsidian` hariç).

## Sonuçlar

| Ölçü | Hedef | Ölçülen | Durum |
|---|---|---|---|
| İlk tarama | 1,5 sn altı | 0,88–0,90 sn (üç koşu); oturumun ilk koşusunda 1,45 sn | Tuttu; ilk koşuda sınırda |
| Değişiklik yokken yeniden tarama | 150 ms altı | 71–103 ms (dört koşu) | Tuttu |
| Önbellekten API yanıtı | 50 ms altı | 14 ucun ortancası 0,4–1,3 ms, en büyüğü 1,5 ms | Tuttu |
| İstemci yokken işlemci | %0 | 60 sn'de 20 ms işlemci süresi (%0,03); süreç içi ölçümde %0,017 | Tuttu (ölçüm duyarlılığında sıfır) |
| Sunucu belleği | 60 MB altı | 24,8 MB (istekten sonra ve 60 sn boşta aynı); süreç içi ölçümde 29,8 MB | Tuttu |
| Ana Sayfa'nın ilk çizimi | 1 sn altı (yerel) | İlk içerikli çizim 76 ms, bölümlerin dolması 58 ms (yedi koşunun ortancası; en büyük 80 ve 67 ms) | Tuttu |
| Grafik, 500 düğüm | Yerleşim 3 sn'de durulur; akıcı sürükleme | Yerleşim 0,35 sn'de duruldu (2026-10-11, gökyüzü görünümüyle yeniden ölçüldü). Sürüklemenin akıcılığı ölçülmedi | Yerleşim tuttu; sürükleme ölçülmedi |
| Grafik süzülürken bir karenin çizimi (500 düğüm) | 16 ms altı | 0,7 ms (60 karenin ortancası; çizim komutları, rasterleştirme hariç) | Tuttu |

"Beyin ne hatırlıyor?" araması önbellekten cevaplanmaz; her istek Beyin CLI'ını çağırır (`context --no-sync`). İlk istek 315 ms; ardından 20 isteğin ortancası 275 ms, en büyüğü 395 ms. PLAN'da bunun için hedef yok.

## Ayrıntı

**API uçları** (`first`: sunucu açıldıktan sonraki ilk istek; `median` ve `max`: ardından 20 istek; milisaniye):

| Uç | first | median | max |
|---|---:|---:|---:|
| `/pulse` | 894,5 | 1,0 | 1,5 |
| `/home` | 13,4 | 0,7 | 1,2 |
| `/projects` | 0,5 | 0,5 | 0,6 |
| `/projects/{ad}` | 0,5 | 0,5 | 0,5 |
| `/tasks` | 0,6 | 0,5 | 0,6 |
| `/knowledge` | 2,0 | 0,5 | 0,6 |
| `/records/{rid}` | 0,5 | 0,4 | 0,5 |
| `/journal/months/{ay}` | 0,5 | 0,4 | 0,6 |
| `/journal/days/{gün}` | 0,7 | 0,6 | 0,7 |
| `/journal/heatmap` | 0,5 | 0,4 | 0,5 |
| `/graph` | 0,9 | 0,6 | 0,7 |
| `/search?q=…` | 8,7 | 0,4 | 0,6 |
| `/search?q=…&mode=beyin` | 315,1 | 274,9 | 395,5 |
| `/memory` | 0,9 | 0,7 | 0,8 |
| `/health` | 1,3 | 1,3 | 1,4 |

`/pulse`'ın ilk isteği vault'un ilk taramasını içerir. Gerçek süreçte (`python3 -m beyin_web`) aynı ilk istek 1,73 sn sürdü; fark, açılışta bir kez çağrılan `doctor` komutudur.

## Ölçek: 2.000 notluk vault (2026-10-12)

PLAN'ın rahat hedefi olan boyut, `scripts/synthetic_vault.py --notes 2000` ile üretilen vault'ta ölçüldü (tek klasörde 2.000 dosya; 500 `fact`, 1.500 `note`). Önceki sütun commit `ffc0a39`, sonraki sütun tarama ölçeği paketi (dosya başına `resolve()` kalktı; stat ve okuma en çok 8 iş parçacığıyla).

| Ortam | Ölçü | Önce | Sonra |
|---|---|---:|---:|
| WSL, vault `/mnt/c` altında | İlk tarama | 31,3 sn | 0,52–0,54 sn (iki koşu) |
| WSL, vault `/mnt/c` altında | Değişiklik yokken yeniden tarama | 693 ms | 164–165 ms |
| Windows (NTFS) | İlk tarama | 1,29 sn | 0,21 sn (Kodzilla'nın ölçümü) |
| Windows (NTFS) | Değişiklik yokken yeniden tarama | 50 ms | 44 ms |
| WSL, gerçek vault (123 dosya) | İlk tarama | 0,88–0,90 sn | 0,10 sn |
| WSL, gerçek vault (123 dosya) | Değişiklik yokken yeniden tarama | 71–103 ms | 61 ms |

- Darboğaz dosya başına `path.resolve()` idi: `/mnt/c` üzerinde yolun her parçası ayrı sorgulanıyordu (400 dosyada 4,8 sn). Okuma sıralıyken 400 dosyada 1,7 sn, 8 iş parçacığıyla 0,13 sn sürdü.
- Paketten önce `measure.py --api` bu vault'ta düşüyordu (ilk istek 30 sn'lik zaman aşımını geçiyordu); şimdi biter. Önbellekten API yanıtları 2.000 notta da hedefin altında: en yavaş uç `/graph`, ortanca 12 ms, en büyük 13 ms; ötekilerin ortancası 0,4–2,0 ms. Sunucu belleği 40,0 MB.
- Denetim aralığı taramanın süresine uyar: yeniden tarama 165 ms sürdüğünde sonraki denetim en erken 2 sn sonra, 1 sn sürdüğünde 10 sn sonra yapılır (üst sınır 30 sn).
- Windows'taki ilk koşu 8,6 sn sürdü (yeni üretilen dosyalara ilk dokunuş); tabloda ikinci koşular var.

## Yöntem

- **Tarama, API, süreç içi işlemci ve bellek:** `python3 scripts/measure.py VAULT --api --repeat 20 --idle 60`. Betik sunucuyu kendi sürecinde, `127.0.0.1`'de boş bir portta açar; işlemci için 60 sn hiç istek atmadan bekler ve `time.process_time()` farkını duvar saatine oranlar; belleği `/proc/self/status`'taki `VmRSS`'ten okur. Bu rakamlar ölçen istemciyi de içerir.
- **İlk taramanın tekrarı:** `python3 scripts/measure.py VAULT` üç kez daha (her koşu yeni süreç). İlk koşunun 1,45 sn sürmesi, dosyaların `/mnt/c` üzerinden o oturumda ilk kez okunmasındandır; sonraki koşularda işletim sistemi önbelleği doludur.
- **Gerçek süreçte işlemci ve bellek:** `python3 -m beyin_web --vault VAULT --port 7391 --no-token`, dokuz API ucuna ve ana sayfaya birer `curl` isteği, ardından `/proc/PID/status`'tan `VmRSS` ve 60 sn arayla `/proc/PID/stat`'tan kullanıcı ve çekirdek süresi (2 tik, `CLK_TCK=100`). PLAN'daki `top` ve `ps` yerine aynı sayaçlar doğrudan `/proc`'tan okundu.
- **Ana Sayfa'nın ilk çizimi:** Selenium ile başsız Edge; sunucu aynı süreçte, gerçek vault Windows yolundan. Her koşuda sayfa yeniden yüklendi; tarayıcının `first-contentful-paint` kaydı ve Ana Sayfa'nın bütün bölümlerinin dolduğu an (`aria-busy="false"`; `performance.now()`) okundu. İlk yükleme ısınma sayılıp atıldı (136 ms). Bölümlerin dolması ilk çizimden önce görünür, çünkü tarayıcı dolu sayfayı bir sonraki karede çizer. Sunucu ve tarayıcı aynı makinede olduğundan ağ gecikmesi yoktur.
- **Grafik:** `scripts/synthetic_vault.py` ile üretilen 500 düğümlü vault, başsız Edge; `tests/e2e/test_graph.py`'deki bütçe testi yerleşimin durulma süresini ve süzülme sırasında 60 karenin çizim süresini `performance.now()` ile ölçer (2026-10-11, iki koşu: 346 ve 357 ms; 0,70 ms). Kare süresi tuvale verilen çizim komutlarının süresidir; tarayıcının rasterleştirmesini içermez. Sürüklemenin akıcılığı için kare hızı ölçümü yapılmadı; bu satır elle denenmeyi bekliyor.
- **Dosyaların değişmediği:** ölçümden önce ve sonra `find … -printf '%T@ %s %p'` çıktıları karşılaştırıldı.

## Sınırlar

- Tek makinede ölçüldü. 2.000 notluk ölçüm sentetik vault'tadır: dosyalar küçük, tek klasörde ve frontmatter'ları düzgündür; gerçek bir 2.000 notluk vault'un dosyaları daha büyük ve klasörleri daha derindir.
- Tarayıcı ölçümü başsız Edge'dedir; görünür pencerede ve başka tarayıcılarda ölçülmedi.
- Windows'ta bellek ölçülmedi (`measure.py` orada `rss_mb: unavailable` yazar).
