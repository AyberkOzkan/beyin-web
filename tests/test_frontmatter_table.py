"""Table-driven tests for parse_frontmatter, written from the contract alone.

The first twenty cases were drafted by a local model without sight of the
implementation; one of them was wrong and was corrected, and the rest were added by hand.
"""

from __future__ import annotations

import unittest

from beyin_web.vault.frontmatter import parse_frontmatter

Case = tuple[str, str, dict, str, str | None]

UNCLOSED = "---\nkind: note\nproject: atlas\n\nBody\n"
INVALID_JSON = '---\n{"kind": "note",}\n---\nBody\n'

CASES: list[Case] = [
    ("json_object", '---\n{"title": "Hello", "kind": "fact"}\n---\nBody text\n', {"title": "Hello", "kind": "fact"}, "Body text", None),
    ("json_with_list", '---\n{"tags": ["a", "b"], "count": 3}\n---\nBody\n', {"tags": ["a", "b"], "count": 3}, "Body", None),
    ("yaml_unquoted", "---\ntitle: Hello World\nkind: fact\n---\nBody\n", {"title": "Hello World", "kind": "fact"}, "Body", None),
    ("yaml_single_quoted", "---\ntitle: 'Hello World'\n---\nBody\n", {"title": "Hello World"}, "Body", None),
    ("yaml_double_quoted", '---\ntitle: "Hello World"\n---\nBody\n', {"title": "Hello World"}, "Body", None),
    ("yaml_double_quoted_with_colon", '---\ntitle: "Atlas A3: test"\n---\nBody\n', {"title": "Atlas A3: test"}, "Body", None),
    ("yaml_int", "---\ncount: 42\n---\nBody\n", {"count": 42}, "Body", None),
    ("yaml_float", "---\nratio: 3.14\n---\nBody\n", {"ratio": 3.14}, "Body", None),
    ("yaml_true", "---\nactive: true\n---\nBody\n", {"active": True}, "Body", None),
    ("yaml_false", "---\nactive: false\n---\nBody\n", {"active": False}, "Body", None),
    ("yaml_empty_value_is_none", "---\ntitle:\n---\nBody\n", {"title": None}, "Body", None),
    ("yaml_inline_list", "---\ntags: [a, b, c]\n---\nBody\n", {"tags": ["a", "b", "c"]}, "Body", None),
    ("yaml_inline_list_quoted_item_with_space", '---\ntags: [a, "b c"]\n---\nBody\n', {"tags": ["a", "b c"]}, "Body", None),
    ("yaml_empty_inline_list", "---\ntags: []\n---\nBody\n", {"tags": []}, "Body", None),
    ("yaml_indented_block_list", "---\ntags:\n  - alpha\n  - beta\n---\nBody\n", {"tags": ["alpha", "beta"]}, "Body", None),
    ("yaml_unindented_block_list", "---\ntags:\n- alpha\n- beta\n---\nBody\n", {"tags": ["alpha", "beta"]}, "Body", None),
    ("yaml_trailing_comment", "---\ntitle: Hello # my comment\n---\nBody\n", {"title": "Hello"}, "Body", None),
    ("yaml_hash_inside_quotes_is_kept", '---\ntitle: "a # b"\n---\nBody\n', {"title": "a # b"}, "Body", None),
    ("yaml_unicode_key", "---\nbaşlık: Merhaba\n---\nBody\n", {"başlık": "Merhaba"}, "Body", None),
    ("yaml_nested_mapping_is_partial", "---\nkind: note\nowner:\n  name: Deniz\n  role: lead\nproject: atlas\n---\nBody\n",
     {"kind": "note", "project": "atlas"}, "Body", "frontmatter_partial"),
    ("yaml_block_text_is_partial", "---\nkind: task\nnotes: |\n  first line\n  second line\nproject: cinar\n---\nBody\n",
     {"kind": "task", "project": "cinar"}, "Body", "frontmatter_partial"),
    ("bom_before_frontmatter", "﻿---\nkind: note\n---\nBody\n", {"kind": "note"}, "Body", None),
    ("crlf_frontmatter", "---\r\nkind: note\r\ncount: 2\r\n---\r\nBody\r\nMore\r\n", {"kind": "note", "count": 2}, "Body\nMore", None),
    ("no_frontmatter", "# Title\n\nBody\n", {}, "# Title\n\nBody", None),
    ("unclosed_frontmatter", UNCLOSED, {}, UNCLOSED, "frontmatter_unclosed"),
    ("invalid_json", INVALID_JSON, {}, INVALID_JSON, "frontmatter_invalid"),
]


def typed(value: object) -> object:
    if isinstance(value, dict):
        return {key: typed(item) for key, item in value.items()}
    if isinstance(value, list):
        return [typed(item) for item in value]
    return (type(value).__name__, value)


class FrontmatterTableTests(unittest.TestCase):
    def test_cases(self) -> None:
        for name, text, expected_meta, expected_body, expected_warning in CASES:
            with self.subTest(name=name):
                meta, body, warning = parse_frontmatter(text)
                self.assertEqual(typed(meta), typed(expected_meta))
                self.assertEqual(body.replace("\r\n", "\n").strip(), expected_body.replace("\r\n", "\n").strip())
                self.assertEqual(warning, expected_warning)

    def test_case_names_are_unique(self) -> None:
        names = [case[0] for case in CASES]
        self.assertEqual(len(names), 26)
        self.assertEqual(len(set(names)), 26)


if __name__ == "__main__":
    unittest.main()
