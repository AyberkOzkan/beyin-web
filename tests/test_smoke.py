from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from beyin_web import __version__
from beyin_web.__main__ import main, parse_args, resolve_vault
from tests.support import DEFAULT_MTIME, FIXTURES, has_outside_link, make_vault

ROOT: Path = Path(__file__).resolve().parents[1]


class SmokeTests(unittest.TestCase):
    def test_package_metadata(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]
        self.assertEqual(project["name"], "beyin-web")
        self.assertEqual(project["version"], __version__)
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["license"]["text"], "MIT")
        self.assertEqual(project["scripts"]["beyin-web"], "beyin_web.__main__:main")
        package_data = metadata["tool"]["setuptools"]["package-data"]["beyin_web"]
        self.assertIn("static/*", package_data)

    def test_version_output(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "beyin_web", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "beyin-web 0.1.0.dev0\n")
        self.assertEqual(result.stderr, "")

    def test_missing_vault(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for argv in ([], ["--vault", str(root / "missing"), "--open"]):
                with self.subTest(argv=argv):
                    output = io.StringIO()
                    with (
                        patch("beyin_web.__main__.config_directory", return_value=root),
                        patch("beyin_web.__main__.Path.cwd", return_value=root),
                        patch.dict("os.environ", {}, clear=True),
                        contextlib.redirect_stderr(output),
                    ):
                        self.assertEqual(main(argv), 2)
                    self.assertEqual(
                        output.getvalue(),
                        "Vault bulunamadı. --vault ile var olan bir vault klasörü belirtin.\n",
                    )

    def test_argument_defaults(self) -> None:
        args = parse_args([])
        self.assertIsNone(args.vault)
        self.assertEqual(args.port, 7373)
        self.assertFalse(args.open)
        self.assertIsNone(args.idle_exit)
        self.assertFalse(args.no_token)

    def test_explicit_arguments(self) -> None:
        args = parse_args(
            [
                "--vault", "Çınar Projesi", "--port", "7400", "--open",
                "--idle-exit", "15", "--no-token",
            ]
        )
        self.assertEqual(args.vault, Path("Çınar Projesi"))
        self.assertEqual(args.port, 7400)
        self.assertTrue(args.open)
        self.assertEqual(args.idle_exit, 15)
        self.assertTrue(args.no_token)

    def test_invalid_arguments(self) -> None:
        cases = (["--port", "yanlış"], ["--idle-exit", "yanlış"], ["--bilinmeyen"])
        for argv in cases:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    parse_args(argv)
                self.assertEqual(caught.exception.code, 2)


class VaultDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.vault = make_vault(self.tmp)
        self.config_path = self.tmp / "config.json"

    def write_config(self, value: object) -> None:
        self.config_path.write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )

    def test_discovery_priority(self) -> None:
        self.write_config({"vault": "configured"})
        env = {"BEYIN_VAULT": "environment"}
        self.assertEqual(
            resolve_vault("command-line", env, self.vault, self.config_path),
            self.vault / "command-line",
        )
        self.assertEqual(
            resolve_vault(None, env, self.vault, self.config_path),
            self.vault / "environment",
        )
        self.assertEqual(
            resolve_vault(None, {}, self.vault, self.config_path),
            self.vault / "configured",
        )
        self.config_path.unlink()
        self.assertEqual(
            resolve_vault(None, {}, self.vault, self.config_path), self.vault
        )

    def test_absolute_paths(self) -> None:
        self.write_config({"vault": str(self.vault)})
        cases = (
            (self.vault, {}),
            (None, {"BEYIN_VAULT": str(self.vault)}),
            (None, {}),
        )
        for cli, env in cases:
            with self.subTest(cli=cli, env=env):
                self.assertEqual(
                    resolve_vault(cli, env, self.tmp, self.config_path), self.vault
                )

    def test_invalid_config_is_skipped(self) -> None:
        cases = (
            "{", "{}", "[]", "null", '{"vault": null}',
            '{"vault": 3}', '{"vault": ""}',
        )
        for content in cases:
            with self.subTest(content=content):
                self.config_path.write_text(content, encoding="utf-8")
                self.assertEqual(
                    resolve_vault(None, {}, self.vault, self.config_path), self.vault
                )

    def test_config_bom_and_crlf(self) -> None:
        self.config_path.write_text(
            '\ufeff{\r\n  "vault": "Çınar"\r\n}\r\n', encoding="utf-8", newline=""
        )
        self.assertEqual(
            resolve_vault(None, {}, self.tmp, self.config_path), self.tmp / "Çınar"
        )

    def test_empty_environment_is_skipped(self) -> None:
        self.write_config({"vault": "configured"})
        self.assertEqual(
            resolve_vault(None, {"BEYIN_VAULT": ""}, self.tmp, self.config_path),
            self.tmp / "configured",
        )

    def test_beyin_marker(self) -> None:
        app_path = self.vault / ".obsidian" / "app.json"
        app_path.unlink()
        app_path.parent.rmdir()
        (self.vault / "beyin.py").write_text("", encoding="utf-8")
        self.assertEqual(
            resolve_vault(None, {}, self.vault, self.config_path), self.vault
        )

    def test_no_candidate(self) -> None:
        self.assertIsNone(resolve_vault(None, {}, self.tmp, self.config_path))
        self.assertFalse(self.config_path.exists())


class FixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.vault = make_vault(self.tmp)

    def test_copy_location_and_files(self) -> None:
        self.assertEqual(self.vault, self.tmp / "vault")
        for source in (FIXTURES / "vault").rglob("*"):
            if source.is_file():
                with self.subTest(path=source):
                    copied = self.vault / source.relative_to(FIXTURES / "vault")
                    self.assertTrue(copied.is_file())
        self.assertEqual((self.vault / "notes" / "bos.md").stat().st_size, 0)

    def test_crlf_conversion(self) -> None:
        relative = Path("notes") / "Çınar Projesi.md"
        source = (FIXTURES / "vault" / relative).read_text(encoding="utf-8")
        copied = (self.vault / relative).read_bytes()
        self.assertEqual(copied, source.replace("\n", "\r\n").encode("utf-8"))
        self.assertIn(b"\r\n", copied)
        self.assertNotIn(b"\n", copied.replace(b"\r\n", b""))

    def test_bom_conversion(self) -> None:
        relative = Path("notes") / "serbest.md"
        source = (FIXTURES / "vault" / relative).read_text(encoding="utf-8")
        copied = (self.vault / relative).read_bytes()
        self.assertEqual(copied, ("\ufeff" + source).encode("utf-8"))
        self.assertTrue(copied.startswith(b"\xef\xbb\xbf# Serbest not"))

    def test_fixed_mtimes(self) -> None:
        mtimes = json.loads((FIXTURES / "mtimes.json").read_text(encoding="utf-8"))
        for path in self.vault.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(self.vault).as_posix()
            with self.subTest(path=relative):
                timestamp = (
                    datetime.fromisoformat(mtimes[relative]).timestamp()
                    if relative in mtimes else DEFAULT_MTIME
                )
                self.assertAlmostEqual(path.stat().st_mtime, timestamp, delta=1)

    def test_outside_link(self) -> None:
        if not has_outside_link(self.vault):
            self.skipTest("Symbolic links are unavailable on this platform")
        link = self.vault / "notes" / "dışarı.md"
        target = (self.tmp / "outside" / "hedef.md").resolve()
        self.assertEqual(link.resolve(), target)
        self.assertFalse(link.resolve().is_relative_to(self.vault.resolve()))
        self.assertEqual(link.read_text(encoding="utf-8"), "KOK-DISI-ISARETI\n")

    def test_link_creation_can_be_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("tests.support.Path.symlink_to", side_effect=OSError("unavailable")):
                vault = make_vault(Path(directory))
            self.assertFalse(has_outside_link(vault))
            self.assertTrue((vault / "notes" / "atlas.md").is_file())


if __name__ == "__main__":
    unittest.main()
