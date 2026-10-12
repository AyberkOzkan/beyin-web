from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

FIXTURES: Path = Path(__file__).parent / "fixtures"
DEFAULT_MTIME: float = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()


def make_vault(tmp: Path) -> Path:
    vault = tmp / "vault"
    shutil.copytree(FIXTURES / "vault", vault)

    project_note = vault / "notes" / "Çınar Projesi.md"
    project_text = project_note.read_text(encoding="utf-8")
    project_note.write_text(
        project_text.replace("\n", "\r\n"), encoding="utf-8", newline=""
    )
    free_note = vault / "notes" / "serbest.md"
    free_text = free_note.read_text(encoding="utf-8").lstrip("\ufeff")
    free_note.write_text("\ufeff" + free_text, encoding="utf-8", newline="")

    outside = tmp / "outside" / "hedef.md"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("KOK-DISI-ISARETI\n", encoding="utf-8", newline="")
    try:
        (vault / "notes" / "dışarı.md").symlink_to(outside.resolve())
    except (OSError, NotImplementedError):
        pass

    mtimes = json.loads((FIXTURES / "mtimes.json").read_text(encoding="utf-8"))
    # Apply timestamps last so the encoding transformations do not replace them.
    for path in vault.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        value = mtimes.get(path.relative_to(vault).as_posix())
        timestamp = datetime.fromisoformat(value).timestamp() if value else DEFAULT_MTIME
        timestamp_ns = int(timestamp * 1_000_000_000)
        os.utime(path, ns=(timestamp_ns, timestamp_ns))
    return vault


def has_outside_link(vault: Path) -> bool:
    return (vault / "notes" / "dışarı.md").is_symlink()


GOALS: dict[str, str] = {
    "kitap.md": '---\n{"kind": "goal", "horizon": "year", "period": 2026, "area": "öğrenme"}\n---\n'
                "# 12 kitap okumak\n\n- [x] Birinci kitap\n- [ ] İkinci kitap\n- [ ] Üçüncü kitap\n",
    "is.md": '---\n{"kind": "goal", "horizon": "long", "period": "2025–2030", "area": "Üretim"}\n---\n'
             "# Anlamlı bir iş üretmek\n\nKalıcı bir şey bırakmak.\n\n- [x] İlk taslak\n- [ ] Yayın\n",
    "yazi.md": '---\n{"kind": "goal", "horizon": "year", "period": "2026", "area": "Üretim"}\n---\n'
               "# Aylık bir yazı paylaşmak\n",
    "etiketsiz.md": '---\n{"kind": "goal", "horizon": "someday"}\n---\n# Etiketsiz hedef\n',
    "tema.md": '---\n{"kind": "goal", "horizon": "theme", "period": "2026"}\n---\n'
               "# Derinleş ve inşa et\n\nBildiklerimi pratiğe dönüştür.\n",
    "gizli.md": '---\n{"kind": "goal", "horizon": "year", "visibility": "private"}\n---\n'
                "# GIZLI-HEDEF\n\n- [ ] GIZLI-HEDEF\n",
    "spor.md": '---\n{"kind": "habit"}\n---\n# Spor yapmak\n\n- 2026-01-03\n- 2026-01-09\n- 2026-01-12\n',
    "okuma.md": '---\n{"kind": "habit"}\n---\n# Kitap okumak\n',
}


def add_goals(vault: Path) -> None:
    """Give a vault copy goals and habits; the shared fixture has none, so other pages' data stays as it is."""
    folder = vault / "goals"
    folder.mkdir()
    timestamp_ns = int(DEFAULT_MTIME * 1_000_000_000)
    for name, text in GOALS.items():
        path = folder / name
        path.write_text(text, encoding="utf-8", newline="")
        os.utime(path, ns=(timestamp_ns, timestamp_ns))
