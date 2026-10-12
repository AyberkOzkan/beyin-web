from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import cast

from beyin_web.config import Settings
from beyin_web.domain import goals
from beyin_web.http.api import register_api
from beyin_web.http.server import MAX_WRITE_BODY, BeyinHTTPServer
from beyin_web.runtime.beyin_cli import BeyinRuntime
from beyin_web.vault.frontmatter import parse_frontmatter
from beyin_web.vault.records import make_rid
from beyin_web.vault.scan import MarkdownSource
from beyin_web.vault.writer import VaultWriter, WriteConflict
from scripts.update_golden import NOW, TZ
from tests.support import add_goals, make_vault

GOAL = (
    '---\n{\n  "kind": "goal",\n  "horizon": "year",\n  "period": 2026,\n  "area": "Öğrenme"\n}\n---\n'
    "# Kitap\n\nYılda on iki kitap.\n\n- [x] Birinci\n```\n- [ ] kod örneği\n```\n- [ ] İkinci\n  - [X] Alt adım\n"
)


class GoalTextTests(unittest.TestCase):
    def test_steps_skip_code_and_keep_their_order(self) -> None:
        steps = goals.read_steps(parse_frontmatter(GOAL)[1])
        self.assertEqual([(step.index, step.text, step.done) for step in steps],
                         [(0, "Birinci", True), (1, "İkinci", False), (2, "Alt adım", True)])
        self.assertEqual(goals.read_steps("- [ ]\n- [] boş\n-[ ] bitişik\n"), ())

    def test_set_step_changes_one_character_and_nothing_else(self) -> None:
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=newline):
                text = "﻿" + GOAL.replace("\n", newline)
                changed = goals.set_step(text, 1, "İkinci", True)
                self.assertEqual(changed, text.replace("- [ ] İkinci", "- [x] İkinci"))
                self.assertEqual(goals.set_step(changed, 1, "İkinci", False), text)
                self.assertEqual(goals.set_step(text, 2, "Alt adım", False),
                                 text.replace("  - [X] Alt adım", "  - [ ] Alt adım"))
                self.assertEqual(goals.set_step(text, 0, "Birinci", True), text)

    def test_set_step_refuses_a_step_that_moved_or_vanished(self) -> None:
        for index, expected in ((1, "Birinci"), (1, "ikinci"), (3, "İkinci"), (0, "kod örneği")):
            with self.subTest(index=index, expected=expected), self.assertRaises(goals.GoalConflict):
                goals.set_step(GOAL, index, expected, True)

    def test_days_are_unique_sorted_and_valid(self) -> None:
        body = "# Spor\n\n- 2026-01-09\n- 2026-01-03\n- 2026-01-09\n- 2026-02-30\n- 2026-01-04 koşu\n```\n- 2026-01-05\n```\n"
        self.assertEqual(goals.read_days(body), ("2026-01-03", "2026-01-09"))

    def test_set_day_is_idempotent_and_keeps_the_file_style(self) -> None:
        text = '---\n{"kind": "habit"}\n---\n# Spor\n\n- 2026-01-03'
        added = goals.set_day(text, date(2026, 1, 9), True)
        self.assertEqual(added, text + "\n- 2026-01-09\n")
        self.assertEqual(goals.set_day(added, date(2026, 1, 9), True), added)
        self.assertEqual(goals.set_day(added, date(2026, 1, 3), False),
                         '---\n{"kind": "habit"}\n---\n# Spor\n\n- 2026-01-09\n')
        self.assertEqual(goals.set_day(text, date(2026, 1, 9), False), text)
        windows = text.replace("\n", "\r\n") + "\r\n"
        self.assertEqual(goals.set_day(windows, date(2026, 1, 9), True), windows + "- 2026-01-09\r\n")

    def test_check_title_reads_the_note_as_the_scanner_does(self) -> None:
        goals.check_title(GOAL, "Kitap", "dosya")
        goals.check_title("\ufeff" + GOAL.replace("\n", "\r\n"), " Kitap ", "dosya")
        goals.check_title('---\n{"title": "Başlık alanı"}\n---\n# Gövde başlığı\n', "Başlık alanı", "dosya")
        goals.check_title("```\n# kod\n```\nbaşlıksız\n", "dosya", "dosya")
        for text, expected in ((GOAL, "kitap"), (GOAL, "Kitap okumak"), (GOAL, ""),
                               ("# Yeni ad\n", "Kitap"), ("başlıksız\n", "Kitap")):
            with self.subTest(expected=expected), self.assertRaises(goals.GoalConflict):
                goals.check_title(text, expected, "dosya")

    def test_clean_line_and_slug(self) -> None:
        self.assertEqual(goals.clean_line("  Sağlıklı yaşam  ", 20), "Sağlıklı yaşam")
        for value in ("", "   ", "iki\nsatır", "sekme\tli", "x" * 21, None, 5, ["a"], "gizli​boşluk"):
            self.assertIsNone(goals.clean_line(value, 20))
        self.assertEqual(goals.slug("Çığ, Şöför & IŞIK İçin 12 Öğün!"), "cig-sofor-isik-icin-12-ogun")
        self.assertEqual(goals.slug("日本語"), "")
        self.assertEqual([goals.slug(name) for name in ("CON", "Nul", "com1", "LPT9", "conk")],
                         ["con-not", "nul-not", "com1-not", "lpt9-not", "conk"])
        self.assertLessEqual(len(goals.slug("a" * 200)), 60)

    def test_documents_round_trip_through_the_parser(self) -> None:
        text = goals.goal_document('Tırnak "içinde"', "long", "2025–2030", "Üretim", ["Bir", "İki"])
        meta, body, warning = parse_frontmatter(text)
        self.assertIsNone(warning)
        self.assertEqual(meta, {"kind": "goal", "horizon": "long", "period": "2025–2030", "area": "Üretim",
                                "visibility": "internal"})
        self.assertEqual(body, '# Tırnak "içinde"\n\n- [ ] Bir\n- [ ] İki\n')
        meta, body, _ = parse_frontmatter(goals.habit_document("Spor"))
        self.assertEqual((meta, body), ({"kind": "habit", "visibility": "internal"}, "# Spor\n\n"))
        self.assertEqual(goals.set_day(goals.habit_document("Spor"), date(2026, 1, 1), True),
                         goals.habit_document("Spor") + "- 2026-01-01\n")


class GoalModelTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        add_goals(self.vault)
        self.snapshot = MarkdownSource(self.vault).snapshot()

    def test_goals_habits_and_areas(self) -> None:
        built = goals.build_goals(self.snapshot)
        self.assertEqual([(goal.title, goal.horizon, goal.period, goal.area, goal.done, goal.total) for goal in built], [
            ("Anlamlı bir iş üretmek", "long", "2025–2030", "Üretim", 1, 2),
            ("Etiketsiz hedef", "long", None, None, 0, 0),
            ("Derinleş ve inşa et", "theme", "2026", None, 0, 0),
            ("12 kitap okumak", "year", "2026", "öğrenme", 1, 3),
            ("Aylık bir yazı paylaşmak", "year", "2026", "Üretim", 0, 0),
        ])
        self.assertEqual(built[0].summary, "Kalıcı bir şey bırakmak.")
        self.assertEqual(built[3].summary, "")
        self.assertNotIn("GIZLI-HEDEF", json.dumps([goal.title for goal in built]))
        self.assertEqual(goals.areas(built), [
            {"name": "öğrenme", "goals": 1, "done": 1, "total": 3},
            {"name": "Üretim", "goals": 2, "done": 1, "total": 2},
        ])
        self.assertEqual([(habit.title, habit.days) for habit in goals.build_habits(self.snapshot)], [
            ("Kitap okumak", ()), ("Spor yapmak", ("2026-01-03", "2026-01-09", "2026-01-12")),
        ])


class VaultWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "vault"
        self.root.mkdir()
        self.writer = VaultWriter(self.root)

    def test_create_never_replaces(self) -> None:
        self.assertEqual(self.writer.create("hedef", "bir\r\n"), "goals/hedef.md")
        self.assertEqual(self.writer.create("hedef", "iki"), "goals/hedef-2.md")
        self.assertEqual((self.root / "goals" / "hedef.md").read_bytes(), b"bir\r\n")
        self.assertEqual((self.root / "goals" / "hedef-2.md").read_bytes(), b"iki")
        self.assertEqual(sorted(path.name for path in (self.root / "goals").iterdir()), ["hedef-2.md", "hedef.md"])

    def test_create_refuses_a_folder_that_is_not_a_plain_folder(self) -> None:
        (self.root / "goals").write_text("dosya", encoding="utf-8")
        with self.assertRaises(WriteConflict):
            self.writer.create("hedef", "x")
        (self.root / "goals").unlink()
        outside = self.root.parent / "outside"
        outside.mkdir()
        try:
            (self.root / "goals").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        with self.assertRaises(WriteConflict):
            self.writer.create("hedef", "x")
        self.assertEqual(list(outside.iterdir()), [])

    def test_update_rewrites_only_when_the_text_changes(self) -> None:
        path = self.root / "not.md"
        path.write_bytes("﻿bir\r\niki\r\n".encode("utf-8"))
        os.utime(path, ns=(10**18, 10**18))
        self.assertFalse(self.writer.update("not.md", lambda text: text))
        self.assertEqual(path.stat().st_mtime_ns, 10**18)
        self.assertTrue(self.writer.update("not.md", lambda text: text.replace("iki", "üç")))
        self.assertEqual(path.read_bytes(), "﻿bir\r\nüç\r\n".encode("utf-8"))
        self.assertEqual([item.name for item in self.root.iterdir()], ["not.md"])

    def test_update_refuses_unsafe_or_unreadable_targets(self) -> None:
        (self.root / "veri.txt").write_text("x", encoding="utf-8")
        (self.root / "bozuk.md").write_bytes(b"\xff\xfe")
        outside = self.root.parent / "outside.md"
        outside.write_text("dışarıda", encoding="utf-8")
        for relative in ("veri.txt", "yok.md", "../outside.md", "bozuk.md"):
            with self.subTest(relative=relative), self.assertRaises(WriteConflict):
                self.writer.update(relative, lambda text: text + "!")
        try:
            (self.root / "bağ.md").symlink_to(outside)
        except (OSError, NotImplementedError):
            pass
        else:
            with self.assertRaises(WriteConflict):
                self.writer.update("bağ.md", lambda text: text + "!")
        self.assertEqual(outside.read_text(encoding="utf-8"), "dışarıda")

    def test_discard_moves_to_the_trash_and_replaces_nothing(self) -> None:
        for name in ("not.md", "ikiz.md"):
            (self.root / name).write_bytes("\ufeffbir\r\n".encode("utf-8"))
        seen: list[str] = []
        self.assertEqual(self.writer.discard("not.md", seen.append), ".trash/not.md")
        self.assertEqual(seen, ["\ufeffbir\r\n"])
        self.assertFalse((self.root / "not.md").exists())
        self.assertEqual((self.root / ".trash" / "not.md").read_bytes(), "\ufeffbir\r\n".encode("utf-8"))
        (self.root / "not.md").write_text("iki", encoding="utf-8")
        self.assertEqual(self.writer.discard("not.md", lambda text: None), ".trash/not-2.md")
        self.assertEqual((self.root / ".trash" / "not.md").read_bytes(), "\ufeffbir\r\n".encode("utf-8"))
        self.assertEqual((self.root / ".trash" / "not-2.md").read_text(encoding="utf-8"), "iki")

        def refuse(text: str) -> None:
            raise goals.GoalConflict("title_changed")

        with self.assertRaises(goals.GoalConflict):
            self.writer.discard("ikiz.md", refuse)
        self.assertTrue((self.root / "ikiz.md").is_file())
        (self.root / "veri.txt").write_text("x", encoding="utf-8")
        for relative in ("veri.txt", "yok.md", "../outside.md", ".trash"):
            with self.subTest(relative=relative), self.assertRaises(WriteConflict):
                self.writer.discard(relative, lambda text: None)
        self.assertEqual(sorted(item.name for item in self.root.iterdir()), [".trash", "ikiz.md", "veri.txt"])

    def test_discard_refuses_a_trash_that_is_not_a_plain_folder(self) -> None:
        (self.root / "not.md").write_text("bir", encoding="utf-8")
        (self.root / ".trash").write_text("dosya", encoding="utf-8")
        with self.assertRaises(WriteConflict):
            self.writer.discard("not.md", lambda text: None)
        (self.root / ".trash").unlink()
        outside = self.root.parent / "outside"
        outside.mkdir()
        try:
            (self.root / ".trash").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable")
        with self.assertRaises(WriteConflict):
            self.writer.discard("not.md", lambda text: None)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual((self.root / "not.md").read_text(encoding="utf-8"), "bir")

    def test_update_gives_way_to_a_concurrent_save(self) -> None:
        path = self.root / "not.md"
        path.write_text("eski", encoding="utf-8")

        def interrupted(text: str) -> str:
            path.write_text("Obsidian'da kaydedildi", encoding="utf-8")
            return text + " web"

        with self.assertRaises(WriteConflict):
            self.writer.update("not.md", interrupted)
        self.assertEqual(path.read_text(encoding="utf-8"), "Obsidian'da kaydedildi")
        self.assertEqual([item.name for item in self.root.iterdir()], ["not.md"])


