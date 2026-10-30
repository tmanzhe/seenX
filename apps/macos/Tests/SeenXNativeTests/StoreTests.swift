import AppKit
import XCTest
@testable import SeenXNative

final class StoreTests: XCTestCase {
    @MainActor
    func testSaveReloadSearchAndOCRUpdate() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = try makeImage(in: directory)
        let store = try CaptureStore(directory: directory.appendingPathComponent("library"))
        let box = TextBox(text: "Database indexing", x: 0.2, y: 0.3, width: 0.4, height: 0.1)
        let saved = try store.save(image: source, note: "Read this tomorrow", boxes: [box], highlights: [Highlight(boxes: [box])])
        XCTAssertTrue(FileManager.default.fileExists(atPath: store.imageURL(for: saved).path))
        let reload = try CaptureStore(directory: store.directory)
        XCTAssertEqual(reload.captures, store.captures)
        XCTAssertEqual(reload.captures.first?.ocrComplete, false)
        XCTAssertEqual(reload.results(for: "DATABASE tomorrow").map(\.id), [saved.id])
        XCTAssertTrue(reload.results(for: "missing").isEmpty)
        try reload.updateOCR(id: saved.id, boxes: [TextBox(text: "query plans", x: 0, y: 0, width: 1, height: 1)])
        let secondReload = try CaptureStore(directory: store.directory)
        XCTAssertEqual(secondReload.results(for: "plans").count, 1)
        XCTAssertEqual(secondReload.captures.first?.highlights.first?.text, box.text)
        XCTAssertEqual(secondReload.captures.first?.note, "Read this tomorrow")
        XCTAssertEqual(secondReload.captures.first?.ocrComplete, true)
        XCTAssertEqual(secondReload.captures.first?.boxes?.first?.text, "query plans")
    }

    @MainActor
    func testInvalidCaptureDoesNotEnterLibrary() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = try CaptureStore(directory: directory)
        let invalid = directory.appendingPathComponent("invalid.png")
        try Data("not an image".utf8).write(to: invalid)
        XCTAssertThrowsError(try store.save(image: invalid, note: "keep me", boxes: [], highlights: []))
        XCTAssertTrue(store.captures.isEmpty)
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.appendingPathComponent("library.json").path))
    }

    @MainActor
    func testCorruptManifestIsNotSilentlyOverwritten() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let manifest = directory.appendingPathComponent("library.json")
        let original = Data("broken library".utf8)
        try original.write(to: manifest)
        XCTAssertThrowsError(try CaptureStore(directory: directory))
        XCTAssertEqual(try Data(contentsOf: manifest), original)
    }

    @MainActor
    func testManifestWriteFailureDoesNotPublishOrLeaveNewImage() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = try makeImage(in: directory)
        let store = try CaptureStore(directory: directory.appendingPathComponent("library"))
        // A directory at the manifest path makes the atomic manifest replacement fail.
        try FileManager.default.createDirectory(at: store.directory.appendingPathComponent("library.json"), withIntermediateDirectories: true)
        XCTAssertThrowsError(try store.save(image: source, note: "do not discard", boxes: [], highlights: []))
        XCTAssertTrue(store.captures.isEmpty)
        let remaining = try FileManager.default.contentsOfDirectory(atPath: store.directory.path)
        XCTAssertEqual(remaining, ["library.json"])
        XCTAssertTrue(FileManager.default.fileExists(atPath: source.path))
    }

    @MainActor
    func testMissingOriginalDoesNotLoseNoteOnReload() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = try makeImage(in: directory)
        let store = try CaptureStore(directory: directory.appendingPathComponent("library"))
        let saved = try store.save(image: source, note: "A durable note", boxes: [], highlights: [])
        try FileManager.default.removeItem(at: store.imageURL(for: saved))
        let reloaded = try CaptureStore(directory: store.directory)
        XCTAssertEqual(reloaded.results(for: "durable").first?.note, "A durable note")
    }

    @MainActor
    func testExplicitImportRoundTripsAllDataAndOriginalBytesAfterReload() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = try makeImage(in: directory)
        let original = try Data(contentsOf: source)
        let writer = try CaptureStore(directory: directory.appendingPathComponent("writer"))
        let selected = TextBox(text: "選択 café\nline two", x: 0.125, y: 0.25, width: 0.5, height: 0.125)
        let unselected = TextBox(text: "OCR outside highlights", x: 0, y: 0.75, width: 1, height: 0.25)
        let highlights = [Highlight(boxes: [selected]), Highlight(boxes: [unselected, selected])]
        let note = "  A note 📝\nKeep whitespace.  "
        let saved = try writer.save(image: source, note: note, boxes: [selected, unselected],
                                    highlights: highlights, ocrComplete: true)
        XCTAssertEqual(saved.boxes, [selected, unselected])
        XCTAssertEqual(saved.highlights, highlights)
        XCTAssertEqual(saved.note, note)
        XCTAssertEqual(saved.text, [selected.text, unselected.text].joined(separator: " "))
        let revision = try XCTUnwrap(saved.imageRevision)
        XCTAssertEqual(revision.pixelWidth, 12)
        XCTAssertEqual(revision.pixelHeight, 12)
        XCTAssertEqual(revision.exifOrientation, 1)
        XCTAssertEqual(revision.sha256.count, 64)

        let expected = CaptureImport(capture: saved, originalImage: original)
        XCTAssertEqual(try CaptureStore(directory: writer.directory).readCapture(id: saved.id), expected)
        let destination = try CaptureStore(directory: directory.appendingPathComponent("destination"))
        XCTAssertEqual(try destination.importCapture(expected), saved)
        // Neither the source path nor the first library is required for read-back.
        try FileManager.default.removeItem(at: source)
        try FileManager.default.removeItem(at: writer.directory)
        let reopened = try CaptureStore(directory: destination.directory)
        let actual = try reopened.readCapture(id: saved.id)
        XCTAssertEqual(actual.originalImage, original)
        XCTAssertEqual(actual.capture, expected.capture)
        XCTAssertEqual(actual, expected)
        XCTAssertThrowsError(try reopened.importCapture(expected))
        XCTAssertEqual(reopened.captures, [saved])
        XCTAssertEqual(try reopened.readCapture(id: saved.id), expected)
    }

    @MainActor
    func testReadBackDetectsChangedOriginalAndPreservesMetadata() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let source = try makeImage(in: directory)
        let store = try CaptureStore(directory: directory.appendingPathComponent("library"))
        let saved = try store.save(image: source, note: "Retain this evidence", boxes: [], highlights: [])
        try Data("changed original".utf8).write(to: store.imageURL(for: saved))
        let reopened = try CaptureStore(directory: store.directory)
        XCTAssertThrowsError(try reopened.readCapture(id: saved.id))
        XCTAssertEqual(reopened.captures, [saved])
    }

    @MainActor
    func testLegacyManifestKeepsUnknownOCRBoxesAndRevisionUnknown() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let id = UUID()
        let json = """
        [{"id":"\(id.uuidString)","createdAt":0,"imageName":"legacy.png",
          "note":"Legacy note","text":"Legacy OCR","highlights":[]}]
        """
        try Data(json.utf8).write(to: directory.appendingPathComponent("library.json"))
        let store = try CaptureStore(directory: directory)
        XCTAssertNil(store.captures.first?.boxes)
        XCTAssertNil(store.captures.first?.imageRevision)
        XCTAssertEqual(store.captures.first?.text, "Legacy OCR")
        XCTAssertEqual(store.captures.first?.note, "Legacy note")
    }

    @MainActor
    private func makeImage(in directory: URL) throws -> URL {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 12, pixelsHigh: 12, bitsPerSample: 8,
                                      samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                      bytesPerRow: 0, bitsPerPixel: 0)!
        let url = directory.appendingPathComponent("source.png")
        try XCTUnwrap(bitmap.representation(using: .png, properties: [:])).write(to: url)
        return url
    }
}
