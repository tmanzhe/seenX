import AppKit
import Combine

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
        guard let image = NSImage(contentsOf: source), image.size.width > 0, image.size.height > 0 else {
            throw CocoaError(.fileReadCorruptFile)
        }
        let id = UUID()
        let capture = SavedCapture(id: id, createdAt: Date(), imageName: "\(id.uuidString).png", note: note,
                                   text: boxes.map(\.text).joined(separator: " "), highlights: highlights, ocrComplete: ocrComplete)
        let target = imageURL(for: capture)
        try Data(contentsOf: source).write(to: target, options: .atomic)
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

    func updateOCR(id: UUID, boxes: [TextBox]) throws {
        guard let index = captures.firstIndex(where: { $0.id == id }) else { return }
        var updated = captures
        updated[index].text = boxes.map(\.text).joined(separator: " ")
        updated[index].ocrComplete = true
        try JSONEncoder().encode(updated).write(to: manifest, options: .atomic)
        captures = updated
    }
}
