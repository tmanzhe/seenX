"""Versioned, unencrypted whole-library archives for the trusted local owner.

Only authoritative catalog rows travel. SQL, derived indexes, and grants never do.
Archive paths are validated and read explicitly; ZIP members are never extracted.
"""

from contextlib import closing
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import tempfile
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile
from zlib import error as ZlibError

from seenx.catalog import APPLICATION_ID, SCHEMA_VERSION, Catalog, timestamp


ARCHIVE_VERSION = 1
TABLES = {
    "assets": "id source_path current_revision_id created_at",
    "revisions": "id asset_id sha256 width height format exif_orientation byte_size created_at",
    "regions": "id revision_id kind x y width height",
    "annotations": "id region_id note selected_text origin confirmation created_at updated_at selected_text_origin selected_text_confirmation",
    "ocr_runs": "id revision_id configuration_key configuration_json created_at",
    "text_observations": "id run_id position text confidence x y width height origin confirmation",
    "annotation_quotes": "annotation_id observation_id",
    "collections": "id name",
    "collection_assets": "collection_id asset_id",
}
HASH = re.compile(r"[0-9a-f]{64}")


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_object(payload: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    try:
        value = json.loads(payload, object_pairs_hook=unique,
                           parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid archive JSON") from error
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _read_catalog(library: Path) -> dict:
    # A read transaction pins one catalog snapshot, including under WAL writers.
    # Objects are immutable and logical deletion deliberately retains them.
    database = library.expanduser().resolve() / "catalog.sqlite3"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        if (connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
            raise ValueError("Archive operations require catalog schema version 4; open older libraries with Catalog first")
        return {table: [dict(row) for row in connection.execute(
            f"SELECT {', '.join(columns.split())} FROM {table} ORDER BY {columns.split()[0]}")]
            for table, columns in TABLES.items()}


def _restore_catalog(data: dict, root: Path) -> None:
    if set(data) != set(TABLES):
        raise ValueError("Unexpected archive catalog tables (grants are excluded)")
    for table, column_string in TABLES.items():
        columns = column_string.split()
        rows = data[table]
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or set(row) != set(columns) for row in rows
        ):
            raise ValueError(f"Invalid catalog rows: {table}")
        for row in rows:
            if any(type(value) not in (str, int, float, type(None))
                   or isinstance(value, float) and not math.isfinite(value) for value in row.values()):
                raise ValueError(f"Invalid catalog values: {table}")
    for revision in data["revisions"]:
        if not isinstance(revision["sha256"], str) or HASH.fullmatch(revision["sha256"]) is None:
            raise ValueError("Invalid snapshot hash")
    with Catalog(root) as catalog:
        connection = catalog.connection
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("PRAGMA defer_foreign_keys = ON")
            for table, column_string in TABLES.items():
                columns = column_string.split()
                rows = data[table]
                connection.executemany(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                    [[row[column] for column in columns] for row in rows])
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Invalid catalog relationship target")
            if connection.execute("""SELECT 1 FROM assets a JOIN revisions r ON r.id = a.current_revision_id
                                     WHERE r.asset_id != a.id""").fetchone():
                raise ValueError("Current revision belongs to another asset")
        catalog.rebuild_search()


def _safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or "\x00" in name or path.is_absolute()
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError(f"Unsafe archive member path: {name!r}")


def _read_archive(archive: ZipFile) -> tuple[dict, dict, dict]:
    names = set()
    for member in archive.infolist():
        _safe_member(member.filename)
        if member.filename in names or member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
            raise ValueError("Duplicate, directory, or symlink archive member")
        if member.flag_bits & 1:
            raise ValueError("Encrypted archives are not supported")
        names.add(member.filename)
    if "manifest.json" not in names:
        raise ValueError("Archive manifest is missing")
    try:
        manifest = _json_object(archive.read("manifest.json"))
    except (BadZipFile, ZlibError, EOFError) as error:
        raise ValueError("Corrupt archive manifest") from error
    if (type(manifest.get("archive_format_version")) is not int
            or manifest["archive_format_version"] != ARCHIVE_VERSION):
        raise ValueError("Unsupported archive format version")
    if (type(manifest.get("catalog_schema_version")) is not int
            or manifest["catalog_schema_version"] != SCHEMA_VERSION):
        raise ValueError("Unsupported archive catalog schema version")
    if manifest.get("mode") not in ("complete", "context-only"):
        raise ValueError("Invalid archive mode")
    try:
        if datetime.fromisoformat(manifest["created_at"]).utcoffset() is None:
            raise ValueError("Timestamp needs a timezone")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid archive creation timestamp") from error
    files = manifest.get("files")
    if not isinstance(files, dict) or "catalog.json" not in files:
        raise ValueError("Invalid archive file checksums")
    for name, digest in files.items():
        _safe_member(name)
        if (name != "catalog.json" and re.fullmatch(r"objects/[0-9a-f]{64}", name) is None
                or not isinstance(digest, str) or HASH.fullmatch(digest) is None):
            raise ValueError("Invalid archive file checksum or member")
    if names - {"manifest.json"} - set(files):
        raise ValueError("Archive contains files absent from the manifest")
    report = {"ok": True, "mode": manifest["mode"], "missing_files": [],
              "checksum_mismatches": [], "relinked_files": []}
    for name, digest in files.items():
        if name not in names:
            report["missing_files"].append(name)
        else:
            try:
                actual = _digest(archive.read(name))
            except (BadZipFile, ZlibError, EOFError):
                actual = None  # CRC failures are corrupt payloads too.
            if actual != digest:
                report["checksum_mismatches"].append(name)
    if "catalog.json" in report["missing_files"] + report["checksum_mismatches"]:
        report["ok"] = False
        return manifest, {}, report
    data = _json_object(archive.read("catalog.json"))
    # Reconstruct using our own schema, constraints and triggers, never archived SQL.
    with tempfile.TemporaryDirectory() as temporary:
        _restore_catalog(data, Path(temporary))
    objects = {f"objects/{row['sha256']}" for row in data["revisions"]}
    expected = {"catalog.json"} | (objects if manifest["mode"] == "complete" else set())
    if set(files) != expected:
        raise ValueError("Manifest file list does not match the catalog and mode")
    for name in objects & set(files):
        if files[name] != name.split("/")[1] and name not in report["checksum_mismatches"]:
            report["checksum_mismatches"].append(name)
    report["ok"] = not (report["missing_files"] or report["checksum_mismatches"])
    return manifest, data, report


def _resolve_originals(digests: set[str], original_folder: Path | None) -> dict[str, Path]:
    if original_folder is None or not digests:
        return {}
    folder = original_folder.expanduser().resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Original folder must be a directory")
    found = {}
    # Paths in the catalog are history, not permission to browse outside this folder.
    # Do not follow symlink files or directories into other locations.
    for directory, _, files in os.walk(folder, followlinks=False):
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                continue
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest in digests:
                found.setdefault(digest, path)
            if found.keys() >= digests:
                return found
    return found


def _context_report(data: dict, report: dict, original_folder: Path | None) -> dict[str, Path]:
    digests = {row["sha256"] for row in data["revisions"]}
    found = _resolve_originals(digests, original_folder)
    report["relinked_files"] = [{"file": f"objects/{digest}", "original_path": str(path)}
                                for digest, path in sorted(found.items())]
    report["missing_files"].extend(f"objects/{digest}" for digest in sorted(digests - found.keys()))
    report["ok"] = not (report["missing_files"] or report["checksum_mismatches"])
    return found


def verify_archive(path: Path, original_folder: Path | None = None) -> dict:
    """Read-only verification; context objects can be resolved by hash in a folder."""
    with ZipFile(path.expanduser()) as archive:
        manifest, data, report = _read_archive(archive)
        if data and manifest["mode"] == "context-only":
            _context_report(data, report, original_folder)
        return report


def verify_library(library: Path, original_folder: Path | None = None) -> dict:
    """Check managed objects; report potential relinks without changing the library."""
    data = _read_catalog(library)
    root = library.expanduser().resolve()
    report = {"ok": True, "missing_files": [], "checksum_mismatches": [], "relinked_files": []}
    missing = set()
    for digest in sorted({row["sha256"] for row in data["revisions"]}):
        if not isinstance(digest, str) or HASH.fullmatch(digest) is None:
            raise ValueError("Invalid snapshot hash")
        name = f"objects/{digest}"
        path = root / name
        if not path.is_file():
            missing.add(digest)
        elif _digest(path.read_bytes()) != digest:
            report["checksum_mismatches"].append(name)
    _context_report({"revisions": [{"sha256": digest} for digest in missing]}, report, original_folder)
    return report


def export_library(library: Path, destination: Path, mode: str = "complete") -> dict:
    if mode not in ("complete", "context-only"):
        raise ValueError("Choose complete or context-only mode")
    data = _read_catalog(library)
    destination = destination.expanduser().absolute()
    if os.path.lexists(destination):
        raise FileExistsError("Archive destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"archive_format_version": ARCHIVE_VERSION, "catalog_schema_version": SCHEMA_VERSION,
                "mode": mode, "created_at": timestamp(), "files": {}}
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / "archive.zip"
        with ZipFile(staging, "w", compression=ZIP_DEFLATED) as archive:
            payload = _json_bytes(data)
            archive.writestr("catalog.json", payload)
            manifest["files"]["catalog.json"] = _digest(payload)
            if mode == "complete":
                for digest in sorted({row["sha256"] for row in data["revisions"]}):
                    if not isinstance(digest, str) or HASH.fullmatch(digest) is None:
                        raise ValueError("Invalid snapshot hash")
                    name = f"objects/{digest}"
                    payload = (library.expanduser().resolve() / name).read_bytes()
                    if _digest(payload) != digest:
                        raise ValueError(f"Snapshot checksum mismatch: {name}")
                    archive.writestr(name, payload)
                    manifest["files"][name] = digest
            archive.writestr("manifest.json", _json_bytes(manifest))
        # Validate catalog constraints, relationships, and every written payload before publication.
        with ZipFile(staging) as archive:
            _, _, report = _read_archive(archive)
        if not report["ok"]:
            raise ValueError(f"Export verification failed: {report}")
        os.link(staging, destination)  # Exclusive publication; never overwrite a backup.
    return {"archive": str(destination), "manifest": manifest, "verified": True}


def restore_library(archive_path: Path, target: Path, original_folder: Path | None = None) -> dict:
    """Restore to an absent path. Context without originals remains usable for search."""
    target = target.expanduser().absolute()
    if os.path.lexists(target):
        raise FileExistsError("Restore requires a NEW library path; target already exists")
    with ZipFile(archive_path.expanduser()) as archive:
        manifest, data, report = _read_archive(archive)
        if not report["ok"]:
            raise ValueError(f"Archive verification failed: {report}")
        found = {}
        if manifest["mode"] == "context-only":
            found = _context_report(data, report, original_folder)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
            staging = Path(temporary) / "library"
            _restore_catalog(data, staging)
            with Catalog(staging) as catalog:
                for digest in sorted({row["sha256"] for row in data["revisions"]}):
                    if manifest["mode"] == "complete":
                        payload = archive.read(f"objects/{digest}")
                    elif digest in found:
                        payload = found[digest].read_bytes()
                    else:
                        continue
                    if _digest(payload) != digest:
                        raise ValueError("Image changed during restore")
                    catalog._store_snapshot(payload, digest)
            # Reserve exclusively even if a different process created the target during validation.
            target.mkdir()
            try:
                for child in staging.iterdir():
                    child.rename(target / child.name)
            except BaseException:
                shutil.rmtree(target)
                raise
    return {"library": str(target), "restored": True, **report}
