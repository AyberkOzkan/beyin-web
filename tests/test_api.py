from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from beyin_web.http import api
from beyin_web.domain.obsidian import obsidian_uri, obsidian_vault_uri
from beyin_web.vault.records import make_rid
from scripts.update_golden import ENDPOINTS, NOW, TZ, normalize, request, running_server
from tests.support import FIXTURES, make_vault


class APITests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        environment = patch.dict(os.environ, {"FAKE_BEYIN_MODE": "ok", "FAKE_BEYIN_LOG": "",
                                              "FAKE_BEYIN_SOURCE": "notes/Çınar Projesi.md", "FAKE_BEYIN_TEXT": "Sentetik bağlam"})
        environment.start()
        self.addCleanup(environment.stop)
        self.now = NOW
        context = running_server(self.vault, clock=lambda: self.now)
        self.server = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def payload(self, endpoint: str, expected_status: int = 200) -> dict[str, object]:
        status, headers, body = request(self.server, endpoint)
        self.assertEqual(status, expected_status, body)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        payload = json.loads(body)
        self.assertIn("generation", payload)
        content = json.dumps(normalize(payload, self.vault), ensure_ascii=False)
        self.assertNotIn(str(self.vault), content)
        self.assertNotIn(self.vault.as_posix(), content)
        return payload

    def test_all_golden_responses_and_privacy(self) -> None:
        for name, endpoint in ENDPOINTS.items():
            with self.subTest(endpoint=endpoint):
                payload = self.payload(endpoint)
                expected = json.loads((FIXTURES / "golden" / f"{name}.json").read_text(encoding="utf-8"))
                self.assertEqual(normalize(payload, self.vault), expected)
                if name not in {"record", "pulse"}:
                    self.assertNotIn("obsidian://", json.dumps(payload))
                    self.assertNotIn("obsidian_uri", json.dumps(payload))
                self.assertNotIn("GIZLI-SIZINTI-ISARETI", json.dumps(payload))
        snapshot = self.server.source.snapshot()
        for rid in snapshot.records:
            self.assertNotIn("GIZLI-SIZINTI-ISARETI", json.dumps(self.payload("/records/" + rid)))
        self.assertNotIn("GIZLI-SIZINTI-ISARETI", json.dumps(self.payload("/graph?receipts=1&unresolved=1")))

    def test_record_obsidian_uri_uses_server_vault_and_encodes_paths(self) -> None:
        for path in ("notes/atlas.md", "notes/Çınar Projesi.md"):
            with self.subTest(path=path):
                payload = self.payload("/records/" + make_rid(path))
                self.assertEqual(payload["obsidian_uri"], obsidian_uri(str(self.server.settings.vault), path))
                if "Çınar" in path:
                    self.assertIn("%C3%87%C4%B1nar%20Projesi.md", payload["obsidian_uri"])
        self.assertEqual(self.payload("/records/" + make_rid("notes/gizli.md"), 404)["error"]["code"], "not_found")

    def test_private_receipt_title_never_leaks(self) -> None:
        marker = "PRIVATE-RECEIPT-TITLE"
        path = "receipts/" + "f" * 64 + ".md"
        (self.vault / path).write_text(
            '---\nkind: receipt\nvisibility: private\ncreated_at: "2026-01-12T12:00:00+03:00"\n---\n'
            + marker + ".\n", encoding="utf-8",
        )
        for endpoint in (*ENDPOINTS.values(), "/graph?receipts=1&unresolved=1",
                         "/search?q=" + marker, "/records/" + make_rid(path)):
            with self.subTest(endpoint=endpoint):
                status = 404 if endpoint == "/records/" + make_rid(path) else 200
                self.assertNotIn(marker, json.dumps(self.payload(endpoint, status)))
        for rid in self.server.source.snapshot().records:
            self.assertNotIn(marker, json.dumps(self.payload("/records/" + rid)))

    def test_receipt_prefix_tracks_visible_projects_and_preserves_explicit_titles(self) -> None:
        body = "roundtrip: **Başlıkla** aranabilen çalışma tamamlandı. Devam."
        title = "Başlıkla aranabilen çalışma tamamlandı"
        path = "receipts/" + "a" * 64 + ".md"
        receipt = self.vault / path
        header = '---\nkind: receipt\ncreated_at: "2026-01-12T12:00:00+03:00"\n'
        receipt.write_text(header + "---\n" + body, encoding="utf-8")
        rid = make_rid(path)
        self.assertEqual(self.payload("/records/" + rid)["title"], "roundtrip: " + title)
        project = self.vault / "notes" / "roundtrip.md"
        project.write_text("---\nproject: roundtrip\n---\n# Roundtrip\n", encoding="utf-8")
        record = self.payload("/records/" + rid)
        self.assertEqual(record["title"], title)
        snapshot = self.server.source.snapshot()
        self.assertIs(self.server.source.snapshot(), snapshot)
        self.assertEqual(snapshot.records[rid].title, title)
        results = self.payload("/search?q=" + quote("Başlıkla"))["results"]
        self.assertEqual(next(item["title"] for item in results if item["rid"] == rid), title)
        graph = self.payload("/graph?receipts=1&connected_only=0")
        self.assertEqual(next(item["title"] for item in graph["nodes"] if item["id"] == rid), title)
        project.unlink()
        self.assertEqual(self.payload("/records/" + rid)["title"], "roundtrip: " + title)
        project.write_text("---\nproject: roundtrip\nvisibility: private\n---\n# Gizli\n", encoding="utf-8")
        self.assertEqual(self.payload("/records/" + rid)["title"], "roundtrip: " + title)
        project.write_text("---\nproject: roundtrip\n---\n# Roundtrip\n", encoding="utf-8")
        receipt.write_text(header + 'title: "roundtrip: Özel başlık"\n---\n' + body, encoding="utf-8")
        self.assertEqual(self.payload("/records/" + rid)["title"], "roundtrip: Özel başlık")

    def test_normalize_rejects_wrong_vault_without_exposing_uri(self) -> None:
        payload = self.payload(ENDPOINTS["record"])
        with self.assertRaisesRegex(RuntimeError, "^invalid obsidian_uri$"):
            normalize({**payload, "obsidian_uri": obsidian_uri("/elsewhere", payload["path"])}, self.vault)
        self.assertEqual(payload["obsidian_uri"], obsidian_uri(str(self.vault), payload["path"]))

    def test_pulse_vault_name_and_server_drawings(self) -> None:
        payload = self.payload("/pulse")
        self.assertEqual(payload["obsidian_uri"], obsidian_vault_uri(str(self.server.settings.vault)))
        self.assertEqual(normalize(payload, self.vault)["obsidian_uri"], obsidian_vault_uri("/vault"))
        with self.assertRaisesRegex(RuntimeError, "^invalid obsidian_uri$"):
            normalize({**payload, "obsidian_uri": obsidian_vault_uri("/elsewhere")}, self.vault)
        self.assertEqual(payload["vault_name"], self.vault.name)
        self.assertEqual(payload["language"], "tr")
        self.assertEqual({slot: len(paths) for slot, paths in payload["drawings"].items()},
                         {"hero-palace": 8, "sidebar-tree": 7, "heading-mountains": 8, "card-window": 7})
        self.assertEqual(payload["drawings"]["card-window"][0], "/static/img/card-window-01.svg")
        self.server.drawings = {"hero-palace": ["/static/img/hero-palace.png"]}
        self.assertEqual(self.payload("/pulse")["drawings"], self.server.drawings)
        self.server.settings = replace(self.server.settings, language="en")
        self.assertEqual(self.payload("/pulse")["language"], "en")

    def test_etags_and_generation_changes(self) -> None:
        for name, endpoint in ENDPOINTS.items():
            if name == "search_beyin":
                continue
            with self.subTest(endpoint=endpoint):
                status, headers, _ = request(self.server, endpoint)
                self.assertEqual(status, 200)
                status, second_headers, body = request(self.server, endpoint, headers["ETag"])
                self.assertEqual(status, 304)
                self.assertEqual(body, b"")
                self.assertEqual(second_headers["ETag"], headers["ETag"])
        _, headers, before = request(self.server, ENDPOINTS["record"])
        note = self.vault / "notes" / "atlas.md"
        note.write_text(note.read_text(encoding="utf-8") + "\nYeni içerik.\n", encoding="utf-8")
        status, changed_headers, after = request(self.server, ENDPOINTS["record"], headers["ETag"])
        self.assertEqual(status, 200)
        self.assertNotEqual(headers["ETag"], changed_headers["ETag"])
        self.assertGreater(json.loads(after)["generation"], json.loads(before)["generation"])
        self.assertIn("Yeni içerik.", json.loads(after)["body"])

    def test_time_dependent_etags(self) -> None:
        endpoints = ("/home", "/projects", "/projects/atlas", "/journal/heatmap", "/reports")
        old = {endpoint: request(self.server, endpoint)[1]["ETag"] for endpoint in endpoints}
        self.now += timedelta(days=1)
        for endpoint in endpoints:
            self.assertEqual(request(self.server, endpoint, old[endpoint])[0], 200)
        _, headers, _ = request(self.server, "/home")
        self.now = self.now.replace(hour=20)
        self.assertEqual(request(self.server, "/home", headers["ETag"])[0], 200)
        self.assertEqual(self.payload("/home")["greeting"]["period"], "evening")

    def test_projects_quiet_changes_at_local_day(self) -> None:
        (self.vault / "notes" / "quiet.md").write_text('---\nproject: quiet\n---\n# Quiet\n', encoding="utf-8")
        timestamp = datetime(2026, 1, 1, 12, tzinfo=TZ).timestamp()
        os.utime(self.vault / "notes" / "quiet.md", (timestamp, timestamp))
        self.now = datetime(2026, 1, 31, 16, tzinfo=TZ)
        before = self.payload("/projects/quiet")
        self.assertFalse(before["project"]["quiet"])
        self.now += timedelta(days=1)
        self.assertTrue(self.payload("/projects/quiet")["project"]["quiet"])

    def test_reports_default_week_validation_and_midnight(self) -> None:
        before = self.payload("/reports")
        self.assertEqual(before["week"]["start"], "2026-01-12")
        self.assertEqual(before, self.payload("/reports?week=2026-01-18"))
        self.assertEqual(before["today"], "2026-01-12")
        self.assertEqual(before["month"]["end"], before["today"])
        _, headers, _ = request(self.server, "/reports")
        self.assertEqual(request(self.server, "/reports", headers["ETag"])[0], 304)
        self.now += timedelta(days=1)
        status, after_headers, body = request(self.server, "/reports", headers["ETag"])
        self.assertEqual(status, 200)
        self.assertNotEqual(headers["ETag"], after_headers["ETag"])
        self.assertNotEqual(json.loads(body), before)
        for query, parameter in (("week=20260107", "week"), ("week=2026-02-30", "week"),
                                 ("week=2026-01-19", "week"), ("week=", "week"),
                                 ("week=2026-01-07&week=2026-01-08", "week"), ("other=secret", "other")):
            with self.subTest(query=query):
                self.assertEqual(self.payload("/reports?" + query, 400)["error"],
                                 {"code": "bad_request", "message": "invalid_parameter: " + parameter})

    def test_reports_private_records_and_receipts_do_not_affect_any_values(self) -> None:
        before = self.payload("/reports?week=2026-01-07")
        (self.vault / "notes" / "private-report.md").write_text(
            '---\nvisibility: private\nproject: secret\n---\n# SECRET-NOTE\n', encoding="utf-8")
        (self.vault / "receipts" / "private-report.md").write_text(
            '---\nkind: receipt\nvisibility: private\ncreated_at: "2026-01-07T12:00:00+03:00"\n'
            'refs: [notes/atlas.md]\n---\nSECRET-SUMMARY\nÖğrenilen: SECRET-LEARNED\n', encoding="utf-8")
        after = self.payload("/reports?week=2026-01-07")
        self.assertEqual({key: value for key, value in before.items() if key != "generation"},
                         {key: value for key, value in after.items() if key != "generation"})
        self.assertNotIn("SECRET", json.dumps(after))
        for item in after["knowledge"]["most_worked"]:
            record = self.server.source.snapshot().records[item["record"]["rid"]]
            self.assertEqual(item["record"], api.record_summary(record))

    def test_runtime_dependent_etags(self) -> None:
        for endpoint in ("/pulse", "/health"):
            _, headers, before = request(self.server, endpoint)
            doctor = self.server.runtime.doctor()
            doctor = {**doctor, "updates": {**doctor["updates"], "current_version": "0.2.0", "status": "outdated"}}
            with patch.object(self.server.runtime, "doctor", return_value=doctor):
                status, _, after = request(self.server, endpoint, headers["ETag"])
            self.assertEqual(status, 200)
            self.assertNotEqual(before, after)
        _, headers, _ = request(self.server, "/health")
        doctor["hook-health.json"] = {"at": 1767225601, "sync": {"status": "failed"}}
        with patch.object(self.server.runtime, "doctor", return_value=doctor):
            self.assertEqual(request(self.server, "/health", headers["ETag"])[0], 200)

    def test_health_directory_is_relative(self) -> None:
        doctor = self.server.runtime.doctor()
        for directory, expected in ((str(self.vault / "🔮 850-Companion"), "🔮 850-Companion"),
                                    ("/outside/companion", None), ("C:/outside/companion", None)):
            report = {**doctor, "companion_hygiene": {**doctor["companion_hygiene"], "directory": directory}}
            with self.subTest(directory=directory), patch.object(self.server.runtime, "doctor", return_value=report):
                self.assertEqual(self.payload("/health")["health_summary"]["companion_dir"], expected)

    def test_derived_models_are_cached(self) -> None:
        with patch.object(api, "build_tasks", wraps=api.build_tasks) as tasks, patch.object(api, "build_projects", wraps=api.build_projects) as projects:
            for endpoint in ("/home", "/projects", "/tasks", "/projects/atlas", "/graph", "/home"):
                self.payload(endpoint)
            self.assertEqual(tasks.call_count, 1)
            self.assertEqual(projects.call_count, 1)
            self.now += timedelta(days=1)
            self.payload("/home")
            self.assertEqual(tasks.call_count, 1)
            self.assertEqual(projects.call_count, 2)
            (self.vault / "notes" / "added.md").write_text("# Added\n", encoding="utf-8")
            self.payload("/home")
            self.assertEqual(tasks.call_count, 2)

    def test_unknown_records_projects_and_invalid_parameters(self) -> None:
        for endpoint in ("/records/missing", "/projects/missing", "/records/" + make_rid("notes/gizli.md")):
            self.assertEqual(self.payload(endpoint, 404)["error"]["code"], "not_found")
        for endpoint, parameter in (
            ("/journal/months/2026-13", "month"), ("/journal/days/2026-02-30", "day"),
            ("/journal/days/20260112", "day"), ("/search?limit=51", "limit"),
            ("/search?limit=secret-value", "limit"), ("/search?limit=0", "limit"),
            ("/search?mode=secret-value", "mode"), ("/tasks?status=secret-value", "status"),
            ("/graph?receipts=secret-value", "receipts"), ("/graph?depth=2", "depth"),
            ("/graph?focus=missing&depth=-1", "depth"), ("/search?kind=secret-value", "kind"),
            ("/journal/heatmap?weeks=-1", "weeks"), ("/search?limit=2&limit=3", "limit"),
        ):
            with self.subTest(endpoint=endpoint):
                error = self.payload(endpoint, 400)["error"]
                self.assertEqual(error["code"], "bad_request")
                self.assertIn(parameter, error["message"])
                self.assertNotIn("secret-value", error["message"])

    def test_raw_markdown_and_consistent_summaries(self) -> None:
        payload = self.payload("/records/" + make_rid("notes/güvenilmez.md"))
        self.assertIn("<script>alert(1)</script>", payload["body"])
        self.assertIn("![x]", payload["body"])
        self.assertNotIn("<html", payload["body"])
        snapshot = self.server.source.snapshot()
        for item in self.payload("/search?q=Atlas")["results"]:
            expected = api.record_summary(snapshot.records[item["rid"]])
            self.assertEqual({key: item[key] for key in expected}, expected)
        record = self.payload(ENDPOINTS["record"])
        self.assertEqual(record["wikilinks"]["kavram-bir"], make_rid("knowledge/concepts/kavram-bir.md"))
        self.assertNotIn("gizli", record["wikilinks"])
        self.assertNotIn("kod-icinde", record["wikilinks"])
        knowledge = self.payload("/knowledge")
        items = [item for group in knowledge["groups"] for item in group["records"]]
        self.assertEqual(next(item for item in items if item["rid"] == make_rid("knowledge/concepts/kavram-bir.md"))["summary"], "Atlas için temel kavramın özeti.")

    def test_filters_and_focus(self) -> None:
        tasks = self.payload("/tasks?project=atlas&status=active")["tasks"]
        self.assertTrue(tasks)
        self.assertTrue(all(task["project"] == "atlas" and task["status"] == "active" for task in tasks))
        rid = make_rid("notes/atlas.md")
        result = self.payload("/graph?focus=" + rid + "&depth=1")
        neighbors = api.graph.neighborhood(rid, self.server.api._models.links)
        self.assertEqual({node["id"] for node in result["nodes"]}, neighbors)
        graph = self.payload("/graph?kinds=task&project=atlas&connected_only=0")
        self.assertTrue(graph["nodes"])
        self.assertTrue(all(node["kind"] == "task" and node["project"] == "atlas" for node in graph["nodes"]))

    def test_beyin_search_and_errors(self) -> None:
        endpoint = "/search?q=" + quote("-Atlas") + "&mode=beyin"
        status, headers, body = request(self.server, endpoint)
        self.assertEqual(status, 200)
        self.assertNotIn("ETag", headers)
        self.assertEqual(json.loads(body)["results"][0]["text"], "Sentetik bağlam")
        self.assertEqual(request(self.server, endpoint, '"1"')[0], 200)
        for mode, status, code in (("fail", 503, "runtime_unavailable"), ("badjson", 503, "runtime_unavailable"), ("slow", 504, "timeout")):
            with self.subTest(mode=mode), patch.dict(os.environ, {"FAKE_BEYIN_MODE": mode}):
                self.server.runtime.timeout = 0.2 if mode == "slow" else 5
                self.assertEqual(self.payload(endpoint, status)["error"]["code"], code)

    def test_beyin_search_omits_hidden_and_unknown_sources(self) -> None:
        for source in ("notes/gizli.md", "notes/missing.md", "../notes/atlas.md", str(self.vault / "notes" / "atlas.md")):
            with self.subTest(source=source), patch.dict(os.environ, {"FAKE_BEYIN_SOURCE": source, "FAKE_BEYIN_TEXT": "GIZLI-SIZINTI-ISARETI"}):
                payload = self.payload("/search?q=Atlas&mode=beyin")
                self.assertEqual(payload["omitted"], 1)
                self.assertEqual(payload["results"], [])
                self.assertNotIn("GIZLI-SIZINTI-ISARETI", json.dumps(payload))
                self.assertNotIn("fake-1", json.dumps(payload))

    def test_beyin_search_rejects_malformed_records(self) -> None:
        for report in ({"records": None}, {"records": [{"source": "notes/atlas.md", "text": {"unexpected": "value"}}]}):
            with self.subTest(report=report), patch.object(self.server.runtime, "context", return_value=report):
                self.assertEqual(self.payload("/search?mode=beyin&q=Atlas", 503)["error"]["code"], "runtime_unavailable")

    def test_session_times_have_offsets(self) -> None:
        for card in (self.payload("/home")["last_session"],
                     self.payload("/memory")["last_session"]["card"],
                     self.payload("/journal/days/2026-01-12")["cards"][0]):
            self.assertEqual(datetime.fromisoformat(card["time"]).utcoffset(), timedelta(hours=3))
        self.assertIsNone(self.payload("/journal/days/2026-01-05")["cards"][0]["time"])

    def test_plain_vault(self) -> None:
        shutil.rmtree(self.vault / "🔮 850-Companion")
        with running_server(self.vault, beyin=False) as server:
            for endpoint in ("/health", "/home", "/memory"):
                status, _, body = request(server, endpoint)
                self.assertEqual(status, 200, body)
                payload = json.loads(body)
                if endpoint == "/health":
                    self.assertFalse(payload["beyin_available"])
                if endpoint == "/home":
                    self.assertIsNone(payload["last_session"])
                    self.assertEqual(payload["threads"], [])
                if endpoint == "/memory":
                    self.assertTrue(all(section["raw"] == "" for key, section in payload.items() if key != "generation"))
            status, _, body = request(server, "/search?mode=beyin&q=Atlas")
            self.assertEqual(status, 503)
            self.assertEqual(json.loads(body)["error"]["code"], "runtime_unavailable")


if __name__ == "__main__":
    unittest.main()
