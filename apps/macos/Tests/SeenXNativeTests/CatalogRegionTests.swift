import AppKit
import SeenXEngineClient
import XCTest
@testable import SeenXNative

final class CatalogRegionTests: XCTestCase {
    func testDrawingUsesTopLeftCoordinatesInEitherDirectionAndAtDifferentScales() throws {
        let expected = CGRect(x: 0.1, y: 0.2, width: 0.3, height: 0.4)
        for scale in [CGFloat(1), CGFloat(2), CGFloat(0.5)] {
            for reverse in [false, true] {
                let start = CGPoint(x: 10 * scale, y: 40 * scale)
                let end = CGPoint(x: 40 * scale, y: 120 * scale)
                let rect = try XCTUnwrap(CatalogRegionDraft.rectangle(from: reverse ? end : start, to: reverse ? start : end,
                    imageSize: CGSize(width: 100 * scale, height: 200 * scale)))
                XCTAssertEqual(rect.minX, expected.minX, accuracy: 0.000001)
                XCTAssertEqual(rect.minY, expected.minY, accuracy: 0.000001)
                XCTAssertEqual(rect.width, expected.width, accuracy: 0.000001)
                XCTAssertEqual(rect.height, expected.height, accuracy: 0.000001)
            }
        }
    }

    func testDrawingClampsEdgesAndRejectsClicksAndStartsOutsideImage() throws {
        let size = CGSize(width: 100, height: 200)
        let rect = try XCTUnwrap(CatalogRegionDraft.rectangle(from: CGPoint(x: 50, y: 100), to: CGPoint(x: 400, y: 600), imageSize: size))
        XCTAssertEqual(rect, CGRect(x: 0.5, y: 0.5, width: 0.5, height: 0.5))
        XCTAssertNil(CatalogRegionDraft.rectangle(from: .zero, to: CGPoint(x: 1, y: 2), imageSize: size))
        XCTAssertNil(CatalogRegionDraft.rectangle(from: CGPoint(x: -10, y: 0), to: CGPoint(x: 40, y: 60), imageSize: size))
        XCTAssertNil(CatalogRegionDraft.rectangle(from: .zero, to: CGPoint(x: 40, y: 60), imageSize: .zero))
    }

    @MainActor
    func testNewDraftRequiresGeometryAndNoteAndCancelDiscardsOnlyTheDraft() {
        let model = EngineBrowserModel()
        model.newRegion()
        XCTAssertTrue(model.drawingRegion)
        XCTAssertTrue(model.hasRegionChanges)
        XCTAssertFalse(model.canSaveRegion)
        model.regionDraft?.note = "Keep spacing"
        XCTAssertFalse(model.canSaveRegion)
        model.finishDrawing(CGRect(x: 0.1, y: 0.2, width: 0.3, height: 0.4))
        XCTAssertFalse(model.drawingRegion)
        XCTAssertTrue(model.canSaveRegion)
        XCTAssertEqual(model.regionDraft?.coordinates, [0.1, 0.2, 0.3, 0.4])
        model.cancelRegionDraft()
        XCTAssertNil(model.regionDraft)
        XCTAssertFalse(model.hasRegionChanges)
        XCTAssertFalse(model.canSaveRegion)
    }

