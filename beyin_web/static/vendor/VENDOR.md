# Üçüncü taraf dosyalar

Bu klasördeki dosyalar npm kayıt defterindeki paketlerden 2026-10-11 tarihinde alındı. Her paketin arşivi indirildi, kayıt defterindeki bütünlük değeriyle (`dist.integrity`) doğrulandı ve yalnızca aşağıdaki dosyalar kopyalandı. Lisans metinleri `licenses/` altındadır.

| Dosya | Kaynak | Paketteki yol | Lisans | SHA-256 |
|---|---|---|---|---|
| `markdown-it.esm.min.js` | npm markdown-it@15.0.2 | `dist/browser/markdown-it.esm.min.mjs` | MIT | `85feb50fd6ce1b7c49acb02b0337eb622ecc4fc2ed4ae0dcbb8c084556d463b6` |
| `d3-dispatch.min.js` | npm d3-dispatch@3.0.1 | `dist/d3-dispatch.min.js` | ISC | `94b3bbdb6b98dc1325a15762b051013e8253999b0e0436b27d1da17b952ba0af` |
| `d3-quadtree.min.js` | npm d3-quadtree@3.0.1 | `dist/d3-quadtree.min.js` | ISC | `57e2ad12824ed82893ba447523f2a2fb9beeb9222aafb2c778a9f5b313348b0e` |
| `d3-timer.min.js` | npm d3-timer@3.0.1 | `dist/d3-timer.min.js` | ISC | `911ceda305f014b6b53ca68d5c896a9a387da120cfd56a421a2c60cca2fc9b36` |
| `d3-force.min.js` | npm d3-force@3.0.0 | `dist/d3-force.min.js` | ISC | `1e07b473241328795d5ea9ad479a7bbabd765012fa2ef95633c83b69868dff6b` |
| `lucide-sprite.svg` | npm lucide-static@1.55.0 | `icons/*.svg (68 ikon, betikle birleştirildi)` | ISC | `a85fcc299637749fd2019ea0d61e315e0b0820c5615808206c1a4018c45bb7e7` |
| `fonts/eb-garamond-latin-wght-normal.woff2` | npm @fontsource-variable/eb-garamond@5.3.0 | `files/eb-garamond-latin-wght-normal.woff2` | OFL-1.1 | `88603384163d301aebd5bd769832a8bfe3c9004ec24178417b9817f0ad32c63b` |
| `fonts/eb-garamond-latin-ext-wght-normal.woff2` | npm @fontsource-variable/eb-garamond@5.3.0 | `files/eb-garamond-latin-ext-wght-normal.woff2` | OFL-1.1 | `f8d3fa06e20989a938972165406a1b731cdc7fe33ff2b0b6798c75aa63709901` |
| `fonts/eb-garamond-latin-wght-italic.woff2` | npm @fontsource-variable/eb-garamond@5.3.0 | `files/eb-garamond-latin-wght-italic.woff2` | OFL-1.1 | `c664773f7e1d42d36326aa457becf7674236168c74cf7d74e87e5778ef7640f9` |
| `fonts/eb-garamond-latin-ext-wght-italic.woff2` | npm @fontsource-variable/eb-garamond@5.3.0 | `files/eb-garamond-latin-ext-wght-italic.woff2` | OFL-1.1 | `fa866520f8b7fb646ebc730fd0d3cbf8945db74d92f25fdd6fee486808652fdf` |
| `fonts/source-serif-4-latin-wght-normal.woff2` | npm @fontsource-variable/source-serif-4@5.3.1 | `files/source-serif-4-latin-wght-normal.woff2` | OFL-1.1 | `382475f38242c52d42a3e5ff8dc69b5d73f10d0d21e4550b5fe232984688779a` |
| `fonts/source-serif-4-latin-ext-wght-normal.woff2` | npm @fontsource-variable/source-serif-4@5.3.1 | `files/source-serif-4-latin-ext-wght-normal.woff2` | OFL-1.1 | `d10ccbbd0dc4ebae2938958dc1f622a53460fe297e9c958564742dd684309c3f` |
| `fonts/source-serif-4-latin-wght-italic.woff2` | npm @fontsource-variable/source-serif-4@5.3.1 | `files/source-serif-4-latin-wght-italic.woff2` | OFL-1.1 | `b4f56ddc9873487f1c9a3ad5bbce31982fe89b951f57e4604f62b4c8a540fb19` |
| `fonts/source-serif-4-latin-ext-wght-italic.woff2` | npm @fontsource-variable/source-serif-4@5.3.1 | `files/source-serif-4-latin-ext-wght-italic.woff2` | OFL-1.1 | `14e38c2d6a4ea6effcddde38f0262c03af252cbf82dbc68037f2d6c9112f2097` |
| `fonts/fonts.css` | Fontsource stil dosyalarından türetildi | `wght.css, wght-italic.css (yalnız latin ve latin-ext)` | OFL-1.1 | `7e61ba60003c058b14ffc9dd9908d5073195bf07a4f6730a42e8d14f2d50296a` |

## Notlar

- `markdown-it.esm.min.js`: paketin tarayıcı için tek dosyalık ES modülü; uzantısı sunucunun içerik türü tablosuna uysun diye `.mjs`'ten `.js`'e çevrildi, içeriği aynıdır. `import markdownit from "…/markdown-it.esm.min.js"` ile yüklenir.
- `d3-*.min.js`: UMD dosyaları; `<script src>` ile şu sırada yüklenir ve `window.d3` altında birleşir: `d3-dispatch`, `d3-quadtree`, `d3-timer`, `d3-force`.
- `lucide-sprite.svg`: Lucide ikonlarından 68 tanesi tek dosyada, her biri `<symbol id="ad">`. Kullanım: `<svg class="icon"><use href="/static/vendor/lucide-sprite.svg#ad"></use></svg>`; çizgi rengi ve kalınlığı `<svg>` üzerinden CSS ile verilir. İkonlar: house, folder-kanban, book-open, calendar-days, calendar, waypoints, search, brain, settings, circle, circle-check, circle-dot, circle-dashed, circle-x, circle-pause, circle-alert, check, x, chevron-right, chevron-down, chevron-left, chevron-up, arrow-right, arrow-left, external-link, clock, history, file-text, notebook-text, scroll-text, list-todo, square-check, square, triangle-alert, info, refresh-cw, ellipsis, funnel, zoom-in, zoom-out, maximize, link, lock, eye-off, hourglass, ban, inbox, bot, terminal, sparkles, lightbulb, activity, layers, receipt, target, user, shield-check, message-square, network, hash, quote, flag, sunrise, sun, moon, panel-right, menu, tag.
- Yazı tipleri değişken ağırlıklıdır (EB Garamond 400–800, Source Serif 4 200–900). `latin` ve `latin-ext` alt kümeleri Türkçe harflerin tamamını kapsar (ç, ö, ü `latin`'de; ğ, ı, İ, ş `latin-ext`'te). `fonts/fonts.css` `@font-face` kurallarını ve `unicode-range` değerlerini taşır.
- Güncelleme: sürüm değişince dosya yeniden alınır ve bu tablo ile SHA-256 değerleri yenilenir.
