from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.cwd = self.tmp / "outside"
        self.cwd.mkdir()
        self.env = os.environ.copy()
        self.env["PYTHONUTF8"] = "1"
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + self.env.get("PATH", "")

    def run_launcher(self, launcher: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if launcher.suffix == ".cmd":
            if os.name != "nt":
                self.skipTest("Windows cmd launcher requires Windows")
            command_line = subprocess.list2cmdline([str(launcher), *args])
            command = f'{subprocess.list2cmdline([os.environ.get("COMSPEC", "cmd.exe")])} /d /s /c "{command_line}"'
        else:
            shell = shutil.which("sh")
            if shell is None:
                self.skipTest("POSIX launcher requires sh; sh was not found")
            command = [shell, str(launcher), *args]
        return subprocess.run(command, cwd=self.cwd, env=self.env, capture_output=True,
                              encoding="utf-8", timeout=20, check=False)

    def assert_version(self, launcher: Path) -> None:
        result = self.run_launcher(launcher, ["--version"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "beyin-web 0.1.0\n")
        self.assertEqual(result.stderr, "")

    def test_posix_version_outside_repository(self) -> None:
        self.assert_version(ROOT / "scripts" / "beyin-web")

    def test_windows_version_outside_repository(self) -> None:
        self.assert_version(ROOT / "scripts" / "beyin-web.cmd")

    def assert_missing_vault(self, launcher: Path) -> None:
        result = self.run_launcher(launcher, ["--vault", "olmayan klasör ğü"])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr,
                         "Vault bulunamadı. --vault ile var olan bir vault klasörü belirtin.\n")

    def test_posix_unicode_argument(self) -> None:
        self.assert_missing_vault(ROOT / "scripts" / "beyin-web")

    def test_windows_unicode_argument(self) -> None:
        self.assert_missing_vault(ROOT / "scripts" / "beyin-web.cmd")

    def test_posix_symlink_chain(self) -> None:
        links = self.tmp / "links ğü"
        links.mkdir()
        first = links / "first"
        second = links / "beyin-web"
        try:
            first.symlink_to(ROOT / "scripts" / "beyin-web")
            second.symlink_to("first")
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symbolic links unavailable: {error}")
        self.assert_version(second)

    def assert_fake_package(self, filename: str) -> None:
        repo = self.tmp / "depo klasörü ğü"
        scripts = repo / "scripts"
        scripts.mkdir(parents=True)
        launcher = scripts / filename
        shutil.copyfile(ROOT / "scripts" / filename, launcher)
        package = repo / "beyin_web"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "__main__.py").write_text(
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "import launcher_marker\n"
            "print(json.dumps({'argv': sys.argv[1:], 'cwd': str(Path.cwd()),\n"
            "    'package': str(Path(__file__).resolve().parent),\n"
            "    'marker': launcher_marker.VALUE, 'path': sys.path}))\n"
            "raise SystemExit(23)\n", encoding="utf-8",
        )
        original_path = self.tmp / "existing path ğü"
        original_path.mkdir()
        (original_path / "launcher_marker.py").write_text("VALUE = 'preserved'\n", encoding="utf-8")
        self.env["PYTHONPATH"] = str(original_path)
        shadow = self.cwd / "beyin_web"
        shadow.mkdir()
        (shadow / "__init__.py").write_text("", encoding="utf-8")
        (shadow / "__main__.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
        args = ["--vault", "olmayan klasör ğü", "--port", "7400"]
        result = self.run_launcher(launcher, args)
        self.assertEqual(result.returncode, 23, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["argv"], args)
        self.assertEqual(Path(output["cwd"]), self.cwd)
        self.assertEqual(Path(output["package"]), package)
        self.assertEqual(output["marker"], "preserved")
        paths = [Path(value).resolve() for value in output["path"] if value]
        self.assertLess(paths.index(repo.resolve()), paths.index(original_path.resolve()))

    def test_posix_copy_preserves_pythonpath_arguments_and_cwd(self) -> None:
        self.assert_fake_package("beyin-web")

    def test_windows_copy_preserves_pythonpath_arguments_and_cwd(self) -> None:
        self.assert_fake_package("beyin-web.cmd")


if __name__ == "__main__":
    unittest.main()