    @MainActor
    func testSaveRedrawCopyAndDeleteRefreshSavedEvidence() async throws {
        let model = try await connectedModel()
        defer { model.disconnect() }
        model.newRegion()
        model.regionDraft?.note = "Created"
        model.finishDrawing(CGRect(x: 0.1, y: 0.2, width: 0.3, height: 0.4))
        model.saveRegion()
        try await idle(model)
        XCTAssertNil(model.error)
        XCTAssertEqual(model.memory?.annotations.count, 1)
        XCTAssertEqual(model.selectedAnnotation?.note, "Created")
        XCTAssertFalse(model.hasRegionChanges)
        model.regionDraft?.note = "Edited"
        model.drawingRegion = true
        model.finishDrawing(CGRect(x: 0.5, y: 0.5, width: 0.5, height: 0.5))
        model.saveRegion()
        try await idle(model)
        XCTAssertEqual(model.selectedAnnotation?.note, "Edited")
        XCTAssertEqual(model.selectedAnnotation?.target.x, 0.5)
        let pasteboard = NSPasteboard(name: NSPasteboard.Name(UUID().uuidString))
        defer { pasteboard.releaseGlobally() }
        pasteboard.setString("Before", forType: .string)
        model.regionDraft?.note = "Unsaved"
        model.copyForLLM(pasteboard: pasteboard)
        XCTAssertFalse(model.busy)
        XCTAssertEqual(pasteboard.string(forType: .string), "Before")
        model.selectAnnotation(model.memory?.annotations.first)
        model.copyForLLM(pasteboard: pasteboard)
        try await idle(model)
        XCTAssertNotNil(model.copyStatus)
        let text = try XCTUnwrap(pasteboard.string(forType: .string))
        let payload = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(text.utf8)) as? [String: Any])
        XCTAssertEqual(payload["schema_version"] as? Int, 1)
        let parts = try XCTUnwrap(payload["content"] as? [[String: String]])
        XCTAssertEqual(parts[0]["text"], "{\"note\":\"Edited\",\"evidence_trust\":\"untrusted\"}")
        XCTAssertEqual(parts[1]["mimeType"], "image/png")
        model.deleteRegion()
        try await idle(model)
        XCTAssertNil(model.error)
        XCTAssertTrue(model.memory?.annotations.isEmpty == true)
        XCTAssertNil(model.regionDraft)
    }

    @MainActor
    func testFailedAndDisconnectedCopiesLeaveClipboardUntouched() async throws {
        for disconnect in [false, true] {
            let action = disconnect ? "sleep 0.2; reply '\(Self.payload)'" :
                #"printf '{"version":1,"id":"%s","trace_id":"mock","error":{"code":"resource_limit","message":"Too large"}}\n' "$id""#
            let model = try await connectedModel(payloadAction: action)
            defer { model.disconnect() }
            model.newRegion()
            model.regionDraft?.note = "Created"
            model.finishDrawing(CGRect(x: 0.1, y: 0.2, width: 0.3, height: 0.4))
            model.saveRegion()
            try await idle(model)
            let pasteboard = NSPasteboard(name: NSPasteboard.Name(UUID().uuidString))
            defer { pasteboard.releaseGlobally() }
            pasteboard.setString("Before", forType: .string)
            model.copyForLLM(pasteboard: pasteboard)
            if disconnect { model.disconnect() }
            try await Task.sleep(nanoseconds: 350_000_000)
            try await idle(model)
            XCTAssertEqual(pasteboard.string(forType: .string), "Before")
            XCTAssertNil(model.copyStatus)
            XCTAssertEqual(model.connected, !disconnect)
            if !disconnect { XCTAssertNotNil(model.error) }
        }
    }

    private static let payload = #"{"schema_version":1,"content":[{"type":"text","text":"{\"note\":\"Edited\",\"evidence_trust\":\"untrusted\"}"},{"type":"image","mimeType":"image/png","data":"cG5n"}]}"#

    @MainActor
    private func connectedModel(payloadAction: String? = nil) async throws -> EngineBrowserModel {
        let bitmap = try XCTUnwrap(NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 10, pixelsHigh: 20,
            bitsPerSample: 8, samplesPerPixel: 3, hasAlpha: false, isPlanar: false, colorSpaceName: .deviceRGB,
            bytesPerRow: 0, bitsPerPixel: 0))
        bitmap.bitmapData?.initialize(repeating: 0, count: bitmap.bytesPerRow * bitmap.pixelsHigh)
        let png = try XCTUnwrap(bitmap.representation(using: .png, properties: [:])).base64EncodedString()
        let annotation = #"{"id":"note","region_id":"region","revision_id":"revision","note":"Created","selected_text":"","origin":"user","confirmation":"confirmed","selected_text_origin":"user","selected_text_confirmation":"confirmed","created_at":"now","updated_at":"now","target":{"kind":"region","x":0.1,"y":0.2,"width":0.3,"height":0.4}}"#
        let memory = #"{"schema_version":3,"asset":{"id":"asset","source_name":"fixture.png","current_revision_id":"revision","created_at":"now"},"revision":{"id":"revision","asset_id":"asset","sha256":"hash","width":10,"height":20,"format":"PNG","exif_orientation":1,"byte_size":100,"created_at":"now","snapshot_verified":true,"coordinate_space":"normalized_top_left_exif_corrected"},"source_missing":false,"revisions":[],"annotations":ANNOTATIONS,"relationships":[],"ocr_runs":[],"image":{"media_type":"image/png","encoding":"base64","width":10,"height":20,"sha256":"hash","data":"IMAGE_DATA"}}"#
        let empty = memory.replacingOccurrences(of: "ANNOTATIONS", with: "[]").replacingOccurrences(of: "IMAGE_DATA", with: png)
        let created = memory.replacingOccurrences(of: "ANNOTATIONS", with: "[\(annotation)]").replacingOccurrences(of: "IMAGE_DATA", with: png)
        let edited = created.replacingOccurrences(of: "Created", with: "Edited")
            .replacingOccurrences(of: "\"x\":0.1,\"y\":0.2,\"width\":0.3,\"height\":0.4", with: "\"x\":0.5,\"y\":0.5,\"width\":0.5,\"height\":0.5")
        let script = #"""
        state=empty
        reply() { printf '{"version":1,"id":"%s","trace_id":"mock","result":%s}\n' "$id" "$1"; }
        while IFS= read -r line; do
            id=$(printf '%s' "$line" | /usr/bin/sed -n 's/.*"id"[ ]*:[ ]*"\([^"]*\)".*/\1/p')
            case "$line" in
                *engine.info*) reply '{"protocol_version":1,"catalog_schema_version":3,"read_only_requests":false,"methods":["engine.info","memory.search","memory.fetch","region.fetch","annotation.create","annotation.update","annotation.delete","payload.build"],"limits":{}}' ;;
                *memory.search*) reply '[{"asset_id":"asset","revision_id":"revision","is_current_revision":true,"matched_field":"note","method":"fts5","excerpt":"Fixture","score":1,"score_kind":"rank","score_direction":"lower","provenance":{"origin":"user","confirmation":"confirmed"},"target":{"kind":"whole","x":0,"y":0,"width":1,"height":1}}]' ;;
                *annotation.create*) state=created; reply '{"annotation_id":"note","region_id":"region","revision_id":"revision"}' ;;
                *annotation.update*) state=edited; reply '{"annotation_id":"note","region_id":"region","revision_id":"revision"}' ;;
                *annotation.delete*) state=empty; reply '{"annotation_id":"note","region_id":"region","revision_id":"revision"}' ;;
                *memory.fetch*) case "$state" in
                    empty) reply 'EMPTY' ;; created) reply 'CREATED' ;; edited) reply 'EDITED' ;;
                    esac ;;
                *payload.build*) PAYLOAD_ACTION ;;
                *) exit 1 ;;
            esac
        done
        """#
            .replacingOccurrences(of: "EMPTY", with: empty)
            .replacingOccurrences(of: "CREATED", with: created)
            .replacingOccurrences(of: "EDITED", with: edited)
            .replacingOccurrences(of: "PAYLOAD_ACTION", with: payloadAction ?? "reply '\(Self.payload)'")
        let model = EngineBrowserModel()
        model.connect(configuration: .init(executableURL: URL(fileURLWithPath: "/bin/sh"), arguments: ["-c", script], allowsWrites: true))
        try await idle(model)
        XCTAssertTrue(model.connected, model.error ?? "")
        model.query = "Fixture"
        model.search()
        try await idle(model)
        model.open(try XCTUnwrap(model.hits.first))
        try await idle(model)
        XCTAssertNotNil(model.image, model.error ?? "")
        return model
    }

    @MainActor
    private func idle(_ model: EngineBrowserModel) async throws {
        for _ in 0..<200 {
            if !model.busy { return }
            try await Task.sleep(nanoseconds: 10_000_000)
        }
        XCTFail("Mock engine did not finish")
    }
}
