# Sentetik vault

Bütün adlar ve içerikler uydurmadır; tarihler Ocak 2026'dır. Gerçek vault okunmaz.
Kaynak notlar UTF-8 olarak tutulur; CRLF, BOM ve sembolik bağ `make_vault()` çağrısında oluşturulur.
`mtimes.json` UTC ISO 8601 zamanlarını yollarla eşler; listede olmayan dosyaların zamanı 2026-01-01T00:00:00+00:00 olur.

| Dosya (vault köküne göre) | Sınanan kural |
|---|---|
| `AGENTS.md` | Vault kökündeki talimat dosyalarının taramadan dışlanması. |
| `.obsidian/app.json` | Noktayla başlayan klasörlerin taramadan dışlanması. |
| `node_modules/paket/README.md` | node_modules klasörünün taramadan dışlanması. |
| `notes/atlas.md` | JSON frontmatter; düz, takma adlı, başlıklı, eksik ve gizli wikilink'ler; kod bloğundaki bağlantının dışlanması. |
| `notes/Çınar Projesi.md` | Düz YAML, satır içi ve girintili listeler, sonda yorum, Türkçe dosya adı ve çalışma anında CRLF dönüşümü. |
| `notes/serbest.md` | Frontmatter olmadan ilk başlıktan ad türetme ve çalışma anında UTF-8 BOM ekleme. |
| `notes/başlıksız.md` | Frontmatter ve başlık yokken dosya adına geri düşme. |
| `notes/gizli.md` | Gizli kaydın başlığının ve gövdesinin veri katmanında elenmesi. |
| `notes/bos.md` | Sıfır baytlık dosyanın taramadan dışlanması. |
| `notes/bozuk.md` | Kapanmayan frontmatter için uyarı ve frontmatter'sız nota geri düşme. |
| `notes/güvenilmez.md` | Güvenilmez tür rozeti, ham HTML ve uzak görselin güvenli gösterimi. |
| `notes/tuhaf-görünürlük.md` | Geçersiz visibility değerinin ayrıştırılması. |
| `knowledge/index.md` | Bilgi dizinindeki wikilink ve tek satırlık özetlerin çıkarılması. |
| `knowledge/concepts/kavram-bir.md` | Proje bağlı bilgi notu, tablo, kod bloğu ve görev kutularının gösterimi. |
| `knowledge/concepts/kavram-iki.md` | Projesiz bilgi notu, başlık hedefi ve proje notuna geri bağlantı. |
| `knowledge/concepts/reddedilen.md` | Reddedilen çıkarımın listelerden elenmesi ve ret alanlarının korunması. |
| `knowledge/v3/outcomes.md` | Otomatik bilgi dizininin listelerden ve grafikten elenmesi. |
| `daily/v3/2026-01-05.md` | Otomatik günlük dizininin listelerden ve grafikten elenmesi. |
| `tasks/cinar-1.md` | Gelen kutusu durumu, Çınar projesi ve yaklaşan review_at tarihi. |
| `🔮 850-Companion/Core.md` | Emoji adlı hafıza klasörünün keşfi ve kimlik metninin olduğu gibi korunması. |
| `🔮 850-Companion/Kurallar.md` | Tam biçimli kural, gerekçesiz kural ve biçimsiz madde için ayrıştırma ve geri düşme. |
| `🔮 850-Companion/Last-Session.md` | Saatli ve saatsiz oturum başlıkları, win-offline kimliği ve önceki oturumlar bölümünün dışlanması. |
| `🔮 850-Companion/Threads.md` | Dört etiketli etkin konu, serbest metinli konu ve kapanan konu ayrımı. |
| `🔮 850-Companion/Journal.md` | Kısa hafıza günlüğünün rolünün tanınması. |
| `🔮 850-Companion/Arşiv/Last-Session-2026-01.md` | Hafıza arşivindeki private kaydın elenmesi. |
| `tasks/atlas-a1.md` | Atlas done görevi; kimlik, başlık, sahip ve revizyon. |
| `tasks/atlas-a2.md` | Atlas done görevi; kimlik, başlık, sahip ve revizyon. |
| `tasks/atlas-a3.md` | Atlas active görevi; kimlik, başlık, sahip ve revizyon, next_action ve dört kutudan ikisinin işaretli olması. |
| `tasks/atlas-a4.md` | Atlas waiting görevi; kimlik, başlık, sahip ve revizyon, yaklaşan due_at tarihi. |
| `tasks/atlas-a5.md` | Atlas blocked görevi; kimlik, başlık, sahip ve revizyon. |
| `tasks/atlas-a6.md` | Atlas cancelled görevi; kimlik, başlık, sahip ve revizyon, ilerleme paydasından çıkarılması. |
| `receipts/0000000000000000000000000000000000000000000000000000000000000001.md` | r1: Özetin hemen altındaki (boş satırsız, gerçek biçim) boş öğrenilen alanının ayrılması ve refs üzerinden Atlas projesinin bulunması. |
| `receipts/0000000000000000000000000000000000000000000000000000000000000002.md` | r2: Çoklu refs, codex kaynağı ve dolu öğrenilen alanının ayrılması. |
| `receipts/0000000000000000000000000000000000000000000000000000000000000003.md` | r3: UTC+3 saat diliminde 6 Ocak gününe düşmesi ve öğrenilen satırının bulunmaması. |
| `receipts/0000000000000000000000000000000000000000000000000000000000000004.md` | r4: Hafıza refs değerinin proje hesabından dışlanması ve cinar önekinden proje çıkarımı. |
| `receipts/0000000000000000000000000000000000000000000000000000000000000005.md` | r5: Proje öneki ve proje taşıyan kaynak bulunmadığında projesiz kalması. |
| `receipts/0000000000000000000000000000000000000000000000000000000000000006.md` | r6: Session alanının korunması, mikrosaniyeli `created_at` ve Türkçe dosya adlı refs üzerinden proje bulunması. |
| `notes/dışarı.md` (çalışma anında) | Vault kökü dışındaki `outside/hedef.md` hedefine bağ; destek yoksa `has_outside_link()` ile test atlama. |

`outside/hedef.md`, geçici vault'un kardeş klasöründe oluşturulur ve `KOK-DISI-ISARETI` içerir.
Sembolik bağ kurulamadığında diğer dönüşümler ve sabit zamanlar uygulanmaya devam eder.
