"""Build the release archive that Beyin's `web kur` downloads, and pin its digest in the launcher.

    python3 scripts/build_release.py [--out dist] [--no-pin]

Writes dist/beyin-web-<version>.zip and dist/beyin-web-<version>.zip.sha256. The archive is reproducible:
the same tree gives the same bytes on any machine (sorted names, fixed dates and modes, stored without
compression, so no zlib version can change it). Unless --no-pin is given, VERSION and SHA256 in
upstream/beyin_v3_web.py are rewritten to match, so `kur --paket` accepts exactly this archive.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beyin_web import __version__  # noqa: E402

LAUNCHER = ROOT / "upstream" / "beyin_v3_web.py"
TOP_LEVEL = ("LICENSE", "README.md", "CHANGELOG.md")
DATE = (1980, 1, 1, 0, 0, 0)


def release_files(root: Path = ROOT) -> list[tuple[str, Path]]:
    """The files of the release: what git tracks under beyin_web/ (a stray local file stays out), or every
    file there when the tree is not a git checkout (an unpacked source archive)."""
    try:
        listed = subprocess.run(["git", "ls-files", "-z", "--", "beyin_web"], cwd=root, capture_output=True,
                                check=True, timeout=60).stdout.decode("utf-8").split("\0")
        names = [name for name in listed if name]
    except (OSError, subprocess.SubprocessError):
        names = [path.relative_to(root).as_posix() for path in (root / "beyin_web").rglob("*") if path.is_file()]
    names = [name for name in names if "__pycache__" not in name.split("/") and not name.endswith((".pyc", ".pyo"))
             and (root / name).is_file()]
    return sorted((name, root / name) for name in [*TOP_LEVEL, *names])


def build(root: Path = ROOT) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, path in release_files(root):
            entry = zipfile.ZipInfo(name, DATE)
            entry.external_attr = 0o100644 << 16
            entry.create_system = 3
            archive.writestr(entry, path.read_bytes())
    return buffer.getvalue()


def pin(launcher: Path, version: str, digest: str) -> None:
    text = launcher.read_text(encoding="utf-8")
    text, versions = re.subn(r"^VERSION = '[^']*'$", f"VERSION = '{version}'", text, count=1, flags=re.M)
    text, digests = re.subn(r"^SHA256 = '[0-9a-f]{64}'$", f"SHA256 = '{digest}'", text, count=1, flags=re.M)
    if versions != 1 or digests != 1:
        raise SystemExit(f"{launcher}: VERSION or SHA256 line not found")
    launcher.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--no-pin", action="store_true")
    args = parser.parse_args(argv)
    data = build()
    digest = hashlib.sha256(data).hexdigest()
    name = f"beyin-web-{__version__}.zip"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / name).write_bytes(data)
    (args.out / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8", newline="\n")
    if not args.no_pin:
        pin(LAUNCHER, __version__, digest)
    print(f"{args.out / name}: {len(data) // 1024} KB, sha256 {digest}" + ("" if args.no_pin else f"; pinned in {LAUNCHER.name}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
