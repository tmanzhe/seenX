import AppKit
import Carbon
import ScreenCaptureKit
import Vision

enum NativeServices {
    /// Checks current capture authorization using the framework that consumes it.
    /// Enumerating shareable content reads metadata only; it captures no pixels.
    static func checkCaptureAccess() async throws {
        _ = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
    }

    static func isScreenPermissionError(_ error: Error) -> Bool {
        var current: Error? = error
        // Framework errors can be wrapped by another operation. Bound traversal in
        // case an NSError contains a cyclic underlying-error graph.
        for _ in 0..<8 {
            guard let next = current else { return false }
            let failure = next as NSError
            if failure.domain == SCStreamError.errorDomain,
               failure.code == SCStreamError.userDeclined.rawValue { return true }
            current = failure.userInfo[NSUnderlyingErrorKey] as? Error
        }
        return false
    }

    /// An authored image for trying annotations without accessing the user's screen.
    @MainActor
    static func sampleImage() throws -> URL {
        guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1200, pixelsHigh: 760,
                                            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                            isPlanar: false, colorSpaceName: .deviceRGB,
                                            bytesPerRow: 0, bitsPerPixel: 0),
              let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
            throw CocoaError(.fileWriteUnknown)
        }
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = context
        NSColor(srgbRed: 0.96, green: 0.97, blue: 1, alpha: 1).setFill()
        NSRect(x: 0, y: 0, width: 1200, height: 760).fill()
        NSColor.white.setFill()
        NSBezierPath(roundedRect: NSRect(x: 80, y: 56, width: 1040, height: 648), xRadius: 18, yRadius: 18).fill()
        let ink = NSColor(srgbRed: 0.094, green: 0.169, blue: 0.286, alpha: 1)
        let muted = NSColor(srgbRed: 0.357, green: 0.435, blue: 0.545, alpha: 1)
        func text(_ value: String, x: CGFloat, y: CGFloat, size: CGFloat, weight: NSFont.Weight = .regular, color: NSColor? = nil) {
            (value as NSString).draw(at: NSPoint(x: x, y: y), withAttributes: [
                .font: NSFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color ?? ink
            ])
        }
        text("STUDIO NORTH", x: 136, y: 622, size: 18, weight: .semibold)
        text("Sample invoice", x: 136, y: 550, size: 40, weight: .semibold)
        text("A sample image. Your screen has not been captured.", x: 136, y: 505, size: 20, color: muted)
        NSColor(srgbRed: 0.84, green: 0.89, blue: 0.95, alpha: 1).setFill()
        NSRect(x: 136, y: 465, width: 928, height: 2).fill()
        text("DESCRIPTION", x: 136, y: 422, size: 15, weight: .semibold, color: muted)
        text("AMOUNT", x: 900, y: 422, size: 15, weight: .semibold, color: muted)
        text("Design consultation", x: 136, y: 368, size: 24)
        text("$320.00", x: 900, y: 368, size: 24)
        text("Interface review", x: 136, y: 316, size: 24)
        text("$160.00", x: 900, y: 316, size: 24)
        NSColor(srgbRed: 0.92, green: 0.95, blue: 0.99, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 120, y: 164, width: 960, height: 100), xRadius: 12, yRadius: 12).fill()
        text("Total due November 14", x: 144, y: 198, size: 27, weight: .semibold)
        text("$480.00", x: 890, y: 194, size: 32, weight: .semibold)
        text("Try highlighting the due date, then add a thought to remember why.", x: 136, y: 104, size: 19, color: muted)
        NSGraphicsContext.restoreGraphicsState()
        guard let data = bitmap.representation(using: .png, properties: [:]) else { throw CocoaError(.fileWriteUnknown) }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("seenx-sample-\(UUID().uuidString).png")
        try data.write(to: url, options: .atomic)
        return url
    }

    static func recognize(_ url: URL) async throws -> [TextBox] {
        try await Task.detached(priority: .userInitiated) {
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true
            try VNImageRequestHandler(url: url, options: [:]).perform([request])
            return (request.results ?? []).flatMap { observation -> [TextBox] in
                guard let candidate = observation.topCandidates(1).first else { return [] }
                let text = candidate.string
                var words: [TextBox] = []
                for range in tokenRanges(in: text) {
                    let rect = (try? candidate.boundingBox(for: range))?.boundingBox ?? observation.boundingBox
                    words.append(TextBox(text: String(text[range]), x: rect.minX, y: 1 - rect.maxY, width: rect.width, height: rect.height))
                }
                if words.isEmpty {
                    let rect = observation.boundingBox
                    words = [TextBox(text: text, x: rect.minX, y: 1 - rect.maxY, width: rect.width, height: rect.height)]
                }
                return words
            }
        }.value
    }

    // Whitespace boundaries preserve code identifiers, operators and punctuation in search.
    static func tokenRanges(in text: String) -> [Range<String.Index>] {
        var ranges: [Range<String.Index>] = []
        var start: String.Index?
        for index in text.indices {
            if text[index].isWhitespace {
                if let beginning = start { ranges.append(beginning..<index); start = nil }
            } else if start == nil { start = index }
        }
        if let start { ranges.append(start..<text.endIndex) }
        return ranges
    }

    /// The system picker handles region selection, display scaling and screen permissions.
    /// A canceled picker produces no image and is never entered into the library.
    static func capture() async throws -> URL? {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("seenx-\(UUID().uuidString).png")
        return try await CaptureAttempt(imageURL: url).run()
    }
}

