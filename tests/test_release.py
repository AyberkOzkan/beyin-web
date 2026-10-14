from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from beyin_web import __version__
from scripts import build_release
from tests.support import make_vault
from upstream import beyin_v3_web as launcher

ROOT = Path(__file__).resolve().parents[1]


def archive(entries: dict[str, bytes], links: tuple[str, ...] = ()) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as handle:
        for name, data in entries.items():
            entry = zipfile.ZipInfo(name)
            if name in links:
                entry.external_attr = 0o120777 << 16
            handle.writestr(entry, data)
    return buffer.getvalue()


class ReleaseArchiveTests(unittest.TestCase):
    def test_archive_is_reproducible_and_holds_only_the_package(self) -> None:
        first, second = build_release.build(), build_release.build()
        self.assertEqual(first, second)
        with zipfile.ZipFile(io.BytesIO(first)) as handle:
            entries = handle.infolist()
        names = [entry.filename for entry in entries]
        self.assertEqual(names, sorted(names))
        self.assertEqual({name.split("/")[0] for name in names}, {"beyin_web", "LICENSE", "README.md", "CHANGELOG.md"})
        for expected in ("beyin_web/__main__.py", "beyin_web/static/index.html", "beyin_web/assets/app-icon.ico",
                         "beyin_web/assets/app-icon.png"):
            self.assertIn(expected, names)
        self.assertFalse([name for name in names if "__pycache__" in name or name.endswith(".pyc")])
        for entry in entries:
            self.assertEqual((entry.date_time, entry.compress_type, entry.external_attr >> 16),
                             ((1980, 1, 1, 0, 0, 0), zipfile.ZIP_STORED, 0o100644))

    def test_pin_rewrites_only_the_two_lines(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "beyin_v3_web.py"
            shutil.copyfile(launcher.__file__, copy)
            before = copy.read_text(encoding="utf-8")
            build_release.pin(copy, "9.8.7", "ab" * 32)
            after = copy.read_text(encoding="utf-8")
            self.assertIn("VERSION = '9.8.7'\n", after)
            self.assertIn(f"SHA256 = '{'ab' * 32}'\n", after)
            self.assertEqual(len(before.splitlines()), len(after.splitlines()))
            self.assertEqual(sum(a != b for a, b in zip(before.splitlines(), after.splitlines())), 2)
            copy.write_text("x = 1\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                build_release.pin(copy, "1", "ab" * 32)

    def test_launcher_follows_the_package_version_and_stays_small_and_standalone(self) -> None:
        self.assertEqual(launcher.VERSION, __version__)
        source = Path(launcher.__file__).read_text(encoding="utf-8")
        self.assertLess(len(source.encode("utf-8")), 24_000)
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertLessEqual(imported, set(sys.stdlib_module_names))


class LauncherTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)
        self.state = self.root / "state"
        self.package = self.root / "beyin-web.zip"
        self.package.write_bytes(build_release.build())
        self.digest = hashlib.sha256(self.package.read_bytes()).hexdigest()
        pinned = patch.object(launcher, "SHA256", self.digest)
        pinned.start()
        self.addCleanup(pinned.stop)
        # Whatever the installed copy writes for itself (a token for the status probe) stays in the test folder.
        self.env = {**launcher._python_env(), "APPDATA": str(self.root / "config"), "XDG_CONFIG_HOME": str(self.root / "config"),
                    "XDG_DATA_HOME": str(self.root / "share")}
        self.env.pop("WSL_DISTRO_NAME", None)

    def vault_files(self) -> list[str]:
        return sorted(str(path.relative_to(self.vault)) for path in self.vault.rglob("*"))


class LauncherTests(LauncherTestCase):
    def test_state_folder_is_found_the_way_beyin_finds_it(self) -> None:
        default = launcher.default_state(self.vault.resolve())
        self.assertEqual(default.parent.name, "beyin-v3")
        self.assertEqual(default.name, hashlib.sha256(str(self.vault.resolve()).encode()).hexdigest()[:16])
        self.assertEqual(launcher.resolve_state(self.vault), default)
        config = self.vault / ".beyin-runtime.json"
        config.write_text(json.dumps({"state": str(self.state)}), encoding="utf-8")
        self.assertEqual(launcher.resolve_state(self.vault), self.state)
        # A pin from another machine through a synced vault is not absolute here and is not followed.
        config.write_text(json.dumps({"state": "relative/state"}), encoding="utf-8")
        self.assertEqual(launcher.resolve_state(self.vault), default)

    def test_install_status_and_uninstall_leave_the_vault_alone(self) -> None:
        before = self.vault_files()
        self.assertFalse(launcher.status(self.vault, self.state, env=self.env)["kurulu"])
        stale = self.state / "web" / "0.0.1"
        stale.mkdir(parents=True)
        done = launcher.install(self.vault, self.state, package=self.package, shortcut=False, language="en")
        app = self.state / "web" / __version__
        self.assertEqual((done["status"], done["surum"], Path(done["klasor"]), done["kisayol"]),
                         ("kuruldu", __version__, app.resolve(), []))
        self.assertTrue((app / "beyin_web" / "assets" / "app-icon.ico").is_file())
        self.assertFalse(stale.exists())
        self.assertEqual(json.loads((self.state / "web.json").read_text(encoding="utf-8")),
                         {"schema": 1, "surum": __version__, "sha256": self.digest, "dil": "en", "kisayol": []})
        result = subprocess.run([sys.executable, "-m", "beyin_web", "--version"], cwd=app, env=self.env,
                                capture_output=True, encoding="utf-8", timeout=60, check=False)
        self.assertEqual(result.stdout, f"beyin-web {__version__}\n")
        state = launcher.status(self.vault, self.state, env=self.env)
        self.assertEqual((state["kurulu"], state["surum"], state["guncel"], state["calisiyor"]),
                         (True, __version__, True, None))
        with patch.object(launcher, "SHA256", "0" * 64):
            self.assertFalse(launcher.status(self.vault, self.state, env=self.env)["guncel"])
        removed = launcher.uninstall(self.vault, self.state)
        self.assertEqual(removed["kaldirilan"], ["web/", "web.json"])
        self.assertEqual(list(self.state.iterdir()), [])
        self.assertEqual(self.vault_files(), before)

    def test_a_package_with_another_digest_changes_nothing(self) -> None:
        launcher.install(self.vault, self.state, package=self.package, shortcut=False)
        record = (self.state / "web.json").read_text(encoding="utf-8")
        other = self.root / "other.zip"
        other.write_bytes(self.package.read_bytes() + b"\0")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            launcher.install(self.vault, self.state, package=other, shortcut=False)
        self.assertEqual((self.state / "web.json").read_text(encoding="utf-8"), record)
        self.assertTrue((self.state / "web" / __version__ / "beyin_web" / "__main__.py").is_file())

    def test_unpack_refuses_what_a_release_never_holds_and_keeps_the_old_copy(self) -> None:
        target = self.root / "app"
        launcher.unpack(self.package.read_bytes(), target)
        good = {"beyin_web/__main__.py": b"x = 1\n"}
        cases = {"parent": {**good, "beyin_web/../../escape.py": b""}, "absolute": {**good, "/etc/escape": b""},
                 "drive": {**good, "C:/escape": b""}, "backslash": {**good, "beyin_web\\..\\escape": b""},
                 "foreign": {**good, "scripts/run.sh": b""}, "empty": {"LICENSE": b"MIT"}}
        for label, entries in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                launcher.unpack(archive(entries), target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            launcher.unpack(archive({**good, "beyin_web/link": b"/etc/passwd"}, links=("beyin_web/link",)), target)
        with self.assertRaisesRegex(ValueError, "ZIP"):
            launcher.unpack(b"not a zip", target)
        self.assertTrue((target / "beyin_web" / "static" / "index.html").is_file())
        self.assertFalse((self.root / "escape.py").exists())
        self.assertEqual(sorted(path.name for path in self.root.iterdir() if path.name.startswith("app")), ["app"])

    def test_launch_line_names_the_vault_and_the_language(self) -> None:
        self.assertEqual(launcher.launch_arguments(Path("/home/deniz/Beyin Notları")),
                         ["-m", "beyin_web", "--vault", str(Path("/home/deniz/Beyin Notları")), "--open", "--reuse",
                          "--idle-exit", "30"])
        self.assertEqual(launcher.launch_arguments(Path("/v"), "en")[-2:], ["--lang", "en"])
        with self.assertRaisesRegex(ValueError, "kurulu degil"):
            launcher.open_interface(self.vault, self.state)

    def test_cli_installs_reports_and_removes(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(launcher.main(["--json", "kur", "--paket", str(self.package), "--kisayol-yok"],
                                           vault=self.vault, state=self.state), 0)
        self.assertEqual(json.loads(output.getvalue())["surum"], __version__)
        self.assertEqual(launcher.human({"kurulu": False}, "durum"), "Kurulu: hayir\nKurmak icin: beyin.py web kur")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(launcher.main(["kaldir", "--json"], vault=self.vault, state=self.state), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "kaldirildi")
        with self.assertRaisesRegex(ValueError, "Vault bulunamadi"):
            launcher.main(["durum"], vault=self.root / "missing", state=self.state)

    @unittest.skipIf(os.name == "nt", "a Windows run would write to the real Start menu and desktop")
    def test_shortcut_is_written_by_the_installed_copy_and_removed_with_it(self) -> None:
        done = launcher.install(self.vault, self.state, package=self.package, env=self.env)
        entry = self.root / "share" / "applications" / "beyin-web.desktop"
        self.assertEqual((done["kisayol"], done["kisayol_hatasi"]), ([str(entry)], None))
        text = entry.read_text(encoding="utf-8")
        app = self.state.resolve() / "web" / __version__
        self.assertIn(f"Path={app}\n", text)
        self.assertIn(f"Icon={app / 'beyin_web' / 'assets' / 'app-icon.png'}\n", text)
        self.assertIn(f"--vault {self.vault.resolve()} --open --reuse --idle-exit 30\n", text)
        self.assertIn(str(entry), launcher.uninstall(self.vault, self.state, env=self.env)["kaldirilan"])
        self.assertFalse(entry.exists())


if __name__ == "__main__":
    unittest.main()
