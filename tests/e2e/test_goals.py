from __future__ import annotations

from typing import Any

from beyin_web.domain import goals
from beyin_web.vault.records import make_rid
from tests.e2e.support import PageTestCase
from tests.support import GOALS, add_goals


class GoalsCase(PageTestCase):
    beyin = False

    def setUp(self) -> None:
        super().setUp()
        add_goals(self.vault)
        self.folder = self.vault / "goals"

    def ready(self) -> None:
        self.wait_for('.goals-page[aria-busy="false"]')

    def show(self, hash: str = "#/hedefler") -> None:
        self.open(hash)
        self.ready()

    def read(self, name: str) -> str:
        return (self.folder / name).read_text(encoding="utf-8")

    def goal(self, name: str) -> Any:
        return self.wait_for(f'.goals-goal[data-rid="{make_rid("goals/" + name)}"]')

    def day(self, name: str, day: str) -> Any:
        return self.wait_for(f'#goals-habits tr[data-rid="{make_rid("goals/" + name)}"] [data-day="{day}"]')


class GoalsTests(GoalsCase):
    def test_sections_show_the_vault(self) -> None:
        self.show()
        self.assertEqual(self.text("#main h1"), self.messages["page.goals.title"])
        self.assertEqual([item.text for item in self.all("#goals-long .goals-goal-title strong")],
                         ["Anlamlı bir iş üretmek", "Etiketsiz hedef"])
        self.assertEqual([item.text for item in self.all("#goals-year .goals-goal-title strong")],
                         ["12 kitap okumak", "Aylık bir yazı paylaşmak"])
        self.assertIn("2025–2030 · Üretim", self.goal("is.md").text)
        self.assertIn("1 / 3", self.goal("kitap.md").text)
        self.assertIn(self.messages["goals.noSteps"], self.goal("yazi.md").text)
        self.assertIn("Derinleş ve inşa et", self.text("#goals-theme"))
        self.assertIn("2026", self.text(".goals-theme-period"))
        self.assertEqual([item.get_attribute("data-area") for item in self.all("#goals-areas li")], ["öğrenme", "Üretim"])
        self.assertIn("1 / 2", self.text('#goals-areas li[data-area="Üretim"]'))
        self.assertEqual(self.text(".goals-month-label"), "Ocak 2026")
        self.assertEqual(len(self.all("#goals-habits thead th")), 32)
        self.assertEqual([button.get_attribute("data-day") for button in self.all('.goals-day[aria-pressed="true"]')],
                         ["2026-01-03", "2026-01-09", "2026-01-12"])
        self.assertTrue(self.day("spor.md", "2026-01-12").is_enabled())
        self.assertFalse(self.day("spor.md", "2026-01-13").is_enabled())
        self.assertNotIn("GIZLI-HEDEF", self.text("#main"))
        self.assertEqual(self.wait_for('#navigation [data-page="goals"]').get_attribute("aria-current"), "page")
        self.assert_clean_text()
        self.assert_no_overflow()

    def test_step_is_ticked_in_the_note(self) -> None:
        self.show()
        row = self.goal("kitap.md")
        row.find_element("css selector", "summary").click()
        boxes = row.find_elements("css selector", ".goals-step input")
        self.assertEqual([box.is_selected() for box in boxes], [True, False, False])
        boxes[1].click()
        self.wait_until(lambda driver: "2 / 3" in self.goal("kitap.md").text)
        self.assertEqual(self.read("kitap.md"), GOALS["kitap.md"].replace("- [ ] İkinci kitap", "- [x] İkinci kitap"))
        # The goal stays open after the page has redrawn itself from the vault.
        row = self.goal("kitap.md")
        self.assertTrue(row.get_attribute("open"))
        row.find_elements("css selector", ".goals-step input")[0].click()
        self.wait_until(lambda driver: "1 / 3" in self.goal("kitap.md").text)
        self.assertEqual(self.read("kitap.md"), GOALS["kitap.md"].replace("- [x] Birinci kitap", "- [ ] Birinci kitap")
                         .replace("- [ ] İkinci kitap", "- [x] İkinci kitap"))
        self.assertIn("1 / 3", self.text('#goals-areas li[data-area="öğrenme"]'))

    def test_goal_is_added_from_the_form(self) -> None:
        self.show()
        self.wait_for('[data-add="year"]').click()
        form = self.wait_for('#goals-year form[data-form="year"]')
        self.assertIn(self.messages["goals.field.areaHint"], form.text)
        self.assertEqual(self.driver.switch_to.active_element.get_attribute("name"), "title")
        form.find_element("css selector", '[type="submit"]').click()
        self.assertFalse((self.folder / "duzenli-spor.md").exists())
        form.find_element("name", "title").send_keys("Düzenli spor")
        form.find_element("name", "area").send_keys("Sağlık")
        form.find_element("name", "steps").send_keys("Haftada üç gün\n- Yüzme")
        form.find_element("css selector", '[type="submit"]').click()
        row = self.goal("duzenli-spor.md")
        self.assertIn("2026 · Sağlık", row.text)
        self.assertIn("0 / 2", row.text)
        self.assertEqual(self.read("duzenli-spor.md"),
                         goals.goal_document("Düzenli spor", "year", "2026", "Sağlık", ["Haftada üç gün", "Yüzme"]))
        self.assertEqual(self.all("#goals-year form"), [])
        self.assertIn("Sağlık", [item.get_attribute("data-area") for item in self.all("#goals-areas li")])
        self.wait_for('[data-add="long"]').click()
        self.wait_for('#goals-long form [type="button"]').click()
        self.assertEqual(self.all("#goals-long form"), [])
        self.assertEqual(len(list(self.folder.iterdir())), len(GOALS) + 1)

    def test_habits_are_ticked_and_added(self) -> None:
        self.show()
        self.day("spor.md", "2026-01-10").click()
        self.wait_until(lambda driver: self.day("spor.md", "2026-01-10").get_attribute("aria-pressed") == "true")
        self.assertEqual(self.read("spor.md"), GOALS["spor.md"] + "- 2026-01-10\n")
        self.assertIn(self.messages["goals.habits.count"].format(count=4), self.text("#goals-habits tbody"))
        self.day("spor.md", "2026-01-03").click()
        self.wait_until(lambda driver: self.day("spor.md", "2026-01-03").get_attribute("aria-pressed") == "false")
        self.assertEqual(self.read("spor.md"), GOALS["spor.md"].replace("- 2026-01-03\n", "") + "- 2026-01-10\n")
        self.wait_for('[data-add="habits"]').click()
        form = self.wait_for('#goals-habits form[data-form="habits"]')
        form.find_element("name", "title").send_keys("Erken uyumak")
        form.find_element("css selector", '[type="submit"]').click()
        self.wait_until(lambda driver: len(self.all("#goals-habits tbody tr")) == 3)
        self.assertEqual(self.read("erken-uyumak.md"), goals.habit_document("Erken uyumak"))

    def test_goal_and_habit_are_deleted_into_the_trash(self) -> None:
        self.show()
        rid = make_rid("goals/kitap.md")
        row = self.goal("kitap.md")
        row.find_element("css selector", "summary").click()
        self.wait_for(f'.goals-goal [data-delete="{rid}"]').click()
        box = self.wait_for(f'[data-confirm="{rid}"]')
        self.assertIn("12 kitap okumak", box.text)
        self.assertIn(".trash", box.text)
        # Changing one's mind costs nothing.
        box.find_elements("css selector", "button")[1].click()
        self.assertEqual(self.all("[data-confirm]"), [])
        self.assertTrue((self.folder / "kitap.md").is_file())
        self.wait_for(f'.goals-goal [data-delete="{rid}"]').click()
        self.wait_for(f'[data-confirm="{rid}"] .goals-danger').click()
        self.wait_until(lambda driver: not self.all(f'.goals-goal[data-rid="{rid}"]'))
        self.assertFalse((self.folder / "kitap.md").exists())
        self.assertEqual((self.vault / ".trash" / "kitap.md").read_text(encoding="utf-8"), GOALS["kitap.md"])
        self.assertEqual([item.get_attribute("data-area") for item in self.all("#goals-areas li")], ["Üretim"])
        habit = make_rid("goals/spor.md")
        button = self.wait_for(f'#goals-habits [data-delete="{habit}"]')
        self.assertEqual(button.get_attribute("aria-label"), self.messages["goals.deleteLabel"].format(title="Spor yapmak"))
        button.click()
        self.wait_for(f'#goals-habits [data-confirm="{habit}"] .goals-danger').click()
        self.wait_until(lambda driver: len(self.all("#goals-habits tbody tr")) == 1)
        self.assertEqual((self.vault / ".trash" / "spor.md").read_text(encoding="utf-8"), GOALS["spor.md"])
        # The delete control of a habit is a button one can see and hit, not a faint glyph.
        size = self.wait_for("#goals-habits .goals-delete").size
        self.assertGreaterEqual(min(size["width"], size["height"]), 28)
        self.assertEqual(self.all(".goals-message")[0].get_attribute("textContent"), "")
        self.assert_clean_text()

    def test_trash_restores_and_deletes_for_good(self) -> None:
        self.show()
        self.assertEqual([item for item in self.all("#goals-trash") if item.is_displayed()], [])
        rid = make_rid("goals/kitap.md")
        self.goal("kitap.md").find_element("css selector", "summary").click()
        self.wait_for(f'.goals-goal [data-delete="{rid}"]').click()
        self.wait_for(f'[data-confirm="{rid}"] .goals-danger').click()
        self.wait_until(lambda driver: len(self.all("#goals-trash li")) == 1)
        self.ready()
        habit = make_rid("goals/okuma.md")
        self.wait_for(f'#goals-habits [data-delete="{habit}"]').click()
        self.wait_for(f'#goals-habits [data-confirm="{habit}"] .goals-danger').click()
        self.wait_until(lambda driver: len(self.all("#goals-trash li")) == 2)
        rows = self.all("#goals-trash li")
        self.assertEqual([row.find_element("css selector", "strong").text for row in rows], ["12 kitap okumak", "Kitap okumak"])
        self.assertIn(self.messages["goals.trash.kind.goal"], rows[0].text)
        self.assertIn(self.messages["goals.trash.kind.habit"], rows[1].text)
        rows[0].find_element("css selector", "[data-restore]").click()
        self.wait_until(lambda driver: len(self.all("#goals-trash li")) == 1)
        self.assertEqual(self.read("kitap.md"), GOALS["kitap.md"])
        self.assertIn("1 / 3", self.goal("kitap.md").text)
        trashed = self.vault / ".trash" / "okuma.md"
        self.wait_for("#goals-trash [data-purge]").click()
        box = self.wait_for("#goals-trash [data-confirm]")
        self.assertIn(self.messages["goals.trash.confirm"].format(title="Kitap okumak"), box.text)
        box.find_elements("css selector", "button")[1].click()
        self.assertEqual(self.all("#goals-trash [data-confirm]"), [])
        self.assertTrue(trashed.is_file())
        self.wait_for("#goals-trash [data-purge]").click()
        self.wait_for("#goals-trash [data-confirm] .goals-danger").click()
        self.wait_until(lambda driver: not [item for item in self.all("#goals-trash") if item.is_displayed()])
        self.assertFalse(trashed.exists())
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), sorted(name for name in GOALS if name != "okuma.md"))
        self.assert_clean_text()
        self.assert_no_overflow()

    def test_unrelated_vault_changes_leave_the_page_alone(self) -> None:
        self.show()
        self.goal("kitap.md").find_element("css selector", "summary").click()
        mark = "document.querySelector('#goals-year .goals-goal').dataset.mark"
        self.driver.execute_script(mark + " = 'kept'")
        changed = "document.dispatchEvent(new CustomEvent('beyin:changed'))"
        (self.vault / "notes" / "atlas.md").write_text("# Atlas\n\nBaşka bir not değişti.\n", encoding="utf-8")
        self.driver.execute_script(changed)
        self.ready()
        self.wait_until(lambda driver: driver.execute_script(
            "return document.querySelector('.goals-page').getAttribute('aria-busy') === 'false' && " + mark) == "kept")
        # A change to a goal made elsewhere is shown, and the goal the reader opened stays open.
        (self.folder / "kitap.md").write_text(
            GOALS["kitap.md"].replace("- [ ] İkinci kitap", "- [x] İkinci kitap"), encoding="utf-8", newline="")
        self.driver.execute_script(changed)
        self.wait_until(lambda driver: "2 / 3" in self.goal("kitap.md").text)
        self.assertIsNone(self.driver.execute_script("return " + mark + " ?? null"))
        self.assertTrue(self.goal("kitap.md").get_attribute("open"))

    def test_months_live_in_the_address(self) -> None:
        self.show()
        self.assertFalse(self.wait_for('[data-month="next"]').is_enabled())
        self.wait_for('[data-month="previous"]').click()
        self.wait_until(lambda driver: self.text(".goals-month-label") == "Aralık 2025")
        self.assertEqual(self.hash(), "#/hedefler?ay=2025-12")
        self.assertEqual(self.all('.goals-day[aria-pressed="true"]'), [])
        self.assertTrue(self.day("spor.md", "2025-12-31").is_enabled())
        self.wait_for('[data-month="next"]').click()
        self.wait_until(lambda driver: self.text(".goals-month-label") == "Ocak 2026")
        self.assertEqual(self.hash(), "#/hedefler")
        self.show("#/hedefler?ay=2999-01")
        self.assertEqual(self.text(".goals-month-label"), "Ocak 2026")

    def test_an_open_form_survives_a_month_change(self) -> None:
        self.show()
        self.wait_for('[data-add="habits"]').click()
        self.wait_for('#goals-habits form [name="title"]').send_keys("Erken uyumak")
        self.wait_for('[data-add="long"]')
        self.wait_for('[data-month="previous"]').click()
        self.wait_until(lambda driver: self.text(".goals-month-label") == "Aralık 2025")
        self.ready()
        # The page was rendered anew; the form, its text and its buttons are still the reader's.
        field = self.wait_for('#goals-habits form [name="title"]')
        self.assertEqual(field.get_attribute("value"), "Erken uyumak")
        self.wait_for('#goals-habits form [type="submit"]').click()
        self.wait_until(lambda driver: len(self.all("#goals-habits tbody tr")) == 3)
        self.assertEqual(self.read("erken-uyumak.md"), goals.habit_document("Erken uyumak"))
        self.assertEqual(self.all("#goals-habits form"), [])
        self.wait_for('[data-add="year"]').click()
        self.wait_for('[data-month="next"]').click()
        self.wait_until(lambda driver: self.text(".goals-month-label") == "Ocak 2026")
        self.ready()
        self.wait_for('#goals-year form [type="button"]').click()
        self.assertEqual(self.all("#goals-year form"), [])
        self.assertTrue(self.wait_for('[data-add="year"]').is_displayed())

    def test_a_note_changed_elsewhere_is_not_overwritten(self) -> None:
        self.show()
        row = self.goal("kitap.md")
        row.find_element("css selector", "summary").click()
        changed = GOALS["kitap.md"].replace("İkinci kitap", "İkinci kitap (Obsidian'da düzeltildi)")
        (self.folder / "kitap.md").write_text(changed, encoding="utf-8", newline="")
        row.find_elements("css selector", ".goals-step input")[1].click()
        self.wait_until(lambda driver: self.text(".goals-message") == self.messages["goals.conflict"])
        self.assertEqual(self.read("kitap.md"), changed)
        self.wait_until(lambda driver: "Obsidian'da düzeltildi" in self.goal("kitap.md").text)
        self.assertIn("1 / 3", self.goal("kitap.md").text)
        # The refusal is the server's answer to a stale page, not a console error.
        self.driver.get_log("browser")

    def test_empty_vault_invites_the_first_goal(self) -> None:
        for path in self.folder.iterdir():
            path.unlink()
        self.show()
        for section in ("long", "year", "areas", "habits"):
            self.assertIn(self.messages[f"goals.{section}.emptyTitle"], self.text(f"#goals-{section}"))
        self.assertEqual([item for item in self.all("#goals-theme") if item.is_displayed()], [])
        self.assertEqual(len(self.all(".goals-add")), 3)
        self.assert_no_overflow()


class ReadOnlyGoalsTests(GoalsCase):
    read_only = True

    def test_nothing_can_be_changed(self) -> None:
        self.show()
        self.assertEqual(self.text(".goals-notice"), self.messages["goals.readOnly"])
        self.assertEqual(self.all(".goals-add, .goals-delete"), [])
        row = self.goal("kitap.md")
        row.find_element("css selector", "summary").click()
        self.assertEqual([box.is_enabled() for box in row.find_elements("css selector", ".goals-step input")], [False] * 3)
        self.assertEqual([button for button in self.all(".goals-day") if button.is_enabled()], [])
        self.assertEqual({name: self.read(name) for name in GOALS}, GOALS)

    def test_trash_is_shown_without_buttons(self) -> None:
        (self.vault / ".trash").mkdir()
        (self.vault / ".trash" / "eski.md").write_text('---\n{"kind": "goal"}\n---\n# Eski hedef\n', encoding="utf-8")
        self.show()
        self.assertIn("Eski hedef", self.text("#goals-trash"))
        self.assertEqual(self.all("#goals-trash button"), [])
