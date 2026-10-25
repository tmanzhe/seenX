"""Diagnostics use temporary local files; no cloud or personal data is required."""

import json
from pathlib import Path
import os
import tempfile
import unittest

from seenx.observability import (CURRENT_RUN, configure_logging, count, event,
                           file_id, observed_search, run_context, stage)
from seenx.record_cache import get_record, open_cache, save_record


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / "events.jsonl"
        configure_logging(path=self.log, debug=True)
        self.addCleanup(configure_logging, enabled=False)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_structured_events_correlate_without_saving_private_fields(self):
        secret = "private-document-sentinel"
        with run_context("test") as run_id:
            event("example", query=secret, text=secret, path=secret,
                  record={"content": secret}, embedding=[123], error=secret, count=2)
            count("cache_hits", 2)
            with stage("example_stage"):
                pass
        events = self.events()
        self.assertTrue(all(item["run_id"] == run_id for item in events))
        self.assertTrue(all(item["schema_version"] == 1 and item["timestamp"] for item in events))
        self.assertNotIn(secret, self.log.read_text())
        self.assertEqual(events[-1]["counters"]["cache_hits"], 2)
        self.assertGreaterEqual(events[-1]["stages_ms"]["example_stage"], 0)

    def test_errors_are_recorded_and_context_is_cleaned_up(self):
        with self.assertRaises(ValueError):
            with run_context("test"):
                with stage("failed_stage"):
                    raise ValueError("private-error-sentinel")
        self.assertIsNone(CURRENT_RUN.get())
        events = self.events()
        self.assertEqual(events[-1]["event"], "run_failed")
        self.assertEqual(events[-1]["error_type"], "ValueError")
        self.assertTrue(any(item["event"] == "stage_finished" and item["outcome"] == "error"
                            for item in events))
        self.assertNotIn("private-error-sentinel", self.log.read_text())

    def test_nested_searches_reuse_a_run_and_file_ids_are_scoped(self):
        wrapped = observed_search(lambda: event("nested"))
        with run_context("outer"):
            first = file_id("/private/example.pdf")
            self.assertEqual(first, file_id("/private/example.pdf"))
            wrapped()
        with run_context("other"):
            self.assertNotEqual(first, file_id("/private/example.pdf"))
        self.assertEqual(sum(item["event"] == "run_started" for item in self.events()), 2)
        self.assertNotIn("/private/example.pdf", self.log.read_text())

    def test_logs_rotate_and_remain_valid_json(self):
        configure_logging(path=self.log, max_bytes=512, backups=2)
        for number in range(30):
            event("rotation_check", sequence=number)
        files = list(self.root.glob("events.jsonl*"))
        self.assertEqual(len(files), 3)
        for path in files:
            for line in path.read_text().splitlines():
                self.assertEqual(json.loads(line)["event"], "rotation_check")

    def test_disabled_logging_does_not_create_a_file(self):
        unused = self.root / "unused" / "events.jsonl"
        configure_logging(enabled=False, path=unused)
        with run_context("test"):
            event("not_saved")
        self.assertFalse(unused.exists())

    def test_cache_miss_reasons_and_recovery_are_observable(self):
        path = self.root / "placeholder.pdf"
        path.write_text("placeholder")
        record = {"kind": "pdf", "path": str(path), "pages": []}
        with run_context("test"), open_cache(self.root / "cache.sqlite3") as cache:
            state = path.stat()
            self.assertIsNone(get_record(cache, path, "v1", state))
            save_record(cache, path, "v1", state, record)
            self.assertEqual(get_record(cache, path, "v1", state), record)
            self.assertIsNone(get_record(cache, path, "v2", state))
            os.utime(path, ns=(state.st_atime_ns, state.st_mtime_ns + 1_000_000))
            changed = path.stat()
            self.assertIsNone(get_record(cache, path, "v1", changed))
            save_record(cache, path, "v1", changed, record)
            cache.execute("UPDATE records SET record = 'not-json'")
            cache.commit()
            self.assertIsNone(get_record(cache, path, "v1", changed))
        reasons = {item["reason"] for item in self.events() if item["event"] == "cache_miss"}
        self.assertEqual(reasons, {"not_cached", "reader_variant_missing", "source_changed", "invalid_record"})
        summary = self.events()[-1]
        self.assertEqual(summary["counters"]["cache_hits"], 1)
        self.assertEqual(summary["counters"]["cache_misses"], 4)
        self.assertNotIn(str(path), self.log.read_text())


if __name__ == "__main__":
    unittest.main()
