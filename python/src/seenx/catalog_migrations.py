"""Additive catalog migrations, executed atomically under a write lock."""

import sqlite3


V2_STATEMENTS = (
    """CREATE TABLE ocr_runs (
        id TEXT PRIMARY KEY,
        revision_id TEXT NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
        configuration_key TEXT NOT NULL,
        configuration_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(revision_id, configuration_key)
    )""",
    """CREATE TABLE text_observations (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES ocr_runs(id) ON DELETE CASCADE,
        position INTEGER NOT NULL CHECK(position >= 0),
        text TEXT NOT NULL CHECK(length(trim(text)) > 0),
        confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
        x REAL NOT NULL CHECK(x >= 0),
        y REAL NOT NULL CHECK(y >= 0),
        width REAL NOT NULL CHECK(width > 0 AND x + width <= 1),
        height REAL NOT NULL CHECK(height > 0 AND y + height <= 1),
        origin TEXT NOT NULL CHECK(origin = 'ocr'),
        confirmation TEXT NOT NULL CHECK(confirmation = 'unverified'),
        UNIQUE(run_id, position)
    )""",
    "ALTER TABLE annotations ADD COLUMN selected_text_origin TEXT NOT NULL DEFAULT 'user' CHECK(selected_text_origin IN ('user', 'ocr'))",
    "ALTER TABLE annotations ADD COLUMN selected_text_confirmation TEXT NOT NULL DEFAULT 'confirmed' CHECK(selected_text_confirmation IN ('confirmed', 'unverified'))",
    """CREATE TABLE annotation_quotes (
        annotation_id TEXT PRIMARY KEY REFERENCES annotations(id) ON DELETE CASCADE,
        observation_id TEXT NOT NULL REFERENCES text_observations(id)
            ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TRIGGER quote_revision_guard BEFORE INSERT ON annotation_quotes
    WHEN (SELECT g.revision_id FROM annotations a JOIN regions g ON g.id = a.region_id
          WHERE a.id = NEW.annotation_id) !=
         (SELECT r.revision_id FROM text_observations o JOIN ocr_runs r ON r.id = o.run_id
          WHERE o.id = NEW.observation_id)
    BEGIN SELECT RAISE(ABORT, 'Quote must reference the same image revision'); END""",
    """CREATE TRIGGER quote_revision_update_guard BEFORE UPDATE ON annotation_quotes
    WHEN (SELECT g.revision_id FROM annotations a JOIN regions g ON g.id = a.region_id
          WHERE a.id = NEW.annotation_id) !=
         (SELECT r.revision_id FROM text_observations o JOIN ocr_runs r ON r.id = o.run_id
          WHERE o.id = NEW.observation_id)
    BEGIN SELECT RAISE(ABORT, 'Quote must reference the same image revision'); END""",
    "CREATE INDEX ocr_runs_revision ON ocr_runs(revision_id)",
    "CREATE INDEX quote_observation ON annotation_quotes(observation_id)",
)


def migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        # Recheck after locking in case another local process already migrated.
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 2:
            return
        if version != 1:
            raise ValueError("Cannot apply the version-2 migration to this catalog")
        for statement in V2_STATEMENTS:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 2")
