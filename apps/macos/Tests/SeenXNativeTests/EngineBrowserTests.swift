import AppKit
import Combine
import SeenXEngineClient
import XCTest
@testable import SeenXNative

final class EngineBrowserTests: XCTestCase {
    @MainActor
    private func waitUntil(_ condition: () -> Bool, timeout: TimeInterval = 5) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition() {
            guard Date() < deadline else { throw EngineClientError.timeout }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
    }

    @MainActor
    func testLaunchFailurePreservesQueryAndAllowsReconnect() async throws {
        let model = EngineBrowserModel()
        model.query = "An unsent query"
        model.connect(configuration: .init(executableURL: URL(fileURLWithPath: "/no-such-seenx-helper")))
        try await waitUntil { !model.busy }
        XCTAssertFalse(model.connected)
        XCTAssertNotNil(model.error)
        XCTAssertEqual(model.query, "An unsent query")
        model.disconnect()
        XCTAssertNil(model.error)
        XCTAssertEqual(model.query, "An unsent query")
    }

    @MainActor
    func testDisconnectDuringHandshakeCannotReopenTheWindowSession() async throws {
        let model = EngineBrowserModel()
        model.connect(configuration: .init(executableURL: URL(fileURLWithPath: "/bin/sleep"),
                                           arguments: ["0.2"], requestTimeout: 0.5))
        model.disconnect()
        try await Task.sleep(nanoseconds: 350_000_000)
        XCTAssertFalse(model.connected)
        XCTAssertFalse(model.busy)
        XCTAssertNil(model.error)
        XCTAssertTrue(model.hits.isEmpty)
    }

