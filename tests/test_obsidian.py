from __future__ import annotations

import unittest
from urllib.parse import unquote

from beyin_web.domain.obsidian import obsidian_uri

PREFIX = "obsidian://open?path="

CASES: list[tuple[str, str, str, str]] = [
    ("posix_plain", "/home/deniz/vault", "notes/atlas.md", "/home/deniz/vault/notes/atlas.md"),
    ("posix_trailing_slash", "/home/deniz/vault/", "notes/atlas.md", "/home/deniz/vault/notes/atlas.md"),
    ("posix_space_and_turkish", "/home/deniz/vault", "notes/Çınar Projesi.md", "/home/deniz/vault/notes/Çınar Projesi.md"),
    ("wsl_mount", "/mnt/c/Users/deniz/Documents/Beyin-Notları", "notes/atlas.md", r"C:\Users\deniz\Documents\Beyin-Notları\notes\atlas.md"),
    ("wsl_mount_upper_drive", "/mnt/D/Vault", "a.md", r"D:\Vault\a.md"),
    ("wsl_not_a_mount", "/mnt/data/vault", "a.md", "/mnt/data/vault/a.md"),
    ("windows_backslashes", r"C:\Users\deniz\Vault", "notes/a.md", r"C:\Users\deniz\Vault\notes\a.md"),
    ("windows_forward_slashes_lower_drive", "c:/Users/deniz/Vault", "notes/a.md", r"C:\Users\deniz\Vault\notes\a.md"),
    ("windows_unc", r"\\server\share\Vault", "notes/a.md", r"\\server\share\Vault\notes\a.md"),
    ("rel_backslashes_and_leading_slash", "/home/deniz/vault", r"\notes\atlas.md", "/home/deniz/vault/notes/atlas.md"),
    ("rel_dot_segments", "/home/deniz/vault", "./notes/./atlas.md", "/home/deniz/vault/notes/atlas.md"),
    ("emoji_folder", "/home/deniz/vault", "🔮 850-Companion/Core.md", "/home/deniz/vault/🔮 850-Companion/Core.md"),
]


class TestObsidianUri(unittest.TestCase):
    def test_cases(self) -> None:
        for name, vault_root, rel_path, expected_path in CASES:
            with self.subTest(name=name):
                uri = obsidian_uri(vault_root, rel_path)
                self.assertTrue(uri.startswith(PREFIX))
                encoded = uri[len(PREFIX):]
                self.assertEqual(unquote(encoded), expected_path)
                for ch in ("/", "\\", " ", ":"):
                    self.assertNotIn(ch, encoded)

    def test_known_literal(self) -> None:
        self.assertEqual(
            obsidian_uri("/home/deniz/vault", "notes/atlas.md"),
            "obsidian://open?path=%2Fhome%2Fdeniz%2Fvault%2Fnotes%2Fatlas.md",
        )
        self.assertEqual(
            obsidian_uri("/mnt/c/V", "a b.md"),
            "obsidian://open?path=C%3A%5CV%5Ca%20b.md",
        )

    def test_rejected_paths(self) -> None:
        for bad in ("", "/", ".", "../a.md", "notes/../../a.md"):
            with self.subTest(rel_path=bad):
                with self.assertRaises(ValueError):
                    obsidian_uri("/home/deniz/vault", bad)


if __name__ == "__main__":
    unittest.main()
