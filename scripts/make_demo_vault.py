"""Write the demo vault the README screenshots are taken from.

    py -3 scripts/make_demo_vault.py OUT [--today 2026-10-14] [--beyin-from VAULT [--beyin-state PATH]]

The vault belongs to an invented person, Deniz, and four invented projects. Only its shape comes from a real
vault: how many receipts were written on which day, how the tasks of a project stand, how the knowledge notes
are spread over the projects. Every word is invented here, so the pictures show a vault that looks lived in
without showing anyone's notes. Dates are counted back from --today; file times follow the receipts, so
"recent notes" are recent. --beyin-from copies Beyin's own program files (never notes, never its state pin)
from an installed vault, so the interface can be photographed in Beyin mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

LOCAL = timezone(timedelta(hours=3))
COMPANION = "🔮 850-Companion"

# --- receipts: (project, event slug, summary, learned, extra refs) ------------------------------------------

SETUP = [
    ("setup", "beyin-kurulum", "Beyin V3 resmî sürüm paketiyle kuruldu; SHA-256 ve doctor temiz. Claude Code için hook güveni Deniz'e gösterildi ve onaylandı.", "", []),
    ("setup", "ilk-bilgi", "İlk bilgi kaydedildi: Deniz'in en sevdiği gezegen Jüpiter, Türkçe eski adı Erendiz. Yeni oturumda context ile geri okundu, kaynak notes/Jüpiter.md.", "", ["notes/Jüpiter.md"]),
]
KUMRU = [
    ("kumru", "baslangic", "Kumru başlatıldı: rustlings tarzında PostgreSQL alıştırmaları. Docker'da PostgreSQL 16, her alıştırmayı pytest ile denetleyen küçük bir koşucu, `kumru watch` dosya değişince sınıyor.", "", []),
    ("kumru", "secme", "Kumru: ilk beş alıştırma (SELECT, WHERE, ORDER BY, LIMIT, NULL karşılaştırması) yazıldı; her birinin çözümü ve iki ipucu var.", "", []),
    ("kumru", "join", "Kumru: JOIN alıştırmaları (6–10) eklendi. LEFT JOIN ile WHERE'in birlikte kullanıldığı tuzak alıştırması, denetçide ayrı bir hata mesajı aldı.", "", []),
    ("kumru", "group-by", "Kumru: toplama ve GROUP BY alıştırmaları (11–15); HAVING ile WHERE farkını soran alıştırmanın ipucu yeniden yazıldı.", "", []),
    ("kumru", "cte", "Kumru: alt sorgular ve CTE (16–20). Öğrenilen not alındı.", "PostgreSQL 12'den beri yan etkisiz CTE'ler varsayılan olarak sorguya gömülüyor; eski davranış için MATERIALIZED yazmak gerekiyor.", ["knowledge/concepts/postgres-cte-materialized.md"]),
    ("kumru", "explain", "Kumru: indeks bölümü başladı. İlk alıştırma EXPLAIN ANALYZE çıktısında Seq Scan ile Index Scan'i ayırt ettiriyor.", "EXPLAIN ANALYZE sorguyu gerçekten çalıştırır; yazan sorgularda işlem içinde deneyip geri almak gerekir.", ["knowledge/concepts/postgres-explain-analyze.md"]),
    ("kumru", "kismi-indeks", "Kumru: kısmi indeks ve index-only scan alıştırmaları.", "Index-only scan için tablonun görünürlük haritası güncel olmalı; VACUUM'dan önce yine yığına gidiliyor.", ["knowledge/concepts/postgres-index-only-scan.md", "knowledge/concepts/postgres-partial-index.md"]),
    ("kumru", "jsonb", "Kumru: JSONB ve GIN indeks alıştırmaları; `@>` ile `->>` karşılaştırmasının indeksi kullanıp kullanmadığını soran alıştırma eklendi.", "", ["knowledge/concepts/postgres-jsonb-gin.md"]),
    ("kumru", "yalitim", "Kumru: işlem yalıtımı bölümü. Denetçi iki oturum açıp sırayla komut gönderebiliyor; READ COMMITTED ile REPEATABLE READ farkı tek alıştırmada görülüyor.", "", ["knowledge/concepts/postgres-transaction-isolation.md"]),
    ("kumru", "kilit", "Kumru: kilit zaman aşımı alıştırması; lock_timeout ile statement_timeout ayrımı ipucuna yazıldı.", "", ["knowledge/concepts/postgres-lock-timeout.md"]),
    ("kumru", "ipucu", "Kumru: `kumru hint` komutu eklendi; ipuçları sırayla açılıyor, çözüm en sonda. 34 alıştırmanın hepsi denetçiden geçti.", "", []),
    ("kumru", "vacuum", "Kumru: VACUUM ve tablo şişkinliği alıştırması; pg_stat_user_tables'tan n_dead_tup okunuyor.", "", ["knowledge/concepts/postgres-vacuum-autovacuum.md"]),
    ("kumru", "pgbouncer", "Kumru: bağlantı havuzu bölümünün taslağı. PgBouncer'ın transaction kipinde oturum ayarlarının taşınmadığını gösteren alıştırma planlandı; Deniz'in onayı bekleniyor.", "", ["knowledge/concepts/postgres-pgbouncer-pooling.md"]),
]
POYRAZ = [
    ("poyraz", "baslangic", "Poyraz başlatıldı: Windows tepsisinde yaşayan küçük bir hava durumu arkadaşı. Plan A0–D2 olarak yazıldı; Tauri ve TypeScript seçildi.", "", ["tasks/poyraz-a0-iskelet.md"]),
    ("poyraz", "a0-iskelet", "Poyraz A0: proje iskeleti, ESLint, Vitest ve Tauri derlemesi kuruldu.", "", ["tasks/poyraz-a0-iskelet.md"]),
    ("poyraz", "a0-bitti", "Poyraz A0 bitti: tepsi simgesi görünüyor, GitHub Actions'ta Windows derlemesi yeşil.", "", ["tasks/poyraz-a0-iskelet.md"]),
    ("poyraz", "a1-palet", "Poyraz A1: gökyüzü paletleri; renk gün doğumu ve batımına göre yumuşakça değişiyor.", "", ["tasks/poyraz-a1-tema-motoru.md"]),
    ("poyraz", "a1-sahneler", "Poyraz A1: dokuz hava sahnesi çizildi (açık, parçalı bulutlu, kapalı, sis, çisenti, yağmur, kar, fırtına, rüzgâr). Deniz sahneleri playground sayfasında onayladı.", "", ["tasks/poyraz-a1-tema-motoru.md"]),
    ("poyraz", "a1-bitti", "Poyraz A1 bitti: sahne seçimi kalıcı, bilinmeyen hava kodu gelirse \"açık\" sahneye dönülüyor.", "", ["tasks/poyraz-a1-tema-motoru.md"]),
    ("poyraz", "a2-pencere", "Poyraz A2: kenarsız pencere, \"her zaman üstte\" seçeneği ve ekran köşesine yapışma.", "", ["tasks/poyraz-a2-pencere.md"]),
    ("poyraz", "a2-dpi", "Poyraz A2: %150 ölçekli ekranda bulanık tepsi simgesi düzeltildi.", "Windows tepsi simgesi için 16, 20, 24 ve 32 piksellik ayrı çizimler gerekiyor; tek büyük simgeyi küçültmek bulanık gösteriyor.", ["tasks/poyraz-a2-pencere.md", "knowledge/concepts/tauri-tray-icon-dpi.md"]),
    ("poyraz", "a3-istemci", "Poyraz A3: Open-Meteo istemcisi; veri 15 dakikada bir tazeleniyor, istekler önbellekten önce kontrol ediliyor.", "", ["tasks/poyraz-a3-veri-hatti.md", "knowledge/concepts/open-meteo-api.md"]),
    ("poyraz", "a3-cevrimdisi", "Poyraz A3: ağ yokken son veri soluk gösteriliyor ve saati yazıyor.", "", ["tasks/poyraz-a3-veri-hatti.md"]),
    ("poyraz", "a3-bitti", "Poyraz A3 bitti: veri hattının 46 testi geçti.", "", ["tasks/poyraz-a3-veri-hatti.md"]),
    ("poyraz", "b2-yagmur", "Poyraz B2: yağmur başlamadan 30 dakika önce bildirim; aynı yağmur için ikinci bildirim gönderilmiyor.", "", ["tasks/poyraz-b2-bildirimler.md"]),
    ("poyraz", "b2-appid", "Poyraz B2: bildirimler geliştirme derlemesinde görünmüyordu; neden AppUserModelID'nin Başlat menüsü kısayoluna yazılmamasıydı.", "Windows bildirimi, AppUserModelID'si Başlat menüsündeki bir kısayolda kayıtlı uygulamadan gelmezse sessizce düşer.", ["tasks/poyraz-b2-bildirimler.md", "knowledge/concepts/windows-toast-appid.md"]),
    ("poyraz", "b3-kartlar", "Poyraz B3: yedi günlük kartlar; kartın üstüne gelince saatlik grafik açılıyor.", "", ["tasks/poyraz-b3-haftalik-kartlar.md"]),
    ("poyraz", "b3-bitti", "Poyraz B3 bitti; Deniz kart yazısının bir boy büyümesini istedi, yapıldı.", "", ["tasks/poyraz-b3-haftalik-kartlar.md"]),
    ("poyraz", "c1-konum", "Poyraz C1: şehir araması ve konum izni; izin verilmezse son seçilen şehir kullanılıyor.", "", ["tasks/poyraz-c1-konum.md"]),
    ("poyraz", "c1-bitti", "Poyraz C1 bitti: konum kişisel bilgi olarak hiçbir günlüğe yazılmıyor, ayarlarda yalnızca şehir adı duruyor.", "", ["tasks/poyraz-c1-konum.md"]),
    ("poyraz", "b1-olcum", "Poyraz B1: boşta işlemci %0,4, bellek 48 MB ölçüldü; hedef %0,2 ve 40 MB.", "", ["tasks/poyraz-b1-performans.md"]),
    ("poyraz", "b1-pil", "Poyraz B1: pil tasarrufu açıkken animasyon saniyede 30 kareye iniyor; boşta işlemci %0,25 oldu.", "", ["tasks/poyraz-b1-performans.md"]),
    ("poyraz", "b4-baslangic", "Poyraz B4: ayarlar penceresi başladı; sekmeler Genel, Birimler, Bildirimler.", "", ["tasks/poyraz-b4-ayarlar.md"]),
    ("poyraz", "c2-plan", "Poyraz C2: çevrimdışı önbellek planı yazıldı; üç günlük tahmin diskte saklanacak.", "", ["tasks/poyraz-c2-cevrimdisi.md"]),
    ("poyraz", "c3-takvim", "Poyraz C3: takvim entegrasyonu için Google Calendar API anahtarı gerekiyor; Deniz anahtarı kendisi oluşturacak, iş beklemede.", "", ["tasks/poyraz-c3-takvim.md"]),
    ("poyraz", "d1-msi", "Poyraz D1: imzasız MSI paketi denendi; SmartScreen uyarısı bekleniyordu, kurulum ve kaldırma temiz.", "", ["tasks/poyraz-d1-kurulum-paketi.md"]),
    ("poyraz", "b4-birimler", "Poyraz B4: birim seçimi (°C/°F, km/sa ve m/sn) ayarlara eklendi, anında uygulanıyor.", "", ["tasks/poyraz-b4-ayarlar.md"]),
    ("poyraz", "d1-winget", "Poyraz D1: winget bildirim dosyası taslağı hazırlandı; yayın Deniz'in kararında.", "", ["tasks/poyraz-d1-kurulum-paketi.md"]),
    ("poyraz", "haftalik", "Poyraz: haftalık gözden geçirme. Açık işler sıralandı: önce B1 ölçümü, sonra B4 ve D1. macOS sürümü gelen kutusuna alındı.", "", ["tasks/poyraz-d2-macos.md"]),
]
CINAR = [
    ("cinar", "konu", "Çınar: tez konusu netleşti; İstanbul'da sokak ağaçlarının yaz öğleden sonrası gölgesi. Veri: belediyenin ağaç envanteri ve sayısal yükseklik modeli.", "", []),
    ("cinar", "pilot", "Çınar: QGIS'te ilk gölge haritası, Kadıköy pilot alanı. 21 Haziran 15:00 için kaldırımların %38'i gölgede çıktı.", "", []),
    ("cinar", "dem", "Çınar: 1 m ve 5 m çözünürlüklü yükseklik modelleri karşılaştırıldı.", "5 m çözünürlükte tek ağaçların gölgesi kayboluyor; sokak ölçeği için 1 m gerekiyor.", ["knowledge/concepts/qgis-golge-dem.md"]),
    ("cinar", "danisman", "Çınar: danışman görüşmesi. Yöntem bölümü onaylandı; sıradaki iş literatür taraması ve karşılaştırma için ikinci bir ilçe.", "", []),
]
ATLAS = [
    ("atlas", "baslangic", "Atlas başlatıldı: kişisel okuma listesi, alıntılar ve okuma istatistiği. Yığın: FastAPI, SQLite, derleme adımı olmayan JavaScript.", "", []),
    ("atlas", "veri-modeli", "Atlas: veri modeli yazıldı (kitap, baskı, okuma oturumu, alıntı); göç betiği ve 18 test.", "", []),
    ("atlas", "goodreads", "Atlas: Goodreads CSV içe aktarma. 214 kitap aktarıldı, ISBN'siz 9 satır elle eşleştirilmek üzere listelendi.", "", []),
    ("atlas", "kitap-karti", "Atlas: kitap kartı; kapak, yazar ve okuma ilerlemesi çubuğu.", "", []),
    ("atlas", "oturum", "Atlas: okuma oturumu kaydı. Sayfa aralığı ve süre giriliyor, günün toplamı başlıkta görünüyor.", "", []),
    ("atlas", "fts5", "Atlas: SQLite FTS5 ile başlık, yazar ve alıntılarda arama.", "", ["knowledge/concepts/sqlite-fts5-turkce.md"]),
    ("atlas", "turkce-arama", "Atlas: \"istanbul\" araması \"İstanbul\"u bulmuyordu; arama metni Türkçe kurallarıyla küçültülüp ayrı bir sütunda tutuluyor.", "SQLite'ın lower() ve FTS5'in unicode61 belirteçleyicisi Türkçe İ/ı dönüşümünü bilmiyor; katlama uygulamada yapılmalı.", ["knowledge/concepts/sqlite-fts5-turkce.md"]),
    ("atlas", "etiketler", "Atlas: kitaplara çoklu etiket ve etiket bulutu.", "", []),
    ("atlas", "alintilar", "Atlas: alıntılar sayfası; alıntılar kitaba göre gruplu, kopyalama düğmesi var.", "", []),
    ("atlas", "kindle", "Atlas: Kindle \"My Clippings.txt\" içe aktarma. 1.380 vurgu okundu, 212 yinelenen ayıklandı.", "", []),
    ("atlas", "yinelenen", "Atlas: aynı vurgunun genişletilmiş hâli yinelenen sayılmıyordu; konum aralığı örtüşen vurgular birleştiriliyor.", "", []),
    ("atlas", "istatistik", "Atlas: istatistik sayfası; aylık okunan sayfa ve tür dağılımı grafikleri.", "", []),
    ("atlas", "hedef", "Atlas: yıllık kitap hedefi ve ilerleme halkası. Deniz'in 2026 hedefi 24 kitap, şu an 17.", "", []),
    ("atlas", "ci", "Atlas: 118 test; GitHub Actions'ta Linux ve Windows'ta koşuyor.", "", []),
    ("atlas", "koyu-tema", "Atlas: koyu tema; sistem ayarını izliyor, elle de seçilebiliyor.", "", []),
    ("atlas", "mobil", "Atlas: dar ekranda liste tek sütun, kapaklar küçülüyor.", "", []),
    ("atlas", "pwa", "Atlas: uygulama ağ yokken de açılıyor (servis çalışanı); okuma oturumları bağlantı gelince gönderiliyor.", "", []),
    ("atlas", "yedek", "Atlas: veritabanı her gece 03:00'te yedekleniyor, 14 gün saklanıyor. Geri yükleme bir kez denendi.", "", []),
    ("atlas", "kapaklar", "Atlas: kapak görselleri Open Library'den çekilip yerelde önbelleğe alınıyor.", "", []),
    ("atlas", "istek-siniri", "Atlas: toplu içe aktarmada Open Library istek sınırına takıldı; istekler saniyede bire indirildi ve yeniden denemeler aralıklı.", "", []),
    ("atlas", "klavye", "Atlas: bütün sayfalar klavyeyle geziliyor, odak halkaları görünür.", "", []),
    ("atlas", "paylasim", "Atlas: alıntıdan paylaşılabilir görsel kart üretiliyor (PNG).", "", []),
    ("atlas", "seri", "Atlas: okuma serisi göstergesi; üst üste okunan gün sayısı.", "", []),
    ("atlas", "sihirbaz", "Atlas: içe aktarma sihirbazı üç adımdan tek ekrana indi.", "", []),
    ("atlas", "performans", "Atlas: 2.000 kitaplık deneme verisinde liste 40 ms'de geliyor; kapak önbelleği olmadan 310 ms'ydi.", "", []),
    ("atlas", "saat-dilimi", "Atlas: gece yarısından sonra girilen oturum bir önceki güne yazılıyordu; günler artık yerel saatle hesaplanıyor.", "", []),
    ("atlas", "dil", "Atlas: ayarlara dil seçimi geldi (Türkçe, İngilizce).", "", []),
    ("atlas", "ingilizce", "Atlas: İngilizce çeviri bitti; tarih ve sayı biçimleri dile uyuyor.", "", []),
    ("atlas", "kitap-sayfasi", "Atlas: kitap sayfası sekmeli oldu (Notlar, Alıntılar, Oturumlar).", "", []),
    ("atlas", "disa-aktarma", "Atlas: Markdown'a dışa aktarma; her kitap bir not, alıntılar alıntı bloğu. Obsidian'da açılıp denendi.", "", []),
    ("atlas", "vurgulama", "Atlas: arama sonuçlarında eşleşen sözcük vurgulanıyor.", "", []),
    ("atlas", "seriler", "Atlas: kitap serileri; cilt sırası ve seride sıradaki kitap.", "", []),
    ("atlas", "siralama", "Atlas: okuma listesi sürükle-bırakla sıralanıyor.", "", []),
    ("atlas", "odunc", "Atlas: ödünç verilen kitaplar; kime, ne zaman ve hatırlatma.", "", []),
    ("atlas", "guvenlik", "Atlas: oturum çerezi SameSite=Strict, yazan isteklerde CSRF belirteci; güvenlik testleri eklendi.", "", []),
    ("atlas", "docker", "Atlas: Docker imajı 61 MB; veritabanı ayrı birimde.", "", []),
    ("atlas", "belgeler", "Atlas: README ve kurulum rehberi yazıldı.", "", []),
    ("atlas", "surum-010", "Atlas 0.1.0 yerelde etiketlendi; push Deniz isteyince.", "", []),
    ("atlas", "ekran", "Atlas: README'ye ekran görüntüleri eklendi.", "", []),
    ("atlas", "bom", "Atlas: bir arkadaşın CSV'si içe aktarılamadı; neden dosyanın başındaki BOM'du, okuma utf-8-sig ile yapılıyor.", "Excel'in kaydettiği CSV'ler BOM ile başlar; ilk sütunun adı BOM'lu okunursa eşleşmez.", []),
    ("atlas", "surum-011", "Atlas 0.1.1: BOM düzeltmesi ve kapak önbelleği temizliği.", "", []),
    ("atlas", "yol-haritasi", "Atlas: 0.2 yol haritası yazıldı; sesli kitap süresi, ortak listeler ve yıl sonu özeti.", "", []),
]

# Receipts per day, counted back from --today; the same rhythm as the vault the shape comes from.
PLAN = [
    (16, [SETUP, SETUP, KUMRU]),
    (15, [KUMRU, KUMRU]),
    (14, [KUMRU, KUMRU, KUMRU, KUMRU, POYRAZ, POYRAZ]),
    (13, [POYRAZ] * 5 + [KUMRU] * 2),
    (12, [POYRAZ] * 2),
    (11, [POYRAZ] * 6 + [KUMRU] * 2),
    (10, [POYRAZ] * 3 + [CINAR] * 2),
    (8, [CINAR]),
    (7, [KUMRU]),
    (4, [ATLAS] * 16 + [POYRAZ] * 5),
    (3, [ATLAS] * 6 + [POYRAZ] * 2),
    (2, [ATLAS] * 8 + [CINAR, KUMRU]),
    (1, [ATLAS] * 8 + [POYRAZ]),
    (0, [ATLAS] * 4),
]

# --- notes ---------------------------------------------------------------------------------------------------

TASKS = [
    # (file stem, phase, title, status, revision, next action, purpose, steps as (done, text))
    ("poyraz-a0-iskelet", "A0", "Proje iskeleti", "done", 2, "Bitti: tepsi simgesi görünüyor, CI yeşil.",
     "Tauri ve TypeScript ile boş ama derlenen bir uygulama, test ve lint altyapısı.",
     [(1, "Tauri projesi ve klasör düzeni"), (1, "ESLint, Prettier ve Vitest"), (1, "Tepsi simgesi ve çıkış menüsü"), (1, "GitHub Actions'ta Windows derlemesi")]),
    ("poyraz-a1-tema-motoru", "A1", "Tema motoru", "done", 3, "Bitti: dokuz sahne, seçim kalıcı.",
     "Hava durumuna ve günün saatine göre değişen gökyüzü ve sahne çizimleri.",
     [(1, "Gün doğumu ve batımına göre renk paletleri"), (1, "Dokuz hava sahnesi (playground'da onaylandı)"), (1, "Sahne geçişleri yumuşak"), (1, "Bilinmeyen hava kodunda \"açık\" sahne")]),
    ("poyraz-a2-pencere", "A2", "Pencere", "done", 2, "Bitti: kenarsız pencere, köşeye yapışma, keskin tepsi simgesi.",
     "Masaüstünde az yer kaplayan, istenince öne gelen pencere.",
     [(1, "Kenarsız pencere ve sürükleme"), (1, "\"Her zaman üstte\" seçeneği"), (1, "Ekran köşesine yapışma"), (1, "Yüksek DPI'da keskin simge")]),
    ("poyraz-a3-veri-hatti", "A3", "Veri hattı", "done", 2, "Bitti: 46 test geçti.",
     "Hava verisini düzenli ve hatalara dayanıklı biçimde almak.",
     [(1, "Open-Meteo istemcisi"), (1, "15 dakikalık tazeleme ve önbellek"), (1, "Ağ yokken son veriyi göster"), (1, "Hata durumunda geri çekilme")]),
    ("poyraz-b1-performans", "B1", "Performans", "active", 3, "Boşta işlemciyi %0,2'nin altına indir; ölçümü pil modunda tekrarla.",
     "Bütün gün açık kalan bir uygulamanın pili ve belleği yormaması.",
     [(1, "Boşta işlemci ve bellek ölçümü"), (1, "Pil tasarrufunda 30 kare"), (0, "Arka plandayken çizimi durdur"), (0, "Bellek hedefi: 40 MB")]),
    ("poyraz-b2-bildirimler", "B2", "Bildirimler", "done", 2, "Bitti: yağmur bildirimi tek sefer, AppUserModelID kayıtlı.",
     "Önemli hava değişikliklerinde rahatsız etmeyen bildirimler.",
     [(1, "Yağmurdan 30 dakika önce bildirim"), (1, "Aynı olay için ikinci bildirim yok"), (1, "AppUserModelID kısayola yazılıyor"), (1, "Sessiz saatler")]),
    ("poyraz-b3-haftalik-kartlar", "B3", "Haftalık kartlar", "done", 2, "Bitti; kart yazısı bir boy büyütüldü.",
     "Yedi günün tahmini bir bakışta.",
     [(1, "Yedi günlük kartlar"), (1, "Saatlik grafik üstüne gelince"), (1, "Kart yazısı büyütüldü")]),
    ("poyraz-b4-ayarlar", "B4", "Ayarlar penceresi", "active", 2, "Bildirimler sekmesini bitir; ayar dosyası sürüm alanını ekle.",
     "Bütün seçenekler tek pencerede, değişiklik anında uygulanır.",
     [(1, "Sekmeler: Genel, Birimler, Bildirimler"), (1, "Birim seçimi (°C/°F, km/sa, m/sn)"), (0, "Bildirimler sekmesi"), (0, "Ayar dosyasında sürüm alanı")]),
    ("poyraz-c1-konum", "C1", "Konum", "done", 2, "Bitti: konum günlüklere yazılmıyor.",
     "Şehir seçimi ve isteğe bağlı konum izni.",
     [(1, "Şehir araması"), (1, "Konum izni istemi"), (1, "İzin yoksa son seçilen şehir"), (1, "Konum günlüğe yazılmıyor")]),
    ("poyraz-c2-cevrimdisi", "C2", "Çevrimdışı önbellek", "active", 1, "Önbellek biçimini yaz: üç günlük tahmin, JSON, sürüm alanı.",
     "Ağ yokken de son üç günün tahmini.",
     [(1, "Plan yazıldı"), (0, "Diskte üç günlük tahmin"), (0, "Bozuk önbellekte sessizce yeniden çek")]),
    ("poyraz-c3-takvim", "C3", "Takvim entegrasyonu", "waiting", 1, "Deniz Google Calendar API anahtarını oluşturunca devam.",
     "Takvimdeki dış mekân etkinlikleri için hava uyarısı.",
     [(0, "API anahtarı (Deniz)"), (0, "Etkinlikleri okuma izni"), (0, "Etkinlik saatine göre uyarı")]),
    ("poyraz-d1-kurulum-paketi", "D1", "Kurulum paketi", "active", 2, "İmzalama sertifikası seçeneklerini karşılaştır; winget taslağını Deniz'e göster.",
     "Tek tıkla kurulan ve temiz kaldırılan paket.",
     [(1, "İmzasız MSI denemesi"), (1, "winget bildirim taslağı"), (0, "Kod imzalama"), (0, "Otomatik güncelleme")]),
    ("poyraz-d2-macos", "D2", "macOS sürümü", "inbox", 1, "Önce B1 ve D1 bitsin; sonra menü çubuğu tasarımı konuşulacak.",
     "Aynı arkadaş macOS menü çubuğunda.",
     [(0, "Menü çubuğu simgesi"), (0, "Bildirim izinleri")]),
]

FACTS = {
    # file stem: (project or None, title, points, sources)
    "postgres-cte-materialized": ("kumru", "PostgreSQL'de CTE'lerin sorguya gömülmesi", [
        "PostgreSQL 12'den önce her CTE ayrı hesaplanırdı (optimizasyon sınırı).",
        "12'den beri yan etkisi olmayan ve bir kez kullanılan CTE'ler ana sorguya gömülür.",
        "Eski davranış için `WITH x AS MATERIALIZED (...)`, gömmeyi zorlamak için `NOT MATERIALIZED` yazılır.",
    ], ["PostgreSQL belgeleri: WITH Queries"]),
    "postgres-explain-analyze": ("kumru", "EXPLAIN ANALYZE çıktısını okumak", [
        "`EXPLAIN` planı tahmin eder; `EXPLAIN ANALYZE` sorguyu gerçekten çalıştırır.",
        "Yazan sorgular için `BEGIN; EXPLAIN ANALYZE ...; ROLLBACK;` kullanılır.",
        "Tahmini satır sayısı ile gerçek satır sayısı arasındaki büyük fark, istatistiklerin eskidiğini gösterir.",
        "`BUFFERS` seçeneği önbellekten ve diskten okunan sayfaları ayırır.",
    ], ["PostgreSQL belgeleri: Using EXPLAIN"]),
    "postgres-index-only-scan": ("kumru", "Index-only scan ve görünürlük haritası", [
        "Sorgunun istediği bütün sütunlar indeksteyse PostgreSQL tabloya gitmeden yanıt verebilir.",
        "Bunun için sayfanın görünürlük haritasında \"hepsi görünür\" olarak işaretli olması gerekir.",
        "Yeni yazılmış sayfalar VACUUM görene kadar işaretsizdir; plan index-only olsa da \"Heap Fetches\" artar.",
    ], ["PostgreSQL belgeleri: Index-Only Scans"]),
    "postgres-partial-index": ("kumru", "Kısmi indeks", [
        "`CREATE INDEX ... WHERE durum = 'açık'` yalnızca koşulu sağlayan satırları indeksler.",
        "Sorgunun WHERE koşulu indeksin koşulunu içermelidir; planlayıcı bunu kendisi ispatlayabilmelidir.",
        "Az sayıda \"sıcak\" satırın olduğu büyük tablolarda indeksi küçük ve hızlı tutar.",
    ], ["PostgreSQL belgeleri: Partial Indexes"]),
    "postgres-jsonb-gin": ("kumru", "JSONB ve GIN indeksleri", [
        "`jsonb_ops` varsayılan sınıftır; `@>`, `?`, `?|` ve `?&` işleçlerini destekler.",
        "`jsonb_path_ops` daha küçüktür ama yalnızca `@>` içindir.",
        "`veri->>'alan' = 'x'` GIN indeksini kullanmaz; bunun için ifade indeksi gerekir.",
    ], ["PostgreSQL belgeleri: jsonb Indexing"]),
    "postgres-transaction-isolation": ("kumru", "İşlem yalıtım düzeyleri", [
        "PostgreSQL'in varsayılanı READ COMMITTED'dır: her komut kendi anlık görüntüsünü görür.",
        "REPEATABLE READ işlem boyunca tek bir anlık görüntü kullanır; çakışan güncellemede serileştirme hatası verir.",
        "SERIALIZABLE, hatalı sonuç verebilecek işlemleri iptal eder; uygulama yeniden denemeye hazır olmalıdır.",
    ], ["PostgreSQL belgeleri: Transaction Isolation"]),
    "postgres-lock-timeout": ("kumru", "lock_timeout ve statement_timeout", [
        "`lock_timeout` yalnızca kilit beklerken geçen süreyi sınırlar.",
        "`statement_timeout` komutun toplam süresini sınırlar.",
        "Göçlerde `SET lock_timeout = '3s'` uzun bir kilit kuyruğunun bütün uygulamayı durdurmasını önler.",
    ], ["PostgreSQL belgeleri: Client Connection Defaults"]),
    "postgres-vacuum-autovacuum": ("kumru", "VACUUM, autovacuum ve şişkinlik", [
        "Güncellenen ve silinen satırlar \"ölü\" olarak kalır; VACUUM yerlerini yeniden kullanılabilir yapar.",
        "`pg_stat_user_tables` içindeki `n_dead_tup` ve `last_autovacuum` ilk bakılacak yerlerdir.",
        "`VACUUM FULL` tabloyu yeniden yazar ve tablo boyunca kilitler; günlük bakım için değildir.",
    ], ["PostgreSQL belgeleri: Routine Vacuuming"]),
    "postgres-pgbouncer-pooling": ("kumru", "PgBouncer havuz kipleri", [
        "session kipinde istemci bağlantı boyunca aynı sunucu bağlantısını tutar.",
        "transaction kipinde sunucu bağlantısı işlem bitince başkasına verilir; `SET` ile değiştirilen oturum ayarları taşınmaz.",
        "Hazır ifadeler (prepared statements) transaction kipinde ancak PgBouncer 1.21 ve sonrasında, ayarla desteklenir.",
    ], ["PgBouncer belgeleri: Configuration"]),
    "postgres-generated-columns": ("kumru", "Üretilmiş sütunlar", [
        "`GENERATED ALWAYS AS (...) STORED` değeri yazarken hesaplar ve diskte saklar.",
        "İfade yalnızca aynı satırdaki sütunları ve değişmez (IMMUTABLE) fonksiyonları kullanabilir.",
        "Arama için küçük harfe çevrilmiş bir kopya tutmanın en kısa yoludur.",
    ], ["PostgreSQL belgeleri: Generated Columns"]),
    "tauri-tray-icon-dpi": ("poyraz", "Tepsi simgesi ve yüksek DPI", [
        "Windows tepsisi ekran ölçeğine göre 16, 20, 24 ya da 32 piksellik simge ister.",
        "Tek bir büyük PNG'yi küçültmek ince çizgileri bulanıklaştırır; ICO içine her boy ayrı çizilir.",
        "Ölçek değişince (başka ekrana taşıma) simge yeniden ayarlanmalıdır.",
    ], ["Microsoft belgeleri: Notification area icons"]),
    "windows-toast-appid": ("poyraz", "Windows bildirimleri ve AppUserModelID", [
        "Masaüstü uygulamasının bildirimi, AppUserModelID'si Başlat menüsündeki bir kısayolda kayıtlıysa görünür.",
        "Geliştirme derlemesinde kısayol yoksa bildirim hatasız ama sessizce düşer.",
        "Kurulum paketi kısayolu oluştururken kimliği de yazmalıdır.",
    ], ["Microsoft belgeleri: Send a local toast notification"]),
    "open-meteo-api": ("poyraz", "Open-Meteo kullanım notları", [
        "Ticari olmayan kullanım için anahtar gerekmez; günlük istek sınırı vardır.",
        "Saatlik ve günlük alanlar istekte tek tek seçilir; gereksiz alan istemek yanıtı büyütür.",
        "Saatler `timezone=auto` verilmezse UTC gelir.",
    ], ["open-meteo.com/en/docs"]),
    "sqlite-fts5-turkce": ("atlas", "SQLite FTS5 ile Türkçe arama", [
        "FTS5'in `unicode61` belirteçleyicisi büyük/küçük harfi Unicode'un genel kuralıyla katlar; Türkçe İ/ı'yı bilmez.",
        "\"İstanbul\" ile \"istanbul\"un eşleşmesi için metin uygulamada Türkçe kurallarıyla küçültülüp indekslenir.",
        "`remove_diacritics 2` aksanları siler ama ı ile i'yi birleştirmez.",
    ], ["SQLite belgeleri: FTS5"]),
    "qgis-golge-dem": ("cinar", "Gölge hesabında yükseklik modeli çözünürlüğü", [
        "5 m çözünürlükte tek bir sokak ağacı bir iki hücreye düşer; gölgesi kaybolur.",
        "1 m çözünürlük sokak ölçeğinde gölgeyi taşır ama hesap süresi yaklaşık 25 kat artar.",
        "Pilot alanda 1 m, şehir ölçeğinde 2 m bir orta yol olarak denenecek.",
    ], ["QGIS belgeleri: Hillshade"]),
    "git-worktree": (None, "git worktree ile paralel çalışma", [
        "`git worktree add ../dal-adi dal-adi` aynı deponun ikinci bir çalışma klasörünü açar.",
        "Bir dal aynı anda yalnızca bir çalışma klasöründe çıkarılabilir.",
        "İş bitince `git worktree remove` ile kaldırılır; klasörü elle silmek kaydı bırakır (`git worktree prune`).",
    ], ["git-scm.com/docs/git-worktree"]),
    "ssh-config-include": (None, "ssh_config'te Include ve Host sırası", [
        "`Include ~/.ssh/config.d/*` ek dosyaları okur; yol göreliyse `~/.ssh` altında aranır.",
        "Her ayarın ilk bulunan değeri geçerlidir; özel `Host` blokları genel `Host *` bloğundan önce yazılır.",
    ], ["man ssh_config"]),
    "unicode-nfc-nfd": (None, "Unicode NFC ve NFD", [
        "\"ş\" tek bir karakter (NFC) ya da \"s\" artı birleşen çengel (NFD) olarak yazılabilir.",
        "macOS dosya adlarını tarihsel olarak NFD'ye yakın tutar; Windows ve Linux olduğu gibi saklar.",
        "Karşılaştırmadan önce `unicodedata.normalize('NFC', metin)` ile iki taraf aynı biçime getirilir.",
    ], ["Unicode Standard Annex #15"]),
    "pipx-ve-venv": (None, "pipx ve venv ne zaman", [
        "Komut satırı araçları için pipx: her araç kendi ortamında, komutu PATH'te.",
        "Bir projenin bağımlılıkları için venv: proje klasöründe, projeyle birlikte.",
        "Sistemin Python'una `pip install` yapmak dağıtımın paketleriyle çakışır; yeni dağıtımlar bunu engeller (PEP 668).",
    ], ["PEP 668"]),
    "systemd-timer": (None, "cron yerine systemd zamanlayıcısı", [
        "`.timer` dosyası bir `.service` dosyasını tetikler; çıktı journal'a düşer (`journalctl -u ad`).",
        "`Persistent=true`, makine kapalıyken kaçırılan çalıştırmayı açılışta yapar.",
        "`systemctl list-timers` sonraki çalıştırma zamanlarını gösterir.",
    ], ["man systemd.timer"]),
}

NOTES = {
    "atlas": """# Atlas

