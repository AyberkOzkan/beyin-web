from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from beyin_web import __version__
from beyin_web.__main__ import find_running, main, parse_args
from beyin_web.config import Settings
from beyin_web.http.server import create_server
from beyin_web.install import (
    LAUNCH_ARGUMENTS, command_file, copy_package, data_directory, desktop_entry, install, remember_vault,
    run_shortcut_script, uninstall, windows_shortcut, wsl_shortcut,
)
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault

WRITE_HEADERS = {"Content-Type": "application/json", "X-Beyin-Web": "1"}


class InstallTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vault = make_vault(self.root)
        self.config = self.root / "config"
        self.data = self.root / "data"


class PlanTests(InstallTestCase):
    def test_data_directory_per_platform(self) -> None:
        self.assertEqual(data_directory({"LOCALAPPDATA": str(self.root)}, "win32"), self.root / "beyin-web")
        self.assertEqual(data_directory({"XDG_DATA_HOME": str(self.root)}, "linux"), self.root / "beyin-web")
        with patch("beyin_web.install.Path.home", return_value=self.root):
            self.assertEqual(data_directory({}, "win32"), self.root / "AppData" / "Local" / "beyin-web")
            self.assertEqual(data_directory({}, "linux"), self.root / ".local" / "share" / "beyin-web")
            self.assertEqual(data_directory({"XDG_DATA_HOME": "relative"}, "linux"), self.root / ".local" / "share" / "beyin-web")
            self.assertEqual(data_directory({}, "darwin"), self.root / "Library" / "Application Support" / "beyin-web")

    def test_every_launcher_opens_reuses_and_stops_when_idle(self) -> None:
        self.assertEqual(LAUNCH_ARGUMENTS, ("-m", "beyin_web", "--open", "--reuse", "--idle-exit", "30"))
        args = parse_args(list(LAUNCH_ARGUMENTS[2:]))
        self.assertTrue(args.open and args.reuse)
        self.assertEqual(args.idle_exit, 30)

    def test_desktop_entry_quotes_what_a_shell_would_expand(self) -> None:
        app = PurePosixPath("/home/deniz/.local/share/beyin-web/app")
        entry = desktop_entry('/opt/my "py"/python$3 100%`x`', app, "Beyin'in web arayüzünü açar")
        self.assertIn('Exec="/opt/my \\"py\\"/python\\$3 100%%\\`x\\`" -m beyin_web --open --reuse --idle-exit 30\n', entry)
        self.assertIn("Path=" + str(app) + "\n", entry)
        self.assertIn("Terminal=false\n", entry)
        self.assertTrue(entry.startswith("[Desktop Entry]\nType=Application\nName=Beyin Web\n"))
        for bad in ("/bin/py\nthon", "/bin/py\rthon", "/bin/py\x00thon"):
            with self.assertRaises(ValueError):
                desktop_entry(bad, app, "x")
        with self.assertRaises(ValueError):
            desktop_entry("/bin/python3", app, "two\nlines")

    def test_command_file_survives_spaces_and_quotes(self) -> None:
        text = command_file("/usr/bin/python3", PurePosixPath("/Users/deniz/Library/Application Support/it's/app"))
        self.assertEqual(text, "#!/bin/sh\ncd '/Users/deniz/Library/Application Support/it'\\''s/app' && "
                               "exec '/usr/bin/python3' -m beyin_web --open --reuse --idle-exit 30\n")
        shell = shutil.which("sh")
        if shell is not None and os.name != "nt":
            folder = self.root / "it's here"
            folder.mkdir()
            script = self.root / "open.command"
            script.write_text(command_file(sys.executable, folder).replace(" ".join(LAUNCH_ARGUMENTS), "-c 'import os; print(os.getcwd())'"),
                              encoding="utf-8")
            result = subprocess.run([shell, str(script)], capture_output=True, encoding="utf-8", check=False)
            self.assertEqual(Path(result.stdout.strip()).resolve(), folder.resolve())

    def test_windows_shortcut_prefers_the_windowless_python(self) -> None:
        folder = self.root / "python"
        folder.mkdir()
        python = folder / "python.exe"
        python.touch()
        values = windows_shortcut(str(python), self.data / "app", "açıklama")
        self.assertEqual(values["BW_TARGET"], str(python))
        (folder / "pythonw.exe").touch()
        values = windows_shortcut(str(python), self.data / "app", "açıklama")
        self.assertEqual(values["BW_TARGET"], str(folder / "pythonw.exe"))
        self.assertEqual(values["BW_ARGUMENTS"], "-m beyin_web --open --reuse --idle-exit 30")
        self.assertEqual(values["BW_WORKDIR"], str(self.data / "app"))

    def test_wsl_shortcut_starts_the_distribution_in_the_installed_folder(self) -> None:
        values = wsl_shortcut("Ubuntu", "/usr/bin/python3", PurePosixPath("/home/deniz/my data/beyin-web/app"), "x")
        self.assertEqual((values["BW_TARGET"], values["BW_WINDOW"], values["BW_WORKDIR"]), ("wsl.exe", "7", ""))
        self.assertEqual(values["BW_ARGUMENTS"], '-d Ubuntu --cd "/home/deniz/my data/beyin-web/app" --exec /usr/bin/python3 '
                                                 "-m beyin_web --open --reuse --idle-exit 30")


