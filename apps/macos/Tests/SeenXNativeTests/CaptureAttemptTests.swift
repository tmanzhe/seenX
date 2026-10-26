import AppKit
import ScreenCaptureKit
import XCTest
@testable import SeenXNative

final class CaptureAttemptTests: XCTestCase {
    func testValidPNGSuccessIsReturned() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.deletingLastPathComponent()) }
        XCTAssertEqual(try CaptureAttempt.result(imageURL: fixture, status: 0, reason: .exit, standardError: ""), fixture)
    }

    func testSuccessfulExitWithoutFileIsCleanNoOutputOutcome() throws {
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".png")
        XCTAssertNil(try CaptureAttempt.result(imageURL: missing, status: 0, reason: .exit, standardError: " \n"))
    }

    func testNonzeroExitWithEmptyStderrIsVisibleFailure() {
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".png")
        XCTAssertThrowsError(try CaptureAttempt.result(imageURL: missing, status: 1, reason: .exit, standardError: "")) {
            XCTAssertEqual($0 as? CaptureFailure, .processExited(status: 1, message: ""))
            XCTAssertFalse($0.localizedDescription.isEmpty)
        }
    }

    func testSignalTerminationIsNeverCancellation() {
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".png")
        XCTAssertThrowsError(try CaptureAttempt.result(imageURL: missing, status: 9, reason: .uncaughtSignal, standardError: "")) {
            XCTAssertEqual($0 as? CaptureFailure, .interrupted(signal: 9))
        }
    }

    func testSuccessfulExitWithInvalidFileIsVisibleFailure() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.deletingLastPathComponent()) }
        try Data("not a png".utf8).write(to: fixture)
        XCTAssertThrowsError(try CaptureAttempt.result(imageURL: fixture, status: 0, reason: .exit, standardError: "")) {
            XCTAssertEqual($0 as? CaptureFailure, .invalidImage)
        }
        try Data().write(to: fixture)
        XCTAssertThrowsError(try CaptureAttempt.result(imageURL: fixture, status: 0, reason: .exit, standardError: "")) {
            XCTAssertEqual($0 as? CaptureFailure, .invalidImage)
        }
    }

    func testSuccessfulExitWithoutFileButWithErrorIsNotCancellation() {
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".png")
        XCTAssertThrowsError(try CaptureAttempt.result(imageURL: missing, status: 0, reason: .exit, standardError: " capture failed\n")) {
            XCTAssertEqual($0 as? CaptureFailure, .processExited(status: 0, message: "capture failed"))
        }
    }

    func testNonzeroExitDoesNotAcceptEvenValidPNG() throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.deletingLastPathComponent()) }
        XCTAssertThrowsError(try CaptureAttempt.result(imageURL: fixture, status: 2, reason: .exit, standardError: "permission refused")) {
            XCTAssertEqual($0 as? CaptureFailure, .processExited(status: 2, message: "permission refused"))
        }
    }

    func testPermissionInspectionUsesActualFrameworkDomainAndCode() {
        let declined = NSError(domain: SCStreamError.errorDomain, code: SCStreamError.userDeclined.rawValue)
        XCTAssertTrue(NativeServices.isScreenPermissionError(declined))
        let wrapped = NSError(domain: "SeenXTest", code: 1, userInfo: [NSUnderlyingErrorKey: declined])
        XCTAssertTrue(NativeServices.isScreenPermissionError(wrapped))
        XCTAssertFalse(NativeServices.isScreenPermissionError(NSError(domain: "Other", code: -3801)))
        XCTAssertFalse(NativeServices.isScreenPermissionError(NSError(domain: SCStreamError.errorDomain, code: SCStreamError.failedToStart.rawValue)))
        XCTAssertFalse(NativeServices.isScreenPermissionError(CaptureFailure.processExited(status: 1, message: "permission denied")))
    }

    func testChildProcessCanFinishAfterLaunchScopeReturnsWithoutScreenCapture() async throws {
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".png")
        let result = try await CaptureAttempt(imageURL: missing, executableURL: URL(fileURLWithPath: "/bin/sleep"), arguments: ["0.01"]).run()
        XCTAssertNil(result)
    }

    private func makeFixture() throws -> URL {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let bitmap = try XCTUnwrap(NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 8, pixelsHigh: 8,
                                                   bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                                   colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0))
        let imageURL = directory.appendingPathComponent("fixture.png")
        try XCTUnwrap(bitmap.representation(using: .png, properties: [:])).write(to: imageURL)
        return imageURL
    }
}