Kişisel okuma listesi, alıntılar ve okuma istatistiği. Deniz'in kendi kullanımı için; yerelde ya da küçük bir sunucuda çalışır.

## Kararlar

- Yığın FastAPI, SQLite ve derleme adımı olmayan JavaScript. Yeni bağımlılık eklemeden önce Deniz'e sorulur.
- Veri Deniz'in makinesinde kalır; bulut eşitlemesi yok, dışa aktarma Markdown.
- Arama Türkçe kurallarıyla: \"İstanbul\" ile \"istanbul\" aynı sonucu verir ([[sqlite-fts5-turkce]]).

## Değişmez kurallar

- Testler koşmadan \"bitti\" denmez; çıktı gösterilir.
- Push ve sürüm yayını yalnızca Deniz isteyince.

## Durum

### 0.1.1 (yayınlandı, yerelde)

- İçe aktarma: Goodreads CSV, Kindle vurguları; BOM'lu dosyalar okunuyor.
- Okuma oturumları, yıllık hedef, okuma serisi, istatistik sayfası.
- Arama: başlık, yazar ve alıntılarda; sonuçlarda vurgulama.
- Koyu tema, dar ekran yerleşimi, klavyeyle gezinme, ağ yokken açılma.
- 131 test; Linux ve Windows'ta CI.

