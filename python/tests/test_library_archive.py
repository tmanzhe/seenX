"""Portable-library behavior without native OCR or image decoding dependencies."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
from io import StringIO
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from seenx.catalog import Catalog, SCHEMA_VERSION
from seenx.catalog_access import AccessDeniedError
from seenx.catalog_ocr import persist_observations
from seenx.image_ocr import COORDINATE_SPACE
from seenx.library_archive import export_library, restore_library, verify_archive, verify_library
from seenx.memory_cli import main


class LibraryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / "library"
        self.originals = self.root / "originals"
        self.originals.mkdir()
        self.source = self.originals / "capture.image"
        self.catalog = Catalog(self.library)
        self.addCleanup(self.catalog.connection.close)
        self.source.write_bytes(b"first immutable image bytes")
        self.first = self.import_image()
        observations = persist_observations(self.catalog, self.first["revision_id"], {
            "configuration": {"engine": "fixture", "revision": 1}, "width": 100, "height": 200,
            "coordinate_space": COORDINATE_SPACE,
            "observations": [{"text": "Checkout", "confidence": 0.9,
                              "box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}}]})
        self.catalog.add_note(self.first["revision_id"], "Spacing thought",
                              observation_id=observations["observations"][0]["id"])
        self.source.write_bytes(b"second immutable image bytes")
        self.second = self.import_image()
        self.catalog.add_note(self.second["revision_id"], "Region thought", "Selection",
                              region=[0.1, 0.2, 0.4, 0.3])
        self.catalog.add_note(self.second["revision_id"], "Point thought", point=[0.5, 0.7])
        self.catalog.add_note(self.second["revision_id"], "Whole thought")
        self.collection = self.catalog.access.create_collection("Keep collection")
        self.catalog.access.add_member(self.collection, self.first["asset_id"])
        self.catalog.access.grant_source("source-assistant", self.first["asset_id"])
        self.catalog.access.grant_collection("collection-assistant", self.collection)
        self.archive = self.root / "backup.zip"
        self.target = self.root / "restored"

    def import_image(self):
        with patch("seenx.catalog.Image.open") as opened, patch("seenx.catalog.ImageOps.exif_transpose") as oriented:
            opened.return_value.__enter__.return_value.format = "PNG"
            opened.return_value.__enter__.return_value.getexif.return_value = {274: 1}
            oriented.return_value.size = (100, 200)
            return self.catalog.import_image(self.source)

    def rewrite(self, changes=None, omit=(), catalog_change=None, manifest_change=None):
        with ZipFile(self.archive) as archive:
            entries = {name: archive.read(name) for name in archive.namelist() if name not in omit}
        manifest = json.loads(entries["manifest.json"])
        if catalog_change:
            data = json.loads(entries["catalog.json"])
            catalog_change(data)
            entries["catalog.json"] = json.dumps(data).encode()
            manifest["files"]["catalog.json"] = hashlib.sha256(entries["catalog.json"]).hexdigest()
        if manifest_change:
            manifest_change(manifest)
        entries["manifest.json"] = json.dumps(manifest).encode()
        entries.update(changes or {})
        with ZipFile(self.archive, "w") as archive:
            for name, payload in entries.items():
                archive.writestr(name, payload)

    def rows(self, catalog, table):
        return sorted([dict(row) for row in catalog.connection.execute(f"SELECT * FROM {table}")],
                      key=lambda row: json.dumps(row, sort_keys=True))

    def test_complete_round_trip_preserves_bytes_catalog_and_grounding(self):
        # Neither orphaned objects nor unrelated private files belong in the archive.
        (self.library / "objects" / ("f" * 64)).write_bytes(b"removed private memory")
        (self.library / "private.txt").write_text("not library context")
        result = export_library(self.library, self.archive)
        manifest = result["manifest"]
        self.assertTrue(result["verified"])
        self.assertEqual(manifest["archive_format_version"], 1)
        self.assertEqual(manifest["catalog_schema_version"], SCHEMA_VERSION)
        self.assertEqual(manifest["mode"], "complete")
        self.assertIn("+00:00", manifest["created_at"])
        with ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest.json", *manifest["files"]})
            for name, digest in manifest["files"].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
        self.assertTrue(verify_archive(self.archive)["ok"])
        self.assertTrue(restore_library(self.archive, self.target)["ok"])
        self.assertTrue(verify_library(self.target)["ok"])
        with Catalog(self.target) as restored:
            for table in ("assets", "revisions", "regions", "annotations", "ocr_runs", "text_observations",
                          "annotation_quotes", "collections", "collection_assets"):
                self.assertEqual(self.rows(restored, table), self.rows(self.catalog, table), table)
            for imported in (self.first, self.second):
                revision = imported["revision_id"]
                self.assertEqual(restored.read_revision_bytes(revision, trusted_local=True),
                                 self.catalog.read_revision_bytes(revision, trusted_local=True))
                before = self.catalog.get_memory(imported["asset_id"], revision, trusted_local=True)
                after = restored.get_memory(imported["asset_id"], revision, trusted_local=True)
                before["revision"].pop("snapshot_path")
                after["revision"].pop("snapshot_path")
                self.assertEqual(before, after)
            self.assertEqual(restored.search("thought", trusted_local=True),
                             self.catalog.search("thought", trusted_local=True))

    def test_context_only_contains_no_images_and_searches_without_originals(self):
        export_library(self.library, self.archive, "context-only")
        with ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest.json", "catalog.json"})
            self.assertNotIn(b"immutable image bytes", archive.read("catalog.json"))
        report = restore_library(self.archive, self.target)
        self.assertTrue(report["restored"])
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["missing_files"]), 2)
        self.assertFalse((self.target / "objects").exists())
        with Catalog(self.target) as restored:
            self.assertTrue(restored.search("thought", trusted_local=True))
            self.assertEqual(self.rows(restored, "annotations"), self.rows(self.catalog, "annotations"))
            with self.assertRaises(FileNotFoundError):
                restored.read_revision_bytes(self.first["revision_id"], trusted_local=True)

    def test_checksum_tamper_is_reported_and_restore_leaves_no_target(self):
        export_library(self.library, self.archive)
        name = f"objects/{self.first['sha256']}"
        self.rewrite({name: b"tampered bytes"})
        report = verify_archive(self.archive)
        self.assertFalse(report["ok"])
        self.assertEqual(report["checksum_mismatches"], [name])
        with self.assertRaisesRegex(ValueError, "verification failed"):
            restore_library(self.archive, self.target)
        self.assertFalse(self.target.exists())

    def test_missing_archive_file_is_reported(self):
        export_library(self.library, self.archive)
        name = f"objects/{self.first['sha256']}"
        self.rewrite(omit=[name])
        self.assertEqual(verify_archive(self.archive)["missing_files"], [name])
        with self.assertRaises(ValueError):
            restore_library(self.archive, self.target)
        self.assertFalse(self.target.exists())

    def test_zip_payload_corruption_is_reported_as_a_checksum_mismatch(self):
        export_library(self.library, self.archive)
        name = f"objects/{self.first['sha256']}"
        with ZipFile(self.archive) as archive:
            member = archive.getinfo(name)
        raw = bytearray(self.archive.read_bytes())
        # Corrupt compressed image data while leaving the directory and manifest intact.
        offset = member.header_offset + 30 + len(member.filename.encode()) + len(member.extra)
        raw[offset + member.compress_size // 2] ^= 1
        self.archive.write_bytes(raw)
        self.assertEqual(verify_archive(self.archive)["checksum_mismatches"], [name])

    def test_catalog_checksum_tamper_is_reported_before_json_is_read(self):
        export_library(self.library, self.archive)
        self.rewrite({"catalog.json": b"invalid JSON"})
        self.assertEqual(verify_archive(self.archive)["checksum_mismatches"], ["catalog.json"])

    def test_restore_refuses_every_existing_target(self):
        export_library(self.library, self.archive)
        empty = self.root / "empty"
        empty.mkdir()
        existing_file = self.root / "file"
        existing_file.write_bytes(b"keep")
        link = self.root / "link"
        link.symlink_to(self.root / "absent")
        for target in (self.library, empty, existing_file, link):
            with self.subTest(target=target), self.assertRaises(FileExistsError):
                restore_library(self.archive, target)
        self.assertEqual(existing_file.read_bytes(), b"keep")
        self.assertEqual(list(empty.iterdir()), [])
        self.assertTrue(link.is_symlink())
        self.assertTrue(self.catalog.search("thought", principal_id="source-assistant"))

    def test_grants_are_excluded_and_restored_access_is_deny_by_default(self):
        for mode in ("complete", "context-only"):
            archive = self.root / f"{mode}.zip"
            target = self.root / f"{mode}-restored"
            export_library(self.library, archive, mode)
            with ZipFile(archive) as zipped:
                payload = zipped.read("catalog.json")
                for excluded in (b"source_grants", b"collection_grants", b"source-assistant", b"collection-assistant"):
                    self.assertNotIn(excluded, payload)
            restore_library(archive, target)
            with Catalog(target) as restored:
                self.assertEqual(self.rows(restored, "source_grants"), [])
                self.assertEqual(self.rows(restored, "collection_grants"), [])
                self.assertEqual(len(self.rows(restored, "collection_assets")), 1)
                for principal in ("source-assistant", "collection-assistant"):
                    self.assertEqual(restored.search("thought", principal_id=principal), [])
                    with self.assertRaises(AccessDeniedError):
                        restored.get_memory(self.first["asset_id"], principal_id=principal)

    def test_path_traversal_and_symlink_members_are_rejected(self):
        for name in ("../escape", "/absolute", "objects/../../escape", "objects\\..\\escape",
                     "C:/escape", "objects/./file", "objects//file"):
            with self.subTest(name=name):
                archive = self.root / "unsafe.zip"
                with ZipFile(archive, "w") as zipped:
                    zipped.writestr(name, b"escape")
                with self.assertRaisesRegex(ValueError, "Unsafe archive member"):
                    restore_library(archive, self.target)
                self.assertFalse(self.target.exists())
        with ZipFile(self.archive, "w") as zipped:
            member = ZipInfo("catalog.json")
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            zipped.writestr(member, b"/outside")
        with self.assertRaisesRegex(ValueError, "symlink"):
            verify_archive(self.archive)
        self.assertFalse((self.root / "escape").exists())

    def test_verify_reports_missing_and_hash_relinks_with_renamed_originals(self):
        export_library(self.library, self.archive, "context-only")
        # The old revision is absent; source_path alone cannot recover it.
        unresolved = verify_archive(self.archive)
        self.assertEqual(len(unresolved["missing_files"]), 2)
        partial = verify_archive(self.archive, self.originals)
        self.assertFalse(partial["ok"])
        self.assertEqual(partial["missing_files"], [f"objects/{self.first['sha256']}"])
        self.assertEqual(partial["relinked_files"], [
            {"file": f"objects/{self.second['sha256']}", "original_path": str(self.source)}])
        nested = self.originals / "nested"
        nested.mkdir()
        historical = nested / "renamed.image"
        historical.write_bytes(b"first immutable image bytes")
        self.assertTrue(verify_archive(self.archive, self.originals)["ok"])
        self.assertTrue(restore_library(self.archive, self.target, self.originals)["ok"])
        self.assertEqual(len(list((self.target / "objects").iterdir())), 2)
        historical.unlink()
        self.source.unlink()
        self.assertTrue(verify_library(self.target)["ok"])  # Relinks are managed copies.

    def test_verify_library_reports_missing_corruption_and_possible_relinks_without_writing(self):
        export_library(self.library, self.archive)
        restore_library(self.archive, self.target)
        first = self.target / "objects" / self.first["sha256"]
        second = self.target / "objects" / self.second["sha256"]
        first.write_bytes(b"bad")
        second.unlink()
        report = verify_library(self.target, self.originals)
        self.assertFalse(report["ok"])
        self.assertEqual(report["checksum_mismatches"], [f"objects/{self.first['sha256']}"])
        self.assertEqual(report["missing_files"], [])
        self.assertEqual(len(report["relinked_files"]), 1)
        self.assertFalse(second.exists())

    def test_external_symlink_originals_are_not_relinked(self):
        export_library(self.library, self.archive, "context-only")
        elsewhere = self.root / "outside.image"
        self.source.rename(elsewhere)
        self.source.symlink_to(elsewhere)
        self.assertEqual(verify_archive(self.archive, self.originals)["relinked_files"], [])

    def test_unsupported_versions_invalid_relationships_and_duplicate_ids_are_rejected(self):
        export_library(self.library, self.archive)
        original = self.archive.read_bytes()
        mutations = [
            ({"manifest_change": lambda m: m.update(archive_format_version=99)}, ValueError),
            ({"manifest_change": lambda m: m.update(catalog_schema_version=99)}, ValueError),
            ({"catalog_change": lambda d: d["regions"][0].update(revision_id="missing")},
             (ValueError, sqlite3.IntegrityError)),
            ({"catalog_change": lambda d: d["assets"].append(deepcopy(d["assets"][0]))}, sqlite3.IntegrityError),
            ({"catalog_change": lambda d: d.update(source_grants=[])}, ValueError),
            ({"catalog_change": lambda d: d["revisions"][0].update(sha256="../bad")}, ValueError),
        ]
        for arguments, error in mutations:
            with self.subTest(arguments=arguments):
                self.archive.write_bytes(original)
                self.rewrite(**arguments)
                with self.assertRaises(error):
                    restore_library(self.archive, self.target)
                self.assertFalse(self.target.exists())

    def test_failed_export_does_not_publish_and_existing_backup_is_preserved(self):
        self.catalog.object_path(self.first["sha256"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            export_library(self.library, self.archive)
        self.assertFalse(self.archive.exists())
        self.archive.write_bytes(b"existing backup")
        with self.assertRaises(FileExistsError):
            export_library(self.library, self.archive)
        self.assertEqual(self.archive.read_bytes(), b"existing backup")

    def test_restore_write_failure_discards_staging_and_does_not_create_target(self):
        export_library(self.library, self.archive)
        before = set(self.root.iterdir())
        with patch("seenx.library_archive.Catalog._store_snapshot", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                restore_library(self.archive, self.target)
        self.assertFalse(self.target.exists())
        self.assertEqual(set(self.root.iterdir()), before)

    def test_restore_refuses_target_created_during_staging(self):
        export_library(self.library, self.archive)
        original_store = Catalog._store_snapshot

        def store_and_create_target(catalog, payload, digest):
            original_store(catalog, payload, digest)
            self.target.mkdir(exist_ok=True)
            (self.target / "keep.txt").write_text("other process")

        with patch("seenx.library_archive.Catalog._store_snapshot", new=store_and_create_target):
            with self.assertRaises(FileExistsError):
                restore_library(self.archive, self.target)
        self.assertEqual((self.target / "keep.txt").read_text(), "other process")
        self.assertEqual(len(list(self.target.iterdir())), 1)

    def test_export_uses_one_catalog_snapshot_when_a_wal_writer_edits_a_note(self):
        self.catalog.connection.execute("PRAGMA journal_mode = WAL")
        note = self.rows(self.catalog, "annotations")[0]
        connect = sqlite3.connect
        edited = False

        def connect_with_writer(*args, **kwargs):
            connection = connect(*args, **kwargs)
            if isinstance(args[0], str) and args[0].endswith("?mode=ro"):
                def trace(statement):
                    nonlocal edited
                    # The assets query has established a snapshot before later tables are read.
                    if not edited and statement.startswith("SELECT id, asset_id"):
                        edited = True
                        self.catalog.edit_note(note["id"], note="Concurrent edit")
                connection.set_trace_callback(trace)
            return connection

        with patch("seenx.library_archive.sqlite3.connect", side_effect=connect_with_writer):
            export_library(self.library, self.archive)
        self.assertTrue(edited)
        restore_library(self.archive, self.target)
        with Catalog(self.target) as restored:
            self.assertEqual(next(row for row in self.rows(restored, "annotations") if row["id"] == note["id"]), note)
        self.assertEqual(self.catalog.connection.execute("SELECT note FROM annotations WHERE id = ?", (note["id"],)).fetchone()[0],
                         "Concurrent edit")

    def cli(self, *args, exit_code=0):
        output = StringIO()
        with patch("sys.argv", ["seenx-memory", "--no-log", *map(str, args)]), redirect_stdout(output), redirect_stderr(StringIO()):
            if exit_code:
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, exit_code)
            else:
                main()
        return json.loads(output.getvalue()) if output.getvalue() else None

    def test_cli_export_restore_and_verify_do_not_create_default_catalogs(self):
        self.cli("--library", self.library, "export", self.archive, "--mode", "context-only")
        self.assertFalse(self.cli("verify", self.archive, exit_code=1)["ok"])
        report = self.cli("--library", self.target, "restore", self.archive, "--original-folder", self.originals)
        self.assertTrue(report["restored"])
        self.assertEqual(len(report["relinked_files"]), 1)
        self.assertFalse(self.cli("--library", self.target, "verify", exit_code=1)["ok"])
        absent = self.root / "absent-library"
        self.cli("--library", absent, "verify", exit_code=1)
        self.assertFalse(absent.exists())
        self.cli("--library", self.target, "restore", self.archive, exit_code=1)


if __name__ == "__main__":
    unittest.main()