class GoalServerCase(unittest.TestCase):
    token = ""
    read_only = False

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.vault = make_vault(Path(temporary.name))
        add_goals(self.vault)
        settings = Settings(vault=self.vault, port=0, token_enabled=bool(self.token), token=self.token,
                            read_only=self.read_only)
        self.server = BeyinHTTPServer(settings, MarkdownSource(self.vault, min_interval=0),
                                      BeyinRuntime(self.vault, enabled=False))
        register_api(self.server, clock=lambda: NOW, tz=TZ)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()

        def stop() -> None:
            self.server.shutdown()
            thread.join(timeout=5)
            self.server.server_close()

        self.addCleanup(stop)
        self.port = self.server.server_port
        self.rid = make_rid("goals/kitap.md")
        self.habit = make_rid("goals/spor.md")

    def call(
        self, path: str, body: object = None, *, method: str = "POST",
        headers: Mapping[str, str] | None = None, raw: bytes | None = None,
    ) -> tuple[int, dict[str, object]]:
        sent = {"Origin": f"http://127.0.0.1:{self.port}", "Content-Type": "application/json",
                "X-Beyin-Web": "1"} if method != "GET" else {}
        sent.update(headers or {})
        sent = {name: value for name, value in sent.items() if value}
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            data = raw if raw is not None else json.dumps(body).encode("utf-8") if body is not None else None
            connection.request(method, "/api/v1" + path, body=data, headers=sent)
            response = connection.getresponse()
            return response.status, cast(dict[str, object], json.loads(response.read()))
        finally:
            connection.close()

    def goals(self) -> dict[str, object]:
        status, payload = self.call("/goals", method="GET")
        self.assertEqual(status, 200)
        return payload

    def files(self) -> dict[str, bytes]:
        return {path.relative_to(self.vault).as_posix(): path.read_bytes()
                for path in self.vault.rglob("*") if path.is_file() and not path.is_symlink()}

    def assert_refused(self, status: int, code: str, path: str, body: object = None, **options: object) -> None:
        before = self.files()
        result = self.call(path, body, **options)  # type: ignore[arg-type]
        self.assertEqual((result[0], cast(dict[str, str], result[1]["error"])["code"]), (status, code))
        self.assertEqual(self.files(), before)


