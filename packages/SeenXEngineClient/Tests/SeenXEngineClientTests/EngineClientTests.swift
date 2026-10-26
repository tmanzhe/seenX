import Foundation
import XCTest
@testable import SeenXEngineClient

final class EngineClientTests: XCTestCase {
    private let info = #"{"protocol_version":1,"catalog_schema_version":3,"read_only_requests":true,"methods":["engine.info","memory.search","memory.fetch","region.fetch"],"limits":{"request_bytes":65536,"response_bytes":8388608}}"#
    private let target = #"{"kind":"region","x":0.1,"y":0.2,"width":0.3,"height":0.4}"#
    private let hit = #"{"asset_id":"asset","revision_id":"revision","is_current_revision":false,"annotation_id":null,"observation_id":"observation","region_id":null,"matched_field":"ocr","method":"catalog-fts5","excerpt":"[saved] text","score":-0.001,"score_kind":"fts5-bm25","score_direction":"lower_is_better","provenance":{"origin":"ocr","confirmation":"unverified"},"target":{"kind":"region","x":0.1,"y":0.2,"width":0.3,"height":0.4}}"#

    /// A plain shell helper exercises actual pipes without Python, a server, or bitmap fixtures.
    private func configuration(action: String, timeout: TimeInterval = 2, infoOverride: String? = nil) -> EngineClient.Configuration {
        let script = """
        while IFS= read -r line; do
          id=$(printf '%s' "$line" | /usr/bin/sed -n 's/.*"id"[ ]*:[ ]*"\\([^"]*\\)".*/\\1/p')
          case "$line" in
            *engine.info*) printf '%s\\n' '{"version":1,"id":"'"$id"'","trace_id":"trace","result":\(infoOverride ?? info)}' ;;
            *) \(action) ;;
          esac
        done
        """
        return .init(executableURL: URL(fileURLWithPath: "/bin/sh"), arguments: ["-c", script], requestTimeout: timeout)
    }

    private func response(_ result: String) -> String {
        "printf '%s\\n' '{\"version\":1,\"id\":\"'\"$id\"'\",\"trace_id\":\"trace\",\"result\":\(result)}'"
    }

    private func assertError<T>(_ expected: EngineClientError, operation: () async throws -> T,
                                file: StaticString = #filePath, line: UInt = #line) async {
        do { _ = try await operation(); XCTFail("Expected transport error", file: file, line: line) }
        catch { XCTAssertEqual(error as? EngineClientError, expected, file: file, line: line) }
    }

