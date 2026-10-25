"""Cache checks use temporary placeholder files and invented records."""

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from load_images import read_folder
from record_cache import get_record, open_cache, save_record


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "inputs"
        self.folder.mkdir()
        self.path = self.folder / "example.pdf"
        self.path.write_bytes(b"placeholder, not a real PDF")
        self.database = self.root / "cache.sqlite3"
        self.record = {"path": str(self.path), "kind": "pdf", "pages": [
            {"number": 1, "text": "Train booking"},
        ]}

    def test_records_survive_reopening_the_database(self):
        state = self.path.stat()
        with open_cache(self.database) as cache:
            save_record(cache, self.path, "test-reader", state, self.record)
        with open_cache(self.database) as cache:
            self.assertEqual(get_record(cache, self.path, "test-reader", state), self.record)
            self.assertIsNone(get_record(cache, self.path, "changed-reader", state))

    def test_changed_size_or_timestamp_is_a_cache_miss(self):
        with open_cache(self.database) as cache:
            state = self.path.stat()
            save_record(cache, self.path, "test-reader", state, self.record)
            os.utime(self.path, ns=(state.st_atime_ns, state.st_mtime_ns + 1_000_000))
            self.assertIsNone(get_record(cache, self.path, "test-reader", self.path.stat()))
            self.path.write_bytes(b"different length")
            os.utime(self.path, ns=(state.st_atime_ns, state.st_mtime_ns))
            self.assertIsNone(get_record(cache, self.path, "test-reader", self.path.stat()))

    def test_failed_ocr_is_not_saved(self):
        with open_cache(self.database) as cache:
            state = self.path.stat()
            save_record(cache, self.path, "ocr", state, {"ocr_error": "temporary failure"})
            self.assertIsNone(get_record(cache, self.path, "ocr", state))

    def test_disabled_cache_does_not_create_a_database(self):
        with open_cache(None) as cache:
            self.assertIsNone(cache)
            save_record(cache, self.path, "reader", self.path.stat(), self.record)
        self.assertFalse(self.database.exists())

    def test_folder_reuses_records_refreshes_and_ignores_removed_files(self):
        with open_cache(self.database) as cache, redirect_stdout(StringIO()):
            with patch("load_images.inspect_pdf", return_value=self.record) as reader:
                first = read_folder(self.folder, 10, False, cache)
                second = read_folder(self.folder, 10, False, cache)
                self.assertEqual(first, second)
                self.assertEqual(reader.call_count, 1)
                read_folder(self.folder, 10, False, cache, refresh=True)
                self.assertEqual(reader.call_count, 2)
                self.path.write_bytes(b"changed document")
                read_folder(self.folder, 10, False, cache)
                self.assertEqual(reader.call_count, 3)
                self.path.unlink()
                self.assertEqual(read_folder(self.folder, 10, False, cache), [])

    def test_file_changed_during_reading_is_not_cached(self):
        def change_file(path):
            path.write_bytes(b"changed while reading")
            return self.record

        with open_cache(self.database) as cache, redirect_stdout(StringIO()):
            with patch("load_images.inspect_pdf", side_effect=change_file):
                self.assertEqual(read_folder(self.folder, 10, False, cache), [])
            self.assertEqual(cache.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
