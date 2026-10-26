# Connecting the Mac app to Python

We already had two useful pieces: a native screenshot app, and a Python catalog that understands saved images, notes, revisions, and recognized text. They were separate programs with separate libraries. This step gives the native app a way to browse the Python library without moving anyone's captures.

## What changed, in order

1. **Preserve the native baseline.** The capture app, annotation editor, storage checks, and existing shortcuts were committed separately. That gives us a clear point to compare against if integration breaks a capture behavior.
2. **Add a Swift client package.** [SeenXEngineClient](../packages/SeenXEngineClient) launches the existing Python helper and communicates through process pipes. It imports Foundation and Darwin; there are no downloaded Swift packages or new Python dependencies.
3. **Agree on the message format.** The client first sends `engine.info` and checks the protocol and supported methods. Requests carry an ID; the response must carry that same ID. Typed Swift models decode the search hits, memory context, regions, and attachments.
4. **Add an explicit browser.** The menu-bar action **Open Python Library…** opens a separate development browser. You choose the repository and existing catalog, then search and open evidence. This doesn't replace the main capture launcher.
5. **Handle failures as part of the feature.** Requests run off the main UI thread. A timeout, closed pipe, invalid response, or exited helper ends that connection. A normal method error can leave it usable. Closing the browser disconnects it; an old request cannot repopulate a closed or newly connected window.
6. **Check real behavior.** Helper-process tests cover the client boundary. Native model tests cover closing/reconnecting and failure state. An opt-in integration check seeds an isolated catalog with an existing image, then exercises actual Swift → Python search, full-image fetch, OCR-region fetch, and point/region crops.

## Try it

From the repository root, prepare Python once:

```sh
uv sync --project python --all-extras --locked
uv run --project python seenx-memory list
```

If that library is empty, import an existing image and save a note using the [catalog lesson](../python/docs/catalog.md). Images in the input folder don't automatically become catalog memories.

Build and open the native app:

```sh
bash apps/macos/build.sh
open apps/macos/.build/app/seenX.app
```

If an older copy is running, quit it through the app first so it can protect any unsaved annotation draft. Then open the new build.

1. Open the seenX menu-bar menu and choose **Open Python Library…**.
2. Click **Connect…** and select the seenX repository. This selects its prepared `python/.venv/bin/python` helper environment.
3. Select the existing folder containing `catalog.sqlite3`, normally `python/library`. The chooser starts there. It doesn't import your native captures.
4. Enter words from a saved note, selection, or OCR observation and press **Search** or Return.
5. Click a match. The app fetches its exact saved revision and shows the matching target on the full image. You can switch to **Saved region** to fetch only that saved crop.
6. Choose **Disconnect**, or close the browser, when finished. After a helper failure, use **Connect…** again.

Search uses the existing FTS5 phrase mode. It doesn't run CLIP, perform OCR, search filenames, or understand synonyms. Results are evidence hits: one image can appear once for its note and again for a matching OCR line. Earlier revisions are labeled. The main capture launcher still searches its native development library using its existing matching rules.

## Why pipes, and what is a client?

The Python engine owns retrieval behavior. The Swift **client** asks it to perform an operation and decodes the answer. This is similar to calling a function, except the call crosses into another running program.

The operating system supplies two pipes: one carries requests into the helper's standard input, and the other carries responses out of its standard output. Each message is one JSON line. The helper stays running while the browser is connected, rather than starting a fresh Python process for every search.

No HTTP server is needed for this local development connection. The client code lives in its own [Swift package](../packages/SeenXEngineClient); its contract can be tested independently of windows, permission dialogs, and capture shortcuts. Python remains our behavior reference while we decide which pieces belong in the eventual native engine.

The helper is launched from the repository you deliberately select. The library directory is a launch argument, not something a search request can change. This connection is trusted local access to that whole catalog; assistant grants and an MCP adapter haven't been added.

## Images and coordinates

The stored snapshot remains the original imported bytes. When requested, Python decodes those bytes, corrects the EXIF orientation, optionally crops a saved target, and returns PNG bytes in memory. These aren't newly imagined pictures, generated fixtures, or persisted thumbnail files.

Base64 allows those bytes to travel inside JSON. Swift decodes them, checks the image format and dimensions, and displays them. The preview computes the displayed image's actual fitted size before placing the normalized target, so a highlight follows the image when the window changes size. A crop is displayed without reapplying the parent-image coordinates.

The delivered PNG has its own hash. The catalog revision hash still identifies the original snapshot. Re-encoding an image changes its bytes even when it depicts the same thing.

## Failure handling and logging

The client serializes requests on a worker queue, bounds request/response sizes, correlates response IDs, and checks the protocol envelope. Its default request deadline is 15 seconds. Timeout or cancellation closes the session because a late response could otherwise be mistaken for the next request's answer. Shutdown closes stdin, allows the helper to finish, and escalates if it doesn't exit.

The browser tracks a connection generation. Closing or replacing the connection changes that generation; asynchronous work from an older generation can't overwrite the current screen. Fatal transport errors change the browser to disconnected while preserving the typed query. None of these operations touches the capture editor or its unsaved draft.

Python's normal local JSONL diagnostics remain enabled for this browser. They record engine method names, correlation IDs, timings, and outcome/error codes. Query text, note bodies, paths, and image bytes aren't logged by the client. Helper stderr is discarded rather than copied into a UI error or another log. See [the engine contract](../python/docs/engine-contract.md) for exact limits and error codes.

Fetch/search requests are read-only. Starting the helper can initialize/migrate an existing catalog and its derived index under the same rules as the CLI. Selecting a missing catalog is rejected before launch. This development browser doesn't expose annotation writes, deletion, export, or migration from the native manifest.

## Run the checks

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift test --package-path packages/SeenXEngineClient
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift test --package-path apps/macos
```

The real-engine native test is skipped unless you supply both environment variables. Replace the example paths with an existing prepared interpreter and image; the image isn't modified or committed:

```sh
SEENX_TEST_PYTHON="$PWD/python/.venv/bin/python" \
SEENX_TEST_IMAGE="$PWD/practice-images/your-existing-image.jpeg" \
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
xcrun swift test --package-path apps/macos --filter EngineBrowserTests
```

The check imports into a temporary library, creates test notes/OCR observations there, and removes that isolated library afterward. Its OCR text is a contract fixture, not a claim that Vision recognized those words. Original image bytes are compared before and after.

Concepts to learn next: **Swift packages**, **Codable/Decodable**, **async/await**, **the main actor**, **process pipes**, **timeouts**, **request IDs**, and **stale asynchronous results**. On the Python side, follow **JSON serialization**, **context managers**, **exceptions**, and **database transactions** through the [engine lesson](../python/docs/engine-contract.md).

Next comes an explicit import/write design for native captures. The two libraries need a deliberate mapping for image revisions, OCR boxes, notes, and highlights before the main launcher can rely on one shared catalog. Portable export and assistant access remain separate roadmap steps.
