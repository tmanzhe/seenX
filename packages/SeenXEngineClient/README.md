# SeenXEngineClient

A small Foundation-only Swift client for the Python engine's version 1 JSON Lines protocol. It runs on macOS 14 or later and has no external dependencies. See the [engine contract](../../python/docs/engine-contract.md) for request shapes and catalog behavior.

```swift
import SeenXEngineClient

let client = try await EngineClient.launch(configuration: .init(
    executableURL: repository.appendingPathComponent("python/.venv/bin/python"),
    arguments: ["-m", "seenx.engine_stdio", "--library", library.path, "--trusted-local", "--no-log"],
    currentDirectoryURL: repository
))
let hits = try await client.search("remember this")
if let hit = hits.first {
    let memory = try await client.fetchMemory(
        assetID: hit.assetID, revisionID: hit.revisionID, includeImage: true
    )
    // memory.image?.data contains PNG bytes; decode and check dimensions before display.
}
await client.close()
```

The caller explicitly chooses a trusted executable and library. This package doesn't discover a repository, install Python, import native captures, or grant access to assistants. By default it inherits the app's environment with `PYTHONPATH` and `PYTHONHOME` removed. A supplied environment replaces that default.

Launching includes a capabilities handshake. Requests run sequentially on a worker queue, including pipe reads, JSON decoding, and base64 decoding. Each active request has a timeout; time spent waiting behind another request isn't counted toward that deadline. Requests and responses have the same 64 KiB and 8 MiB bounds as the engine. Attachments are checked for encoding, type, dimensions, and byte budget. The package doesn't render PNGs or independently verify their SHA-256 hashes.

For local annotation editing, add `--allow-writes` to the trusted-local arguments and set `Configuration.allowsWrites = true`. The default client rejects a writable handshake. `canWriteAnnotations` checks all three advertised annotation methods; `createAnnotation`, `updateAnnotation`, and `deleteAnnotation` return stable IDs, after which the caller refreshes memory. `buildPayload(assetID:revisionID:regionIDs:imageMode:)` calls the existing read-only H3 builder; `LLMPayload.clipboardJSON()` preserves the exact metadata text and `schema_version`/`mimeType` wire keys. Older engines remain usable for search/fetch when optional capabilities are absent.

Method errors preserve the connection. Protocol errors, EOF, timeouts, and task cancellation close the session so a late response can't be mistaken for a subsequent result. Cancellation invalidates queued operations too. The protocol has no cancellation method. To retry, start a new client. Closing waits for a pending bounded request, closes stdin, gives the child time to exit, then escalates to termination and SIGKILL if needed. Process termination is observed through a bounded completion handler. Dropping an unclosed client schedules the same cleanup off the main thread; prefer explicit `await close()`.

The client doesn't log requests, responses, environment variables, paths, or diagnostic contents. Child stderr goes to a null sink so it cannot fill a pipe or leak contents through a client error. `EngineClientError.engine` retains the server's error code, message, and trace ID for deliberate handling; its default localized description omits the message. The engine's own logging follows its launch flags.

Run the shell-helper transport tests from the repository root:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  xcrun swift test --package-path packages/SeenXEngineClient --build-system native
```

These tests use subprocess pipes and text fixtures without creating images or requiring Python. The native app's opt-in integration test covers the actual Python engine and an existing local image.
