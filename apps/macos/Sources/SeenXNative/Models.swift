import Foundation

struct TextBox: Codable, Identifiable, Equatable {
    var id = UUID()
    var text: String
    // Coordinates use a normalized top-left origin, independent of display scale.
    var x: Double
    var y: Double
    var width: Double
    var height: Double
    var rect: CGRect { CGRect(x: x, y: y, width: width, height: height) }
}

struct Highlight: Codable, Identifiable, Equatable {
    var id = UUID()
    var boxes: [TextBox]
    var text: String { boxes.map(\.text).joined(separator: " ") }
}

/// Immutable evidence metadata. Dimensions describe the orientation-corrected image;
/// the stored original bytes retain their orientation metadata.
struct CaptureImageRevision: Codable, Equatable {
    var id: UUID
    var sha256: String
    var pixelWidth: Int
    var pixelHeight: Int
    var exifOrientation: Int
}

/// A lossless native-library record and its original encoded image, for explicit import/read-back.
struct CaptureImport: Equatable {
    var capture: SavedCapture
    var originalImage: Data
}

struct SavedCapture: Codable, Identifiable, Equatable {
    var id: UUID
    var createdAt: Date
    var imageName: String
    var note: String
    var text: String
    var highlights: [Highlight]
    // Optional for compatibility with manifests written by the first prototype.
    var ocrComplete: Bool? = nil
    // nil means unavailable in a legacy manifest, rather than an empty OCR result.
    var boxes: [TextBox]? = nil
    var imageRevision: CaptureImageRevision? = nil
    var title: String {
        if let first = note.split(separator: "\n").first, !first.isEmpty { return String(first.prefix(80)) }
        if !text.isEmpty { return String(text.prefix(80)) }
        return "Screenshot"
    }
}

enum SubmitAction: Equatable { case committedHighlight, save }

/// Pure editor transitions; keeping pending selection separate prevents an accidental save
/// on the same Command-Return that finishes a highlight.
struct AnnotationState: Equatable {
    var highlights: [Highlight] = []
    var pending: [TextBox] = []
    var selected: UUID?

    mutating func submit() -> SubmitAction {
        guard !pending.isEmpty else { return .save }
        let highlight = Highlight(boxes: pending)
        highlights.append(highlight)
        pending = []
        selected = highlight.id
        return .committedHighlight
    }

    mutating func delete() {
        if !pending.isEmpty { pending = []; return }
        if let selected, let index = highlights.firstIndex(where: { $0.id == selected }) {
            highlights.remove(at: index)
        } else if !highlights.isEmpty {
            highlights.removeLast()
        }
        selected = highlights.last?.id
    }
}