### Bilinen eksikler

- Kapak bulunamayan 9 kitap elle eşleştirilecek.
- Ödünç hatırlatması yalnızca uygulama açıkken çalışıyor.

## Yol haritası (0.2)

- [ ] Sesli kitaplar için dinleme süresi
- [ ] Ortak okuma listeleri (salt okunur paylaşım bağlantısı)
- [ ] Yıl sonu özeti
- [ ] Open Library dışında ikinci kapak kaynağı

## Sonraki adım

0.2 yol haritasından ilk iş seçilecek; Deniz'in önceliği yıl sonu özeti. Bağlam: [[Last-Session]], [[Threads]].
""",
    "poyraz": """# Poyraz

Windows tepsisinde yaşayan küçük bir hava durumu arkadaşı. Gökyüzü günün saatine ve havaya göre değişir; yağmurdan önce haber verir.

## Kullanıcı kararları

- Tauri ve TypeScript; Electron seçilmedi (bellek).
- Veri Open-Meteo'dan ([[open-meteo-api]]); anahtar gerekmez.
- Konum kişisel bilgidir: günlüğe yazılmaz, ayarlarda yalnızca şehir adı tutulur.
- Her aşama bitince Deniz onay verir, sonra sıradakine geçilir.

## Değişmez kurallar

