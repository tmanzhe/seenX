"""OCR persistence and migration checks require no native framework or image generation."""

from contextlib import closing
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from seenx.catalog import Catalog, SCHEMA, SCHEMA_VERSION
from seenx.catalog_migrations import V2_STATEMENTS
from seenx.catalog_ocr import persist_observations, recognize_revision
from seenx.image_ocr import COORDINATE_SPACE


class CatalogOcrTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "input.image"
        self.source.write_bytes(b"placeholder")
        self.catalog = Catalog(self.root / "library")
        self.addCleanup(self.catalog.connection.close)
        self.imported = self.import_placeholder(self.source)
        self.revision_id = self.imported["revision_id"]
        self.result = {"configuration": {"engine": "test", "revision": 1},
            "width": 100, "height": 200, "coordinate_space": COORDINATE_SPACE,
            "observations": [{"text": "Checkout", "confidence": 0.9,
                              "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}}]}

    def import_placeholder(self, path):
        with patch("seenx.catalog.Image.open") as opened, patch("seenx.catalog.ImageOps.exif_transpose") as oriented:
            opened.return_value.__enter__.return_value.format = "PNG"
            opened.return_value.__enter__.return_value.getexif.return_value = {274: 1}
            oriented.return_value.size = (100, 200)
            return self.catalog.import_image(path)

    def test_observations_and_quote_survive_restart_with_unverified_transcription(self):
        run = persist_observations(self.catalog, self.revision_id, self.result)
        observation = run["observations"][0]
        saved = self.catalog.add_note(self.revision_id, "Use this spacing", observation_id=observation["id"])
        with Catalog(self.root / "library") as reopened:
            memory = reopened.get_memory(self.imported["asset_id"])
        note = memory["annotations"][0]
        self.assertEqual(note["id"], saved["annotation_id"])
        self.assertEqual(note["selected_text"], "Checkout")
        self.assertEqual(note["quoted_observation_id"], observation["id"])
        self.assertEqual(note["selected_text_origin"], "ocr")
        self.assertEqual(note["selected_text_confirmation"], "unverified")
        self.assertEqual(note["pixel_bounds"], {"left": 10, "top": 40, "right": 40, "bottom": 60})
        self.assertEqual(memory["ocr_runs"][0]["observations"][0]["confirmation"], "unverified")
        self.assertTrue(any(link["predicate"] == "quotes" for link in memory["relationships"]))

    def test_same_configuration_reuses_ids_without_reexecuting_ocr(self):
        first = persist_observations(self.catalog, self.revision_id, self.result)
        again = persist_observations(self.catalog, self.revision_id, self.result)
        self.assertTrue(again["reused"])
        self.assertEqual(first["observations"][0]["id"], again["observations"][0]["id"])
        extractor = Mock(side_effect=AssertionError("OCR rerun"))
        cached = recognize_revision(self.catalog, self.revision_id,
                                    configuration=self.result["configuration"], extractor=extractor)
        extractor.assert_not_called()
        self.assertEqual(cached["id"], first["id"])

    def test_new_configuration_preserves_previous_observations_and_notes(self):
        first = persist_observations(self.catalog, self.revision_id, self.result)
        self.catalog.add_note(self.revision_id, "Keep this", observation_id=first["observations"][0]["id"])
        changed = deepcopy(self.result)
        changed["configuration"]["revision"] = 2
        changed["observations"][0]["text"] = "Different recognition"
        second = persist_observations(self.catalog, self.revision_id, changed)
        self.assertNotEqual(first["id"], second["id"])
        memory = self.catalog.get_memory(self.imported["asset_id"])
        self.assertEqual(len(memory["ocr_runs"]), 2)
        self.assertEqual(memory["annotations"][0]["selected_text"], "Checkout")

    def test_empty_success_is_saved_but_recognition_failure_is_not(self):
        empty = deepcopy(self.result)
        empty["observations"] = []
        run = persist_observations(self.catalog, self.revision_id, empty)
        self.assertEqual(run["observations"], [])
        with patch("seenx.catalog_ocr.Image.open"):
            with self.assertRaises(RuntimeError):
                recognize_revision(self.catalog, self.revision_id, {"engine": "test", "revision": 2},
                                   extractor=Mock(side_effect=RuntimeError("failed")))
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM ocr_runs").fetchone()[0], 1)

    def test_invalid_observations_are_not_partially_saved(self):
        for field, value in (("confidence", math.nan), ("text", "")):
            bad = deepcopy(self.result)
            bad["observations"].append(deepcopy(bad["observations"][0]))
            bad["observations"][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                persist_observations(self.catalog, self.revision_id, bad)
        for updates in ({"width": 200}, {"coordinate_space": "bottom-left"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                persist_observations(self.catalog, self.revision_id, {**self.result, **updates})
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM ocr_runs").fetchone()[0], 0)

    def test_mid_write_failure_rolls_back_the_run_and_all_observations(self):
        self.catalog.connection.execute("""CREATE TRIGGER fail_second_observation
            BEFORE INSERT ON text_observations WHEN NEW.position = 1
            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        result = deepcopy(self.result)
        result["observations"] *= 2
        with self.assertRaises(sqlite3.IntegrityError):
            persist_observations(self.catalog, self.revision_id, result)
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM ocr_runs").fetchone()[0], 0)
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM text_observations").fetchone()[0], 0)

    def test_quote_write_failure_does_not_leave_a_partial_annotation(self):
        observation = persist_observations(self.catalog, self.revision_id, self.result)["observations"][0]
        self.catalog.connection.execute("""CREATE TRIGGER fail_quote BEFORE INSERT ON annotation_quotes
            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalog.add_note(self.revision_id, "A note", observation_id=observation["id"])
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM regions").fetchone()[0], 0)
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM annotations").fetchone()[0], 0)

    def test_cached_ocr_still_requires_an_intact_snapshot(self):
        persist_observations(self.catalog, self.revision_id, self.result)
        self.catalog.object_path(self.imported["sha256"]).write_bytes(b"damaged snapshot")
        with self.assertRaisesRegex(OSError, "content-hash"):
            recognize_revision(self.catalog, self.revision_id, self.result["configuration"])

    def test_recognition_configuration_mismatch_is_not_saved(self):
        with patch("seenx.catalog_ocr.Image.open"):
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                recognize_revision(self.catalog, self.revision_id, {"engine": "test", "revision": 2},
                                   extractor=Mock(return_value=self.result))
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM ocr_runs").fetchone()[0], 0)

    def test_quote_cannot_cross_revision_boundaries_even_through_sql(self):
        first = persist_observations(self.catalog, self.revision_id, self.result)["observations"][0]
        self.source.write_bytes(b"changed placeholder")
        other = self.import_placeholder(self.source)
        second = persist_observations(self.catalog, other["revision_id"], self.result)["observations"][0]
        with self.assertRaises(LookupError):
            self.catalog.add_note(other["revision_id"], "Wrong version", observation_id=first["id"])
        note = self.catalog.add_note(self.revision_id, "Correct", observation_id=first["id"])
        with self.assertRaises(sqlite3.IntegrityError), self.catalog.connection:
            self.catalog.connection.execute("UPDATE annotation_quotes SET observation_id = ? WHERE annotation_id = ?",
                                            (second["id"], note["annotation_id"]))

    def test_note_edit_preserves_quote_and_text_correction_detaches_it(self):
        observation = persist_observations(self.catalog, self.revision_id, self.result)["observations"][0]
        note = self.catalog.add_note(self.revision_id, observation_id=observation["id"])
        self.catalog.edit_note(note["annotation_id"], note="A thought")
        self.assertEqual(self.catalog.get_memory(self.imported["asset_id"])["annotations"][0]["quoted_observation_id"], observation["id"])
        self.catalog.edit_note(note["annotation_id"], selected_text="Corrected transcription")
        memory = self.catalog.get_memory(self.imported["asset_id"])
        self.assertIsNone(memory["annotations"][0]["quoted_observation_id"])
        self.assertEqual(memory["annotations"][0]["selected_text_origin"], "user")
        self.assertEqual(memory["ocr_runs"][0]["observations"][0]["text"], "Checkout")

    def test_memory_removal_cascades_observations_and_quotes(self):
        observation = persist_observations(self.catalog, self.revision_id, self.result)["observations"][0]
        self.catalog.add_note(self.revision_id, observation_id=observation["id"])
        self.catalog.remove_memory(self.imported["asset_id"])
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM text_observations").fetchone()[0], 0)
        self.assertEqual(self.catalog.connection.execute("SELECT count(*) FROM annotation_quotes").fetchone()[0], 0)
        self.assertEqual(self.catalog.connection.execute("PRAGMA foreign_key_check").fetchall(), [])


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        payload = b"legacy snapshot"
        digest = hashlib.sha256(payload).hexdigest()
        (self.root / "objects").mkdir()
        (self.root / "objects" / digest).write_bytes(payload)
        with closing(sqlite3.connect(self.root / "catalog.sqlite3")) as connection:
            connection.executescript(SCHEMA)
            connection.execute("INSERT INTO assets VALUES ('asset', '/missing.png', NULL, 'old-time')")
            connection.execute("INSERT INTO revisions VALUES ('revision', 'asset', ?, 100, 200, 'PNG', 1, ?, 'old-time')", (digest, len(payload)))
            connection.execute("UPDATE assets SET current_revision_id = 'revision'")
            connection.execute("INSERT INTO regions VALUES ('region', 'revision', 'whole', 0, 0, 1, 1)")
            connection.execute("INSERT INTO annotations VALUES ('note', 'region', 'Legacy note', 'Quote', 'user', 'confirmed', 'old-time', 'old-time')")
            connection.commit()

    def test_version_one_migrates_without_changing_existing_notes_or_ids(self):
        with Catalog(self.root) as catalog:
            memory = catalog.get_memory("asset")
            self.assertEqual(memory["schema_version"], SCHEMA_VERSION)
            self.assertEqual(memory["annotations"][0]["id"], "note")
            self.assertEqual(memory["annotations"][0]["note"], "Legacy note")
            self.assertEqual(memory["annotations"][0]["selected_text_origin"], "user")
            self.assertEqual(memory["annotations"][0]["created_at"], "old-time")
            self.assertEqual(memory["ocr_runs"], [])
        with Catalog(self.root) as catalog:
            self.assertEqual(len(catalog.get_memory("asset")["annotations"]), 1)

    def test_failed_migration_rolls_back_schema_and_can_be_retried(self):
        with patch("seenx.catalog_migrations.V2_STATEMENTS", (*V2_STATEMENTS[:3], "INVALID SQL")):
            with self.assertRaises(sqlite3.OperationalError):
                Catalog(self.root)
        with closing(sqlite3.connect(self.root / "catalog.sqlite3")) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'ocr_runs'").fetchone())
            self.assertNotIn("selected_text_origin", [row[1] for row in connection.execute("PRAGMA table_info(annotations)")])
        with Catalog(self.root) as catalog:
            self.assertEqual(catalog.get_memory("asset")["annotations"][0]["note"], "Legacy note")


if __name__ == "__main__":
    unittest.main()
