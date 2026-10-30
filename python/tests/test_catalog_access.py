"""Durable grant storage and atomic upgrades, with no decoded image fixtures."""

from contextlib import closing, redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from seenx.catalog import Catalog, SCHEMA, SCHEMA_VERSION
from seenx.catalog_access import V4_STATEMENTS
from seenx.catalog_migrations import V2_STATEMENTS
from seenx.catalog_search_schema import V3_STATEMENTS
from seenx.engine_contract import Engine
from seenx.memory_cli import main


class CatalogAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        with closing(sqlite3.connect(self.root / "catalog.sqlite3")) as connection:
            connection.executescript(SCHEMA)
            for statement in (*V2_STATEMENTS, *V3_STATEMENTS):
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 3")
            connection.execute("INSERT INTO assets VALUES ('asset', '/missing.png', NULL, 'old-time')")
            connection.execute("INSERT INTO revisions VALUES ('revision', 'asset', ?, 10, 10, 'PNG', 1, 1, 'old-time')",
                               ("a" * 64,))
            connection.execute("UPDATE assets SET current_revision_id = 'revision'")
            connection.execute("INSERT INTO regions VALUES ('region', 'revision', 'whole', 0, 0, 1, 1)")
            connection.execute("""INSERT INTO annotations
                (id, region_id, note, selected_text, origin, confirmation, created_at, updated_at)
                VALUES ('note', 'region', 'Legacy thought', '', 'user', 'confirmed', 'old-time', 'old-time')""")
            connection.commit()

    def test_version_three_upgrade_preserves_ids_and_index_and_creates_no_grants(self):
        with Catalog(self.root) as catalog:
            self.assertEqual(catalog.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(catalog.search("legacy thought")[0]["annotation_id"], "note")
            self.assertEqual(catalog.search("legacy thought", principal_id="assistant"), [])
            self.assertFalse(catalog.access.allows("assistant", "asset"))
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM source_grants").fetchone()[0], 0)
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM collection_grants").fetchone()[0], 0)
            self.assertEqual(catalog.connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_failed_access_upgrade_rolls_back_schema_and_can_be_retried(self):
        with patch("seenx.catalog_migrations.V4_STATEMENTS", (*V4_STATEMENTS[:3], "INVALID SQL")):
            with self.assertRaises(sqlite3.OperationalError):
                Catalog(self.root)
        with closing(sqlite3.connect(self.root / "catalog.sqlite3")) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'collections'").fetchone())
            self.assertEqual(connection.execute("SELECT note FROM annotations").fetchone()[0], "Legacy thought")
        with Catalog(self.root) as catalog:
            self.assertEqual(catalog.search("legacy thought")[0]["annotation_id"], "note")

    def test_all_pending_migrations_roll_back_if_access_upgrade_fails(self):
        old = self.root / "version-one"
        old.mkdir()
        with closing(sqlite3.connect(old / "catalog.sqlite3")) as connection:
            connection.executescript(SCHEMA)
        with patch("seenx.catalog_migrations.V4_STATEMENTS", (*V4_STATEMENTS[:1], "INVALID SQL")):
            with self.assertRaises(sqlite3.OperationalError):
                Catalog(old)
        with closing(sqlite3.connect(old / "catalog.sqlite3")) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'ocr_runs'").fetchone())
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name = 'search_documents'").fetchone())
        with Catalog(old) as catalog:
            self.assertEqual(catalog.connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_grants_require_existing_targets_and_do_not_accept_invalid_principals(self):
        with Catalog(self.root) as catalog:
            for operation in (catalog.access.grant_source, catalog.access.grant_collection):
                with self.assertRaises(sqlite3.IntegrityError):
                    operation("assistant", "missing")
                for principal in ("", " ", "x" * 129, "\ud800", None):
                    with self.subTest(principal=repr(principal)), self.assertRaises(ValueError):
                        operation(principal, "asset")
            for kwargs in ({"principal_id": ""}, {"trusted_local": "true"},
                           {"trusted_local": True, "principal_id": "assistant"}):
                with self.assertRaises(ValueError):
                    Engine(catalog, **kwargs)

    def test_idempotent_grants_and_target_removal_cascade(self):
        with Catalog(self.root) as catalog:
            access = catalog.access
            collection = access.create_collection("Shared")
            for _ in range(2):
                access.add_member(collection, "asset")
                access.grant_source("assistant", "asset")
                access.grant_collection("assistant", collection)
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM source_grants").fetchone()[0], 1)
            self.assertTrue(access.allows("assistant", "asset"))
            catalog.remove_memory("asset")
            self.assertFalse(access.allows("assistant", "asset"))
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM source_grants").fetchone()[0], 0)
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM collection_assets").fetchone()[0], 0)
            with catalog.connection:
                catalog.connection.execute("DELETE FROM collections WHERE id = ?", (collection,))
            self.assertEqual(catalog.connection.execute("SELECT count(*) FROM collection_grants").fetchone()[0], 0)
            access.revoke_source("assistant", "asset")
            access.revoke_collection("assistant", collection)

    def cli(self, *arguments):
        output = StringIO()
        with patch.object(sys, "argv", ["seenx-memory", "--library", str(self.root), "--no-log", *arguments]):
            with redirect_stdout(output), redirect_stderr(StringIO()):
                main()
        return output.getvalue()

    def test_owner_cli_persists_explicit_grants_and_revocation(self):
        self.cli("grant", "assistant", "--source", "asset")
        with Catalog(self.root) as catalog:
            self.assertTrue(catalog.access.allows("assistant", "asset"))
        self.cli("revoke", "assistant", "--source", "asset")
        with Catalog(self.root) as catalog:
            self.assertFalse(catalog.access.allows("assistant", "asset"))


if __name__ == "__main__":
    unittest.main()
