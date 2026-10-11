from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from beyin_web.vault.frontmatter import declares_private, parse_frontmatter
from tests.support import make_vault


class FrontmatterTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))

    def parse_text(self, text: str) -> tuple[dict, str, str | None]:
        path = self.vault / "notes" / "parser.md"
        path.write_text(text, encoding="utf-8", newline="")
        with path.open(encoding="utf-8", newline="") as stream:
            return parse_frontmatter(stream.read())

    def declares_text(self, text: str) -> bool:
        path = self.vault / "notes" / "privacy.md"
        path.write_text(text, encoding="utf-8", newline="")
        return declares_private(path.read_text(encoding="utf-8"))

    def test_json_fixture(self) -> None:
        text = (self.vault / "notes" / "atlas.md").read_text(encoding="utf-8")
        meta, body, warning = parse_frontmatter(text)
        self.assertEqual(meta, {"kind": "note", "project": "atlas"})
        self.assertTrue(body.startswith("# Atlas\n"))
        self.assertIsNone(warning)

    def test_yaml_crlf_fixture(self) -> None:
        with (self.vault / "notes" / "Çınar Projesi.md").open(encoding="utf-8", newline="") as stream:
            meta, body, warning = parse_frontmatter(stream.read())
        self.assertEqual(meta["tags"], ["plan", "deneme"])
        self.assertEqual(meta["participants"], ["Deniz", "Atlas"])
        self.assertEqual(meta["owner"], "Deniz")
        self.assertTrue(body.startswith("# Çınar Projesi\r\n"))
        self.assertIsNone(warning)

    def test_bom_and_crlf_frontmatter(self) -> None:
        for block in ('title: "Çınar"', '{"title": "Çınar"}'):
            with self.subTest(block=block):
                meta, body, warning = self.parse_text(f"\ufeff---\r\n{block}\r\n---\r\nGövde\r\n")
                self.assertEqual(meta, {"title": "Çınar"})
                self.assertEqual(body, "Gövde\r\n")
                self.assertIsNone(warning)

    def test_no_frontmatter(self) -> None:
        for name in ("serbest.md", "başlıksız.md", "bos.md"):
            with self.subTest(name=name):
                text = (self.vault / "notes" / name).read_text(encoding="utf-8")
                self.assertEqual(parse_frontmatter(text), ({}, text, None))
        text = "Önsöz\n---\ntitle: geç\n---\n"
        self.assertEqual(self.parse_text(text), ({}, text, None))

    def test_scalar_types_and_comments(self) -> None:
        meta, body, warning = self.parse_text(
            "---\n# Header\nTürkçe: çığ\nempty:\ncount: -12\nrate: 1.25\n"
            "exponent: 2e3\nyes: true\nno: false\nsingle: 'Deniz''in # notu'\n"
            'double: "a \\"quote\\" # metin" # yorum\n'
            'number_text: "42"\nplain: Deniz\'in notu # yorum\n'
            "hash: hedef#başlık\n---\nBody\n"
        )
        self.assertEqual(meta, {
            "Türkçe": "çığ", "empty": None, "count": -12, "rate": 1.25,
            "exponent": 2000.0, "yes": True, "no": False,
            "single": "Deniz'in # notu", "double": 'a "quote" # metin',
            "number_text": "42", "plain": "Deniz'in notu", "hash": "hedef#başlık",
        })
        self.assertEqual(body, "Body\n")
        self.assertIsNone(warning)

    def test_lists(self) -> None:
        meta, _, warning = self.parse_text(
            '---\ninline: [a, "b c", \'d,e\', 2, false] # yorum\nempty: []\n'
            "block:\n    - Çınar # yorum\n\n    # açıklama\n    - 'Atlas'\n"
            "    - true\n    - 3.5\nnext: value\n---\n"
        )
        self.assertEqual(meta, {
            "inline": ["a", "b c", "d,e", 2, False], "empty": [],
            "block": ["Çınar", "Atlas", True, 3.5], "next": "value",
        })
        self.assertIsNone(warning)

    def test_list_text_with_colons_and_apostrophes(self) -> None:
        meta, _, warning = self.parse_text(
            '---\ninline: [https://example.test, "a: b", Deniz\'in]\n'
            'block:\n  - https://example.test\n  - "a: b"\n  - Deniz\'in\n---\n'
        )
        expected = ["https://example.test", "a: b", "Deniz'in"]
        self.assertEqual(meta, {"inline": expected, "block": expected})
        self.assertIsNone(warning)

    def test_nested_mapping_skips_only_its_key(self) -> None:
        meta, body, warning = self.parse_text(
            "---\ntitle: Keep\nparent:\n  child: value\n  deeper:\n    child: value\n"
            "flow: {child: value}\nlist_mapping:\n  - first\n  - child: value\nkind: fact\n---\nBody\n"
        )
        self.assertEqual(meta, {"title": "Keep", "kind": "fact"})
        self.assertEqual(body, "Body\n")
        self.assertEqual(warning, "frontmatter_partial")

    def test_unsupported_values_preserve_other_keys(self) -> None:
        cases = (
            "unsupported:\n  child: value\n  deeper:\n    child: value\n",
            "unsupported: {child: value}\n",
            "unsupported: |\n  first line\n  second line\n",
            "unsupported: >\n  first line\n  second line\n",
            'unsupported: "unclosed\n  continuation\n',
            "unsupported: 'unclosed\n  continuation\n",
            "unsupported: [a, b\n  continuation\n",
            "unsupported: [a,,b]\n",
            "unsupported: nested: value\n",
            "unsupported:\n  - a\n   - b\n",
            "unsupported:\n\t- a\n",
            "unsupported:\n- a\n- {child: value}\n",
        )
        for unsupported in cases:
            with self.subTest(unsupported=unsupported):
                meta, body, warning = self.parse_text(
                    "---\nkind: task\nproject: atlas\nvisibility: private\n"
                    + unsupported + "owner: Deniz\n---\nBody\n"
                )
                self.assertEqual(meta, {"kind": "task", "project": "atlas", "visibility": "private", "owner": "Deniz"})
                self.assertEqual(body, "Body\n")
                self.assertEqual(warning, "frontmatter_partial")

    def test_unindented_block_lists(self) -> None:
        meta, body, warning = self.parse_text(
            '---\nkind: fact\nparticipants:\n- Deniz\n# comment\n\n- "Atlas: bir"\n'
            "values:\n- 42\n- false\n-\nproject: atlas\n---\nBody\n"
        )
        self.assertEqual(meta, {"kind": "fact", "participants": ["Deniz", "Atlas: bir"],
                                "values": [42, False, None], "project": "atlas"})
        self.assertEqual(body, "Body\n")
        self.assertIsNone(warning)

    def test_partial_does_not_mask_structural_error(self) -> None:
        text = '---\nkind: task\nunsupported: "unclosed\nnot a key\n---\nBody\n'
        self.assertEqual(self.parse_text(text), ({}, text, "frontmatter_invalid"))

    def test_declares_private_spellings(self) -> None:
        for key in ("visibility", "VISIBILITY", '"visibility"', "'Visibility'"):
            for value in ("private", "PRIVATE", '"Private"', "'private'"):
                for suffix in ("", ",", " # comment", ", # comment"):
                    with self.subTest(key=key, value=value, suffix=suffix):
                        self.assertTrue(self.declares_text(f"\ufeff---\r\n  {key}: {value}{suffix}\r\n---\r\nBody\r\n"))
        self.assertTrue(self.declares_text('---\n{"title": "Title", "visibility": "private",\n---\nBody'))
        self.assertTrue(self.declares_text('---\n{"visibility":"private"}\n---\nBody'))

    def test_declares_private_boundaries(self) -> None:
        self.assertTrue(self.declares_text("---\n" + "# filler\n" * 198 + "visibility: private\n"))
        self.assertFalse(self.declares_text("---\n" + "# filler\n" * 199 + "visibility: private\n"))
        self.assertTrue(self.declares_text("---\n" + "# filler\n" * 250 + "visibility: private\n---\nBody\n"))
        for text in (
            "visibility: private\n", "\ufeff# Note\n---\nvisibility: private\n---\n",
            "---\nkind: note\n---\nvisibility: private\n",
            "---\n# visibility: private\n---\n",
            "---\nother_visibility: private\n---\n",
            "---\nvisibility: privateer\n---\n",
            "---\nvisibility: public\n---\n",
            '---\nnote: "visibility: private"\n---\n',
        ):
            with self.subTest(text=text):
                self.assertFalse(self.declares_text(text))

    def test_declares_private_errs_on_the_safe_side(self) -> None:
        for text in (
            '---\nvisibility: "private\n---\n',
            "---\nvisibility: 'private\n---\n",
            "---\nvisibility: private-other\n---\n",
            '---\n"visibility": "private-other"\n---\n',
        ):
            with self.subTest(text=text):
                self.assertTrue(self.declares_text(text))

    def test_invalid_or_unclosed_returns_full_text(self) -> None:
        cases = (
            ("\ufeff---\r\ntitle: lost\r\nBody\r\n", "frontmatter_unclosed"),
            ("---\n{broken}\n---\nBody\n", "frontmatter_invalid"),
            ("---\n[1, 2]\n---\nBody\n", "frontmatter_invalid"),
            ("---\nnot a mapping\n---\nBody\n", "frontmatter_invalid"),
            ("---\nkind: task\nnot a mapping\n---\nBody\n", "frontmatter_invalid"),
            ("---\n- child: value\n---\nBody\n", "frontmatter_invalid"),
        )
        for text, expected_warning in cases:
            with self.subTest(text=text):
                meta, body, warning = self.parse_text(text)
                self.assertEqual(meta, {})
                self.assertEqual(body, text)
                self.assertEqual(warning, expected_warning)


if __name__ == "__main__":
    unittest.main()
