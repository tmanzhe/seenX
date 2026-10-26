"""FTS5 retrieval, source/index consistency, and additive migration checks."""

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from seenx.catalog import Catalog, SCHEMA, SCHEMA_VERSION
from seenx.catalog_migrations import V2_STATEMENTS, V3_STATEMENTS
from seenx.catalog_ocr import persist_observations
from seenx.image_ocr import COORDINATE_SPACE


class CatalogSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.library = self.root / "library"
        self.source = self.root / "input.image"
        self.source.write_bytes(b"placeholder-A")
        self.catalog = Catalog(self.library)
        self.addCleanup(self.catalog.connection.close)
        self.imported = self.import_source(self.source)
        self.revision = self.imported["revision_id"]

    def import_source(self, path):
        with patch("seenx.catalog.Image.open") as opened, patch("seenx.catalog.ImageOps.exif_transpose") as oriented:
            opened.return_value.__enter__.return_value.format = "PNG"
            opened.return_value.__enter__.return_value.getexif.return_value = {274: 1}
            oriented.return_value.size = (100, 200)
            return self.catalog.import_image(path)

    def add_ocr(self, text="Continue to checkout"):
        return persist_observations(self.catalog, self.revision, {
            "configuration": {"engine": "test"}, "width": 100, "height": 200,
            "coordinate_space": COORDINATE_SPACE,
            "observations": [{"text": text, "confidence": 0.9,
                "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}}],
        })["observations"][0]

    def assert_index_consistent(self):
        self.catalog.connection.execute("INSERT INTO catalog_fts(catalog_fts, rank) VALUES ('integrity-check', 1)")
        self.catalog.connection.commit()

    def test_note_search_survives_restart_and_points_to_exact_annotation(self):
        saved = self.catalog.add_note(self.revision, "Keep this spacing", region=[0.1, 0.2, 0.3, 0.1])
        with Catalog(self.library) as reopened:
            results = reopened.search("keep this spacing")
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["annotation_id"], saved["annotation_id"])
        self.assertEqual(result["asset_id"], self.imported["asset_id"])
        self.assertEqual(result["revision_id"], self.revision)
        self.assertEqual(result["matched_field"], "note")
        self.assertEqual(result["target"]["x"], 0.1)
        self.assertEqual(result["provenance"], {"origin": "user", "confirmation": "confirmed"})
        self.assertIn("spacing", result["excerpt"].casefold())
        self.assertEqual(result["score_direction"], "lower_is_better")
        self.assert_index_consistent()

    def test_selected_text_and_ocr_keep_separate_evidence_and_provenance(self):
        observation = self.add_ocr()
        saved = self.catalog.add_note(self.revision, "This button", observation_id=observation["id"])
        results = self.catalog.search("continue to checkout")
        self.assertEqual({result["matched_field"] for result in results}, {"selected_text", "ocr"})
        self.assertTrue(all(result["observation_id"] == observation["id"] for result in results))
        self.assertTrue(all(result["provenance"]["confirmation"] == "unverified" for result in results))
        self.assertEqual(next(result for result in results if result["matched_field"] == "selected_text")["annotation_id"], saved["annotation_id"])

    def test_edits_remove_old_terms_and_deletion_removes_all_annotation_hits(self):
        note = self.catalog.add_note(self.revision, "Original wording", "Selected phrase")
        self.assertEqual(len(self.catalog.search("original wording")), 1)
        self.catalog.edit_note(note["annotation_id"], note="Replacement wording")
        self.assertEqual(self.catalog.search("original wording"), [])
        self.assertEqual(len(self.catalog.search("replacement wording")), 1)
        self.assertEqual(len(self.catalog.search("selected phrase")), 1)
        self.catalog.edit_note(note["annotation_id"], selected_text="New quotation")
        self.assertEqual(self.catalog.search("selected phrase"), [])
        self.assertEqual(len(self.catalog.search("new quotation")), 1)
        self.catalog.delete_note(note["annotation_id"])
        self.assertEqual(self.catalog.search("replacement wording"), [])
        self.assertEqual(self.catalog.search("new quotation"), [])
        self.assert_index_consistent()

    def test_corrected_selection_does_not_rewrite_ocr_evidence(self):
        observation = self.add_ocr("Model spelling")
        note = self.catalog.add_note(self.revision, observation_id=observation["id"])
        self.catalog.edit_note(note["annotation_id"], selected_text="Corrected spelling")
        old = self.catalog.search("model spelling")
        new = self.catalog.search("corrected spelling")
        self.assertEqual([result["matched_field"] for result in old], ["ocr"])
        self.assertEqual(new[0]["provenance"], {"origin": "user", "confirmation": "confirmed"})
        self.assertIsNone(new[0]["observation_id"])

    def test_removal_clears_ocr_and_note_hits_without_affecting_other_assets(self):
        self.add_ocr("Shared evidence")
        self.catalog.add_note(self.revision, "Shared evidence")
        other_source = self.root / "other.image"
        other_source.write_bytes(b"placeholder-B")
        other = self.import_source(other_source)
        self.catalog.add_note(other["revision_id"], "Shared evidence")
        self.catalog.remove_memory(self.imported["asset_id"])
        results = self.catalog.search("shared evidence")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["asset_id"], other["asset_id"])
        self.assert_index_consistent()

    def test_failed_index_update_rolls_back_the_source_edit_too(self):
        note = self.catalog.add_note(self.revision, "Original text")
        self.catalog.connection.execute("""CREATE TRIGGER fail_new_document BEFORE INSERT ON search_documents
            WHEN NEW.content = 'Replacement text' BEGIN SELECT RAISE(ABORT, 'injected indexing failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.catalog.edit_note(note["annotation_id"], note="Replacement text")
        self.assertEqual(len(self.catalog.search("original text")), 1)
        self.assertEqual(self.catalog.search("replacement text"), [])
        self.assertEqual(self.catalog.get_memory(self.imported["asset_id"])["annotations"][0]["note"], "Original text")
        self.assert_index_consistent()

    def test_phrase_all_terms_unicode_and_token_boundaries(self):
        self.catalog.add_note(self.revision, "Keep this spacing in Montréal café; connection-refused; testing")
        self.assertEqual(self.catalog.search("keep spacing"), [])
        self.assertEqual(len(self.catalog.search("spacing keep", match="all")), 1)
        self.assertEqual(len(self.catalog.search("MONTREAL CAFE")), 1)
        self.assertEqual(len(self.catalog.search("connection refused")), 1)
        self.assertEqual(self.catalog.search("test"), [])
        self.assertEqual(self.catalog.search("spacing*extra"), [])

    def test_operator_characters_are_literal_not_query_language(self):
        self.catalog.add_note(self.revision, "Cats", "Dogs")
        for query in ('cats OR dogs', 'cats" OR "dogs', "x'; DROP TABLE annotations; --"):
            with self.subTest(query=query):
                self.assertEqual(self.catalog.search(query), [])
        self.assertEqual(len(self.catalog.search("cats")), 1)

    def test_history_is_searchable_with_explicit_current_and_id_filters(self):
        self.catalog.add_note(self.revision, "Historic thought")
        self.source.write_bytes(b"changed image bytes")
        current = self.import_source(self.source)
        result = self.catalog.search("historic thought")[0]
        self.assertFalse(result["is_current_revision"])
        self.assertEqual(self.catalog.search("historic thought", current_only=True), [])
        self.assertEqual(self.catalog.search("historic thought", revision_id=current["revision_id"]), [])
        self.assertEqual(len(self.catalog.search("historic thought", revision_id=self.revision)), 1)
        self.assertEqual(self.catalog.search("historic thought", asset_id="other"), [])

    def test_rebuild_preserves_sources_results_and_stable_ids(self):
        self.catalog.add_note(self.revision, "Keep this spacing", "Selected text")
        self.add_ocr()
        before = self.catalog.search("spacing")
        self.assertEqual(self.catalog.rebuild_search(), 3)
        self.assertEqual(self.catalog.search("spacing"), before)
        self.assertEqual(self.catalog.rebuild_search(), 3)
        self.assert_index_consistent()

    def test_orphaned_derived_document_cannot_be_returned_as_evidence(self):
        with self.catalog.connection:
            self.catalog.connection.execute("""INSERT INTO search_documents(kind, source_id, revision_id, content)
                VALUES ('note', 'missing-annotation', ?, 'Ghost evidence')""", (self.revision,))
        self.assertEqual(self.catalog.search("ghost evidence"), [])
        self.assertEqual(self.catalog.rebuild_search(), 0)

    def test_bounded_inputs_and_normal_no_match(self):
        self.catalog.add_note(self.revision, "Keep this spacing")
        self.catalog.add_note(self.revision, "Keep this spacing too")
        self.assertEqual(len(self.catalog.search("spacing", limit=1)), 1)
        self.assertEqual(self.catalog.search("submarine"), [])
        for query, options in ((" ", {}), ("!!!", {}), ("x" * 513, {}),
                               ("word " * 33, {"match": "all"}), ("x", {"limit": 0}),
                               ("x", {"limit": 101}), ("x", {"match": "raw"})):
            with self.subTest(query=query, options=options), self.assertRaises(ValueError):
                self.catalog.search(query, **options)


class SearchMigrationTests(unittest.TestCase):
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
            for statement in V2_STATEMENTS:
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 2")
            connection.execute("INSERT INTO assets VALUES ('asset', '/missing.png', NULL, 'old-time')")
            connection.execute("INSERT INTO revisions VALUES ('revision', 'asset', ?, 100, 200, 'PNG', 1, ?, 'old-time')", (digest, len(payload)))
            connection.execute("UPDATE assets SET current_revision_id = 'revision'")
            connection.execute("INSERT INTO regions VALUES ('region', 'revision', 'whole', 0, 0, 1, 1)")
            connection.execute("""INSERT INTO annotations(id, region_id, note, selected_text, origin, confirmation, created_at, updated_at)
                VALUES ('note', 'region', 'Legacy thought', 'Selected quotation', 'user', 'confirmed', 'old-time', 'old-time')""")
            connection.execute("INSERT INTO ocr_runs VALUES ('run', 'revision', 'config', '{\"engine\":\"test\"}', 'old-time')")
            connection.execute("INSERT INTO text_observations VALUES ('observation', 'run', 0, 'Recognized evidence', 0.9, 0.1, 0.2, 0.3, 0.1, 'ocr', 'unverified')")
            connection.commit()

    def test_existing_version_two_sources_are_backfilled_without_id_changes(self):
        with Catalog(self.root) as catalog:
            self.assertEqual(catalog.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(catalog.search("legacy thought")[0]["annotation_id"], "note")
            self.assertEqual(catalog.search("selected quotation")[0]["matched_field"], "selected_text")
            self.assertEqual(catalog.search("recognized evidence")[0]["observation_id"], "observation")
            self.assertEqual(catalog.get_memory("asset")["annotations"][0]["created_at"], "old-time")
        with Catalog(self.root) as catalog:
            self.assertEqual(len(catalog.search("legacy thought")), 1)

    def test_failed_fts_migration_rolls_back_and_can_be_retried(self):
        with patch("seenx.catalog_migrations.V3_STATEMENTS", (*V3_STATEMENTS[:5], "INVALID SQL")):
            with self.assertRaises(sqlite3.OperationalError):
                Catalog(self.root)
        with closing(sqlite3.connect(self.root / "catalog.sqlite3")) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'search_documents'").fetchone())
            self.assertEqual(connection.execute("SELECT note FROM annotations").fetchone()[0], "Legacy thought")
        with Catalog(self.root) as catalog:
            self.assertEqual(len(catalog.search("legacy thought")), 1)

    def test_all_pending_upgrades_roll_back_together_from_version_one(self):
        old = self.root / "version-one"
        old.mkdir()
        with closing(sqlite3.connect(old / "catalog.sqlite3")) as connection:
            connection.executescript(SCHEMA)
        with patch("seenx.catalog_migrations.V3_STATEMENTS", (*V3_STATEMENTS[:3], "INVALID SQL")):
            with self.assertRaises(sqlite3.OperationalError):
                Catalog(old)
        with closing(sqlite3.connect(old / "catalog.sqlite3")) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertNotIn("selected_text_origin", [row[1] for row in connection.execute("PRAGMA table_info(annotations)")])
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'ocr_runs'").fetchone())
        with Catalog(old) as catalog:
            self.assertEqual(catalog.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