class GoalAPITests(GoalServerCase):
    def test_goals_response(self) -> None:
        payload = self.goals()
        self.assertEqual(payload["today"], "2026-01-12")
        self.assertIs(payload["writable"], True)
        listed = cast(list[dict[str, object]], payload["goals"])
        self.assertEqual([goal["title"] for goal in listed],
                         ["Anlamlı bir iş üretmek", "Etiketsiz hedef", "12 kitap okumak", "Aylık bir yazı paylaşmak"])
        self.assertEqual(listed[2]["steps"], [{"index": 0, "text": "Birinci kitap", "done": True},
                                              {"index": 1, "text": "İkinci kitap", "done": False},
                                              {"index": 2, "text": "Üçüncü kitap", "done": False}])
        self.assertEqual(cast(dict[str, object], payload["theme"])["title"], "Derinleş ve inşa et")
        self.assertEqual([habit["title"] for habit in cast(list[dict[str, object]], payload["habits"])],
                         ["Kitap okumak", "Spor yapmak"])
        self.assertNotIn("GIZLI-HEDEF", json.dumps(payload, ensure_ascii=False))
        self.assertNotIn(str(self.vault), json.dumps(payload, ensure_ascii=False))

    def test_habit_ticks_do_not_count_as_worked_notes(self) -> None:
        self.assertEqual(self.call(f"/habits/{self.habit}/days/2026-01-11", {"done": True})[0], 200)
        os.utime(self.vault / "goals" / "spor.md", ns=(int(NOW.timestamp() * 1e9),) * 2)
        home = self.call("/home", method="GET")[1]
        day = self.call("/journal/days/2026-01-12", method="GET")[1]
        for records in (home["recent"], day["changed"]):
            self.assertNotIn(self.habit, [record["rid"] for record in cast(list[dict[str, str]], records)])

    def test_create_goal_and_habit(self) -> None:
        before = self.files()
        status, created = self.call("/goals", {"title": "  Düzenli spor  ", "horizon": "year", "area": "Sağlık",
                                               "steps": ["Haftada üç gün", "Yüzme"]})
        self.assertEqual(status, 200)
        self.assertEqual(created["rid"], make_rid("goals/duzenli-spor.md"))
        self.assertEqual((self.vault / "goals" / "duzenli-spor.md").read_text(encoding="utf-8"), goals.goal_document(
            "Düzenli spor", "year", "2026", "Sağlık", ["Haftada üç gün", "Yüzme"]))
        payload = self.goals()
        self.assertEqual(payload["generation"], created["generation"])
        goal = next(goal for goal in cast(list[dict[str, object]], payload["goals"]) if goal["rid"] == created["rid"])
        self.assertEqual((goal["title"], goal["period"], goal["area"], goal["total"]), ("Düzenli spor", "2026", "Sağlık", 2))
        self.assertEqual(self.call("/goals", {"title": "Düzenli spor", "horizon": "long"})[1]["rid"],
                         make_rid("goals/duzenli-spor-2.md"))
        self.assertEqual(self.call("/habits", {"title": "日本語"})[1]["rid"], make_rid("goals/aliskanlik.md"))
        after = self.files()
        self.assertEqual({path for path in after if path not in before},
                         {"goals/duzenli-spor.md", "goals/duzenli-spor-2.md", "goals/aliskanlik.md"})
        self.assertEqual({path: after[path] for path in before}, before)

    def test_invalid_payloads_write_nothing(self) -> None:
        valid = {"title": "Hedef", "horizon": "year"}
        for body in (
            {"horizon": "year"}, {**valid, "title": ""}, {**valid, "title": "x" * 121}, {**valid, "title": "iki\nsatır"},
            {**valid, "title": 5}, {**valid, "horizon": "theme"}, {**valid, "horizon": None}, {**valid, "period": "x" * 41},
            {**valid, "area": ["a"]}, {**valid, "steps": "adım"}, {**valid, "steps": ["a"] * 31},
            {**valid, "steps": ["a", ""]}, {**valid, "steps": [1]}, {**valid, "path": "../x"}, {**valid, "kind": "note"},
        ):
            with self.subTest(body=body):
                self.assert_refused(400, "bad_request", "/goals", body)
        self.assert_refused(400, "bad_request", "/habits", {"title": "Spor", "days": []})
        self.assert_refused(400, "bad_request", "/goals", raw=b"{bozuk")
        self.assert_refused(400, "bad_request", "/goals", raw=b'["title"]')
        self.assert_refused(400, "bad_request", "/goals", raw=b"\xff\xfe")
        self.assert_refused(413, "payload_too_large", "/goals", raw=b" " * (MAX_WRITE_BODY + 1))

    def test_step_toggle_and_conflicts(self) -> None:
        path = self.vault / "goals" / "kitap.md"
        original = path.read_text(encoding="utf-8")
        self.assertEqual(self.call(f"/goals/{self.rid}/steps/1", {"done": True, "text": "İkinci kitap"})[0], 200)
        self.assertEqual(path.read_text(encoding="utf-8"), original.replace("- [ ] İkinci kitap", "- [x] İkinci kitap"))
        self.assertEqual(self.call(f"/goals/{self.rid}/steps/1", {"done": False, "text": "İkinci kitap"})[0], 200)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assert_refused(409, "conflict", f"/goals/{self.rid}/steps/1", {"done": True, "text": "Birinci kitap"})
        self.assert_refused(409, "conflict", f"/goals/{self.rid}/steps/9", {"done": True, "text": "İkinci kitap"})
        task = make_rid("tasks/atlas-a1.md")
        for rid in (task, self.habit, "0" * 12, make_rid("goals/gizli.md")):
            self.assert_refused(404, "not_found", f"/goals/{rid}/steps/0", {"done": True, "text": "Birinci kitap"})
        for body in ({"done": 1, "text": "x"}, {"done": True}, {"done": True, "text": "x", "index": 0}, {"text": "x"}):
            self.assert_refused(400, "bad_request", f"/goals/{self.rid}/steps/0", body)

    def test_habit_days(self) -> None:
        path = self.vault / "goals" / "spor.md"
        original = path.read_text(encoding="utf-8")
        self.assertEqual(self.call(f"/habits/{self.habit}/days/2026-01-12", {"done": True})[0], 200)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertEqual(self.call(f"/habits/{self.habit}/days/2026-01-10", {"done": True})[0], 200)
        self.assertEqual(path.read_text(encoding="utf-8"), original + "- 2026-01-10\n")
        self.assertEqual(self.call(f"/habits/{self.habit}/days/2026-01-10", {"done": False})[0], 200)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        for day in ("2026-01-13", "2026-02-30", "2999-01-01"):
            self.assert_refused(400, "bad_request", f"/habits/{self.habit}/days/{day}", {"done": True})
        self.assert_refused(400, "bad_request", f"/habits/{self.habit}/days/2026-01-10", {"done": "true"})
        self.assert_refused(404, "not_found", f"/habits/{self.rid}/days/2026-01-10", {"done": True})

    def test_delete_moves_the_note_to_the_trash(self) -> None:
        before = self.files()
        records = self.call("/pulse", method="GET")[1]["records"]
        self.assertEqual(self.call(f"/goals/{self.rid}/delete", {"title": "12 kitap okumak"})[0], 200)
        self.assertEqual(self.call(f"/habits/{self.habit}/delete", {"title": "Spor yapmak"})[0], 200)
        after = self.files()
        self.assertEqual(after.pop(".trash/kitap.md"), before.pop("goals/kitap.md"))
        self.assertEqual(after.pop(".trash/spor.md"), before.pop("goals/spor.md"))
        self.assertEqual(after, before)
        payload = self.goals()
        self.assertNotIn(self.rid, [goal["rid"] for goal in cast(list[dict[str, object]], payload["goals"])])
        self.assertEqual([habit["title"] for habit in cast(list[dict[str, object]], payload["habits"])], ["Kitap okumak"])
        # The trash is a hidden folder: its notes are no longer records of any page.
        self.assertEqual(self.call("/pulse", method="GET")[1]["records"], cast(int, records) - 2)
        self.assert_refused(404, "not_found", f"/goals/{self.rid}/delete", {"title": "12 kitap okumak"})

    def test_delete_is_refused_when_it_would_hit_the_wrong_note(self) -> None:
        other = make_rid("goals/is.md")
        self.assert_refused(409, "conflict", f"/goals/{self.rid}/delete", {"title": "Anlamlı bir iş üretmek"})
        self.assert_refused(409, "conflict", f"/goals/{self.rid}/delete", {"title": ""})
        self.assert_refused(404, "not_found", f"/habits/{self.rid}/delete", {"title": "12 kitap okumak"})
        self.assert_refused(404, "not_found", f"/goals/{self.habit}/delete", {"title": "Spor yapmak"})
        self.assert_refused(404, "not_found", f"/goals/{make_rid('tasks/atlas-a1.md')}/delete", {"title": "x"})
        self.assert_refused(404, "not_found", f"/goals/{make_rid('goals/gizli.md')}/delete", {"title": "GIZLI-HEDEF"})
        for body in ({}, {"title": 5}, {"title": "12 kitap okumak", "force": True}):
            self.assert_refused(400, "bad_request", f"/goals/{self.rid}/delete", body)
        self.assert_refused(403, "forbidden_origin", f"/goals/{other}/delete", {"title": "Anlamlı bir iş üretmek"},
                            headers={"X-Beyin-Web": ""})
        for method in ("DELETE", "PUT"):
            self.assert_refused(405, "method_not_allowed", f"/goals/{other}", {"title": "Anlamlı bir iş üretmek"},
                                method=method)

    def test_forged_requests_are_refused(self) -> None:
        body = {"title": "Sahte", "horizon": "year"}
        for headers in (
            {"Origin": ""}, {"Origin": "http://evil.example"}, {"Origin": f"https://127.0.0.1:{self.port}"},
            {"Origin": f"http://127.0.0.1:{self.port + 1}"}, {"Origin": "null"},
            {"Content-Type": "text/plain"}, {"Content-Type": "application/x-www-form-urlencoded"}, {"Content-Type": ""},
            {"X-Beyin-Web": ""}, {"X-Beyin-Web": "0"},
        ):
            with self.subTest(headers=headers):
                self.assert_refused(403, "forbidden_origin", "/goals", body, headers=headers)
        self.assert_refused(403, "forbidden_host", "/goals", body, headers={"Host": "evil.example"})
        self.assertEqual(self.call("/goals", body, headers={"Origin": f"http://localhost:{self.port}",
                                                             "Content-Type": "application/json; charset=utf-8"})[0], 200)

    def test_a_body_that_never_arrives_is_refused(self) -> None:
        before = self.files()
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.putrequest("POST", "/api/v1/goals")
            for name, value in (("Origin", f"http://127.0.0.1:{self.port}"), ("Content-Type", "application/json"),
                                ("X-Beyin-Web", "1"), ("Content-Length", "64")):
                connection.putheader(name, value)
            connection.endheaders(b'{"title": "Half')
            response = connection.getresponse()
            self.assertEqual((response.status, json.loads(response.read())["error"]["code"]), (400, "bad_request"))
        finally:
            connection.close()
        self.assertEqual(self.files(), before)

    def test_only_post_reaches_a_write_route(self) -> None:
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assert_refused(405, "method_not_allowed", f"/goals/{self.rid}/steps/0",
                                    {"done": True, "text": "Birinci kitap"}, method=method)
        for path in ("/pulse", "/goals/", f"/goals/{self.rid}", f"/goals/{self.rid}/steps/-1", "/records/" + self.rid):
            with self.subTest(path=path):
                self.assert_refused(405, "method_not_allowed", path, {})


