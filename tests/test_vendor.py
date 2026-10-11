from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

VENDOR: Path = Path(__file__).resolve().parents[1] / "beyin_web" / "static" / "vendor"
ROW = re.compile(r"^\| `([^`]+)` \|.*\| `([0-9a-f]{64})` \|$")


class VendorTests(unittest.TestCase):
    def recorded(self) -> dict[str, str]:
        lines = (VENDOR / "VENDOR.md").read_text(encoding="utf-8").splitlines()
        return {match[1]: match[2] for line in lines if (match := ROW.match(line))}

    def test_every_recorded_file_matches_its_hash(self) -> None:
        recorded = self.recorded()
        self.assertTrue(recorded)
        for name, expected in recorded.items():
            with self.subTest(name=name):
                actual = hashlib.sha256((VENDOR / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

    def test_every_vendor_file_is_recorded(self) -> None:
        present = {
            path.relative_to(VENDOR).as_posix() for path in VENDOR.rglob("*")
            if path.is_file() and path.name != "VENDOR.md" and path.parent.name != "licenses"
        }
        self.assertEqual(present, set(self.recorded()))

    def test_every_package_has_a_license_text(self) -> None:
        licenses = list((VENDOR / "licenses").glob("*-LICENSE.txt"))
        self.assertGreaterEqual(len(licenses), 8)
        for path in licenses:
            with self.subTest(name=path.name):
                self.assertGreater(path.stat().st_size, 200)


if __name__ == "__main__":
    unittest.main()
