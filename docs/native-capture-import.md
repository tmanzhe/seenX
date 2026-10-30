# Native capture import slice

`CaptureStore` remains the owner of the separate Swift capture library. This
slice extends its existing `library.json` records; it does not write to the
Python SQLite catalog or change the read-only engine protocol.

- `save(image:note:boxes:highlights:ocrComplete:)` snapshots the original bytes,
  retains every OCR box, and creates capture/revision identities. Image metadata
  includes SHA-256, EXIF orientation, and orientation-corrected pixel dimensions.
- `importCapture(_:)` accepts a `CaptureImport` (a complete `SavedCapture` plus
  original `Data`). It preserves all supplied IDs, dates, text, coordinates,
  ordering, OCR state, and revision metadata. Duplicate capture IDs/image names
  are errors rather than implicit updates. Image names must be single filenames.
- `readCapture(id:)` returns the same record and original bytes. When revision
  metadata exists, it verifies image integrity and dimensions. Missing or damaged
  images throw without removing notes or targets.

The image is written before the manifest. Manifest replacement is atomic; a
reported manifest failure removes the newly written image and leaves published
records unchanged. A process interruption can leave an unreferenced object.
This is not a cross-process transaction: callers must use one store owner per
library, as the current app does.

Assumptions and schema gaps:

- Inputs use the existing normalized top-left coordinates over the full
  orientation-corrected image. Import preserves them without conversion.
- Legacy manifests lack full OCR boxes and revision metadata. These remain nil;
  the importer does not fabricate missing evidence or provenance.
- The native schema has one whole-capture note and box-based highlights. It has
  no independent point/region annotation records, OCR configuration/provenance
  history, source/app/URL fields, or separate asset/revision tables. Existing
  `updateOCR` still replaces current OCR, while highlight box snapshots survive.
- The JSON manifest has additive optional fields rather than a schema-version
  migration system. SQLite/catalog migration and shared write protocol design
  remain separate work.

`StoreTests` includes an explicit import/reopen/read-back round trip comparing
all record data and exact original bytes, plus legacy and integrity coverage.
These tests were authored but not run for this slice, per request.