class ReadOnlyGoalTests(GoalServerCase):
    read_only = True

    def test_goals_response(self) -> None:
        self.assertIs(self.goals()["writable"], False)

    def test_every_write_is_refused(self) -> None:
        for path, body in (("/goals", {"title": "Hedef", "horizon": "year"}), ("/habits", {"title": "Spor"}),
                           (f"/goals/{self.rid}/steps/1", {"done": True, "text": "İkinci kitap"}),
                           (f"/habits/{self.habit}/days/2026-01-10", {"done": True}),
                           (f"/goals/{self.rid}/delete", {"title": "12 kitap okumak"}),
                           (f"/habits/{self.habit}/delete", {"title": "Spor yapmak"})):
            with self.subTest(path=path):
                self.assert_refused(403, "read_only", path, body)



class TokenGoalTests(GoalServerCase):
    token = "test_session_secret"

    def test_goals_response(self) -> None:
        self.assertEqual(self.call("/goals", method="GET")[0], 401)
        self.assertEqual(self.call("/goals", method="GET", headers={"Cookie": "bw_session=" + self.token})[0], 200)

    def test_write_needs_the_session_cookie(self) -> None:
        body = {"title": "Hedef", "horizon": "year"}
        self.assert_refused(401, "unauthorized", "/goals", body)
        self.assert_refused(401, "unauthorized", "/goals?t=" + self.token, body)
        self.assert_refused(401, "unauthorized", "/goals", body, headers={"Cookie": "bw_session=wrong"})
        self.assertEqual(self.call("/goals", body, headers={"Cookie": "bw_session=" + self.token})[0], 200)



if __name__ == "__main__":
    unittest.main()