class InstallTests(InstallTestCase):
    def test_copy_runs_from_its_new_folder_and_replaces_an_older_copy(self) -> None:
        stale = self.data / "app" / "beyin_web" / "removed_module.py"
        stale.parent.mkdir(parents=True)
        stale.write_text("x = 1\n", encoding="utf-8")
        app = copy_package(self.data)
        self.assertEqual(app, self.data / "app")
        self.assertFalse(stale.exists())
        self.assertTrue((app / "beyin_web" / "static" / "index.html").is_file())
        self.assertEqual(list(app.rglob("__pycache__")), [])
        self.assertFalse((self.data / "app.new").exists())
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        environment.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-m", "beyin_web", "--version"], cwd=app, env=environment,
                                capture_output=True, encoding="utf-8", timeout=30, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, f"beyin-web {__version__}\n"))
        self.assertEqual(copy_package(self.data, app / "beyin_web"), app)

    def test_settings_keep_other_keys_and_survive_a_broken_file(self) -> None:
        self.config.mkdir()
        path = self.config / "config.json"
        path.write_text('{"port": 7400, "display_name": "Çınar", "vault": "old"}', encoding="utf-8")
        remember_vault(self.config, self.vault)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                         {"port": 7400, "display_name": "Çınar", "vault": str(self.vault)})
        remember_vault(self.config, self.vault, "en")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["language"], "en")
        path.write_text("{broken", encoding="utf-8")
        remember_vault(self.config, self.vault)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"vault": str(self.vault)})
        self.assertEqual(sorted(item.name for item in self.config.iterdir()), ["config.json"])

    def test_linux_install_writes_a_menu_entry_and_nothing_in_the_vault(self) -> None:
        before = sorted(str(path.relative_to(self.vault)) for path in self.vault.rglob("*"))
        environment = {"XDG_DATA_HOME": str(self.root / "share")}
        written = install(self.vault, self.config, data_dir=self.data, python="/usr/bin/python3",
                          platform="linux", env=environment, description="Beyin'in web arayüzünü açar")
        target = self.root / "share" / "applications" / "beyin-web.desktop"
        self.assertEqual(written, [str(target)])
        entry = target.read_text(encoding="utf-8")
        self.assertIn('Exec="/usr/bin/python3" -m beyin_web --open --reuse --idle-exit 30\n', entry)
        self.assertIn(f"Path={self.data / 'app'}\n", entry)
        self.assertIn("Comment=Beyin'in web arayüzünü açar\n", entry)
        self.assertEqual(json.loads((self.config / "config.json").read_text(encoding="utf-8"))["vault"], str(self.vault))
        self.assertEqual(sorted(str(path.relative_to(self.vault)) for path in self.vault.rglob("*")), before)
        removed = uninstall(data_dir=self.data, platform="linux", env=environment)
        self.assertEqual(removed, [str(target), str(self.data / "app")])
        self.assertFalse(target.exists())
        self.assertTrue((self.config / "config.json").is_file())
        self.assertEqual(uninstall(data_dir=self.data, platform="linux", env=environment), [])

    def test_macos_install_writes_a_command_file_on_the_desktop(self) -> None:
        with patch("beyin_web.install.Path.home", return_value=self.root):
            written = install(self.vault, self.config, data_dir=self.data, python="/usr/bin/python3",
                              platform="darwin", env={})
            target = self.root / "Desktop" / "Beyin Web.command"
            self.assertEqual(written, [str(target)])
            self.assertEqual(target.read_text(encoding="utf-8"), command_file("/usr/bin/python3", self.data / "app"))
            if os.name != "nt":
                self.assertTrue(target.stat().st_mode & 0o100)
            self.assertEqual(uninstall(data_dir=self.data, platform="darwin", env={}), [str(target), str(self.data / "app")])

    @unittest.skipUnless(os.name == "nt", "Windows shortcuts need Windows")
    def test_windows_install_writes_shortcuts_that_point_at_the_copy(self) -> None:
        folders = [self.root / "Başlat Menüsü", self.root / "Masaüstü"]
        for folder in folders:
            folder.mkdir()
        written = install(self.vault, self.config, data_dir=self.data, platform="win32",
                          description="Beyin'in web arayüzünü açar", shortcut_folders=[*folders, self.root / "missing"])
        self.assertEqual(written, [str(folder / "Beyin Web.lnk") for folder in folders])
        # The scripting shortcut object cannot open a path outside the legacy code page; read a copy beside it.
        plain = self.root / "copy.lnk"
        shutil.copyfile(written[0], plain)
        read_back = ("[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
                     "$l = (New-Object -ComObject WScript.Shell).CreateShortcut($env:BW_PATH); "
                     "$l.TargetPath; $l.Arguments; $l.WorkingDirectory; $l.Description")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", read_back],
                                env={**os.environ, "BW_PATH": str(plain)}, capture_output=True, encoding="utf-8",
                                timeout=60, check=False)
        target, arguments, workdir, description = result.stdout.splitlines()[:4]
        self.assertIn(Path(target).name.lower(), {"python.exe", "pythonw.exe"})
        self.assertTrue(Path(target).is_file())
        self.assertEqual(arguments, "-m beyin_web --open --reuse --idle-exit 30")
        self.assertEqual(Path(workdir), self.data / "app")
        self.assertEqual(description, "Beyin'in web arayüzünü açar")
        self.assertTrue((Path(workdir) / "beyin_web" / "__main__.py").is_file())
        removed = uninstall(data_dir=self.data, platform="win32", shortcut_folders=folders)
        self.assertEqual(removed, [*written, str(self.data / "app")])
        self.assertEqual([path for folder in folders for path in folder.iterdir()], [])

    @unittest.skipUnless(os.environ.get("WSL_DISTRO_NAME") and shutil.which("powershell.exe") and shutil.which("wslpath"),
                         "the WSL shortcut needs WSL with Windows interop")
    def test_wsl_install_writes_a_windows_shortcut(self) -> None:
        folder = self.root / "desktop"
        folder.mkdir()
        windows = subprocess.run(["wslpath", "-w", str(folder)], capture_output=True, encoding="utf-8", check=True).stdout.strip()
        values = wsl_shortcut(os.environ["WSL_DISTRO_NAME"], sys.executable, self.data / "app", "Beyin Web")
        written = run_shortcut_script(values, folders=[Path(windows)])
        self.assertEqual(len(written), 1)
        self.assertTrue((folder / "Beyin Web.lnk").is_file())
        self.assertEqual(len(run_shortcut_script({"BW_NAME": "Beyin Web"}, folders=[Path(windows)], remove=True)), 1)
        self.assertFalse((folder / "Beyin Web.lnk").exists())

    def test_cli_installs_warns_without_beyin_and_refuses_both_flags(self) -> None:
        cases = ((["--install", "--vault", str(self.vault)], "beyin-web kuruldu"),
                 (["--install", "--vault", str(self.vault), "--lang", "en"], "beyin-web is installed"))
        for argv, expected in cases:
            with self.subTest(argv=argv[-1]):
                output, errors = io.StringIO(), io.StringIO()
                with (patch("beyin_web.__main__.config_directory", return_value=self.config),
                      patch("beyin_web.__main__.install", return_value=["shortcut-path"]) as installer,
                      contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors)):
                    self.assertEqual(main(argv), 0)
                self.assertEqual(installer.call_args.args, (self.vault.resolve(), self.config))
                self.assertEqual(installer.call_args.kwargs["language"], "en" if "en" in argv else None)
                self.assertIn(expected, output.getvalue())
                self.assertIn("shortcut-path", output.getvalue())
                self.assertEqual("beyin.py" in errors.getvalue(), not (self.vault / "beyin.py").is_file())
        (self.vault / "beyin.py").write_text("", encoding="utf-8")
        errors = io.StringIO()
        with (patch("beyin_web.__main__.config_directory", return_value=self.config),
              patch("beyin_web.__main__.install", side_effect=OSError("denied")),
              contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors)):
            self.assertEqual(main(["--install", "--vault", str(self.vault)]), 2)
        self.assertEqual(errors.getvalue(), "Kurulum tamamlanamadı. Klasör izinlerini denetleyip yeniden deneyin.\n")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            parse_args(["--install", "--uninstall"])
        self.assertEqual(caught.exception.code, 2)
        output = io.StringIO()
        with (patch("beyin_web.__main__.config_directory", return_value=self.config),
              patch("beyin_web.__main__.uninstall", return_value=["gone"]), contextlib.redirect_stdout(output)):
            self.assertEqual(main(["--uninstall"]), 0)
        self.assertIn("gone", output.getvalue())


