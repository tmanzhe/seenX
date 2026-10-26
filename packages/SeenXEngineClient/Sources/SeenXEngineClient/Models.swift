import Foundation

public enum SearchMatch: String, Sendable { case phrase, all }
public enum RegionReference: Sendable { case region(String), observation(String) }

public struct EngineInfo: Decodable, Sendable {
    public let protocolVersion: Int
    public let catalogSchemaVersion: Int
    public let readOnlyRequests: Bool
    public let methods: [String]
    public let limits: [String: Int]
}

public struct Provenance: Decodable, Sendable {
    public let origin: String
    public let confirmation: String
}

public struct NormalizedTarget: Decodable, Sendable {
    public let kind: String
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double
}

public struct NormalizedBox: Decodable, Sendable {
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double
}

public struct PixelBounds: Decodable, Sendable {
    public let left: Int
    public let top: Int
    public let right: Int
    public let bottom: Int
}

public struct PixelPoint: Decodable, Sendable {
    public let x: Int
    public let y: Int
}

public struct SearchHit: Decodable, Sendable, Identifiable {
    public let assetID: String
    public let revisionID: String
    public let isCurrentRevision: Bool
    public let annotationID: String?
    public let observationID: String?
    public let regionID: String?
    public let matchedField: String
    public let method: String
    public let excerpt: String
    public let score: Double
    public let scoreKind: String
    public let scoreDirection: String
    public let provenance: Provenance
    public let target: NormalizedTarget
    public var id: String { "\(revisionID):\(matchedField):\(annotationID ?? observationID ?? regionID ?? assetID)" }
}

public struct MemoryAsset: Decodable, Sendable {
    public let id: String
    public let sourceName: String
    public let currentRevisionID: String
    public let createdAt: String
}

public struct MemoryRevision: Decodable, Sendable {
    public let id: String
    public let assetID: String
    public let sha256: String
    public let width: Int
    public let height: Int
    public let format: String
    public let exifOrientation: Int
    public let byteSize: Int
    public let createdAt: String
    public let snapshotVerified: Bool
    public let coordinateSpace: String
}

public struct RevisionSummary: Decodable, Sendable, Identifiable {
    public let id: String
    public let sha256: String
    public let width: Int
    public let height: Int
    public let createdAt: String
    public let annotationCount: Int
}

public struct Annotation: Decodable, Sendable, Identifiable {
    public let id: String
    public let regionID: String
    public let revisionID: String
    public let note: String
    public let selectedText: String
    public let origin: String
    public let confirmation: String
    public let selectedTextOrigin: String
    public let selectedTextConfirmation: String
    public let quotedObservationID: String?
    public let createdAt: String
    public let updatedAt: String
    public let target: NormalizedTarget
    public let pixelBounds: PixelBounds?
    public let pixelTarget: PixelPoint?
}

public struct TextObservation: Decodable, Sendable, Identifiable {
    public let id: String
    public let runID: String
    public let position: Int
    public let text: String
    public let confidence: Double
    public let origin: String
    public let confirmation: String
    public let box: NormalizedBox
}

public struct OCRRun: Decodable, Sendable, Identifiable {
    public let id: String
    public let revisionID: String
    public let configurationKey: String
    public let configuration: [String: JSONValue]
    public let createdAt: String
    public let coordinateSpace: String
    public let observations: [TextObservation]
}

public struct Relationship: Decodable, Sendable {
    public let subject: String
    public let predicate: String
    public let object: String
    public let origin: String
    public let confirmation: String
}

public struct ImageAttachment: Decodable, Sendable {
    public let mediaType: String
    public let encoding: String
    public let width: Int
    public let height: Int
    public let sha256: String
    /// Decoded PNG bytes. Foundation performs strict base64 decoding.
    public let data: Data

    private enum CodingKeys: String, CodingKey { case mediaType, encoding, width, height, sha256, data }
    public init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        mediaType = try values.decode(String.self, forKey: .mediaType)
        encoding = try values.decode(String.self, forKey: .encoding)
        width = try values.decode(Int.self, forKey: .width)
        height = try values.decode(Int.self, forKey: .height)
        sha256 = try values.decode(String.self, forKey: .sha256)
        data = try values.decode(Data.self, forKey: .data)
        guard mediaType == "image/png", encoding == "base64", width > 0, height > 0,
              width <= 20_000_000, height <= 20_000_000 / width, data.count <= 4 * 1024 * 1024,
              sha256.count == 64, sha256.allSatisfy({ $0.isHexDigit && $0.isASCII })
        else { throw DecodingError.dataCorruptedError(forKey: .data, in: values, debugDescription: "Invalid image attachment") }
    }
}

public struct Memory: Decodable, Sendable {
    public let schemaVersion: Int
    public let asset: MemoryAsset
    public let revision: MemoryRevision
    public let sourceMissing: Bool
    public let revisions: [RevisionSummary]
    public let annotations: [Annotation]
    public let relationships: [Relationship]
    public let ocrRuns: [OCRRun]
    public let image: ImageAttachment?
}

public struct ReferenceImage: Decodable, Sendable {
    public let width: Int
    public let height: Int
    public let sha256: String
}

public struct RegionEvidence: Decodable, Sendable {
    public let assetID: String
    public let revisionID: String
    public let coordinateSpace: String
    public let referenceImage: ReferenceImage
    public let target: NormalizedTarget
    public let pixelBounds: PixelBounds
    public let annotation: Annotation?
    public let observation: TextObservation?
    public let image: ImageAttachment?
}

/// OCR configuration is engine-specific, while evidence fields remain typed.
public enum JSONValue: Decodable, Sendable {
    case null, bool(Bool), number(Double), string(String), array([JSONValue]), object([String: JSONValue])
    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let value = try? c.decode(Bool.self) { self = .bool(value) }
        else if let value = try? c.decode(Double.self) { self = .number(value) }
        else if let value = try? c.decode(String.self) { self = .string(value) }
        else if let value = try? c.decode([JSONValue].self) { self = .array(value) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }
}

public enum EngineClientError: Error, Equatable, Sendable {
    case launchFailed
    case closed
    case timeout
    case processExited(Int32?)
    case requestTooLarge
    case responseTooLarge
    case invalidResponse
    case unsupportedVersion(Int)
    case mismatchedResponseID
    case engine(code: String, message: String, traceID: String)
}

extension EngineClientError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case .launchFailed: return "The local engine could not start. Check the selected Python environment."
        case .closed: return "The local engine session is closed."
        case .timeout: return "The local engine request timed out. Reconnect to retry."
        case .processExited: return "The local engine exited before completing the request."
        case .requestTooLarge: return "The engine request exceeds the byte limit."
        case .responseTooLarge: return "The engine response exceeds the byte limit."
        case .invalidResponse: return "The local engine returned an invalid response."
        case .unsupportedVersion: return "The local engine uses an unsupported protocol version."
        case .mismatchedResponseID: return "The engine response did not match the pending request."
        case let .engine(code, _, _): return "The local engine could not complete the request (\(code))."
        }
    }
}
