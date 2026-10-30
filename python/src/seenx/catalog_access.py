"""Owner-managed grants, separate from read-only engine requests.

An imported file is currently one source: its stable asset ID identifies that
source across revisions. These IDs are not the FTS annotation/observation IDs.
"""

from uuid import uuid4


V4_STATEMENTS = (
    """CREATE TABLE collections (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL CHECK(length(trim(name)) > 0)
    )""",
    """CREATE TABLE collection_assets (
        collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
        PRIMARY KEY(collection_id, asset_id)
    )""",
    "CREATE INDEX collection_assets_asset ON collection_assets(asset_id, collection_id)",
    """CREATE TABLE source_grants (
        principal_id TEXT NOT NULL CHECK(length(trim(principal_id)) > 0),
        asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
        PRIMARY KEY(principal_id, asset_id)
    )""",
    """CREATE TABLE collection_grants (
        principal_id TEXT NOT NULL CHECK(length(trim(principal_id)) > 0),
        collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        PRIMARY KEY(principal_id, collection_id)
    )""",
)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError("Access identifiers must contain 1–128 characters")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("Access identifiers must contain valid Unicode") from None
    return value


def grant_filter(principal_id: str | None) -> tuple[str, tuple]:
    """SQL for the fixed `asset` alias, shared by search and direct fetch."""
    if principal_id is None:
        return "0", ()
    identifier(principal_id)
    return """(EXISTS (
        SELECT 1 FROM source_grants sg
        WHERE sg.asset_id = asset.id AND sg.principal_id = ?
    ) OR EXISTS (
        SELECT 1 FROM collection_assets ca
        JOIN collection_grants cg ON cg.collection_id = ca.collection_id
        WHERE ca.asset_id = asset.id AND cg.principal_id = ?
    ))""", (principal_id, principal_id)


class AccessDeniedError(PermissionError):
    """A grant denial, distinct from an OS-level file permission failure."""


def require_access_context(principal_id: str | None, trusted_local: bool) -> None:
    """In-process evidence reads must deliberately choose their access scope."""
    if type(trusted_local) is not bool or (trusted_local and principal_id is not None):
        raise ValueError("Choose either a grant-scoped principal or trusted local access")
    if principal_id is None:
        if not trusted_local:
            raise ValueError("Evidence reads require principal_id or trusted_local=True")
    else:
        identifier(principal_id)


class AccessGrants:
    """Trusted catalog-owner API. Never exposed as an engine wire method."""

    def __init__(self, connection):
        self.connection = connection

    def create_collection(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip() or len(name) > 512:
            raise ValueError("Collection name must contain 1–512 characters")
        collection_id = uuid4().hex
        with self.connection:
            self.connection.execute("INSERT INTO collections VALUES (?, ?)", (collection_id, name))
        return collection_id

    def add_member(self, collection_id: str, asset_id: str) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO collection_assets VALUES (?, ?) ON CONFLICT DO NOTHING",
                                    (identifier(collection_id), identifier(asset_id)))

    def remove_member(self, collection_id: str, asset_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM collection_assets WHERE collection_id = ? AND asset_id = ?",
                                    (identifier(collection_id), identifier(asset_id)))

    def grant_source(self, principal_id: str, source_id: str) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO source_grants VALUES (?, ?) ON CONFLICT DO NOTHING",
                                    (identifier(principal_id), identifier(source_id)))

    def revoke_source(self, principal_id: str, source_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM source_grants WHERE principal_id = ? AND asset_id = ?",
                                    (identifier(principal_id), identifier(source_id)))

    def grant_collection(self, principal_id: str, collection_id: str) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO collection_grants VALUES (?, ?) ON CONFLICT DO NOTHING",
                                    (identifier(principal_id), identifier(collection_id)))

    def revoke_collection(self, principal_id: str, collection_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM collection_grants WHERE principal_id = ? AND collection_id = ?",
                                    (identifier(principal_id), identifier(collection_id)))

    def allows(self, principal_id: str | None, asset_id: str) -> bool:
        condition, parameters = grant_filter(principal_id)
        return self.connection.execute(
            "SELECT 1 FROM assets asset WHERE asset.id = ? AND " + condition,
            (identifier(asset_id), *parameters),
        ).fetchone() is not None