    @MainActor
    func testSearchTransportExitDisconnectsBrowserAndPreservesQuery() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let helper = directory.appendingPathComponent("helper.sh")
        try #"""
        IFS= read -r request
        request_id=$(printf '%s\n' "$request" | /usr/bin/sed -E 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
        printf '{"version":1,"id":"%s","trace_id":"test","result":{"protocol_version":1,"catalog_schema_version":3,"read_only_requests":true,"methods":["engine.info","memory.search","memory.fetch","region.fetch"],"limits":{}}}\n' "$request_id"
        IFS= read -r request
        exit 1
        """#.write(to: helper, atomically: true, encoding: .utf8)
        let model = EngineBrowserModel()
        model.connect(configuration: .init(executableURL: URL(fileURLWithPath: "/bin/sh"), arguments: [helper.path]))
        try await waitUntil { !model.busy }
        XCTAssertTrue(model.connected, model.error ?? "")
        model.query = "Keep this query"
        model.search()
        try await waitUntil { !model.busy }
        XCTAssertFalse(model.connected)
        XCTAssertNotNil(model.error)
        XCTAssertEqual(model.query, "Keep this query")
        XCTAssertTrue(model.hits.isEmpty)
    }

    @MainActor
    func testLauncherQueuesLatestQueryAndDiscardsAnOlderSearch() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let helper = directory.appendingPathComponent("helper.sh")
        try #"""
        IFS= read -r request
        request_id=$(printf '%s\n' "$request" | /usr/bin/sed -E 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
        printf '{"version":1,"id":"%s","trace_id":"test","result":{"protocol_version":1,"catalog_schema_version":3,"read_only_requests":true,"methods":["engine.info","memory.search","memory.fetch","region.fetch"],"limits":{}}}\n' "$request_id"
        IFS= read -r request
        request_id=$(printf '%s\n' "$request" | /usr/bin/sed -E 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
        /bin/sleep 0.4
        printf '{"version":1,"id":"%s","trace_id":"test","result":[{"asset_id":"asset","revision_id":"revision","is_current_revision":true,"annotation_id":"annotation","matched_field":"note","method":"fts5","excerpt":"Old evidence","score":1,"score_kind":"rank","score_direction":"lower","provenance":{"origin":"user","confirmation":"confirmed"},"target":{"kind":"whole","x":0,"y":0,"width":1,"height":1}}]}\n' "$request_id"
        IFS= read -r request
        request_id=$(printf '%s\n' "$request" | /usr/bin/sed -E 's/.*"id"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
        case "$request" in *latest*) result='[]' ;; *) exit 1 ;; esac
        printf '{"version":1,"id":"%s","trace_id":"test","result":%s}\n' "$request_id" "$result"
        IFS= read -r request
        """#.write(to: helper, atomically: true, encoding: .utf8)
        let model = EngineBrowserModel()
        defer { model.disconnect() }
        model.connect(configuration: .init(executableURL: URL(fileURLWithPath: "/bin/sh"), arguments: [helper.path]))
        try await waitUntil { !model.busy }
        XCTAssertTrue(model.connected, model.error ?? "")
        var displayedOldEvidence = false
        let observation = model.$hits.sink { if !$0.isEmpty { displayedOldEvidence = true } }
        defer { observation.cancel() }
        model.query = "old"
        model.search()
        model.updateSearchQuery("intermediate")
        model.updateSearchQuery("latest")
        try await waitUntil { !model.busy && model.searched }
        XCTAssertEqual(model.query, "latest")
        XCTAssertTrue(model.connected, model.error ?? "")
        XCTAssertNil(model.error)
        XCTAssertTrue(model.hits.isEmpty)
        XCTAssertFalse(displayedOldEvidence)
    }

    /// Opt in locally with a real existing image; no personal fixture is committed.
    @MainActor
    func testRealPythonSearchImageCropAndDisconnect() async throws {
        let env = ProcessInfo.processInfo.environment
        guard let interpreter = env["SEENX_TEST_PYTHON"], let imagePath = env["SEENX_TEST_IMAGE"] else {
            throw XCTSkip("Set SEENX_TEST_PYTHON and SEENX_TEST_IMAGE for the real-engine integration check")
        }
        let repository = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let library = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: library) }
        let original = try Data(contentsOf: URL(fileURLWithPath: imagePath))
        let seed = Process()
        seed.executableURL = URL(fileURLWithPath: interpreter)
        seed.currentDirectoryURL = repository
        seed.arguments = ["-c", """
        import sys
        from pathlib import Path
        from seenx.catalog import Catalog
        from seenx.catalog_ocr import persist_observations
        from seenx.image_ocr import COORDINATE_SPACE
        with Catalog(Path(sys.argv[1])) as c:
            r = c.import_image(Path(sys.argv[2]))
            c.add_note(r['revision_id'], 'native integration marker', region=[.1, .2, .3, .1])
            c.add_note(r['revision_id'], 'corner point marker', point=[1, 1])
            m = c.get_memory(r['asset_id'])
            persist_observations(c, r['revision_id'], {
                'configuration': {'engine': 'integration-fixture', 'languages': ['en-US']},
                'width': m['revision']['width'], 'height': m['revision']['height'],
                'coordinate_space': COORDINATE_SPACE,
                'observations': [{'text': 'fixture observation marker', 'confidence': .9,
                                  'box': {'x': .1, 'y': .2, 'width': .3, 'height': .1}}]})
        """, library.path, imagePath]
        seed.standardOutput = FileHandle.nullDevice
        seed.standardError = FileHandle.nullDevice
        try seed.run()
        seed.waitUntilExit()
        XCTAssertEqual(seed.terminationStatus, 0)

        let model = EngineBrowserModel()
        model.connect(interpreter: URL(fileURLWithPath: interpreter), repository: repository, library: library)
        try await waitUntil { !model.busy }
        XCTAssertTrue(model.connected, model.error ?? "")
        model.query = "native integration marker"
        model.search()
        try await waitUntil { !model.busy }
        let hit = try XCTUnwrap(model.hits.first, model.error ?? "")
        XCTAssertEqual(hit.matchedField, "note")
        model.open(hit)
        try await waitUntil { !model.busy }
        let memory = try XCTUnwrap(model.memory, model.error ?? "")
        XCTAssertNotNil(model.image)
        XCTAssertEqual(model.image?.size.width, CGFloat(memory.revision.width))
        XCTAssertEqual(memory.annotations.count, 2)
        XCTAssertEqual(memory.ocrRuns.first?.observations.first?.confirmation, "unverified")
        guard case .string(let engine)? = memory.ocrRuns.first?.configuration["engine"] else {
            return XCTFail("Expected the original OCR configuration")
        }
        XCTAssertEqual(engine, "integration-fixture")

        model.open(hit, crop: true)
        try await waitUntil { !model.busy }
        XCTAssertTrue(model.showingCrop)
        let crop = try XCTUnwrap(model.image, model.error ?? "")
        XCTAssertLessThan(crop.size.width, CGFloat(memory.revision.width))
        XCTAssertLessThan(crop.size.height, CGFloat(memory.revision.height))

        // The same typed client must decode OCR evidence and an edge-point region.
        let client = try await EngineClient.launch(configuration: .init(executableURL: URL(fileURLWithPath: interpreter),
            arguments: ["-m", "seenx.engine_stdio", "--library", library.path, "--trusted-local", "--no-log"], currentDirectoryURL: repository))
        let observations = try await client.search("fixture observation marker")
        let observation = try XCTUnwrap(observations.first)
        let observationRegion = try await client.fetchRegion(assetID: observation.assetID, revisionID: observation.revisionID,
            target: .observation(try XCTUnwrap(observation.observationID)), includeImage: true)
        XCTAssertEqual(observationRegion.observation?.confirmation, "unverified")
        let point = try XCTUnwrap(memory.annotations.first { $0.target.kind == "point" })
        let pointRegion = try await client.fetchRegion(assetID: hit.assetID, revisionID: hit.revisionID,
            target: .region(point.regionID), includeImage: true)
        XCTAssertEqual(pointRegion.image?.width, 1)
        XCTAssertEqual(pointRegion.image?.height, 1)
        await client.close()
        model.disconnect()
        XCTAssertFalse(model.connected)
        XCTAssertNil(model.image)
        XCTAssertTrue(model.hits.isEmpty)
        XCTAssertEqual(try Data(contentsOf: URL(fileURLWithPath: imagePath)), original)
    }
}