class RunningServerTests(InstallTestCase):
    def start(self, settings: Settings) -> tuple[Settings, threading.Thread]:
        server = create_server(settings, MarkdownSource(settings.vault), BeyinRuntime(settings.vault, enabled=False))
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()

        def stop() -> None:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.addCleanup(stop)
        return replace(settings, port=server.server_address[1]), thread

    def post(self, port: int, path: str, body: str = "{}", headers: dict[str, str] | None = None) -> tuple[int, object]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            sent = {"Origin": f"http://127.0.0.1:{port}", **WRITE_HEADERS} if headers is None else headers
            connection.request("POST", path, body=body.encode("utf-8"), headers=sent)
            response = connection.getresponse()
            return response.status, json.loads(response.read() or b"null")
        finally:
            connection.close()

    def test_a_running_server_is_found_only_for_the_same_vault_and_token(self) -> None:
        running, _ = self.start(Settings(vault=self.vault, port=0, token_enabled=True, token="one_session_secret"))
        self.assertEqual(find_running(running), running.port)
        self.assertIsNone(find_running(replace(running, token="another_secret")))
        other = make_vault(self.root / "other")
        self.assertIsNone(find_running(replace(running, vault=other)))
        self.assertIsNone(find_running(replace(running, port=0)))
        open_server, _ = self.start(Settings(vault=self.vault, port=0, token_enabled=False))
        self.assertEqual(find_running(open_server), open_server.port)

    def test_reuse_opens_the_running_server_instead_of_starting_another(self) -> None:
        running, _ = self.start(Settings(vault=self.vault, port=0, token_enabled=False))
        output = io.StringIO()
        with (patch("beyin_web.__main__.config_directory", return_value=self.config),
              patch("beyin_web.__main__.open_address") as opened,
              patch("beyin_web.__main__.bind_server") as bind, contextlib.redirect_stdout(output)):
            code = main(["--vault", str(self.vault), "--port", str(running.port), "--no-token", "--no-beyin", "--open", "--reuse"])
        self.assertEqual(code, 0)
        bind.assert_not_called()
        opened.assert_called_once_with(f"http://127.0.0.1:{running.port}/")
        self.assertEqual(output.getvalue(), f"beyin-web adresi: http://127.0.0.1:{running.port}/\n")

    def test_shutdown_needs_the_page_and_stops_the_server_even_when_read_only(self) -> None:
        running, thread = self.start(Settings(vault=self.vault, port=0, token_enabled=False, read_only=True))
        port = running.port
        self.assertEqual(self.post(port, "/api/v1/shutdown", headers={"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.post(port, "/api/v1/shutdown", headers={**WRITE_HEADERS, "Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.post(port, "/api/v1/shutdown", body='{"force": true}')[0], 400)
        self.assertEqual(self.post(port, "/api/v1/goals", body='{"title": "x", "horizon": "year"}')[1],
                         {"error": {"code": "read_only", "message": "read_only"}})
        self.assertTrue(thread.is_alive())
        self.assertEqual(self.post(port, "/api/v1/shutdown"), (200, {"stopping": True}))
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
