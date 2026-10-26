"""Derived search documents and FTS5 triggers; source records stay authoritative."""


DOCUMENT_SELECT = """
    SELECT 'note', a.id, g.revision_id, a.note
    FROM annotations a JOIN regions g ON g.id = a.region_id WHERE length(trim(a.note)) > 0
    UNION ALL
    SELECT 'selected_text', a.id, g.revision_id, a.selected_text
    FROM annotations a JOIN regions g ON g.id = a.region_id WHERE length(trim(a.selected_text)) > 0
    UNION ALL
    SELECT 'ocr', o.id, r.revision_id, o.text
    FROM text_observations o JOIN ocr_runs r ON r.id = o.run_id
"""

ANNOTATION_INSERT = """
    INSERT INTO search_documents(kind, source_id, revision_id, content)
    SELECT 'note', NEW.id, g.revision_id, NEW.note FROM regions g
    WHERE g.id = NEW.region_id AND length(trim(NEW.note)) > 0;
    INSERT INTO search_documents(kind, source_id, revision_id, content)
    SELECT 'selected_text', NEW.id, g.revision_id, NEW.selected_text FROM regions g
    WHERE g.id = NEW.region_id AND length(trim(NEW.selected_text)) > 0;
"""

OBSERVATION_INSERT = """
    INSERT INTO search_documents(kind, source_id, revision_id, content)
    SELECT 'ocr', NEW.id, r.revision_id, NEW.text FROM ocr_runs r WHERE r.id = NEW.run_id;
"""

V3_STATEMENTS = (
    """CREATE TABLE search_documents (
        id INTEGER PRIMARY KEY,
        kind TEXT NOT NULL CHECK(kind IN ('note', 'selected_text', 'ocr')),
        source_id TEXT NOT NULL,
        revision_id TEXT NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        UNIQUE(kind, source_id)
    )""",
    "CREATE INDEX search_documents_revision ON search_documents(revision_id)",
    """CREATE VIRTUAL TABLE catalog_fts USING fts5(
        content, content='search_documents', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )""",
    """CREATE TRIGGER search_documents_ai AFTER INSERT ON search_documents BEGIN
        INSERT INTO catalog_fts(rowid, content) VALUES (NEW.id, NEW.content);
    END""",
    """CREATE TRIGGER search_documents_ad AFTER DELETE ON search_documents BEGIN
        INSERT INTO catalog_fts(catalog_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
    END""",
    """CREATE TRIGGER search_documents_au AFTER UPDATE ON search_documents BEGIN
        INSERT INTO catalog_fts(catalog_fts, rowid, content) VALUES ('delete', OLD.id, OLD.content);
        INSERT INTO catalog_fts(rowid, content) VALUES (NEW.id, NEW.content);
    END""",
    f"CREATE TRIGGER annotations_search_ai AFTER INSERT ON annotations BEGIN {ANNOTATION_INSERT} END",
    f"""CREATE TRIGGER annotations_search_au AFTER UPDATE OF note, selected_text, region_id ON annotations BEGIN
        DELETE FROM search_documents WHERE kind IN ('note', 'selected_text') AND source_id = OLD.id;
        {ANNOTATION_INSERT}
    END""",
    """CREATE TRIGGER annotations_search_ad AFTER DELETE ON annotations BEGIN
        DELETE FROM search_documents WHERE kind IN ('note', 'selected_text') AND source_id = OLD.id;
    END""",
    f"CREATE TRIGGER observations_search_ai AFTER INSERT ON text_observations BEGIN {OBSERVATION_INSERT} END",
    f"""CREATE TRIGGER observations_search_au AFTER UPDATE OF text, run_id ON text_observations BEGIN
        DELETE FROM search_documents WHERE kind = 'ocr' AND source_id = OLD.id;
        {OBSERVATION_INSERT}
    END""",
    """CREATE TRIGGER observations_search_ad AFTER DELETE ON text_observations BEGIN
        DELETE FROM search_documents WHERE kind = 'ocr' AND source_id = OLD.id;
    END""",
    f"INSERT INTO search_documents(kind, source_id, revision_id, content) {DOCUMENT_SELECT}",
)
