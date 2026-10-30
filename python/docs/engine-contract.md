# One local interface for search and evidence fetch

We now have a versioned read-only interface over the Python catalog. A local client can launch `seenx-engine`, send JSON requests on stdin, and read JSON responses on stdout. The process keeps one catalog connection open and handles requests sequentially until stdin closes.

This is the first internal app integration boundary. The native app's optional **Open Python Library…** browser now uses it through [SeenXEngineClient](../../packages/SeenXEngineClient); see [the native integration lesson](../../docs/native-engine.md). Its main capture launcher/library remain separate. `seenx-engine` uses its own JSON-line protocol; the optional `seenx-mcp` adapter below supplies MCP JSON-RPC over stdio using the same version-1 search/fetch contract. Neither opens a network listener or downloads models.

## Start with a handshake

From the repository root:

```sh
uv sync --project python --all-extras
printf '%s\n' '{"version":1,"id":"hello","method":"engine.info","params":{}}' \
  | uv run --project python seenx-engine --no-log
```

The response has this shape:

```json
{
  "version": 1,
  "id": "hello",
  "trace_id": "an-engine-generated-correlation-id",
  "result": {
    "protocol_version": 1,
    "catalog_schema_version": 4,
    "read_only_requests": true,
    "methods": ["engine.info", "memory.fetch", "memory.search", "region.fetch"],
    "limits": {}
  }
}
```

The actual `limits` object lists the byte, pixel, and result caps below. The protocol version identifies the wire contract; the catalog schema version identifies the database layout. They serve different purposes and needn't have the same number.

For another library, launch with `--library /path/to/library`. A request cannot change that root or supply an arbitrary filesystem path. Caller access is fixed at launch: `--principal assistant-a` uses persisted grants; no principal and no trusted flag exposes no evidence. The first-party native app explicitly supplies `--trusted-local` for its owner-selected whole library, as intended by the architecture. These options are mutually exclusive and cannot be supplied in request JSON.

### Owner-managed source and collection grants

Catalog schema 4 adds `source_grants`, `collection_grants`, `collections`, and `collection_assets` to the library's `catalog.sqlite3`. Upgrades preserve evidence IDs and create no grants. The trusted Python owner API is `catalog.access` (`AccessGrants`); the local `seenx-memory` CLI can manage it:

```sh
seenx-memory --library /path/to/library grant assistant-a --source ASSET_ID
seenx-memory --library /path/to/library revoke assistant-a --source ASSET_ID
seenx-memory --library /path/to/library collection-create Shared
seenx-memory --library /path/to/library collection-add COLLECTION_ID ASSET_ID
seenx-memory --library /path/to/library grant assistant-a --collection COLLECTION_ID
seenx-memory --library /path/to/library revoke assistant-a --collection COLLECTION_ID
```

Currently a **source is one imported file**, identified by its stable asset ID across all revisions; this is distinct from FTS's internal annotation/observation `source_id`. Folder/app/URL source groups are not implemented. A source grant **or** membership in a granted collection permits the whole asset, including historical revisions and annotations. Collection membership is live: `collection-add` authorizes new members and `collection-remove` removes that route to access. Revoking one grant leaves any other matching grant effective. Removing an asset cascades its source grants and memberships.

The version-1 engine applies the same grant predicate to search candidates **before LIMIT** and to both fetch methods before reading evidence. An ungranted asset (including an unknown ID) returns `access_denied`; search silently excludes ungranted hits, even with explicit asset/revision filters. Grants are re-read on every request, so committed revocation affects subsequent calls in an existing session. The existing single-owner/sequential-request assumption remains; in-flight disclosures cannot be recalled. In-process `Catalog.search`, `Catalog.get_memory`, and `Catalog.read_revision_bytes` require either `principal_id="assistant-a"` or explicit `trusted_local=True`; omitting both raises `ValueError`. Principal-scoped direct fetches raise `PermissionError` when ungranted. `seenx-memory search/get`, OCR writes, and the engine's `--trusted-local` path deliberately retain owner access.

Identity and trusted mode are host configuration, not authentication. The MCP adapter binds its local client to the owner-configured startup principal; tool arguments cannot choose a principal, trusted mode, grant writes, or the catalog path. External authentication isn't implemented. Local processes with direct filesystem/catalog access remain trusted OS-account owners.