- Boşta işlemci %0,5'i, bellek 60 MB'ı geçmez (ölçülür, tahmin edilmez).
- Bildirim aynı olay için bir kez gönderilir.

## Durum

### A: Temel (bitti)

- [[poyraz-a0-iskelet]], [[poyraz-a1-tema-motoru]], [[poyraz-a2-pencere]], [[poyraz-a3-veri-hatti]]

### B: Günlük kullanım

- [[poyraz-b1-performans]] (sürüyor; boşta %0,25)
- [[poyraz-b2-bildirimler]] (bitti), [[poyraz-b3-haftalik-kartlar]] (bitti)
- [[poyraz-b4-ayarlar]] (sürüyor)

### C: Bağlantılar

- [[poyraz-c1-konum]] (bitti), [[poyraz-c2-cevrimdisi]] (sürüyor)
- [[poyraz-c3-takvim]] (API anahtarı bekleniyor)

### D: Dağıtım

- [[poyraz-d1-kurulum-paketi]] (sürüyor), [[poyraz-d2-macos]] (gelen kutusu)

## Öğrenilenler

- Tepsi simgesi her boy için ayrı çizilir: [[tauri-tray-icon-dpi]].
- Bildirimler kısayolsuz düşer: [[windows-toast-appid]].

## Sonraki adım

