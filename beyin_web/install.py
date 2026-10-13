"""Install the interface for one user: a copy of the package, the vault in the settings, and a shortcut to click.

Nothing is written into the vault. A vault is often shared between machines, and a shortcut holds this
machine's paths; it belongs on this machine's desktop and application menu.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePath

from beyin_web.config import read_config

SHORTCUT_NAME = "Beyin Web"
# A click opens the page; a second click finds the running server; an unused server stops by itself.
LAUNCH_ARGUMENTS: tuple[str, ...] = ("-m", "beyin_web", "--open", "--reuse", "--idle-exit", "30")

# Asks Windows where the Start menu and the desktop are (the desktop may live in a synced folder), then
# writes or removes one shortcut in each. Values arrive in the environment, so no path is ever parsed as code.
# The shortcut is written through IShellLinkW: the scripting shortcut object keeps paths in the system's
# legacy code page and cannot save into "Masaüstü" or point into a profile named "Ayşe" on every machine.
_SHORTCUT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
public static class BeyinWebShortcut {
  [ComImport, Guid("00021401-0000-0000-C000-000000000046")] class ShellLink {}
  [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
  interface IShellLinkW {
    void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int size, IntPtr data, int flags);
    void GetIDList(out IntPtr list);
    void SetIDList(IntPtr list);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int size);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder directory, int size);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string directory);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder arguments, int size);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
    void GetHotkey(out short hotkey);
    void SetHotkey(short hotkey);
    void GetShowCmd(out int show);
    void SetShowCmd(int show);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder icon, int size, out int index);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string icon, int index);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, int reserved);
    void Resolve(IntPtr window, int flags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string file);
  }
  public static void Write(string path, string target, string arguments, string directory, int show, string description) {
    IShellLinkW link = (IShellLinkW)new ShellLink();
    link.SetPath(target);
    link.SetArguments(arguments);
    if (directory.Length > 0) link.SetWorkingDirectory(directory);
    link.SetShowCmd(show);
    link.SetDescription(description);
    ((IPersistFile)link).Save(path, true);
  }
}
'@
if ($env:BW_FOLDERS) { $folders = $env:BW_FOLDERS -split '\|' }
else { $folders = @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop')) }
$target = $env:BW_TARGET
if ($target -and -not (Split-Path -Parent $target)) { $target = (Get-Command $target -CommandType Application)[0].Source }
foreach ($folder in $folders) {
  if (-not $folder -or -not (Test-Path -LiteralPath $folder)) { continue }
  $path = Join-Path $folder ($env:BW_NAME + '.lnk')
  if ($env:BW_REMOVE -eq '1') {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path; $path }
    continue
  }
  [BeyinWebShortcut]::Write($path, $target, $env:BW_ARGUMENTS, $env:BW_WORKDIR, [int]$env:BW_WINDOW, $env:BW_DESCRIPTION)
  $path
}
"""
_SHORTCUT_VARIABLES = ("BW_FOLDERS", "BW_NAME", "BW_REMOVE", "BW_TARGET", "BW_ARGUMENTS", "BW_WORKDIR",
                       "BW_WINDOW", "BW_DESCRIPTION")


def data_directory(env: Mapping[str, str] | None = None, platform: str | None = None) -> Path:
    environment = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        base = environment.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "beyin-web"
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "beyin-web"
    base = environment.get("XDG_DATA_HOME")
    return (Path(base) if base and Path(base).is_absolute() else Path.home() / ".local" / "share") / "beyin-web"


