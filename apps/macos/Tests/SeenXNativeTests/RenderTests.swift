import AppKit
import SwiftUI
import XCTest
@testable import SeenXNative

final class RenderTests: XCTestCase {
    func testLauncherCommandsMatchTitlesAndUsefulAliases() {
        XCTAssertTrue(LauncherAction.capture.matches("capture screenshot"))
        XCTAssertTrue(LauncherAction.capture.matches("save region"))
        XCTAssertTrue(LauncherAction.annotate.matches("capture with note"))
        XCTAssertTrue(LauncherAction.annotate.matches("screenshot note"))
        XCTAssertTrue(LauncherAction.library.matches("browse library"))
        XCTAssertTrue(LauncherAction.library.matches("files"))
        XCTAssertFalse(LauncherAction.capture.matches("note"))
        XCTAssertFalse(LauncherAction.library.matches("unrelated query"))
    }
    @MainActor
    func testVisionRecognizesFixtureAndReturnsTopLeftWordBoxes() async throws {
        _ = NSApplication.shared
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let source = directory.appendingPathComponent("ocr-fixture.png")
        let image = try fixtureImage()
        try XCTUnwrap(NSBitmapImageRep(data: XCTUnwrap(image.tiffRepresentation))?.representation(using: .png, properties: [:])).write(to: source)
        let boxes = try await NativeServices.recognize(source)
        let text = boxes.map(\.text).joined(separator: " ").lowercased()
        XCTAssertTrue(text.contains("database indexing"), "Vision returned: \(text)")
        XCTAssertFalse(boxes.isEmpty)
        for box in boxes {
            XCTAssertGreaterThan(box.width, 0)
            XCTAssertGreaterThan(box.height, 0)
            XCTAssertGreaterThanOrEqual(box.x, -0.001)
            XCTAssertGreaterThanOrEqual(box.y, -0.001)
            XCTAssertLessThanOrEqual(box.x + box.width, 1.001)
            XCTAssertLessThanOrEqual(box.y + box.height, 1.001)
        }
        // The title is drawn in the upper half. This detects a Vision bottom-left
        // coordinate accidentally reaching the top-left screenshot canvas unchanged.
        let title = try XCTUnwrap(boxes.first { $0.text.lowercased() == "database" })
        XCTAssertLessThan(title.y + title.height, 0.5)
    }

