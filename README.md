# beyin-web

[AvenoxBeyin](https://github.com/avenoxai/avenoxbeyin) ile tutulan bir ikinci beyin vault'unu sade bir web arayüzünde gösteren, yerel ve isteğe bağlı bir uygulama. Amaç Obsidian'ı bilmeyen birinin de notlarını, projelerini ve asistanının hafızasını rahatça okuyabilmesi.

**Durum:** plan aşaması. Henüz çalışan kod yok.

## İlkeler

- Markdown esastır; arayüz hiçbir veriyi sahiplenmez.
- İlk sürüm salt okunur: vault'a ve Beyin'in durumuna yazmaz.
- Yalnızca yerel: `127.0.0.1`, dışarı ağ çağrısı yok.
- Kurulumu bağımlılıksız: Python standart kütüphanesi, derleme adımı yok.
- Gizli (`visibility: private`) notlar gösterilmez.

## Belgeler

- [`docs/PLAN.md`](docs/PLAN.md): mimari, veri modeli, API, sayfalar, iş paketleri.
- [`docs/specs/`](docs/specs/): paket başına iş tarifleri.
- [`AGENTS.md`](AGENTS.md): kod ajanları için kurallar.

## Lisans

MIT. Bkz. [`LICENSE`](LICENSE).