Requests are read-only. Startup can initialize or migrate the catalog and its derived index, just like the existing CLI. Use `seenx-memory` for deliberate import, annotation, editing, removal, OCR, or reindexing. No write methods are exposed through this protocol yet.

## Read-only MCP over stdio

From the repository root:

```sh
uv run --project python --extra mcp seenx-mcp --library /path/to/library --principal assistant-a
```

The optional `mcp` extra uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x), `mcp>=1.28,<2`, with its low-level server and stdio lifecycle. The major-version bound keeps this adapter on the documented v1 SDK API; this SDK version is separate from the seenX version-1 engine contract. Dependencies were not resolved and `uv.lock` was not refreshed during this code-only change; the next unlocked `uv` invocation resolves the extra. No SDK is needed for the owner CLI or `seenx-engine`.

Generic stdio MCP client configuration (replace both absolute paths):

```json
{
  "mcpServers": {
    "seenx": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/to/seenX/python", "--extra", "mcp", "seenx-mcp", "--library", "/path/to/library", "--principal", "assistant-a"]
    }
  }
}
```

`--principal` is required and validated before opening a library; missing/blank values exit nonzero with a stderr error. There is no `--trusted-local` option. An ungranted principal sees no search hits and cannot fetch any memory. Assign source/collection grants through the owner CLI above.

The tool list is exactly `search` and `fetch`. `search` accepts the `memory.search` parameters below. `fetch` accepts `asset_id`, optional `revision_id`, and `include_image`; adding exactly one `region_id` or `observation_id` requires `revision_id` and selects `region.fetch`. Tool text contains the version-1 response envelope, including trace ID and sanitized errors; failures set MCP `isError`. Requested PNGs become MCP image content blocks, with dimensions/hash retained in text and no duplicate base64. No resources, prompts, writes, imports, removals, grants, or collection tools are registered. Retrieved text/images remain untrusted data. SDK/stdin buffering precedes the engine's request-size check; these are contract payload bounds, not a transport-memory sandbox.

## Framing and types

Every request is one UTF-8 JSON object ending in a newline:

```json
{"version":1,"id":"request-1","method":"memory.search","params":{"query":"keep this spacing","limit":5}}
```

All four top-level fields are required; extra fields are rejected. `id` is a nonempty Unicode string of at most 128 characters. IDs in responses match the request, while `trace_id` connects that operation to local diagnostic events. Invalid envelopes may return a null ID when a valid client ID couldn't be established.

Duplicate JSON keys, nonfinite numbers, malformed UTF-8, batches, and unsupported versions are rejected. Parameter fields are validated per method; unknown parameters aren't silently ignored. Empty lines are ignored. A final complete JSON object at EOF can omit its newline.

There is exactly one response per nonempty request. Stdout contains only JSON lines. Diagnostics are written separately through our existing local logger. `--debug` adds diagnostic detail; `--no-log` disables persistent logs. Query text, note bodies, image data, client IDs, and raw exception messages aren't included in request logs.

## Methods

### `engine.info`

Requires empty `params`. Returns the supported protocol/schema versions, method names, and limits. A native client should handshake before issuing other operations and handle an unsupported version explicitly.

### `memory.search`

Required: `query`. Optional: `match` (`phrase` or `all`), `limit` (1–100), `asset_id`, `revision_id`, and `current_only` (boolean).

The result is the catalog's list of evidence hits: stable IDs, matched field, excerpt, provenance, normalized target, and FTS5 ranking information. All catalog query limits and tokenization rules apply. It doesn't run visual search or OCR. See [catalog search](catalog-search.md).

### `memory.fetch`

Required: `asset_id`. Optional: `revision_id` and `include_image` (boolean, default false).

It fetches the current revision unless another revision is named. The revision must belong to the asset. The response contains saved annotations, OCR observations, revision history, provenance, and snapshot verification information.

Internal source/snapshot paths are removed from this projection; `asset.source_name` retains the original basename. This doesn't make fetched content anonymous—the client intentionally requested personal memory context. Contents are returned as data, never executed as instructions.

With `include_image: true`, `image` contains an orientation-corrected PNG attachment. This is prepared in memory from the stored image, not a generated picture or another file on disk.

### `region.fetch`

Required: `asset_id`, `revision_id`, and exactly one of `region_id` or `observation_id`. Optional: `include_image` (default false).

