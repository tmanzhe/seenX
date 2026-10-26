"""Durable image revisions and user annotations, separate from derived caches."""

from datetime import datetime, timezone
import hashlib
from io import BytesIO
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from uuid import uuid4

from PIL import Image, ImageOps

from seenx.observability import count, event, stage
from seenx.paths import LIBRARY_ROOT
from seenx.catalog_migrations import migrate_catalog


SCHEMA_VERSION = 3
APPLICATION_ID = 0x534E5858
SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    current_revision_id TEXT REFERENCES revisions(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE revisions (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    format TEXT NOT NULL,
    exif_orientation INTEGER NOT NULL,
    byte_size INTEGER NOT NULL CHECK(byte_size > 0),
    created_at TEXT NOT NULL,
    UNIQUE(asset_id, sha256)
);
CREATE TABLE regions (
    id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('whole', 'point', 'region')),
    x REAL NOT NULL CHECK(x >= 0 AND x <= 1),
    y REAL NOT NULL CHECK(y >= 0 AND y <= 1),
    width REAL NOT NULL CHECK(width >= 0 AND x + width <= 1),
    height REAL NOT NULL CHECK(height >= 0 AND y + height <= 1),
    CHECK((kind = 'whole' AND x = 0 AND y = 0 AND width = 1 AND height = 1)
       OR (kind = 'point' AND width = 0 AND height = 0)
       OR (kind = 'region' AND width > 0 AND height > 0))
);
CREATE TABLE annotations (
    id TEXT PRIMARY KEY,
    region_id TEXT NOT NULL UNIQUE REFERENCES regions(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    selected_text TEXT NOT NULL,
    origin TEXT NOT NULL CHECK(origin = 'user'),
    confirmation TEXT NOT NULL CHECK(confirmation = 'confirmed'),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(length(trim(note)) > 0 OR length(trim(selected_text)) > 0)
);
CREATE INDEX regions_revision ON regions(revision_id);
CREATE INDEX revisions_asset ON revisions(asset_id);
PRAGMA application_id = 1397643352;
PRAGMA user_version = 1;
COMMIT;
"""


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def pixel_edge(value: float, dimension: int, upper: bool = False) -> int:
    scaled = value * dimension
    # Avoid a one-pixel expansion from e.g. (0.2 + 0.4) * 200 == 120.00000000000001.
    nearest = round(scaled)
    if math.isclose(scaled, nearest, rel_tol=0, abs_tol=1e-9):
        scaled = nearest
    return math.ceil(scaled) if upper else math.floor(scaled)


def target_geometry(region: list | None = None, point: list | None = None) -> tuple:
    if region is not None and point is not None:
        raise ValueError("Choose a region or a point, not both")
    kind = "whole"
    values = [0.0, 0.0, 1.0, 1.0]
    if region is not None:
        if len(region) != 4:
            raise ValueError("A region needs x, y, width, height")
        kind, values = "region", list(region)
    elif point is not None:
        if len(point) != 2:
            raise ValueError("A point needs x, y")
        kind, values = "point", [*point, 0.0, 0.0]
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        raise ValueError("Coordinates must be finite numbers")
    x, y, width, height = map(float, values)
    if min(x, y, width, height) < 0 or x + width > 1 or y + height > 1:
        raise ValueError("Target must fit inside normalized image coordinates [0, 1]")
    if kind == "region" and (width == 0 or height == 0):
        raise ValueError("Region width and height must be positive")
    return kind, x, y, width, height


class Catalog:
    def __init__(self, root: Path = LIBRARY_ROOT):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.root / "catalog.sqlite3")
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA foreign_keys = ON")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            identity = self.connection.execute("PRAGMA application_id").fetchone()[0]
            if version == 0 and identity == 0:
                tables = self.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
                if tables:
                    raise ValueError("This file is not an empty seenX catalog")
                self.connection.executescript(SCHEMA)
                version, identity = 1, APPLICATION_ID
            if identity != APPLICATION_ID or version not in range(1, SCHEMA_VERSION + 1):
                raise ValueError("Unsupported catalog schema; refusing to change it")
            if version < SCHEMA_VERSION:
                with stage("catalog_migration", from_version=version, to_version=SCHEMA_VERSION):
                    migrate_catalog(self.connection)
        except BaseException:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.connection.close()

    def object_path(self, digest: str) -> Path:
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Invalid snapshot hash")
        return self.root / "objects" / digest

    def _store_snapshot(self, payload: bytes, digest: str) -> None:
        destination = self.object_path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Publish a fully written object without overwriting an existing revision.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                pass
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise OSError("Stored snapshot failed its content-hash check")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def import_image(self, path: Path) -> dict:
        source = path.expanduser().resolve()
        before = source.stat()
        payload = source.read_bytes()
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("Source changed during import; retry")
        digest = hashlib.sha256(payload).hexdigest()
        with Image.open(BytesIO(payload)) as image:
            image.load()
            image_format = image.format
            orientation = int(image.getexif().get(274, 1))
            width, height = ImageOps.exif_transpose(image).size
        self._store_snapshot(payload, digest)
        now = timestamp()
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            asset = self.connection.execute("SELECT id FROM assets WHERE source_path = ?", (str(source),)).fetchone()
            asset_id = asset["id"] if asset else uuid4().hex
            if asset is None:
                self.connection.execute("INSERT INTO assets VALUES (?, ?, NULL, ?)", (asset_id, str(source), now))
            revision = self.connection.execute(
                "SELECT id FROM revisions WHERE asset_id = ? AND sha256 = ?", (asset_id, digest),
            ).fetchone()
            revision_id = revision["id"] if revision else uuid4().hex
            if revision is None:
                self.connection.execute("INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (revision_id, asset_id, digest, width, height, image_format, orientation, len(payload), now))
            self.connection.execute("UPDATE assets SET current_revision_id = ? WHERE id = ?", (revision_id, asset_id))
        count("memories_imported")
        event("memory_imported", asset_id=asset_id, revision_id=revision_id, reused_revision=revision is not None)
        return {"asset_id": asset_id, "revision_id": revision_id, "sha256": digest,
                "width": width, "height": height, "reused_revision": revision is not None}

    def add_note(self, revision_id: str, note: str = "", selected_text: str = "",
                 region: list | None = None, point: list | None = None,
                 observation_id: str | None = None) -> dict:
        annotation_id, region_id, now = uuid4().hex, uuid4().hex, timestamp()
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            if not self.connection.execute("SELECT 1 FROM revisions WHERE id = ?", (revision_id,)).fetchone():
                raise LookupError("Image revision not found")
            if observation_id is not None:
                if selected_text or region is not None or point is not None:
                    raise ValueError("An observation supplies its own text and region")
                observation = self.connection.execute("""
                    SELECT o.*, r.revision_id FROM text_observations o
                    JOIN ocr_runs r ON r.id = o.run_id WHERE o.id = ?
                """, (observation_id,)).fetchone()
                if observation is None or observation["revision_id"] != revision_id:
                    raise LookupError("Observation not found for this image revision")
                selected_text = observation["text"]
                region = [observation[key] for key in ("x", "y", "width", "height")]
            if not note.strip() and not selected_text.strip():
                raise ValueError("Provide a note or selected text")
            kind, x, y, width, height = target_geometry(region, point)
            self.connection.execute("INSERT INTO regions VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (region_id, revision_id, kind, x, y, width, height))
            self.connection.execute("""INSERT INTO annotations
                (id, region_id, note, selected_text, origin, confirmation, created_at, updated_at,
                 selected_text_origin, selected_text_confirmation)
                VALUES (?, ?, ?, ?, 'user', 'confirmed', ?, ?, ?, ?)""",
                (annotation_id, region_id, note, selected_text, now, now,
                 "ocr" if observation_id else "user", "unverified" if observation_id else "confirmed"))
            if observation_id is not None:
                self.connection.execute("INSERT INTO annotation_quotes VALUES (?, ?)", (annotation_id, observation_id))
        event("annotation_saved", annotation_id=annotation_id, revision_id=revision_id, target_kind=kind)
        return {"annotation_id": annotation_id, "region_id": region_id, "revision_id": revision_id}

    def edit_note(self, annotation_id: str, note: str | None = None,
                  selected_text: str | None = None) -> None:
        replace_selection = selected_text is not None
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            previous = self.connection.execute("SELECT * FROM annotations WHERE id = ?", (annotation_id,)).fetchone()
            if previous is None:
                raise LookupError("Annotation not found")
            note = previous["note"] if note is None else note
            selected_text = previous["selected_text"] if selected_text is None else selected_text
            if not note.strip() and not selected_text.strip():
                raise ValueError("Provide a note or selected text")
            self.connection.execute("UPDATE annotations SET note = ?, selected_text = ?, updated_at = ? WHERE id = ?",
                                    (note, selected_text, timestamp(), annotation_id))
            if replace_selection:
                self.connection.execute("DELETE FROM annotation_quotes WHERE annotation_id = ?", (annotation_id,))
                self.connection.execute("""UPDATE annotations SET selected_text_origin = 'user',
                                        selected_text_confirmation = 'confirmed' WHERE id = ?""", (annotation_id,))
        event("annotation_edited", annotation_id=annotation_id)

    def delete_note(self, annotation_id: str) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM regions WHERE id = (SELECT region_id FROM annotations WHERE id = ?)", (annotation_id,),
            )
        event("annotation_removed", annotation_id=annotation_id, removed=bool(cursor.rowcount))
        return bool(cursor.rowcount)

    def remove_memory(self, asset_id: str) -> bool:
        # Retain content-addressed objects: another asset may reference the same bytes.
        with self.connection:
            cursor = self.connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        event("memory_removed", asset_id=asset_id, removed=bool(cursor.rowcount))
        return bool(cursor.rowcount)

    def list_memories(self) -> list:
        rows = self.connection.execute("""
            SELECT a.*, (SELECT count(*) FROM revisions r WHERE r.asset_id = a.id) AS revision_count,
                (SELECT count(*) FROM annotations n JOIN regions g ON g.id = n.region_id
                 JOIN revisions r ON r.id = g.revision_id WHERE r.asset_id = a.id) AS annotation_count
            FROM assets a ORDER BY a.created_at, a.id
        """).fetchall()
        return [dict(row) for row in rows]

    def read_revision_bytes(self, revision_id: str) -> tuple[dict, bytes]:
        row = self.connection.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,)).fetchone()
        if row is None:
            raise LookupError("Image revision not found")
        payload = self.object_path(row["sha256"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise OSError("Stored snapshot failed its content-hash check")
        return dict(row), payload

    def recognize_text(self, revision_id: str) -> dict:
        from seenx.catalog_ocr import recognize_revision
        return recognize_revision(self, revision_id)

    def search(self, query: str, match: str = "phrase", limit: int = 20,
               asset_id: str | None = None, revision_id: str | None = None,
               current_only: bool = False) -> list:
        from seenx.catalog_search import search_catalog
        return search_catalog(self.connection, query, match, limit, asset_id, revision_id, current_only)

    def rebuild_search(self) -> int:
        from seenx.catalog_search import rebuild_index
        return rebuild_index(self.connection)

    def get_memory(self, asset_id: str, revision_id: str | None = None) -> dict:
        from seenx.catalog_ocr import revision_ocr_runs
        asset = self.connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if asset is None:
            raise LookupError("Memory not found")
        revision_id = revision_id or asset["current_revision_id"]
        revision = self.connection.execute("SELECT * FROM revisions WHERE id = ? AND asset_id = ?",
                                           (revision_id, asset_id)).fetchone()
        if revision is None:
            raise LookupError("Revision not found for this memory")
        snapshot = self.object_path(revision["sha256"])
        self.read_revision_bytes(revision_id)
        rows = self.connection.execute("""
            SELECT n.*, g.revision_id, g.kind, g.x, g.y, g.width, g.height
            FROM annotations n JOIN regions g ON g.id = n.region_id
            WHERE g.revision_id = ? ORDER BY n.created_at, n.id
        """, (revision_id,)).fetchall()
        annotations = []
        quotes = {row["annotation_id"]: row["observation_id"] for row in self.connection.execute("""
            SELECT q.* FROM annotation_quotes q JOIN annotations a ON a.id = q.annotation_id
            JOIN regions g ON g.id = a.region_id WHERE g.revision_id = ?
        """, (revision_id,)).fetchall()}
        relationships = [{"subject": revision_id, "predicate": "revision_of", "object": asset_id,
                          "origin": "import", "confirmation": "recorded"}]
        for row in rows:
            annotation = dict(row)
            annotation["quoted_observation_id"] = quotes.get(row["id"])
            target = {key: annotation.pop(key) for key in ("kind", "x", "y", "width", "height")}
            annotation["target"] = target
            width, height = revision["width"], revision["height"]
            if target["kind"] == "point":
                annotation["pixel_target"] = {"x": min(width - 1, pixel_edge(target["x"], width)),
                                               "y": min(height - 1, pixel_edge(target["y"], height))}
            else:
                annotation["pixel_bounds"] = {
                    "left": pixel_edge(target["x"], width), "top": pixel_edge(target["y"], height),
                    "right": min(width, pixel_edge(target["x"] + target["width"], width, upper=True)),
                    "bottom": min(height, pixel_edge(target["y"] + target["height"], height, upper=True)),
                }
            annotations.append(annotation)
            relationships.extend([
                {"subject": row["id"], "predicate": "refers_to", "object": row["region_id"],
                 "origin": "user", "confirmation": "confirmed"},
                {"subject": row["region_id"], "predicate": "part_of", "object": revision_id,
                 "origin": "user", "confirmation": "confirmed"},
            ])
            if row["id"] in quotes:
                relationships.append({"subject": row["id"], "predicate": "quotes", "object": quotes[row["id"]],
                                      "origin": "user", "confirmation": "confirmed"})
        history = self.connection.execute("""
            SELECT r.id, r.sha256, r.width, r.height, r.created_at,
                (SELECT count(*) FROM annotations n JOIN regions g ON g.id = n.region_id
                 WHERE g.revision_id = r.id) AS annotation_count
            FROM revisions r WHERE r.asset_id = ? ORDER BY r.created_at, r.id
        """, (asset_id,)).fetchall()
        return {"schema_version": SCHEMA_VERSION, "asset": dict(asset),
                "revision": {**dict(revision), "snapshot_path": str(snapshot), "snapshot_verified": True,
                             "coordinate_space": "normalized_top_left_exif_corrected"},
                "source_missing": not Path(asset["source_path"]).is_file(),
                "revisions": [dict(row) for row in history],
                "annotations": annotations, "relationships": relationships,
                "ocr_runs": revision_ocr_runs(self.connection, revision_id)}
