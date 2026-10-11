from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Protocol

from beyin_web.vault.records import classify
from beyin_web.vault.scan import VaultSnapshot


class GraphLinks(Protocol):
    @property
    def outgoing(self) -> Mapping[str, tuple[str, ...]]: ...

    @property
    def incoming(self) -> Mapping[str, tuple[str, ...]]: ...

    @property
    def unresolved(self) -> Mapping[str, tuple[str, ...]]: ...


class ReferencingReceipt(Protocol):
    @property
    def rid(self) -> str: ...

    @property
    def ref_rids(self) -> tuple[str, ...]: ...


def build_graph(
    snapshot: VaultSnapshot, links: GraphLinks, receipts: Iterable[ReferencingReceipt],
    kinds: Iterable[str] | None = None, project: str | None = None,
    include_receipts: bool = False, include_unresolved: bool = False,
    connected_only: bool = True,
) -> dict[str, list[dict[str, object]]]:
    """Build a filtered graph; kinds accepts stored kinds or classification names."""
    receipt_by_rid = {receipt.rid: receipt for receipt in receipts}
    selected_kinds = None if kinds is None else set(kinds)
    nodes: dict[str, dict[str, object]] = {}
    for rid, record in sorted(snapshot.records.items()):
        category = classify(record)
        if category in {"index", "rejected"} or (category == "receipt" and not include_receipts):
            continue
        if selected_kinds is not None and not selected_kinds.intersection({record.kind, category}):
            continue
        projects = {record.project} if record.project is not None else set()
        if category == "receipt" and rid in receipt_by_rid:
            receipt = receipt_by_rid[rid]
            receipt_projects = getattr(receipt, "projects", None)
            if receipt_projects is None:
                receipt_projects = {
                    target.project for target_rid in receipt.ref_rids
                    if (target := snapshot.records.get(target_rid)) is not None
                    and classify(target) not in {"index", "rejected", "receipt", "memory"}
                    and target.project is not None
                }
            projects.update(receipt_projects)
        if project is not None and project not in projects:
            continue
        node_project = project if project is not None else record.project
        if node_project is None and projects:
            node_project = min(projects)
        nodes[rid] = {"id": rid, "title": record.title, "kind": record.kind,
                      "project": node_project, "degree": 0}

    edges: set[tuple[str, str, str]] = set()
    for source, targets in links.outgoing.items():
        if source in nodes:
            edges.update((source, target, "link") for target in targets
                         if target in nodes and target != source)
    if include_receipts:
        for receipt in receipt_by_rid.values():
            if receipt.rid in nodes and classify(snapshot.records[receipt.rid]) == "receipt":
                edges.update((receipt.rid, target, "ref") for target in receipt.ref_rids
                             if target in nodes and target != receipt.rid)
    if include_unresolved:
        for source, targets in sorted(links.unresolved.items()):
            if source not in nodes:
                continue
            for title in sorted(set(targets)):
                # Use a separate namespace: an unresolved label cannot identify a hidden record.
                target = "unresolved:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
                nodes.setdefault(target, {"id": target, "title": title, "kind": "unresolved",
                                          "project": None, "degree": 0})
                edges.add((source, target, "link"))

    degrees = dict.fromkeys(nodes, 0)
    for source, target, _ in edges:
        degrees[source] += 1
        degrees[target] += 1
    for rid, node in nodes.items():
        node["degree"] = degrees[rid]
    return {
        "nodes": [nodes[rid] for rid in sorted(nodes) if not connected_only or degrees[rid]],
        "edges": [{"source": source, "target": target, "type": kind}
                  for source, target, kind in sorted(edges)],
    }


def neighborhood(rid: str, links: GraphLinks, depth: int = 1) -> set[str]:
    """Return the focus and its resolved neighbors in either direction."""
    if depth < 0:
        raise ValueError("depth must be nonnegative")
    visited = {rid}
    frontier = {rid}
    for _ in range(depth):
        neighbors = {
            target for source in frontier
            for target in (*links.outgoing.get(source, ()), *links.incoming.get(source, ()))
        } - visited
        if not neighbors:
            break
        visited.update(neighbors)
        frontier = neighbors
    return visited
