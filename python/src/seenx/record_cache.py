"""Optional local cache for extracted records. SQLite comes with Python."""

from contextlib import contextmanager
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sqlite3

from seenx.observability import count, event, file_id
import logging

@contextmanager
def open_cache(path: Path | None):
    if path is None:
        event("cache_opened", enabled=False)
        yield None
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS records (
                path TEXT NOT NULL,
                reader TEXT NOT NULL,
                mtime_ns INTEGER NOT NULL,
                size INTEGER NOT NULL,
                record TEXT NOT NULL,
                PRIMARY KEY (path, reader)
            )
        """)
        connection.commit()
        event("cache_opened", enabled=True)
        yield connection
    finally:
        connection.close()
        event("cache_closed")


def reader_key(path: Path, ocr: bool) -> str:
    # Bump this version if our extraction settings or record format change.
    key = "records-v1:"
    if path.suffix.lower() == ".pdf":
        return key + "pypdf:" + version("pypdf")
    key += "pillow:" + version("Pillow")
    if ocr:
        key += ":vision-en-US-accurate:" + version("pyobjc-framework-Vision")
        key += ":macos:" + platform.mac_ver()[0]
    return key


def get_record(connection, path: Path, reader: str, state) -> dict | None:
    if connection is None:
        count("cache_disabled_lookups")
        return None
    row = connection.execute(
        "SELECT mtime_ns, size, record FROM records WHERE path = ? AND reader = ?",
        (str(path), reader),
    ).fetchone()
    reason = None
    if row is None:
        other = connection.execute("SELECT 1 FROM records WHERE path = ? LIMIT 1", (str(path),)).fetchone()
        reason = "reader_variant_missing" if other else "not_cached"
    elif (row[0], row[1]) != (state.st_mtime_ns, state.st_size):
        reason = "source_changed"
    else:
        try:
            record = json.loads(row[2])
            if not isinstance(record, dict):
                raise ValueError("Invalid cached record")
        except (ValueError, TypeError):
            reason = "invalid_record"
    if reason:
        count("cache_misses")
        count("cache_miss_" + reason)
        event("cache_miss", level=logging.DEBUG, file_id=file_id(path), reader=reader, reason=reason)
        return None
    count("cache_hits")
    event("cache_hit", level=logging.DEBUG, file_id=file_id(path), reader=reader)
    return record


def save_record(connection, path: Path, reader: str, state, record: dict) -> None:
    if connection is None or "ocr_error" in record:
        if "ocr_error" in record:
            count("cache_skipped_ocr_errors")
        return
    connection.execute(
        "INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
        (str(path), reader, state.st_mtime_ns, state.st_size, json.dumps(record)),
    )
    connection.commit()
    count("cache_writes")
    event("cache_write", level=logging.DEBUG, file_id=file_id(path), reader=reader)
