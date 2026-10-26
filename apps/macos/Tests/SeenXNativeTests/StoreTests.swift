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