B1 ölçümünü pil modunda tekrarlamak; sonra B4'ün Bildirimler sekmesi.
""",
    "kumru": """# Kumru

PostgreSQL'i alıştırma çözerek öğrenmek için küçük bir araç; rustlings'in yöntemi. Her alıştırma bir SQL dosyası, denetçi Docker'daki PostgreSQL 16'ya karşı koşar.

## Kararlar

- Alıştırmalar Türkçe; tablo ve sütun adları İngilizce.
- Her alıştırmada en az iki ipucu, çözüm en sonda.
- Denetçi iki oturum açabilir; yalıtım ve kilit alıştırmaları bunun için.

## Bölümler

| Bölüm | Alıştırma | Durum |
|---|---|---|
| Seçme ve süzme | 1–5 | bitti |
| JOIN | 6–10 | bitti |
| Toplama | 11–15 | bitti |
| Alt sorgu ve CTE | 16–20 | bitti |
| İndeksler | 21–26 | bitti |
| JSONB | 27–28 | bitti |
| İşlemler ve kilitler | 29–33 | bitti |
| Bakım | 34 | bitti |
| Bağlantı havuzu | 35– | taslak |

## Öğrenilenler

- [[postgres-cte-materialized]], [[postgres-explain-analyze]], [[postgres-index-only-scan]], [[postgres-partial-index]]
- [[postgres-jsonb-gin]], [[postgres-transaction-isolation]], [[postgres-lock-timeout]], [[postgres-vacuum-autovacuum]]
- [[postgres-pgbouncer-pooling]], [[postgres-generated-columns]]

