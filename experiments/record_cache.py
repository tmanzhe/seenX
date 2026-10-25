"""Optional local cache for extracted records. SQLite comes with Python."""

from contextlib import contextmanager
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sqlite3


@contextmanager
def open_cache(path: Path | None):
    if path is None:
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
        yield connection
    finally:
        connection.close()


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
        return None
    row = connection.execute(
        "SELECT record FROM records WHERE path = ? AND reader = ? AND mtime_ns = ? AND size = ?",
        (str(path), reader, state.st_mtime_ns, state.st_size),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def save_record(connection, path: Path, reader: str, state, record: dict) -> None:
    if connection is None or "ocr_error" in record:
        return
    connection.execute(
        "INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?, ?)",
        (str(path), reader, state.st_mtime_ns, state.st_size, json.dumps(record)),
    )
    connection.commit()
