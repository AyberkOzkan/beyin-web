"""Draw the shortcut icon and turn it into the files a desktop asks for.

    py -3 scripts/build_icon.py [--out beyin_web/assets]

Writes app-icon.svg (the drawing), app-icon.png (256 px, for a Linux application menu) and app-icon.ico (16 to
256 px, for a Windows shortcut), and beside them the same brain without its tile for the sidebar
(beyin_web/static/brand-mark.svg). The pixels come from headless Edge through Selenium, the same browser the
interface tests use; the package itself needs neither, it only carries the files. Run it after the drawing
changes and commit the result.
"""
from __future__ import annotations

import argparse
import base64
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.draw_illustrations import app_icon, brand_mark  # noqa: E402

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# The browser draws the SVG onto a canvas of exactly the asked size, so each size is drawn, not shrunk.
RASTER = """
const [svg, size, done] = arguments;
const image = new Image();
image.onload = () => {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  canvas.getContext("2d").drawImage(image, 0, 0, size, size);
  done(canvas.toDataURL("image/png"));
};
image.onerror = () => done("");
image.src = "data:image/svg+xml;base64," + svg;
"""


def ico(images: dict[int, bytes]) -> bytes:
    """An ICO file whose entries are PNGs (read by Windows since Vista); 256 is written as 0 in the directory."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory, data = b"", b""
    for size, png in sorted(images.items()):
        directory += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return header + directory + data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "beyin_web" / "assets")
    args = parser.parse_args(argv)

    from selenium import webdriver

    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(options=options)
    images: dict[int, bytes] = {}
    try:
        driver.get("about:blank")
        for size in ICO_SIZES:
            svg = base64.b64encode(app_icon(size).encode("utf-8")).decode("ascii")
            url = driver.execute_async_script(RASTER, svg, size)
            if not url.startswith("data:image/png;base64,"):
                raise SystemExit(f"the browser could not draw the {size} px icon")
            images[size] = base64.b64decode(url.split(",", 1)[1])
    finally:
        driver.quit()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "app-icon.svg").write_text(app_icon(256), encoding="utf-8", newline="\n")
    (args.out / "app-icon.png").write_bytes(images[256])
    (args.out / "app-icon.ico").write_bytes(ico(images))
    (ROOT / "beyin_web" / "static" / "brand-mark.svg").write_text(brand_mark(), encoding="utf-8", newline="\n")
    print(f"app-icon: {len(images)} sizes -> {args.out}; brand-mark.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