## Sonraki adım

Bağlantı havuzu bölümünün taslağı Deniz'in onayını bekliyor; onaydan sonra PgBouncer'lı ikinci Docker hizmeti eklenecek.
""",
    "cinar": """# Çınar

Yüksek lisans tezi: İstanbul'da sokak ağaçlarının yaz öğleden sonrası kaldırımlara düşürdüğü gölge.

## Yöntem

- Veri: belediyenin ağaç envanteri (tür, gövde çapı, taç genişliği) ve sayısal yükseklik modeli.
- QGIS'te 21 Haziran için 12:00, 15:00 ve 18:00 gölgeleri; kaldırım katmanıyla kesişim.
- Çözünürlük: sokak ölçeğinde 1 m ([[qgis-golge-dem]]).

## Durum

- Pilot alan Kadıköy: 15:00'te kaldırımların %38'i gölgede.
- Danışman yöntem bölümünü onayladı.

## Sonraki adım

Literatür taraması; karşılaştırma için ikinci bir ilçe seçmek.
""",
}

LAST_SESSION = """# Son oturum

## {d0} 22:40 · Atlas: 0.1.1 ve yol haritası · 7c1e9a02

- **Ne yaptık:** bir arkadaşın CSV'si içe aktarılamıyordu (BOM); düzeltildi, 0.1.1 yerelde etiketlendi. 0.2 yol haritası yazıldı.
- **Sonraki adım:** 0.2'den ilk işi seçmek; Deniz'in önceliği yıl sonu özeti. Push yalnızca Deniz isteyince.
- **Kaynak:** [[atlas]]

