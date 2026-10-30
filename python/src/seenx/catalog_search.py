"""Bounded FTS5 retrieval returning references to durable source evidence."""

from seenx.catalog_search_schema import DOCUMENT_SELECT
from seenx.catalog_access import grant_filter
from seenx.observability import count, event, stage


def match_expression(query: str, mode: str) -> str:
    if not isinstance(query, str) or not query.strip() or len(query) > 512:
        raise ValueError("Search query must contain 1–512 characters")
    if not any(character.isalnum() for character in query):
        raise ValueError("Search query needs a letter or number")
    if mode not in {"phrase", "all"}:
        raise ValueError("Match mode must be phrase or all")
    parts = [query.strip()] if mode == "phrase" else query.split()
    if len(parts) > 32:
        raise ValueError("All-terms mode supports at most 32 terms")
    # Quote every user fragment: FTS operators and wildcards aren't executable syntax.
    return " AND ".join('"' + part.replace('"', '""') + '"' for part in parts)


def search_catalog(connection, query: str, match: str = "phrase", limit: int = 20,
                   asset_id: str | None = None, revision_id: str | None = None,
                   current_only: bool = False, *, principal_id: str | None = None,
                   trusted_local: bool | None = None) -> list:
    if trusted_local is None:
        trusted_local = principal_id is None
    if type(trusted_local) is not bool or (trusted_local and principal_id is not None):
        raise ValueError("Choose either a grant-scoped principal or trusted local access")
    expression = match_expression(query, match)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Result limit must be between 1 and 100")
    conditions = ["catalog_fts MATCH ?"]
    parameters = [expression]
    if not trusted_local:
        condition, grants = grant_filter(principal_id)
        conditions.append(condition)
        parameters.extend(grants)
    for column, value in (("r.asset_id", asset_id), ("r.id", revision_id)):
        if value is not None:
            conditions.append(column + " = ?")
            parameters.append(value)
    if current_only:
        conditions.append("r.id = asset.current_revision_id")
    parameters.append(limit)
    with stage("catalog_text_search"):
        rows = connection.execute("""
            SELECT d.kind, d.source_id, d.revision_id, r.asset_id,
                r.id = asset.current_revision_id AS is_current_revision,
                bm25(catalog_fts) AS score,
                snippet(catalog_fts, 0, '[', ']', ' … ', 20) AS excerpt,
                a.region_id, q.observation_id AS quoted_observation_id,
                a.origin AS note_origin, a.confirmation AS note_confirmation,
                a.selected_text_origin, a.selected_text_confirmation,
                o.origin AS ocr_origin, o.confirmation AS ocr_confirmation,
                g.kind AS target_kind,
                CASE WHEN d.kind = 'ocr' THEN o.x ELSE g.x END AS x,
                CASE WHEN d.kind = 'ocr' THEN o.y ELSE g.y END AS y,
                CASE WHEN d.kind = 'ocr' THEN o.width ELSE g.width END AS width,
                CASE WHEN d.kind = 'ocr' THEN o.height ELSE g.height END AS height
            FROM catalog_fts
            JOIN search_documents d ON d.id = catalog_fts.rowid
            JOIN revisions r ON r.id = d.revision_id
            JOIN assets asset ON asset.id = r.asset_id
            LEFT JOIN annotations a ON a.id = d.source_id AND d.kind IN ('note', 'selected_text')
            LEFT JOIN regions g ON g.id = a.region_id
            LEFT JOIN annotation_quotes q ON q.annotation_id = a.id
            LEFT JOIN text_observations o ON o.id = d.source_id AND d.kind = 'ocr'
            LEFT JOIN ocr_runs ocr_source ON ocr_source.id = o.run_id
            WHERE """ + " AND ".join(conditions) + """
              AND ((d.kind = 'ocr' AND o.id IS NOT NULL AND ocr_source.revision_id = d.revision_id)
                OR (d.kind IN ('note', 'selected_text') AND a.id IS NOT NULL AND g.revision_id = d.revision_id))
            ORDER BY score, CASE d.kind WHEN 'note' THEN 0 WHEN 'selected_text' THEN 1 ELSE 2 END,
                     r.asset_id, r.id, d.kind, d.source_id
            LIMIT ?
        """, parameters).fetchall()
    results = []
    for row in rows:
        field = row["kind"]
        origin = row["note_origin"] if field == "note" else row["selected_text_origin"] if field == "selected_text" else row["ocr_origin"]
        confirmation = row["note_confirmation"] if field == "note" else row["selected_text_confirmation"] if field == "selected_text" else row["ocr_confirmation"]
        results.append({
            "asset_id": row["asset_id"], "revision_id": row["revision_id"],
            "is_current_revision": bool(row["is_current_revision"]),
            "annotation_id": row["source_id"] if field != "ocr" else None,
            "observation_id": row["source_id"] if field == "ocr" else row["quoted_observation_id"],
            "region_id": row["region_id"], "matched_field": field, "method": "catalog-fts5",
            "excerpt": row["excerpt"], "score": row["score"],
            "score_kind": "fts5-bm25", "score_direction": "lower_is_better",
            "provenance": {"origin": origin, "confirmation": confirmation},
            "target": {"kind": "region" if field == "ocr" else row["target_kind"],
                       **{key: row[key] for key in ("x", "y", "width", "height")}},
        })
    count("catalog_search_results", len(results))
    event("catalog_search_completed", query_characters=len(query), match_mode=match,
          limit=limit, current_only=current_only, results=len(results))
    return results


def rebuild_index(connection) -> int:
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM search_documents")
        connection.execute(f"INSERT INTO search_documents(kind, source_id, revision_id, content) {DOCUMENT_SELECT}")
        total = connection.execute("SELECT count(*) FROM search_documents").fetchone()[0]
    event("catalog_index_rebuilt", documents=total)
    return total