    /// Snapshots are a local QA aid, not pixel-perfect golden tests.
    @MainActor
    func testRenderDesignProposalWindowsInBothAppearances() throws {
        _ = NSApplication.shared
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let titles = ["Invoice total due Nov 14", "Kubernetes rollout stuck at 2/3", "Flight AC 884 gate B22",
                      "Brown butter ratio", "Figma spacing tokens", "Lease clause 7.2"]
        let accents = [NSColor.systemOrange, .systemGreen, .systemPurple, .systemYellow, .systemBlue, .systemRed]
        var sources: [URL] = []
        for index in titles.indices {
            let source = directory.appendingPathComponent("fixture-\(index).png")
            let image = try fixtureImage(title: titles[index], accent: accents[index])
            try XCTUnwrap(NSBitmapImageRep(data: XCTUnwrap(image.tiffRepresentation))?.representation(using: .png, properties: [:])).write(to: source)
            sources.append(source)
        }
        let library = try seededStore(directory: directory.appendingPathComponent("library"), titles: titles, sources: sources)
        let search = try seededStore(directory: directory.appendingPathComponent("search"), titles: Array(titles.prefix(3)), sources: Array(sources.prefix(3)))
        let single = try seededStore(directory: directory.appendingPathComponent("single"), titles: Array(titles.prefix(1)), sources: Array(sources.prefix(1)))
        let empty = try CaptureStore(directory: directory.appendingPathComponent("empty"))
        let output = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent(".build/qa", isDirectory: true)
        try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        let sample = try NativeServices.sampleImage()
        defer { try? FileManager.default.removeItem(at: sample) }
        let image = try XCTUnwrap(NSImage(contentsOf: sample))
        let boxes = [TextBox(text: "Total due November 14", x: 0.12, y: 0.696, width: 0.29, height: 0.045)]
        for scheme in [ColorScheme.light, .dark] {
            let suffix = scheme == .dark ? "dark" : "light"
            try render(SearchView(store: single, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: LauncherNavigation())
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 164),
                       to: output.appendingPathComponent("search-single-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: search, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: LauncherNavigation())
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 268),
                       to: output.appendingPathComponent("search-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: search, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: LauncherNavigation())
                .environment(\.colorScheme, scheme).environment(\.seenXForceOpaque, true),
                       size: NSSize(width: 640, height: 268),
                       to: output.appendingPathComponent("search-opaque-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: library, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: LauncherNavigation())
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 372),
                       to: output.appendingPathComponent("search-five-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: empty, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: LauncherNavigation())
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 268),
                       to: output.appendingPathComponent("search-empty-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: empty, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: LauncherNavigation())
                .environment(\.colorScheme, scheme).environment(\.seenXForceOpaque, true), size: NSSize(width: 640, height: 268),
                       to: output.appendingPathComponent("search-empty-opaque-\(suffix).png"), scheme: scheme)
            let commandNavigation = LauncherNavigation()
            commandNavigation.query = "note"
            try render(SearchView(store: empty, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: commandNavigation)
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 268),
                       to: output.appendingPathComponent("search-command-\(suffix).png"), scheme: scheme)
            let libraryNavigation = LauncherNavigation()
            libraryNavigation.showLibrary()
            try render(SearchView(store: library, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: libraryNavigation)
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 500),
                       to: output.appendingPathComponent("library-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: library, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: libraryNavigation)
                .environment(\.colorScheme, scheme).environment(\.seenXForceOpaque, true), size: NSSize(width: 640, height: 500),
                       to: output.appendingPathComponent("library-opaque-\(suffix).png"), scheme: scheme)
            let previewNavigation = LauncherNavigation()
            previewNavigation.showLibrary()
            previewNavigation.open(try XCTUnwrap(library.captures.first))
            try render(SearchView(store: library, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: previewNavigation)
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 500),
                       to: output.appendingPathComponent("preview-\(suffix).png"), scheme: scheme)
            try render(SearchView(store: library, opacity: 0.55, setOpacity: { _ in }, capture: { _ in }, openLibrary: {}, navigation: previewNavigation)
                .environment(\.colorScheme, scheme).environment(\.seenXForceOpaque, true), size: NSSize(width: 640, height: 500),
                       to: output.appendingPathComponent("preview-opaque-\(suffix).png"), scheme: scheme)
            try render(OnboardingView(allowAccess: {}, trySample: {}, skip: {}, permissionDenied: false)
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 420),
                       to: output.appendingPathComponent("onboarding-\(suffix).png"), scheme: scheme)
            try render(OnboardingView(allowAccess: {}, trySample: {}, skip: {}, permissionDenied: true, retryAccess: {}, restartApp: {})
                .environment(\.colorScheme, scheme), size: NSSize(width: 640, height: 480),
                       to: output.appendingPathComponent("onboarding-denied-\(suffix).png"), scheme: scheme)
            let session = AnnotationSession(url: sample, image: image)
            session.recognizing = false
            session.boxes = boxes
            session.select(boxes)
            try render(AnnotationView(session: session, submit: {}, cancel: {}, focusCanvas: {})
                .environment(\.colorScheme, scheme), size: NSSize(width: 1050, height: 740),
                       to: output.appendingPathComponent("annotation-\(suffix).png"), scheme: scheme)
        }
    }

    @MainActor
    private func render<Content: View>(_ content: Content, size: NSSize, to url: URL, scheme: ColorScheme) throws {
        let hosting = NSHostingView(rootView: content)
        hosting.frame = NSRect(origin: .zero, size: size)
        // Match the real floating panel so native Liquid Glass can composite against
        // a clear window rather than an opaque titled-window background.
        let window = NSWindow(contentRect: hosting.frame, styleMask: [.borderless], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.isOpaque = false
        window.backgroundColor = .clear
        window.appearance = NSAppearance(named: scheme == .dark ? .darkAqua : .aqua)
        hosting.appearance = window.appearance
        window.contentView = hosting
        hosting.layoutSubtreeIfNeeded()
        window.displayIfNeeded()
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.15))
        let bitmap = try XCTUnwrap(hosting.bitmapImageRepForCachingDisplay(in: hosting.bounds))
        hosting.cacheDisplay(in: hosting.bounds, to: bitmap)
        try XCTUnwrap(bitmap.representation(using: .png, properties: [:])).write(to: url)
        XCTAssertGreaterThan(bitmap.pixelsWide, 0)
        window.orderOut(nil)
    }

    @MainActor
    private func seededStore(directory: URL, titles: [String], sources: [URL]) throws -> CaptureStore {
        let store = try CaptureStore(directory: directory)
        for index in titles.indices.reversed() {
            _ = try store.save(image: sources[index], note: titles[index], boxes: [], highlights: [], ocrComplete: true)
        }
        var captures = store.captures
        for index in captures.indices {
            captures[index].createdAt = Date().addingTimeInterval(-120 - Double(index) * 86400)
        }
        try JSONEncoder().encode(captures).write(to: directory.appendingPathComponent("library.json"), options: .atomic)
        return try CaptureStore(directory: directory)
    }

    @MainActor
    private func fixtureImage(title: String = "Database indexing", accent: NSColor = .systemBlue) throws -> NSImage {
        let bitmap = try XCTUnwrap(NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1200, pixelsHigh: 700,
                                                   bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                                                   colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0))
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        NSColor(calibratedWhite: 0.97, alpha: 1).setFill()
        NSRect(x: 0, y: 0, width: 1200, height: 700).fill()
        accent.withAlphaComponent(0.15).setFill()
        NSRect(x: 0, y: 610, width: 1200, height: 90).fill()
        ("seenX · Sample screenshot" as NSString).draw(at: NSPoint(x: 72, y: 640), withAttributes: [.font: NSFont.systemFont(ofSize: 18, weight: .medium), .foregroundColor: NSColor.darkGray])
        (title as NSString).draw(at: NSPoint(x: 72, y: 525), withAttributes: [.font: NSFont.systemFont(ofSize: 44, weight: .semibold), .foregroundColor: NSColor.black])
        ("Find the information you saved. Remember why it mattered." as NSString)
            .draw(at: NSPoint(x: 72, y: 455), withAttributes: [.font: NSFont.systemFont(ofSize: 24), .foregroundColor: NSColor.darkGray])
        for index in 0..<4 {
            NSColor(calibratedWhite: 0.83 + Double(index) * 0.025, alpha: 1).setFill()
            NSBezierPath(roundedRect: NSRect(x: 72, y: CGFloat(340 - index * 65), width: CGFloat(1000 - index * 80), height: 18), xRadius: 9, yRadius: 9).fill()
        }
        NSGraphicsContext.restoreGraphicsState()
        let image = NSImage(size: NSSize(width: 1200, height: 700))
        image.addRepresentation(bitmap)
        return image
    }
}