## {d1} 23:10 · Atlas: sürüm 0.1.0, güvenlik, belgeler · 5b02d4e7

- **Ne yaptık:** oturum çerezi ve CSRF, Docker imajı (61 MB), README ve kurulum rehberi; 0.1.0 yerelde etiketlendi.
- **Poyraz:** haftalık gözden geçirme; sıra B1, B4, D1. macOS sürümü gelen kutusunda.
- **Sonraki adım:** bir arkadaşın içe aktarma denemesinin sonucuna bakmak.
- **Kaynak:** [[atlas]], [[poyraz]]

## Önceki oturumlar

Arşivlenen metin: `{companion}/Arşiv/Last-Session-{month}.md`
"""

THREADS = """# Threads

## Active Threads

### Atlas: 0.2 yol haritası

Yıl sonu özeti, ortak listeler, sesli kitap süresi. Kaynak: [[atlas]]

### Poyraz: performans ve kurulum paketi

B1 ölçümü pil modunda, sonra B4 ve D1. Takvim (C3) API anahtarını bekliyor. Kaynak: [[poyraz]]

### Kumru: bağlantı havuzu bölümü

Taslak Deniz'in onayında. Kaynak: [[kumru]]

### Çınar: literatür taraması

Danışman yöntemi onayladı; ikinci ilçe seçilecek. Kaynak: [[cinar]]

## Closed Threads

- Beyin kurulumu ve ilk geri okuma ({setup}).
"""

RULES = """# Kullanıcının düzeltmeleri

- {r0}: Testleri koşmadan \"bitti\" deme; çıktıyı göster.
- {r1}: Commit mesajları Türkçe, geçmiş zamanda.
- {r2}: Poyraz'da bir aşama bitince Deniz onaylamadan sıradakine geçme.
- {r3}: Konum ve ev adresi hiçbir dosyaya yazılmaz; örneklerde Kadıköy kullanılır.
- {r4}: Atlas'a yeni bağımlılık eklemeden önce sor.
- {r5}: Uzun açıklamadan önce iki cümlelik özet.
- {r6}: Push, etiket ve sürüm yalnızca Deniz isteyince.
"""

CORE = """---
{{
  "kind": "note",
  "title": "Core",
  "visibility": "private"
}}
---
# Core

## Kimlik

Deniz. İstanbul'da yazılım geliştirici; yüksek lisansta şehir ağaçları üzerine tez yazıyor. Hitap: Deniz.

## Çalışma biçimi

