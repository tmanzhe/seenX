import AppKit
import Combine
import CryptoKit
import ImageIO

@MainActor
final class CaptureStore: ObservableObject {
    @Published private(set) var captures: [SavedCapture] = []
    let directory: URL
    private let manifest: URL

    init(directory: URL? = nil) throws {
        self.directory = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("seenX Native", isDirectory: true)
        manifest = self.directory.appendingPathComponent("library.json")
        try FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
        if FileManager.default.fileExists(atPath: manifest.path) {
            captures = try JSONDecoder().decode([SavedCapture].self, from: Data(contentsOf: manifest))
        }
    }

    func imageURL(for capture: SavedCapture) -> URL { directory.appendingPathComponent(capture.imageName) }

    func results(for query: String) -> [SavedCapture] {
        let terms = query.split(whereSeparator: \.isWhitespace).map(String.init)
        return captures.filter { capture in
            let content = [capture.note, capture.text, capture.highlights.map(\.text).joined(separator: " ")].joined(separator: " ")
            return terms.allSatisfy { content.localizedCaseInsensitiveContains($0) }
        }
    }

    @discardableResult
    func save(image source: URL, note: String, boxes: [TextBox], highlights: [Highlight], ocrComplete: Bool = false) throws -> SavedCapture {
        let bytes = try Data(contentsOf: source)
        let id = UUID()
        let capture = SavedCapture(id: id, createdAt: Date(), imageName: "\(id.uuidString).original", note: note,
                                   text: boxes.map(\.text).joined(separator: " "), highlights: highlights,
                                   ocrComplete: ocrComplete, boxes: boxes,
                                   imageRevision: try Self.revision(for: bytes))
        return try importCapture(CaptureImport(capture: capture, originalImage: bytes))
    }

    /// Inserts one complete record without regenerating IDs, text, timestamps, or targets.
    /// Originals are copied verbatim; a manifest failure rolls back the new object.
    @discardableResult
    func importCapture(_ input: CaptureImport) throws -> SavedCapture {
        let capture = input.capture
        guard !captures.contains(where: { $0.id == capture.id }),
              !captures.contains(where: { $0.imageName == capture.imageName }),
              !capture.imageName.isEmpty,
              capture.imageName != ".", capture.imageName != "..",
              !capture.imageName.contains("/"), !capture.imageName.contains("\\") else {
            throw CocoaError(.fileWriteInvalidFileName)
        }
        let actual = try Self.revision(for: input.originalImage)
        if let expected = capture.imageRevision {
            guard expected.sha256 == actual.sha256,
                  expected.pixelWidth == actual.pixelWidth,
                  expected.pixelHeight == actual.pixelHeight,
                  expected.exifOrientation == actual.exifOrientation else {
                throw CocoaError(.fileReadCorruptFile)
            }
        }
        let target = imageURL(for: capture)
        // Never overwrite an existing object, including an orphan from an interrupted save.
        try input.originalImage.write(to: target, options: .withoutOverwriting)
        let updated = [capture] + captures
        do {
            try JSONEncoder().encode(updated).write(to: manifest, options: .atomic)
        } catch {
            try? FileManager.default.removeItem(at: target)
            throw error
        }
        captures = updated
        return capture
    }

    /// Reads authoritative metadata and the exact encoded original; missing/corrupt
    /// originals fail explicitly without deleting the surviving notes or targets.
    func readCapture(id: UUID) throws -> CaptureImport {
        guard let capture = captures.first(where: { $0.id == id }) else {
            throw CocoaError(.fileNoSuchFile)
        }
        let bytes = try Data(contentsOf: imageURL(for: capture))
        if let expected = capture.imageRevision {
            let actual = try Self.revision(for: bytes)
            guard expected.sha256 == actual.sha256,
                  expected.pixelWidth == actual.pixelWidth,
                  expected.pixelHeight == actual.pixelHeight,
                  expected.exifOrientation == actual.exifOrientation else {
                throw CocoaError(.fileReadCorruptFile)
            }
        }
        return CaptureImport(capture: capture, originalImage: bytes)
    }

    private static func revision(for bytes: Data) throws -> CaptureImageRevision {
        guard let source = CGImageSourceCreateWithData(bytes as CFData, nil),
              CGImageSourceCreateImageAtIndex(source, 0, nil) != nil,
              let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
              let width = properties[kCGImagePropertyPixelWidth] as? Int,
              let height = properties[kCGImagePropertyPixelHeight] as? Int,
              width > 0, height > 0 else {
            throw CocoaError(.fileReadCorruptFile)
        }
        let orientation = properties[kCGImagePropertyOrientation] as? Int ?? 1
        let swapsAxes = (5...8).contains(orientation)
        return CaptureImageRevision(id: UUID(), sha256: SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined(),
                                    pixelWidth: swapsAxes ? height : width,
                                    pixelHeight: swapsAxes ? width : height, exifOrientation: orientation)
    }

    func updateOCR(id: UUID, boxes: [TextBox]) throws {
        guard let index = captures.firstIndex(where: { $0.id == id }) else { return }
        var updated = captures
        updated[index].text = boxes.map(\.text).joined(separator: " ")
        updated[index].boxes = boxes
        updated[index].ocrComplete = true
        try JSONEncoder().encode(updated).write(to: manifest, options: .atomic)
        captures = updated
    }
}