    func testHandshakeSearchAndRepeatedClose() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: response("[\(hit)]")))
        XCTAssertEqual(client.info.catalogSchemaVersion, 3)
        let hits = try await client.search("saved", revisionID: "revision", currentOnly: false)
        XCTAssertEqual(hits.first?.assetID, "asset")
        XCTAssertEqual(hits.first?.observationID, "observation")
        XCTAssertNil(hits.first?.annotationID)
        XCTAssertEqual(hits.first?.provenance.confirmation, "unverified")
        await client.close()
        await client.close()
        await assertError(.closed) { try await client.search("again") }
    }

    func testMemoryAndRegionDecodeWithOptionalAttachment() async throws {
        let image = #"{"media_type":"image/png","encoding":"base64","width":3,"height":4,"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","data":"cG5n"}"#
        let observation = #"{"id":"observation","run_id":"run","position":0,"text":"saved","confidence":0.9,"origin":"ocr","confirmation":"unverified","box":{"x":0.1,"y":0.2,"width":0.3,"height":0.4}}"#
        let memory = """
        {"schema_version":3,"asset":{"id":"asset","source_name":"personal.jpeg","current_revision_id":"revision","created_at":"now"},"revision":{"id":"revision","asset_id":"asset","sha256":"source-hash","width":10,"height":10,"format":"JPEG","exif_orientation":1,"byte_size":5,"created_at":"now","snapshot_verified":true,"coordinate_space":"normalized_top_left_exif_corrected"},"source_missing":true,"revisions":[],"annotations":[],"relationships":[],"ocr_runs":[{"id":"run","revision_id":"revision","configuration_key":"key","configuration":{"engine":"fake","languages":["en-US"]},"created_at":"now","coordinate_space":"normalized_top_left_exif_corrected","observations":[\(observation)]}]}
        """
        let region = """
        {"asset_id":"asset","revision_id":"revision","coordinate_space":"normalized_top_left_exif_corrected","reference_image":{"width":10,"height":10,"sha256":"source-hash"},"target":\(target),"pixel_bounds":{"left":1,"top":2,"right":4,"bottom":6},"observation":\(observation),"image":\(image)}
        """
        let action = "case \"$line\" in *memory.fetch*) \(response(memory)) ;; *) \(response(region)) ;; esac"
        let client = try await EngineClient.launch(configuration: configuration(action: action))
        let result = try await client.fetchMemory(assetID: "asset", revisionID: "revision")
        XCTAssertEqual(result.asset.currentRevisionID, "revision")
        XCTAssertEqual(result.ocrRuns.first?.observations.first?.runID, "run")
        XCTAssertNil(result.image)
        let crop = try await client.fetchRegion(assetID: "asset", revisionID: "revision", target: .observation("observation"), includeImage: true)
        XCTAssertEqual(crop.pixelBounds.right - crop.pixelBounds.left, crop.image?.width)
        XCTAssertEqual(crop.image?.data, Data("png".utf8))
        XCTAssertEqual(crop.observation?.confirmation, "unverified")
        await client.close()
    }

    func testRemoteMethodErrorDoesNotCloseSession() async throws {
        let action = "printf '%s\\n' '{\"version\":1,\"id\":\"'\"$id\"'\",\"trace_id\":\"trace\",\"error\":{\"code\":\"not_found\",\"message\":\"Missing\"}}'"
        let client = try await EngineClient.launch(configuration: configuration(action: action))
        for _ in 0..<2 {
            await assertError(.engine(code: "not_found", message: "Missing", traceID: "trace")) {
                try await client.search("missing")
            }
        }
        await client.close()
    }

    func testRejectsMismatchedIDAndClosesSession() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: "printf '%s\\n' '{\"version\":1,\"id\":\"wrong\",\"trace_id\":\"trace\",\"result\":[]}'"))
        await assertError(.mismatchedResponseID) { try await client.search("saved") }
        await assertError(.closed) { try await client.search("saved") }
    }

    func testVersionCheckedBeforeDecodingResult() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: "printf '%s\\n' '{\"version\":2,\"id\":\"'\"$id\"'\",\"trace_id\":\"trace\",\"result\":{}}'"))
        await assertError(.unsupportedVersion(2)) { try await client.search("saved") }
    }

    func testMalformedResponseAndAmbiguousEnvelope() async throws {
        for action in ["printf 'not-json\\n'", "printf '%s\\n' '{\"version\":1,\"id\":\"'\"$id\"'\",\"trace_id\":\"trace\",\"result\":[],\"error\":null}'"] {
            let client = try await EngineClient.launch(configuration: configuration(action: action))
            await assertError(.invalidResponse) { try await client.search("saved") }
        }
    }

    func testRequestLimitKeepsSessionUsable() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: response("[]")))
        await assertError(.requestTooLarge) { try await client.search(String(repeating: "x", count: 66_000)) }
        let hits = try await client.search("small")
        XCTAssertTrue(hits.isEmpty)
        await client.close()
    }

    func testResponseLimitStopsBeforeUnboundedAccumulation() async throws {
        let action = "/usr/bin/head -c 8388610 /dev/zero | /usr/bin/tr '\\000' x"
        let client = try await EngineClient.launch(configuration: configuration(action: action, timeout: 5))
        await assertError(.responseTooLarge) { try await client.search("saved") }
    }

    func testProcessExitAndTruncatedResponse() async throws {
        for action in ["exit 7", "printf '{\"version\":1'; exit 0"] {
            let client = try await EngineClient.launch(configuration: configuration(action: action))
            do { _ = try await client.search("saved"); XCTFail("Expected EOF") }
            catch { guard case EngineClientError.processExited = error else { return XCTFail("Expected process exit") } }
            await client.close()
        }
    }

    func testTimeoutTerminatesUnresponsiveProcess() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: "while :; do :; done", timeout: 0.1))
        await assertError(.timeout) { try await client.search("saved") }
        await assertError(.closed) { try await client.search("saved") }
    }

    func testTaskCancellationEndsSession() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: "while :; do :; done", timeout: 10))
        let task = Task { try await client.search("saved") }
        try await Task.sleep(for: .milliseconds(50))
        task.cancel()
        do { _ = try await task.value; XCTFail("Expected cancellation") }
        catch { XCTAssertTrue(error is CancellationError) }
        await client.close()
    }

    func testConcurrentRequestsAreSerialized() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: response("[\(hit)]")))
        try await withThrowingTaskGroup(of: Void.self) { group in
            for _ in 0..<12 { group.addTask {
                let hits = try await client.search("saved")
                XCTAssertEqual(hits.count, 1)
            } }
            try await group.waitForAll()
        }
        await client.close()
    }

    func testStderrCannotBlockResponse() async throws {
        let client = try await EngineClient.launch(configuration: configuration(action: "/usr/bin/head -c 1000000 /dev/zero >&2; \(response("[]"))"))
        let hits = try await client.search("saved")
        XCTAssertTrue(hits.isEmpty)
        await client.close()
    }

    func testLaunchFailureIsSanitized() async {
        await assertError(.launchFailed) {
            try await EngineClient.launch(configuration: .init(executableURL: URL(fileURLWithPath: "/nonexistent/private-path")))
        }
    }

    func testHandshakeRejectsUnsupportedOrIncompleteCapabilities() async {
        let unsupported = info.replacingOccurrences(of: "\"protocol_version\":1", with: "\"protocol_version\":2")
        await assertError(.unsupportedVersion(2)) {
            try await EngineClient.launch(configuration: configuration(action: response("[]"), infoOverride: unsupported))
        }
        let incomplete = info.replacingOccurrences(of: "\"region.fetch\"", with: "\"unknown\"")
        await assertError(.invalidResponse) {
            try await EngineClient.launch(configuration: configuration(action: response("[]"), infoOverride: incomplete))
        }
    }

    func testWholeAndPointAnnotationGeometry() async throws {
        for kind in ["whole", "point"] {
            let geometry = kind == "point"
                ? #""target":{"kind":"point","x":1,"y":1,"width":0,"height":0},"pixel_target":{"x":9,"y":9}"#
                : #""target":{"kind":"whole","x":0,"y":0,"width":1,"height":1},"pixel_bounds":{"left":0,"top":0,"right":10,"bottom":10}"#
            let note = """
            {"id":"note","region_id":"region","revision_id":"revision","note":"remember","selected_text":"","origin":"user","confirmation":"confirmed","selected_text_origin":"user","selected_text_confirmation":"confirmed","quoted_observation_id":null,"created_at":"now","updated_at":"now",\(geometry)}
            """
            let result = """
            {"asset_id":"asset","revision_id":"revision","coordinate_space":"normalized_top_left_exif_corrected","reference_image":{"width":10,"height":10,"sha256":"source"},"target":{ "kind":"\(kind)","x":0,"y":0,"width":1,"height":1},"pixel_bounds":{"left":0,"top":0,"right":10,"bottom":10},"annotation":\(note)}
            """
            let client = try await EngineClient.launch(configuration: configuration(action: response(result)))
            let evidence = try await client.fetchRegion(assetID: "asset", revisionID: "revision", target: .region("region"))
            XCTAssertEqual(evidence.annotation?.regionID, "region")
            XCTAssertEqual(evidence.annotation?.target.kind, kind)
            if kind == "point" {
                XCTAssertEqual(evidence.annotation?.pixelTarget?.x, 9)
                XCTAssertNil(evidence.annotation?.pixelBounds)
            } else { XCTAssertEqual(evidence.annotation?.pixelBounds?.right, 10) }
            await client.close()
        }
    }
}
