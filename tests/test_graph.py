from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from beyin_web.domain.graph import build_graph, neighborhood
from beyin_web.vault.records import classify, make_rid
from beyin_web.vault.scan import MarkdownSource
from tests.support import make_vault


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.snapshot = MarkdownSource(make_vault(Path(temporary.name))).snapshot()
        self.atlas = make_rid("notes/atlas.md")
        self.first = make_rid("knowledge/concepts/kavram-bir.md")
        self.second = make_rid("knowledge/concepts/kavram-iki.md")
        self.task = make_rid("tasks/atlas-a2.md")
        self.isolated = make_rid("notes/serbest.md")
        self.hidden = make_rid("notes/gizli.md")
        self.index = make_rid("knowledge/v3/outcomes.md")
        self.rejected = make_rid("knowledge/concepts/reddedilen.md")
        self.links = SimpleNamespace(
            outgoing={self.atlas: (self.first, self.second, self.task, self.first,
                                   self.hidden, self.index, self.rejected, self.atlas),
                      self.second: (self.first,), self.index: (self.atlas,)},
            incoming={self.first: (self.atlas, self.second), self.second: (self.atlas,),
                      self.task: (self.atlas,)},
            unresolved={self.atlas: ("olmayan-not", "gizli", "olmayan-not"),
                        self.index: ("index-only",)},
        )
        self.receipts = [
            SimpleNamespace(
                rid=record.rid, created_at=datetime.fromisoformat(str(record.meta["created_at"])),
                ref_rids=tuple(make_rid(path) for path in record.meta["refs"]),
            )
            for record in self.snapshot.records.values() if classify(record) == "receipt"
        ]

    def test_default_graph_filters_records_deduplicates_edges_and_counts_degree(self) -> None:
        graph = build_graph(self.snapshot, self.links, self.receipts)
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(set(nodes), {self.atlas, self.first, self.second, self.task})
        self.assertEqual(len(graph["edges"]), 4)
        self.assertEqual(nodes[self.atlas]["degree"], 3)
        self.assertEqual(nodes[self.first]["degree"], 2)
        self.assertEqual(nodes[self.second]["degree"], 2)
        self.assertEqual(nodes[self.task]["degree"], 1)
        self.assertEqual(nodes[self.first]["kind"], "fact")
        self.assertEqual(set(nodes[self.atlas]), {"id", "title", "kind", "project", "degree"})
        for edge in graph["edges"]:
            self.assertEqual(set(edge), {"source", "target", "type"})
            self.assertEqual(edge["type"], "link")
            self.assertIn(edge["source"], nodes)
            self.assertIn(edge["target"], nodes)

    def test_connected_only_drops_isolates_after_filtering(self) -> None:
        graph = build_graph(self.snapshot, self.links, self.receipts, connected_only=False)
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(nodes[self.isolated]["degree"], 0)
        self.assertNotIn(self.index, nodes)
        self.assertNotIn(self.rejected, nodes)
        self.assertNotIn(self.hidden, nodes)
        self.assertEqual(build_graph(self.snapshot, self.links, self.receipts, kinds={"task"}),
                         {"nodes": [], "edges": []})

    def test_project_and_kind_filters_keep_only_matching_nodes_and_edges(self) -> None:
        graph = build_graph(self.snapshot, self.links, self.receipts, project="atlas")
        self.assertTrue(all(node["project"] == "atlas" for node in graph["nodes"]))
        self.assertEqual({node["id"] for node in graph["nodes"]}, {self.atlas, self.first, self.task})
        graph = build_graph(self.snapshot, self.links, self.receipts, kinds={"fact"})
        self.assertEqual({node["id"] for node in graph["nodes"]}, {self.first, self.second})
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(build_graph(self.snapshot, self.links, self.receipts, kinds={"knowledge"}), graph)
        self.assertEqual(build_graph(self.snapshot, self.links, self.receipts, kinds=[]),
                         {"nodes": [], "edges": []})

    def test_receipts_add_refs_and_reference_connected_memory(self) -> None:
        graph = build_graph(self.snapshot, self.links, self.receipts, include_receipts=True)
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertTrue(all(receipt.rid in nodes for receipt in self.receipts))
        self.assertEqual(sum(edge["type"] == "ref" for edge in graph["edges"]), 7)
        self.assertIn(make_rid("🔮 850-Companion/Last-Session.md"), nodes)
        self.assertNotIn(self.index, nodes)
        filtered = build_graph(self.snapshot, self.links, self.receipts,
                               project="atlas", include_receipts=True)
        receipt_ids = {receipt.rid for receipt in self.receipts
                       if self.atlas in receipt.ref_rids}
        self.assertEqual({node["id"] for node in filtered["nodes"] if node["kind"] == "receipt"}, receipt_ids)

    def test_receipt_refs_cannot_reintroduce_hidden_or_excluded_records(self) -> None:
        receipt = self.receipts[0]
        bad_refs = SimpleNamespace(rid=receipt.rid, ref_rids=(self.hidden, self.index, self.rejected))
        graph = build_graph(self.snapshot, self.links, [bad_refs], include_receipts=True)
        self.assertFalse(any(edge["type"] == "ref" for edge in graph["edges"]))
        self.assertNotIn(receipt.rid, {node["id"] for node in graph["nodes"]})

    def test_unresolved_nodes_use_labels_and_never_hidden_record_identity(self) -> None:
        graph = build_graph(self.snapshot, self.links, self.receipts, include_unresolved=True)
        unresolved = [node for node in graph["nodes"] if node["kind"] == "unresolved"]
        self.assertEqual({node["title"] for node in unresolved}, {"gizli", "olmayan-not"})
        self.assertTrue(all(node["id"].startswith("unresolved:") and node["degree"] == 1
                            for node in unresolved))
        self.assertNotIn(self.hidden, {node["id"] for node in graph["nodes"]})
        self.assertNotIn("GIZLI-SIZINTI-ISARETI", repr(graph))
        self.assertFalse(any(node["kind"] == "unresolved"
                             for node in build_graph(self.snapshot, self.links, [])["nodes"]))

    def test_receipt_project_assignment_is_used_when_available(self) -> None:
        receipt = SimpleNamespace(rid=self.receipts[0].rid, ref_rids=(self.atlas,), projects=("inferred",))
        graph = build_graph(self.snapshot, self.links, [receipt], include_receipts=True,
                            project="inferred", connected_only=False)
        self.assertEqual(len(graph["nodes"]), 1)
        self.assertEqual(graph["nodes"][0]["id"], receipt.rid)
        self.assertEqual(graph["nodes"][0]["project"], "inferred")

    def test_neighborhood_includes_incoming_outgoing_cycles_and_depth(self) -> None:
        links = SimpleNamespace(outgoing={"a": ("b",), "b": ("c",), "c": ("a",)},
                                incoming={"a": ("c",), "b": ("a",), "c": ("b",)}, unresolved={})
        self.assertEqual(neighborhood("a", links, 0), {"a"})
        self.assertEqual(neighborhood("a", links), {"a", "b", "c"})
        self.assertEqual(neighborhood("a", links, 10), {"a", "b", "c"})
        self.assertEqual(neighborhood("missing", links), {"missing"})
        chain = SimpleNamespace(outgoing={"a": ("b",), "b": ("c",)},
                                incoming={"b": ("a",), "c": ("b",)}, unresolved={})
        self.assertEqual(neighborhood("a", chain), {"a", "b"})
        self.assertEqual(neighborhood("a", chain, 2), {"a", "b", "c"})
        with self.assertRaises(ValueError):
            neighborhood("a", links, -1)

    def test_output_is_stable_without_mutating_input(self) -> None:
        original = repr((self.snapshot, self.links, self.receipts))
        expected = build_graph(self.snapshot, self.links, self.receipts,
                               include_receipts=True, include_unresolved=True)
        reordered = replace(self.snapshot, records=dict(reversed(list(self.snapshot.records.items()))))
        links = SimpleNamespace(outgoing=dict(reversed(list(self.links.outgoing.items()))),
                                incoming=self.links.incoming,
                                unresolved=dict(reversed(list(self.links.unresolved.items()))))
        self.assertEqual(build_graph(reordered, links, reversed(self.receipts),
                                     include_receipts=True, include_unresolved=True), expected)
        self.assertEqual(repr((self.snapshot, self.links, self.receipts)), original)


if __name__ == "__main__":
    unittest.main()
