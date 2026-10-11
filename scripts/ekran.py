"""Open pages of the app in headless Edge and save screenshots for design review.

    py -3 scripts/ekran.py [--out design/ekran] [--vault PATH] [--full] [--wait 2.5] [HASH ...]

Without --vault the synthetic vault is served with the clock of the golden files. With --vault a
real vault is read (never written); Beyin is not called. The default output folder is not tracked
by git, because pictures of a real vault show its content.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beyin_web.config import Settings  # noqa: E402
from beyin_web.http.server import create_server  # noqa: E402
from beyin_web.runtime.beyin_cli import BeyinRuntime  # noqa: E402
from beyin_web.vault.scan import MarkdownSource  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("hashes", nargs="*", default=["#/"])
    parser.add_argument("--out", type=Path, default=ROOT / "design" / "ekran")
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--full", action="store_true", help="grow the window to the page's height")
    parser.add_argument("--wait", type=float, default=2.5, help="seconds to let a page settle")
    args = parser.parse_args(argv)

    from selenium import webdriver

    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
        if args.vault is None:
            from scripts.altin_guncelle import NOW, TZ
            from tests.support import make_vault
            vault = make_vault(Path(temporary))
        else:
            vault = args.vault
        # Screenshots never need Beyin, and a real vault must not have its CLI run from here.
        server = create_server(Settings(vault=vault, port=0, token_enabled=False),
                               MarkdownSource(vault), BeyinRuntime(vault, enabled=False))
        if args.vault is None:
            server.api.clock = lambda: NOW
            server.api.tz = TZ
        threading.Thread(target=server.serve_forever, daemon=True).start()
        options = webdriver.EdgeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1672,941")
        options.add_argument("--force-device-scale-factor=1")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        driver = webdriver.Edge(options=options)
        try:
            for index, fragment in enumerate(args.hashes):
                driver.get(f"http://127.0.0.1:{server.server_address[1]}/{fragment}")
                driver.refresh()
                time.sleep(args.wait)
                if args.full:
                    height = driver.execute_script("return Math.max(document.documentElement.scrollHeight, 941)")
                    driver.set_window_size(1672, min(height + 120, 4000))
                    time.sleep(0.3)
                name = "".join(char if char.isalnum() else "-" for char in fragment).strip("-") or "ana"
                target = args.out / f"{index:02}-{name}.png"
                driver.save_screenshot(str(target))
                driver.set_window_size(1672, 941)
                errors = [entry["message"][:200] for entry in driver.get_log("browser") if entry["level"] == "SEVERE"]
                print(f"{fragment} -> {target} | {driver.title!r} | console errors: {len(errors)}")
                for message in errors:
                    print("  ", message)
        finally:
            driver.quit()
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
