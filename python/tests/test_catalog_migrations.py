"""Migration backups preserve the committed catalog before any schema changes."""

from contextlib import closing, redirect_stderr
from io import StringIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from seenx.catalog import APPLICATION_ID, Catalog, SCHEMA, SCHEMA_VERSION
from seenx.catalog_migrations import V2_STATEMENTS, V3_STATEMENTS, migrate_catalog


class CatalogBackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "catalog.sqlite3"

    def backups(self):
        return list(self.root.glob("catalog.sqlite3.bak-*"))

    def legacy_catalog(self, version=1):
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        connection.executescript(SCHEMA)
        for target, statements in ((2, V2_STATEMENTS), (3, V3_STATEMENTS)):
            if target <= version:
                for statement in statements:
                    connection.execute(statement)
        connection.execute(f"PRAGMA user_version = {version}")
        connection.execute("INSERT INTO assets VALUES ('asset', '/original.png', NULL, 'old-time')")
        connection.commit()
        return connection

    def test_backup_precedes_each_supported_migration_and_matches_original(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                original = self.legacy_catalog(version)
                expected = list(original.iterdump())
                stderr = StringIO()
                with redirect_stderr(stderr), Catalog(self.root) as catalog:
                    self.assertEqual(catalog.connection.execute("PRAGMA user_version").fetchone()[0],
                                     SCHEMA_VERSION)
                backup, = self.backups()
                self.assertRegex(backup.name, rf"^catalog\.sqlite3\.bak-v{version}-\d{{8}}-\d{{6}}$")
                self.assertIn(str(backup), stderr.getvalue())
                with closing(sqlite3.connect(backup)) as saved:
                    self.assertEqual(list(saved.iterdump()), expected)
                    self.assertEqual(saved.execute("PRAGMA user_version").fetchone()[0], version)
                    self.assertEqual(saved.execute("PRAGMA application_id").fetchone()[0], APPLICATION_ID)
                    self.assertEqual(saved.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                original.close()
                backup.unlink()
                self.path.unlink()

    def test_new_and_empty_catalogs_skip_backup(self):
        for state in ("new", "zero-byte", "empty-sqlite"):
            with self.subTest(state=state):
                if state == "zero-byte":
                    self.path.touch()
                elif state == "empty-sqlite":
                    with closing(sqlite3.connect(self.path)) as empty:
                        empty.execute("VACUUM")
                stderr = StringIO()
                with redirect_stderr(stderr), Catalog(self.root):
                    pass
                self.assertEqual(self.backups(), [])
                self.assertEqual(stderr.getvalue(), "")
                self.path.unlink()

    def test_up_to_date_catalog_skips_backup_including_direct_migration_call(self):
        with Catalog(self.root):
            pass
        stderr = StringIO()
        with redirect_stderr(stderr), Catalog(self.root) as catalog:
            migrate_catalog(catalog.connection)
        self.assertEqual(self.backups(), [])
        self.assertEqual(stderr.getvalue(), "")

    def test_backup_includes_committed_wal_contents(self):
        original = self.legacy_catalog()
        original.execute("PRAGMA journal_mode = WAL")
        original.execute("UPDATE assets SET source_path = '/committed-in-wal.png'")
        original.commit()
        with Catalog(self.root):
            pass
        backup, = self.backups()
        with closing(sqlite3.connect(backup)) as saved:
            self.assertEqual(saved.execute("SELECT source_path FROM assets").fetchone()[0],
                             "/committed-in-wal.png")

    def test_backup_failure_prevents_schema_changes(self):
        original = self.legacy_catalog()
        expected = list(original.iterdump())
        with patch("seenx.catalog_migrations.backup_catalog", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                Catalog(self.root)
        self.assertEqual(list(original.iterdump()), expected)


if __name__ == "__main__":
    unittest.main()
