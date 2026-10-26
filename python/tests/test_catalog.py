"""Catalog tests use mocked decoding and placeholder bytes, not generated photos."""

from contextlib import closing
import hashlib
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from seenx.catalog import APPLICATION_ID, Catalog, target_geometry


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.library = self.root / "library"
        self.source = self.root / "source.image"
        self.source.write_bytes(b"revision-A")
        opener = patch("seenx.catalog.Image.open")
        self.image_open = opener.start()
        self.addCleanup(opener.stop)
        image = self.image_open.return_value.__enter__.return_value
        image.format = "PNG"
        image.getexif.return_value = {274: 1}
        orientation = patch("seenx.catalog.ImageOps.exif_transpose")
        self.oriented = orientation.start()
        self.addCleanup(orientation.stop)
        self.oriented.return_value.size = (100, 200)

    def test_restart_recovers_revision_region_note_and_relationships(self):
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            note = catalog.add_note(imported["revision_id"], "Keep the spacing", "Checkout",
                                    region=[0.1, 0.2, 0.3, 0.4])
        with Catalog(self.library) as catalog:
            memory = catalog.get_memory(imported["asset_id"])
            annotation = memory["annotations"][0]
            self.assertEqual(annotation["id"], note["annotation_id"])
            self.assertEqual(annotation["note"], "Keep the spacing")
            self.assertEqual(annotation["selected_text"], "Checkout")
            self.assertEqual(annotation["pixel_bounds"], {"left": 10, "top": 40, "right": 40, "bottom": 120})
            self.assertEqual({link["predicate"] for link in memory["relationships"]},
                             {"revision_of", "part_of", "refers_to"})
            self.assertEqual(memory["revision"]["sha256"], hashlib.sha256(b"revision-A").hexdigest())
            self.assertTrue(memory["revision"]["snapshot_verified"])
            self.assertEqual(catalog.list_memories()[0]["annotation_count"], 1)
        self.assertEqual(self.source.read_bytes(), b"revision-A")

    def test_identical_import_is_idempotent_and_changed_source_gets_a_new_revision(self):
        with Catalog(self.library) as catalog:
            first = catalog.import_image(self.source)
            catalog.add_note(first["revision_id"], "Old image note")
            again = catalog.import_image(self.source)
            self.assertEqual(first["revision_id"], again["revision_id"])
            self.assertTrue(again["reused_revision"])
            self.source.write_bytes(b"revision-B")
            changed = catalog.import_image(self.source)
            self.assertEqual(first["asset_id"], changed["asset_id"])
            self.assertNotEqual(first["revision_id"], changed["revision_id"])
            current = catalog.get_memory(first["asset_id"])
            self.assertEqual(current["annotations"], [])
            self.assertEqual([item["id"] for item in current["revisions"]],
                             [first["revision_id"], changed["revision_id"]])
            self.assertEqual(current["revisions"][0]["annotation_count"], 1)
            old = catalog.get_memory(first["asset_id"], first["revision_id"])
            self.assertEqual(old["annotations"][0]["note"], "Old image note")
            self.assertEqual(Path(old["revision"]["snapshot_path"]).read_bytes(), b"revision-A")
            self.source.write_bytes(b"revision-A")
            reverted = catalog.import_image(self.source)
            self.assertEqual(reverted["revision_id"], first["revision_id"])
            self.assertEqual(catalog.list_memories()[0]["revision_count"], 2)

    def test_missing_original_does_not_break_saved_evidence(self):
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            self.source.unlink()
            memory = catalog.get_memory(imported["asset_id"])
            self.assertTrue(memory["source_missing"])
            self.assertTrue(memory["revision"]["snapshot_verified"])

    def test_changed_or_missing_snapshot_is_detected_without_deleting_notes(self):
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            catalog.add_note(imported["revision_id"], "Preserve this")
            snapshot = catalog.object_path(imported["sha256"])
            snapshot.write_bytes(b"corrupt")
            with self.assertRaisesRegex(OSError, "content-hash"):
                catalog.get_memory(imported["asset_id"])
            with self.assertRaisesRegex(OSError, "content-hash"):
                catalog.import_image(self.source)
            snapshot.unlink()
            with self.assertRaises(FileNotFoundError):
                catalog.get_memory(imported["asset_id"])
            catalog.import_image(self.source)
            self.assertEqual(catalog.get_memory(imported["asset_id"])["annotations"][0]["note"], "Preserve this")

    def test_edit_and_repeatable_delete_preserve_other_records(self):
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            note = catalog.add_note(imported["revision_id"], "Before")
            catalog.edit_note(note["annotation_id"], note="After")
            annotation = catalog.get_memory(imported["asset_id"])["annotations"][0]
            self.assertEqual(annotation["note"], "After")
            self.assertEqual(annotation["target"]["kind"], "whole")
            with self.assertRaises(ValueError):
                catalog.edit_note(note["annotation_id"], note="")
            self.assertEqual(catalog.get_memory(imported["asset_id"])["annotations"][0]["note"], "After")
            self.assertTrue(catalog.delete_note(note["annotation_id"]))
            self.assertFalse(catalog.delete_note(note["annotation_id"]))
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM regions").fetchone()[0], 0)
            self.assertEqual(len(catalog.list_memories()), 1)

    def test_point_and_selected_text_only_annotations(self):
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            catalog.add_note(imported["revision_id"], selected_text="A quote", point=[1, 1])
            annotation = catalog.get_memory(imported["asset_id"])["annotations"][0]
            self.assertEqual(annotation["pixel_target"], {"x": 99, "y": 199})
            self.assertEqual(annotation["origin"], "user")
            with self.assertRaises(ValueError):
                catalog.add_note(imported["revision_id"], note=" \n ")
            with self.assertRaises(LookupError):
                catalog.add_note("missing", "Note")

    def test_note_and_target_rollback_together_on_write_failure(self):
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            catalog.connection.execute("""CREATE TRIGGER fail_annotation BEFORE INSERT ON annotations
                                      BEGIN SELECT RAISE(ABORT, 'injected write failure'); END""")
            with self.assertRaises(sqlite3.IntegrityError):
                catalog.add_note(imported["revision_id"], "Never partially saved")
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM regions").fetchone()[0], 0)
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM annotations").fetchone()[0], 0)

    def test_remove_cascades_and_keeps_shared_objects_and_sources(self):
        other = self.root / "other.image"
        other.write_bytes(self.source.read_bytes())
        with Catalog(self.library) as catalog:
            first = catalog.import_image(self.source)
            second = catalog.import_image(other)
            catalog.add_note(first["revision_id"], "Remove me")
            self.assertTrue(catalog.remove_memory(first["asset_id"]))
            self.assertFalse(catalog.remove_memory(first["asset_id"]))
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM annotations").fetchone()[0], 0)
            self.assertEqual(catalog.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertTrue(catalog.get_memory(second["asset_id"])["revision"]["snapshot_verified"])
        self.assertTrue(self.source.exists())
        self.assertTrue(other.exists())

    def test_revision_cannot_be_fetched_under_another_asset(self):
        other = self.root / "other.image"
        other.write_bytes(b"another image")
        with Catalog(self.library) as catalog:
            first = catalog.import_image(self.source)
            second = catalog.import_image(other)
            with self.assertRaises(LookupError):
                catalog.get_memory(first["asset_id"], second["revision_id"])

    def test_orientation_corrected_dimensions_and_source_orientation_are_recorded(self):
        self.image_open.return_value.__enter__.return_value.getexif.return_value = {274: 6}
        self.oriented.return_value.size = (200, 100)
        with Catalog(self.library) as catalog:
            imported = catalog.import_image(self.source)
            memory = catalog.get_memory(imported["asset_id"])
            self.assertEqual((memory["revision"]["width"], memory["revision"]["height"]), (200, 100))
            self.assertEqual(memory["revision"]["exif_orientation"], 6)

    def test_future_schema_is_rejected_without_downgrading(self):
        with Catalog(self.library) as catalog:
            self.assertEqual(catalog.connection.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
            catalog.connection.execute("PRAGMA user_version = 99")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            Catalog(self.library)
        with closing(sqlite3.connect(self.library / "catalog.sqlite3")) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_unrelated_database_is_rejected(self):
        self.library.mkdir()
        with closing(sqlite3.connect(self.library / "catalog.sqlite3")) as connection:
            connection.execute("CREATE TABLE unrelated(value TEXT)")
            connection.commit()
        with self.assertRaisesRegex(ValueError, "not an empty"):
            Catalog(self.library)

    def test_source_changing_during_import_does_not_create_catalog_records(self):
        original_read = Path.read_bytes

        def changing_read(path):
            payload = original_read(path)
            if path == self.source:
                path.write_bytes(b"changed during import with a different size")
            return payload

        with Catalog(self.library) as catalog, patch.object(Path, "read_bytes", changing_read):
            with self.assertRaisesRegex(OSError, "changed during import"):
                catalog.import_image(self.source)
            self.assertEqual(catalog.list_memories(), [])


class TargetTests(unittest.TestCase):
    def test_invalid_geometry_is_rejected(self):
        for region in ([0, 0, 0, 1], [0.9, 0, 0.2, 1], [-0.1, 0, 1, 1],
                       [0, 0, math.nan, 1], [0, 0, math.inf, 1], [0, 1]):
            with self.subTest(region=region), self.assertRaises(ValueError):
                target_geometry(region=region)
        with self.assertRaises(ValueError):
            target_geometry(point=[0, 2])
        with self.assertRaises(ValueError):
            target_geometry(region=[0, 0, 1, 1], point=[0, 0])


if __name__ == "__main__":
    unittest.main()
