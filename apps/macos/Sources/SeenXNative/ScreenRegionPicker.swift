import AppKit
import CoreGraphics

/// Selects a region without reading screen pixels. Coordinates are display-local
/// points with a top-left origin, as expected by SCStreamConfiguration.sourceRect.
@MainActor
final class ScreenRegionPicker {
    struct Selection {
        let displayID: CGDirectDisplayID
        let rect: CGRect
    }

    private var panels: [NSPanel] = []
    private var continuation: CheckedContinuation<Selection?, Never>?

    func select() async -> Selection? {
        await withCheckedContinuation { continuation in
            self.continuation = continuation
            for screen in NSScreen.screens {
                guard let number = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber else { continue }
                let panel = FloatingPanel(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
                panel.isReleasedWhenClosed = false
                panel.isOpaque = false
                panel.backgroundColor = .clear
                panel.level = .screenSaver
                panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
                panel.hidesOnDeactivate = false
                let view = RegionView(frame: NSRect(origin: .zero, size: screen.frame.size))
                view.finish = { [weak self] rect in
                    self?.finish(rect.map { Selection(displayID: number.uint32Value, rect: $0) })
                }
                panel.contentView = view
                panels.append(panel)
                panel.orderFrontRegardless()
                panel.makeFirstResponder(view)
            }
            NSApp.activate(ignoringOtherApps: true)
            let panel = panels.first { $0.frame.contains(NSEvent.mouseLocation) } ?? panels.first
            panel?.makeKeyAndOrderFront(nil)
            if panels.isEmpty { finish(nil) }
        }
    }

    private func finish(_ selection: Selection?) {
        panels.forEach { $0.orderOut(nil); $0.close() }
        panels.removeAll()
        let pending = continuation
        continuation = nil
        pending?.resume(returning: selection)
    }
}

@MainActor
private final class RegionView: NSView {
    var finish: ((CGRect?) -> Void)?
    private var start: NSPoint?
    private var selection = NSRect.zero
    override var acceptsFirstResponder: Bool { true }

    override func resetCursorRects() { addCursorRect(bounds, cursor: .crosshair) }

    override func draw(_ dirtyRect: NSRect) {
        let shade = NSBezierPath(rect: bounds)
        if !selection.isEmpty { shade.append(NSBezierPath(rect: selection)) }
        shade.windingRule = .evenOdd
        NSColor.black.withAlphaComponent(0.25).setFill()
        shade.fill()
        NSColor.white.setStroke()
        NSBezierPath(rect: selection).stroke()
        ("Drag to select a region · Esc to cancel" as NSString).draw(
            at: NSPoint(x: 24, y: bounds.height - 48),
            withAttributes: [.font: NSFont.systemFont(ofSize: 16), .foregroundColor: NSColor.white])
    }

    override func mouseDown(with event: NSEvent) {
        window?.makeKey()
        start = convert(event.locationInWindow, from: nil)
    }

    override func mouseDragged(with event: NSEvent) {
        guard let start else { return }
        let end = convert(event.locationInWindow, from: nil)
        selection = NSRect(x: min(start.x, end.x), y: min(start.y, end.y),
                           width: abs(end.x - start.x), height: abs(end.y - start.y)).intersection(bounds)
        needsDisplay = true
    }

    override func mouseUp(with event: NSEvent) {
        mouseDragged(with: event)
        guard selection.width >= 1, selection.height >= 1 else { finish?(nil); return }
        finish?(CGRect(x: selection.minX, y: bounds.height - selection.maxY,
                       width: selection.width, height: selection.height))
    }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 53 { finish?(nil) }
        else { super.keyDown(with: event) }
    }

    override func cancelOperation(_ sender: Any?) { finish?(nil) }
}