final class GlobalHotKeys {
    private var references: [EventHotKeyRef] = []
    private var movementReferences: [EventHotKeyRef] = []
    private var movementEnabled = false
    private var handler: EventHandlerRef?
    var action: ((UInt32) -> Void)?

    func register() -> [String] {
        let context = Unmanaged.passUnretained(self).toOpaque()
        var type = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let status = InstallEventHandler(GetApplicationEventTarget(), { _, event, context in
            guard let event, let context else { return OSStatus(eventNotHandledErr) }
            var id = EventHotKeyID()
            let result = GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil,
                                           MemoryLayout<EventHotKeyID>.size, nil, &id)
            guard result == noErr else { return result }
            let owner = Unmanaged<GlobalHotKeys>.fromOpaque(context).takeUnretainedValue()
            owner.action?(id.id)
            return noErr
        }, 1, &type, context, &handler)
        guard status == noErr else { return ["Global shortcuts could not be installed. Use the menu bar controls."] }
        var failures: [String] = []
        for (key, id, label): (UInt32, UInt32, String) in [(40, 1, "⌘⇧K"), (24, 2, "⌘⇧="), (27, 3, "⌘⇧−")] {
            var reference: EventHotKeyRef?
            let result = RegisterEventHotKey(key, UInt32(cmdKey | shiftKey), EventHotKeyID(signature: 0x534E5858, id: id),
                                             GetApplicationEventTarget(), 0, &reference)
            if result == noErr, let reference { references.append(reference) }
            else { failures.append("\(label) is unavailable. Another app may already use it; use the seenX menu bar control.") }
        }
        return failures
    }

    /// These chords belong to other apps when the search overlay is hidden.
    func setMovementEnabled(_ enabled: Bool) -> [String] {
        guard enabled != movementEnabled else { return [] }
        movementEnabled = enabled
        movementReferences.forEach { UnregisterEventHotKey($0) }
        movementReferences.removeAll()
        guard enabled else { return [] }
        guard handler != nil else { return OverlayDirection.allCases.map { "⌘⇧\($0.symbol)" } }
        var failures: [String] = []
        for direction in OverlayDirection.allCases {
            var reference: EventHotKeyRef?
            let result = RegisterEventHotKey(direction.keyCode, UInt32(cmdKey | shiftKey),
                EventHotKeyID(signature: 0x534E5858, id: direction.rawValue),
                GetApplicationEventTarget(), 0, &reference)
            if result == noErr, let reference { movementReferences.append(reference) }
            else { failures.append("⌘⇧\(direction.symbol)") }
        }
        return failures
    }

    deinit {
        references.forEach { UnregisterEventHotKey($0) }
        movementReferences.forEach { UnregisterEventHotKey($0) }
        if let handler { RemoveEventHandler(handler) }
    }
}
