# One local interface for search and evidence fetch

We now have a versioned read-only interface over the Python catalog. A local client can launch `seenx-engine`, send JSON requests on stdin, and read JSON responses on stdout. The process keeps one catalog connection open and handles requests sequentially until stdin closes.

This is the first internal app integration boundary. The native app's optional **Open Python Library…** browser now uses it through [SeenXEngineClient](../../packages/SeenXEngineClient); see [the native integration lesson](../../docs/native-engine.md). Its main capture launcher/library remain separate. This isn't an HTTP endpoint, an MCP server, or a JSON-RPC implementation. There are no new Python dependencies, network listeners, or model downloads. Keeping the retrieval functions behind this boundary lets a later transport or native implementation preserve the same behavior.

## Start with a handshake

From the repository root:

```sh
uv sync --project python --all-extras --locked
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
    "catalog_schema_version": 3,
    "read_only_requests": true,
    "methods": ["engine.info", "memory.fetch", "memory.search", "region.fetch"],
    "limits": {}
  }
}
```

The actual `limits` object lists the byte, pixel, and result caps below. The protocol version identifies the wire contract; the catalog schema version identifies the database layout. They serve different purposes and needn't have the same number.

For another library, launch with `--library /path/to/library`. A request cannot change that root or supply an arbitrary filesystem path. The local launcher chooses the library; this version grants that trusted process access to its whole selected library. Collection/source grants, revocation, MCP client setup, and untrusted remote access remain separate work.

Requests are read-only. Startup can initialize or migrate the catalog and its derived index, just like the existing CLI. Use `seenx-memory` for deliberate import, annotation, editing, removal, OCR, or reindexing. No write methods are exposed through this protocol yet.

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

Codes include `invalid_json`, `invalid_request`, `unsupported_version`, `unknown_method`, `invalid_parameters`, `request_too_large`, `response_too_large`, `resource_limit`, `not_found`, `evidence_unavailable`, `storage_error`, and `internal_error`. Clients should branch on the code, not parse the message. Raw exception details and filesystem paths aren't echoed into wire errors.

An invalid request doesn't terminate the session. An overlong input line is drained to its newline before reading the next request, so subsequent frames remain aligned. Closing stdin ends the process cleanly. Startup failure returns a nonzero exit code and a short stderr diagnostic. A native client must handle process exit and cancellation as well as method errors.

## Native integration sequence

1. Launch the helper with the explicitly selected library and keep stdin open.
2. Handshake with `engine.info` and check protocol support.
3. Send a search request and decode evidence hits.
4. Fetch the selected memory or saved region by its returned IDs.
5. Decode an optional PNG and display it with its explicit dimensions/coordinate context.
6. On shutdown, close stdin and wait for exit. Handle transport failure without discarding an unsaved native draft.

Requests are processed sequentially in this slice. There is no request cancellation message, background indexing queue, or automatic native-library import. The native development library is still separate; migrating its captures and adding deliberate write operations need an explicit next integration step. Don't expose this whole-library internal helper directly as an assistant tool without adding the planned grants and adapter.

## Verification and learning concepts

Tests cover framing, Unicode/JSON validation, unsupported writes, strict parameter types, ID ownership, source-path omission, point/region bounds, OCR provenance, image/response limits, failure recovery, and diagnostic-content omission. Fake image objects exercise encoding paths without generated bitmap fixtures. A real-process check used an existing practice image and decoded both the full PNG and a saved-region crop; invalid JSON recovery and clean EOF were also verified. Test records were isolated and originals stayed unchanged.

Concepts to look up: `stdin stdout pipes`, `JSON Lines framing`, `versioned API contracts`, `request correlation IDs`, `base64`, `typed error codes`, and `process lifecycle`. The key idea is a stable agreement between the interface and engine, even while their implementations evolve.