Kısa özet, sonra ayrıntı. Kararları kendisi verir; seçenekleri önerisiyle birlikte ister.
"""


def frontmatter(data: dict[str, object]) -> str:
    return "---\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n---\n"


def write(path: Path, text: str, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    os.utime(path, (when.timestamp(), when.timestamp()))


def receipts(today: date, rng: random.Random) -> list[dict[str, object]]:
    queues = {id(group): list(group) for group in (SETUP, KUMRU, POYRAZ, CINAR, ATLAS)}
    events = []
    for back, groups in PLAN:
        day = today - timedelta(days=back)
        minutes = sorted(rng.sample(range(10 * 60, 23 * 60 + 30), len(groups)))
        for group, minute in zip(groups, minutes):
            project, slug, summary, learned, extra = queues[id(group)].pop(0)
            stamp = datetime.combine(day, time(minute // 60, minute % 60, rng.randrange(60)), LOCAL)
            refs = ([f"notes/{project}.md"] if project in NOTES else []) + extra + [f"{COMPANION}/Last-Session.md"]
            events.append({"project": project, "event_id": f"{project}-{slug}-{day:%Y%m%d}", "stamp": stamp,
                           "summary": f"{summary}\nÖğrenilen: {learned or 'yok'}", "refs": refs,
                           "session": rng.getrandbits(96).to_bytes(12, "big").hex() if rng.random() < 0.62 else None})
    assert all(not queue for queue in queues.values()), "every receipt is used exactly once"
    return events


def build(out: Path, today: date, beyin_from: Path | None, beyin_state: str = "/tmp/beyin-web-demo-state") -> int:
    rng = random.Random(14)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    events = receipts(today, rng)
    last_touch: dict[str, datetime] = {}
    for event in events:
        for ref in event["refs"]:
            last_touch[ref] = max(last_touch.get(ref, event["stamp"]), event["stamp"])
    first = {project: min(e["stamp"] for e in events if e["project"] == project) for project in ("atlas", "poyraz", "kumru", "cinar")}

    def touched(path: str, fallback: datetime) -> datetime:
        return last_touch.get(path, fallback)

    for event in events:
        meta = {"kind": "receipt", "event_id": event["event_id"], "harness": "claude", "refs": event["refs"],
                "visibility": "internal", "created_at": event["stamp"].astimezone(timezone.utc).isoformat()}
        if event["session"]:
            meta["session"] = event["session"]
        name = hashlib.sha256(str(event["event_id"]).encode()).hexdigest()
        write(out / "receipts" / f"{name}.md", frontmatter(meta) + event["summary"] + "\n", event["stamp"])

    # Beyin's own projections of the receipts, in its format: one page per local day and one source index.
    days: dict[date, list[dict[str, object]]] = {}
    for event in events:
        days.setdefault(event["stamp"].date(), []).append(event)
    generated = frontmatter({"generated": True, "kind": "receipt-index"})
    for day, items in days.items():
        body = "".join(f"## {e['stamp'].astimezone(timezone.utc).isoformat()}\n\n{e['summary']}\n\n" for e in items)
        write(out / "daily" / "v3" / f"{day}.md",
              generated + "# Recorded outcomes\n\nAgent-authored claims, not independently verified facts.\n\n" + body,
              items[-1]["stamp"])
    index = "".join(f"- {e['stamp'].date()}: {e['summary']}\n  Source: [[receipts/{hashlib.sha256(str(e['event_id']).encode()).hexdigest()}.md]]\n"
                    for e in events)
    write(out / "knowledge" / "v3" / "outcomes.md",
          generated + "# Outcome source index\n\nThis index links semantic receipts. It is not an automatic knowledge compiler.\n\n" + index,
          events[-1]["stamp"])

    for stem, phase, title, status, revision, action, purpose, steps in TASKS:
        meta = {"id": stem, "title": f"Poyraz {phase}: {title}", "kind": "task", "revision": revision, "status": status,
                "owner": "Deniz", "visibility": "internal", "project": "poyraz", "next_action": action}
        body = purpose + "\n\n" + "".join(f"- [{'x' if done else ' '}] {text}\n" for done, text in steps)
        body += "\nPlan: Poyraz `docs/PLAN.md`. Bağlam: [[poyraz]]\n"
        path = f"tasks/{stem}.md"
        write(out / path, frontmatter(meta) + body, touched(path, first["poyraz"]))

    for project, text in NOTES.items():
        path = f"notes/{project}.md"
        write(out / path, frontmatter({"kind": "note", "project": project, "visibility": "internal"}) + text,
              touched(path, first[project]))
    write(out / "notes" / "Jüpiter.md",
          frontmatter({"kind": "fact", "visibility": "internal"})
          + "# Jüpiter\n\nDeniz'in en sevdiği gezegen Jüpiter. Eski Türkçedeki adı Erendiz.\n",
          touched("notes/Jüpiter.md", events[0]["stamp"]))

    for stem, (project, title, points, sources) in FACTS.items():
        meta = {"kind": "fact", "visibility": "internal"}
        if project:
            meta["project"] = project
        body = f"# {title}\n\n## Önemli noktalar\n\n" + "".join(f"- {point}\n" for point in points)
        body += "\n## Kaynaklar\n\n" + "".join(f"- {source}\n" for source in sources)
        if project:
            body += f"- Bağlam: [[{project}]]\n" if project in NOTES else ""
        path = f"knowledge/concepts/{stem}.md"
        fallback = first.get(project or "kumru", events[0]["stamp"]) + timedelta(hours=rng.randrange(1, 30))
        write(out / path, frontmatter(meta) + body, touched(path, fallback))
    links = "".join(f"- [[{stem}]]: {FACTS[stem][1]}\n" for stem in FACTS)
    write(out / "knowledge" / "index.md", frontmatter({"kind": "note", "visibility": "internal"})
          + "# Knowledge index\n\n" + links, first["kumru"] + timedelta(days=3))

    d = [today - timedelta(days=back) for back in range(40)]
    companion = out / COMPANION
    write(companion / "Last-Session.md",
          LAST_SESSION.format(d0=d[0], d1=d[1], companion=COMPANION, month=f"{d[16]:%Y-%m}"), events[-1]["stamp"])
    write(companion / "Threads.md", THREADS.format(setup=d[16]), events[-1]["stamp"] - timedelta(minutes=5))
    write(companion / "Kurallar.md", RULES.format(r0=d[14], r1=d[13], r2=d[11], r3=d[10], r4=d[4], r5=d[3], r6=d[1]),
          datetime.combine(d[1], time(23, 5), LOCAL))
    write(companion / "Journal.md", "# Journal\n\nOturum kartları Last-Session'da; eskileri Arşiv'de.\n",
          datetime.combine(d[16], time(12, 0), LOCAL))
    write(companion / "Core.md", CORE.format(), datetime.combine(d[16], time(11, 30), LOCAL))
    write(companion / "Arşiv" / f"Last-Session-{d[16]:%Y-%m}.md",
          f"# Son oturum arşivi\n\n## {d[16]} · Beyin kurulumu\n\n- Beyin kuruldu, ilk bilgi kaydedildi ve geri okundu ([[Jüpiter]]).\n",
          datetime.combine(d[2], time(9, 0), LOCAL))
    (out / "goals").mkdir()
    goals = {
        "anlamli-bir-is.md": ({"kind": "goal", "horizon": "long", "period": f"{today.year}–{today.year + 4}", "area": "Üretim"},
                              "# Kendi kullandığım araçları yapmak\n\nHer yıl bir aracı başkalarının da kullanabileceği hâle getirmek.\n\n- [x] Atlas 0.1\n- [ ] Poyraz'ın ilk sürümü\n- [ ] Kumru'yu yayınlamak\n"),
        "tez.md": ({"kind": "goal", "horizon": "long", "period": f"{today.year}–{today.year + 1}", "area": "Öğrenme"},
                   "# Tezi bitirmek\n\n- [x] Konu ve yöntem\n- [x] Pilot alan\n- [ ] Literatür taraması\n- [ ] İkinci ilçe\n- [ ] Yazım\n"),
        "kitap.md": ({"kind": "goal", "horizon": "year", "period": str(today.year), "area": "Öğrenme"},
                     "# 24 kitap okumak\n\nAtlas'taki sayaç: 17.\n"),
        "postgres.md": ({"kind": "goal", "horizon": "year", "period": str(today.year), "area": "Öğrenme"},
                        "# PostgreSQL'i derinlemesine öğrenmek\n\n- [x] Sorgular ve indeksler\n- [x] İşlemler ve kilitler\n- [ ] Çoğaltma\n- [ ] Yedekleme ve geri yükleme\n"),
        "yazi.md": ({"kind": "goal", "horizon": "year", "period": str(today.year), "area": "Üretim"},
                    "# Ayda bir yazı yayınlamak\n\n- [x] Ocak\n- [x] Şubat\n- [x] Mart\n- [ ] Nisan\n"),
        "tema.md": ({"kind": "goal", "horizon": "theme", "period": str(today.year)},
                    "# Az ama bitmiş\n\nYarım kalan on iş yerine bitmiş üç iş.\n"),
    }
    for name, (meta, body) in goals.items():
        write(out / "goals" / name, frontmatter(meta) + body, datetime.combine(d[15], time(20, 0), LOCAL))
    habits = {"okuma.md": ("Her gün 20 sayfa okumak", 0.8), "yuruyus.md": ("Yürüyüş", 0.55), "spor.md": ("Spor", 0.35)}
    for name, (title, chance) in habits.items():
        marks = [day for day in d[:28] if rng.random() < chance]
        body = f"# {title}\n\n" + "".join(f"- {day}\n" for day in sorted(marks))
        write(out / "goals" / name, frontmatter({"kind": "habit"}) + body, datetime.combine(d[0], time(21, 0), LOCAL))

    write(out / "AGENTS.md", "# Ajan yönergeleri\n\n<!-- beyin-v3:start -->\nBu vault Beyin V3 ile yönetilir.\n<!-- beyin-v3:end -->\n",
          datetime.combine(d[16], time(11, 0), LOCAL))
    write(out / "CLAUDE.md", "@AGENTS.md\n", datetime.combine(d[16], time(11, 0), LOCAL))

    if beyin_from is not None:
        # Only Beyin's program, never notes, never the source's .beyin-runtime.json: that file pins a vault to its
        # state folder. The demo gets its own, so Beyin keeps the demo's index apart from every real one.
        write(out / ".beyin-runtime.json", json.dumps({"state": beyin_state, "schema": 1}) + "\n", events[0]["stamp"])
        shutil.copy2(beyin_from / "beyin.py", out / "beyin.py")
        shutil.copy2(beyin_from / ".beyin-version", out / ".beyin-version")
        shutil.copytree(beyin_from / ".claude" / "scripts", out / ".claude" / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__", "*.bak*"))
    return len(events)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--beyin-from", type=Path, help="an installed Beyin vault to copy Beyin's program files from")
    parser.add_argument("--beyin-state", default="/tmp/beyin-web-demo-state", help="absolute state folder for the demo's Beyin")
    args = parser.parse_args(argv)
    count = build(args.out, args.today, args.beyin_from, args.beyin_state)
    print(f"demo vault: {count} receipts, {len(TASKS)} tasks, {len(FACTS)} knowledge notes -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