def copy_package(data_dir: Path, source: Path | None = None) -> Path:
    """Copy the running package to ``data_dir/app`` and return that folder; the download can then be deleted."""
    source = Path(__file__).resolve().parent if source is None else source
    app = data_dir / "app"
    if source.parent == app.resolve():
        return app
    staging = data_dir / "app.new"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(source, staging / source.name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.rmtree(app, ignore_errors=True)
    staging.replace(app)
    return app


def remember_vault(config_dir: Path, vault: Path, language: str | None = None) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.json"
    config = read_config(path)
    config["vault"] = str(vault)
    if language is not None:
        config["language"] = language
    temporary = path.with_name("config.json.new")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _checked(value: str) -> str:
    if any(char in value for char in "\r\n\x00"):
        raise ValueError("unsupported_path")
    return value


def _shell_quote(value: str) -> str:
    return "'" + _checked(value).replace("'", "'\\''") + "'"


def _desktop_quote(value: str) -> str:
    # The Desktop Entry specification: quote the argument, then escape the characters a shell would expand.
    escaped = _checked(value).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"' + escaped.replace("%", "%%") + '"'


def desktop_entry(python: str, app: PurePath, description: str) -> str:
    command = " ".join([_desktop_quote(python), *LAUNCH_ARGUMENTS])
    return (f"[Desktop Entry]\nType=Application\nName={SHORTCUT_NAME}\nComment={_checked(description)}\n"
            f"Exec={command}\nPath={_checked(str(app))}\nTerminal=false\nCategories=Office;\n")


def command_file(python: str, app: PurePath) -> str:
    return f"#!/bin/sh\ncd {_shell_quote(str(app))} && exec {_shell_quote(python)} {' '.join(LAUNCH_ARGUMENTS)}\n"


def windows_shortcut(python: str, app: Path, description: str) -> dict[str, str]:
    """The shortcut of a Windows installation: no console window, so pythonw when it is there."""
    windowless = Path(python).with_name("pythonw.exe")
    return {"BW_NAME": SHORTCUT_NAME, "BW_TARGET": str(windowless if windowless.is_file() else python),
            "BW_ARGUMENTS": subprocess.list2cmdline(LAUNCH_ARGUMENTS), "BW_WORKDIR": str(app),
            "BW_WINDOW": "1", "BW_DESCRIPTION": description}


def wsl_shortcut(distribution: str, python: str, app: PurePath, description: str) -> dict[str, str]:
    """A Windows shortcut for an installation inside WSL: Windows starts the distribution when it is clicked."""
    arguments = ["-d", distribution, "--cd", str(app), "--exec", python, *LAUNCH_ARGUMENTS]
    return {"BW_NAME": SHORTCUT_NAME, "BW_TARGET": "wsl.exe", "BW_ARGUMENTS": subprocess.list2cmdline(arguments),
            "BW_WORKDIR": "", "BW_WINDOW": "7", "BW_DESCRIPTION": description}


def run_shortcut_script(values: Mapping[str, str], *, folders: Sequence[Path] | None = None,
                        remove: bool = False) -> list[str]:
    """Run the shortcut script in Windows PowerShell (from Windows or from WSL) and return the paths it touched."""
    environment = os.environ.copy()
    environment.update(values)
    environment["BW_REMOVE"] = "1" if remove else "0"
    environment["BW_FOLDERS"] = "|".join(str(folder) for folder in folders) if folders is not None else ""
    # WSL hands a variable to a Windows program only when WSLENV names it.
    environment["WSLENV"] = ":".join(filter(None, [environment.get("WSLENV", ""), *_SHORTCUT_VARIABLES]))
    encoded = base64.b64encode(_SHORTCUT_SCRIPT.encode("utf-16le")).decode("ascii")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                            env=environment, capture_output=True, encoding="utf-8", errors="replace",
                            timeout=60, check=False)
    if result.returncode != 0:
        raise OSError("shortcut_failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _posix_targets(platform: str, env: Mapping[str, str]) -> Path:
    if platform == "darwin":
        return Path.home() / "Desktop" / f"{SHORTCUT_NAME}.command"
    base = env.get("XDG_DATA_HOME")
    root = Path(base) if base and Path(base).is_absolute() else Path.home() / ".local" / "share"
    return root / "applications" / "beyin-web.desktop"


def install(vault: Path, config_dir: Path, *, language: str | None = None, description: str = SHORTCUT_NAME,
            data_dir: Path | None = None, python: str | None = None, platform: str | None = None,
            env: Mapping[str, str] | None = None, shortcut_folders: Sequence[Path] | None = None) -> list[str]:
    """Install for the current user and return the shortcuts written."""
    environment = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    python = sys.executable if python is None else python
    data_dir = data_directory(environment, platform) if data_dir is None else data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    app = copy_package(data_dir)
    remember_vault(config_dir, vault, language)
    distribution = environment.get("WSL_DISTRO_NAME")
    if platform == "win32":
        return run_shortcut_script(windows_shortcut(python, app, description), folders=shortcut_folders)
    if distribution:
        return run_shortcut_script(wsl_shortcut(distribution, python, app, description), folders=shortcut_folders)
    target = _posix_targets(platform, environment)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = command_file(python, app) if platform == "darwin" else desktop_entry(python, app, description)
    target.write_text(text, encoding="utf-8", newline="\n")
    if platform == "darwin":
        target.chmod(0o755)
    return [str(target)]


def uninstall(*, data_dir: Path | None = None, platform: str | None = None, env: Mapping[str, str] | None = None,
              shortcut_folders: Sequence[Path] | None = None) -> list[str]:
    """Remove the shortcuts and the installed copy; the settings and the vault are left alone."""
    environment = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    data_dir = data_directory(environment, platform) if data_dir is None else data_dir
    removed: list[str] = []
    if platform == "win32" or environment.get("WSL_DISTRO_NAME"):
        removed += run_shortcut_script({"BW_NAME": SHORTCUT_NAME}, folders=shortcut_folders, remove=True)
    else:
        target = _posix_targets(platform, environment)
        if target.is_file():
            target.unlink()
            removed.append(str(target))
    app = data_dir / "app"
    if app.is_dir():
        shutil.rmtree(app)
        removed.append(str(app))
    return removed
