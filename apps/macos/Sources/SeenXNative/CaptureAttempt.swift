import Foundation
import ImageIO

enum CaptureFailure: LocalizedError, Equatable {
    case processExited(status: Int32, message: String)
    case interrupted(signal: Int32)
    case invalidImage

    var errorDescription: String? {
        switch self {
        case .processExited(let status, let message):
            return message.isEmpty ? "The screenshot tool exited with status \(status) without creating a screenshot."
                : "The screenshot tool failed (status \(status)): \(message)"
        case .interrupted(let signal):
            return "The screenshot tool was interrupted (signal \(signal)). Please try again."
        case .invalidImage:
            return "The screenshot tool produced an unreadable or empty image. Please try again."
        }
    }
}

/// Owns the child process until its termination handler has delivered one result.
/// The executable can be substituted by tests without capturing the desktop.
final class CaptureAttempt {
    let imageURL: URL
    private let process: Process

    init(imageURL: URL, executableURL: URL = URL(fileURLWithPath: "/usr/sbin/screencapture"), arguments: [String]? = nil) {
        self.imageURL = imageURL
        process = Process()
        process.executableURL = executableURL
        process.arguments = arguments ?? ["-x", "-i", "-t", "png", imageURL.path]
    }

    func run() async throws -> URL? {
        try await withCheckedThrowingContinuation { continuation in
            let errors = Pipe()
            process.standardError = errors
            // This explicit retain cycle is broken in both completion paths below.
            process.terminationHandler = { [self] completed in
                defer { completed.terminationHandler = nil }
                let data = errors.fileHandleForReading.readDataToEndOfFile()
                let message = String(decoding: data, as: UTF8.self)
                do {
                    let result = try Self.result(imageURL: imageURL, status: completed.terminationStatus,
                                                 reason: completed.terminationReason, standardError: message)
                    if result == nil { try? FileManager.default.removeItem(at: imageURL) }
                    continuation.resume(returning: result)
                } catch {
                    try? FileManager.default.removeItem(at: imageURL)
                    continuation.resume(throwing: error)
                }
            }
            do { try process.run() }
            catch {
                process.terminationHandler = nil
                continuation.resume(throwing: error)
            }
        }
    }

    static func result(imageURL: URL, status: Int32, reason: Process.TerminationReason, standardError: String) throws -> URL? {
        let message = standardError.trimmingCharacters(in: .whitespacesAndNewlines)
        guard reason == .exit else { throw CaptureFailure.interrupted(signal: status) }
        guard status == 0 else { throw CaptureFailure.processExited(status: status, message: message) }
        guard FileManager.default.fileExists(atPath: imageURL.path) else {
            // A successful interactive command with no output represents an aborted
            // selection (or the system picker's deliberate clipboard-only path).
            guard message.isEmpty else { throw CaptureFailure.processExited(status: status, message: message) }
            return nil
        }
        guard let source = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil), image.width > 0, image.height > 0 else {
            throw CaptureFailure.invalidImage
        }
        return imageURL
    }
}