The engine finds that saved target within the specified revision. A region or observation from another revision/asset returns `not_found`. Clients cannot supply raw crop coordinates.

Results include the saved target, its annotation or OCR context, and `reference_image` dimensions/hash. `pixel_bounds` are half-open bounds on the full EXIF-corrected reference image: left/top inclusive, right/bottom exclusive. A point becomes a one-pixel crop, including at image edges. An OCR observation keeps its unverified provenance.

With `include_image: true`, the attachment contains that crop. Its dimensions are `right - left` and `bottom - top`. Normalized targets still refer to the parent image, not the crop. A client overlaying more context on a crop needs to account for the crop's left/top offset.

## Image attachment shape

```json
{
  "media_type": "image/png",
  "encoding": "base64",
  "width": 300,
  "height": 100,
  "sha256": "hash-of-delivered-png-bytes",
  "data": "base64-encoded-bytes"
}
```

Base64 represents binary bytes as JSON-compatible text. It isn't encryption and increases payload size. The attachment hash is for the delivered PNG bytes; the catalog revision hash is for the original snapshot bytes. Re-encoding or cropping changes the former while preserving the latter as the source identity.

Images are not silently resized to fit limits, because that would change the relationship between image pixels and saved targets. A client can fetch metadata without an attachment or request a smaller saved region. No server-generated thumbnails or image files are persisted by these methods.

## Bounds and error behavior

| Resource | Limit |
| --- | --- |
| Request frame, including line ending | 64 KiB |
| Encoded JSON response, excluding line ending | 8 MiB |
| Snapshot bytes read for verification | 32 MiB |
| Whole-image decoded pixel count for attachments | 20 million |
| PNG attachment bytes before base64 | 4 MiB |
| Search results | 100 |

The PNG writer stops when its attachment budget is exceeded. Large source images can be rejected even for a small crop because Pillow needs to decode the parent image. Response limits include memory context and base64 data. There is no silent truncation of a requested memory: over-budget responses return an error. These are payload/decoding bounds, not a general process-memory sandbox or per-request execution deadline.

Error responses have `error` instead of `result`:

```json
{"version":1,"id":"request-1","trace_id":"...","error":{"code":"not_found","message":"Requested memory, revision, or target was not found"}}
```

Codes include `invalid_json`, `invalid_request`, `unsupported_version`, `unknown_method`, `invalid_parameters`, `request_too_large`, `response_too_large`, `resource_limit`, `access_denied`, `not_found`, `evidence_unavailable`, `storage_error`, and `internal_error`. Clients should branch on the code, not parse the message. Raw exception details and filesystem paths aren't echoed into wire errors.

An invalid request doesn't terminate the session. An overlong input line is drained to its newline before reading the next request, so subsequent frames remain aligned. Closing stdin ends the process cleanly. Startup failure returns a nonzero exit code and a short stderr diagnostic. A native client must handle process exit and cancellation as well as method errors.

## Native integration sequence

1. Launch the first-party helper with the explicitly selected library and `--trusted-local`, and keep stdin open.
2. Handshake with `engine.info` and check protocol support.
3. Send a search request and decode evidence hits.
4. Fetch the selected memory or saved region by its returned IDs.
5. Decode an optional PNG and display it with its explicit dimensions/coordinate context.
6. On shutdown, close stdin and wait for exit. Handle transport failure without discarding an unsaved native draft.

Requests are processed sequentially in this slice. There is no request cancellation message, background indexing queue, or automatic native-library import. The native development library is still separate; migrating its captures and adding deliberate write operations need an explicit next integration step. Assistant integration uses the grant-scoped MCP adapter above.

## Verification and learning concepts

Tests cover framing, Unicode/JSON validation, unsupported writes, strict parameter types, ID ownership, source-path omission, point/region bounds, OCR provenance, image/response limits, failure recovery, and diagnostic-content omission. Fake image objects exercise encoding paths without generated bitmap fixtures. A real-process check used an existing practice image and decoded both the full PNG and a saved-region crop; invalid JSON recovery and clean EOF were also verified. Test records were isolated and originals stayed unchanged.

Concepts to look up: `stdin stdout pipes`, `JSON Lines framing`, `versioned API contracts`, `request correlation IDs`, `base64`, `typed error codes`, and `process lifecycle`. The key idea is a stable agreement between the interface and engine, even while their implementations evolve.
