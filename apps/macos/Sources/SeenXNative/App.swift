import AppKit
import Combine
import CoreGraphics
import SwiftUI

final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

@main
struct SeenXMain {
    @MainActor
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        withExtendedLifetime(delegate) { app.run() }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private var store: CaptureStore!
    private var statusItem: NSStatusItem!
    private var searchPanel: FloatingPanel?
    private var onboardingPanel: FloatingPanel?
    private var editorPanel: FloatingPanel?
    private var engineBrowser: EngineBrowserController?
    private let launcherCatalog = EngineBrowserModel()
    private var session: AnnotationSession?
    private let shortcuts = GlobalHotKeys()
    private var eventMonitor: Any?
    private var capturing = false
    private var saving = false
    private var libraryObservation: AnyCancellable?
    private var navigationObservation: AnyCancellable?
    private let navigation = LauncherNavigation()
    private var launcherResultCount = 3
    private var libraryStatus: NSMenuItem?
    private var opacity: Double = UserDefaults.standard.object(forKey: "glassBackgroundOpacity") as? Double ?? 0.55
    private var permissionDenied = false
    private var checkingScreenAccess = false
    private var pendingCaptureMode: Bool?

    func applicationDidFinishLaunching(_ notification: Notification) {
        do { store = try CaptureStore() }
        catch {
            showError("Your library could not be opened. Its existing files have been preserved.\n\(error.localizedDescription)")
            NSApp.terminate(nil)
            return
        }
        buildMenu()
        libraryObservation = store.$captures.sink { [weak self] items in
            self?.libraryStatus?.title = "\(items.count) saved screenshot\(items.count == 1 ? "" : "s")"
            self?.statusItem.button?.toolTip = "seenX · \(items.count) saved screenshots"
        }
        navigationObservation = navigation.$screen.sink { [weak self] screen in self?.resizeLauncher(for: screen) }
        shortcuts.action = { [weak self] id in
            Task { @MainActor in
                switch id {
                case 1: self?.toggleSearch()
                case 2: self?.beginCapture(annotate: false)
                case 3: self?.beginCapture(annotate: true)
                default:
                    if let direction = OverlayDirection(rawValue: id) { self?.moveSearch(direction) }
                }
            }
        }
        let failures = shortcuts.register()
        eventMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self else { return event }
            let handled = MainActor.assumeIsolated { self.handleKey(event) == nil }
            return handled ? nil : event
        }
        if UserDefaults.standard.bool(forKey: "completedSetup") || CGPreflightScreenCaptureAccess() {
            showSearch()
        } else {
            showOnboarding()
        }
        if !failures.isEmpty { showError(failures.joined(separator: "\n")) }
        resumePendingIndexing()
    }

    private func resumePendingIndexing() {
        let pending = store.captures.filter { $0.ocrComplete != true }
        Task { @MainActor in
            for capture in pending {
                do { try store.updateOCR(id: capture.id, boxes: try await NativeServices.recognize(store.imageURL(for: capture))) }
                catch {
                    statusItem.button?.toolTip = "seenX · Some saved screenshots could not be indexed. Their images and notes are preserved."
                }
            }
        }
    }

    private func buildMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem.button?.image = NSImage(systemSymbolName: "viewfinder", accessibilityDescription: "seenX")
        let menu = NSMenu()
        let count = NSMenuItem(title: "0 saved screenshots", action: nil, keyEquivalent: "")
        menu.addItem(count)
        libraryStatus = count
        menu.addItem(.separator())
        for (title, selector) in [("Search  ⌘⇧K", #selector(searchAction)),
                                  ("Open Library", #selector(libraryAction)),
                                  ("Save screenshot  ⌘⇧=", #selector(captureAction)),
                                  ("Screenshot with note  ⌘⇧−", #selector(annotateAction)),
                                  ("Try a sample image", #selector(sampleAction))] {
            let item = NSMenuItem(title: title, action: selector, keyEquivalent: "")
            item.target = self
            menu.addItem(item)
        }
        menu.addItem(.separator())
        let engineItem = NSMenuItem(title: "Open Python Library…", action: #selector(engineLibraryAction), keyEquivalent: "")
        engineItem.target = self
        menu.addItem(engineItem)
        let quit = NSMenuItem(title: "Quit seenX", action: #selector(quitAction), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)
        statusItem.menu = menu
        let mainMenu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        let mainQuit = NSMenuItem(title: "Quit seenX", action: #selector(quitAction), keyEquivalent: "q")
        mainQuit.target = self
        appMenu.addItem(mainQuit)
        appItem.submenu = appMenu
        mainMenu.addItem(appItem)
        let edit = NSMenuItem()
        let editMenu = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", Selector(("undo:")), "z"), ("Redo", Selector(("redo:")), "Z"),
                                    ("Cut", #selector(NSText.cut(_:)), "x"), ("Copy", #selector(NSText.copy(_:)), "c"),
                                    ("Paste", #selector(NSText.paste(_:)), "v"), ("Select All", #selector(NSText.selectAll(_:)), "a")] {
            editMenu.addItem(withTitle: title, action: action, keyEquivalent: key)
        }
        edit.submenu = editMenu
        mainMenu.addItem(edit)
        NSApp.mainMenu = mainMenu
    }

    @objc private func searchAction() { showSearch() }
    @objc private func libraryAction() { showLibrary() }
    @objc private func captureAction() { beginCapture(annotate: false) }
    @objc private func annotateAction() { beginCapture(annotate: true) }
    @objc private func sampleAction() { openSample() }
    @objc private func engineLibraryAction() {
        if engineBrowser == nil { engineBrowser = EngineBrowserController() }
        engineBrowser?.showWindow(nil)
        engineBrowser?.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    @objc private func quitAction() {
        guard confirmDiscard() else { return }
        NSApp.terminate(nil)
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        confirmDiscard() ? .terminateNow : .terminateCancel
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showSearch()
        return true
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        // A Settings grant can take effect when the app returns to the foreground.
        if permissionDenied && CGPreflightScreenCaptureAccess() { retryScreenAccess() }
    }

    private func makePanel(title: String, size: NSSize, resizable: Bool = false) -> FloatingPanel {
        let visibleFrame = (NSScreen.main ?? NSScreen.screens.first)?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let fittedSize = NSSize(width: min(size.width, visibleFrame.width - 48), height: min(size.height, visibleFrame.height - 48))
        let panel = FloatingPanel(contentRect: NSRect(origin: .zero, size: fittedSize),
                                  styleMask: resizable ? [.borderless, .resizable] : [.borderless], backing: .buffered, defer: false)
        panel.title = title
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isReleasedWhenClosed = false
        panel.hasShadow = true
        panel.isMovableByWindowBackground = true
        panel.minSize = NSSize(width: min(fittedSize.width, 540), height: min(fittedSize.height, 300))
        panel.center()
        panel.delegate = self
        return panel
    }

    private func present(_ panel: FloatingPanel, content: some View) {
        panel.appearance = NSAppearance(named: .aqua)
        let hosting = NSHostingView(rootView: content.preferredColorScheme(.light))
        hosting.wantsLayer = true
        hosting.layer?.cornerRadius = 22
        hosting.layer?.masksToBounds = true
        panel.contentView = hosting
        panel.alphaValue = 1
        NSApp.activate(ignoringOtherApps: true)
        panel.makeKeyAndOrderFront(nil)
    }

    private func showOnboarding() {
        hideSearch()
        let panel = onboardingPanel ?? makePanel(title: "Welcome to seenX", size: NSSize(width: 640, height: 420))
        onboardingPanel = panel
        present(panel, content: OnboardingView(
            allowAccess: { [weak self] in self?.allowScreenAccess() },
            trySample: { [weak self] in self?.openSample() },
            skip: { [weak self] in self?.completeSetup(); self?.showSearch() },
            permissionDenied: permissionDenied,
            retryAccess: { [weak self] in self?.retryScreenAccess() },
            restartApp: { [weak self] in self?.restartApplication() }))
        if permissionDenied {
            var frame = panel.frame
            let top = frame.maxY
            frame.size.height = min(480, (panel.screen ?? NSScreen.main)?.visibleFrame.height ?? 480)
            frame.origin.y = max((panel.screen ?? NSScreen.main)?.visibleFrame.minY ?? 0, top - frame.height)
            panel.setFrame(frame, display: true)
        }
    }

    private func completeSetup() {
        UserDefaults.standard.set(true, forKey: "completedSetup")
        onboardingPanel?.orderOut(nil)
        onboardingPanel = nil
    }

    private func allowScreenAccess() {
        if permissionDenied {
            NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")!)
            return
        }
        if !CGPreflightScreenCaptureAccess() { _ = CGRequestScreenCaptureAccess() }
        retryScreenAccess()
    }

    private func retryScreenAccess() {
        guard !checkingScreenAccess else { return }
        checkingScreenAccess = true
        Task { @MainActor in
            defer { checkingScreenAccess = false }
            do {
                // Check the actual capture API; a stale preflight flag must not block it.
                try await NativeServices.checkCaptureAccess()
                permissionDenied = false
                let pending = pendingCaptureMode
                pendingCaptureMode = nil
                completeSetup()
                if let pending { beginCapture(annotate: pending) } else { showSearch() }
            } catch {
                permissionDenied = true
                showOnboarding()
                if !NativeServices.isScreenPermissionError(error) {
                    showError("Screen access could not be checked. Try again, or restart seenX if access is already enabled.\n\(error.localizedDescription)")
                }
            }
        }
    }

    private func restartApplication() {
        guard confirmDiscard() else { return }
        let helper = Process()
        helper.executableURL = URL(fileURLWithPath: "/bin/sh")
        // Positional arguments keep the bundle path out of shell interpolation.
        helper.arguments = ["-c", "i=0; while /bin/kill -0 \"$1\" 2>/dev/null; do i=$((i+1)); [ \"$i\" -lt 100 ] || exit 1; /bin/sleep 0.1; done; exec /usr/bin/open \"$2\"",
                            "seenx-restart", String(ProcessInfo.processInfo.processIdentifier), Bundle.main.bundleURL.path]
        helper.standardInput = FileHandle.nullDevice
        helper.standardOutput = FileHandle.nullDevice
        helper.standardError = FileHandle.nullDevice
        do { try helper.run(); NSApp.terminate(nil) }
        catch { showError("seenX could not restart. Quit it from the menu bar and reopen the app.\n\(error.localizedDescription)") }
    }

    private func openSample() {
        guard !capturing, !saving, confirmDiscard() else { return }
        do {
            let url = try NativeServices.sampleImage()
            pendingCaptureMode = nil
            completeSetup()
            hideSearch()
            openEditor(url)
        } catch { showError("The sample image could not be opened.\n\(error.localizedDescription)") }
    }

    func showSearch() {
        guard !capturing else { return }
        onboardingPanel?.orderOut(nil)
        navigation.resetForSummon()
        if searchPanel == nil {
            let panel = makePanel(title: "seenX Search", size: NSSize(width: 640, height: searchHeight(for: store.captures.count)))
            searchPanel = panel
            present(panel, content: SearchView(store: store, opacity: opacity,
                setOpacity: { [weak self] in self?.setOpacity($0) },
                capture: { [weak self] in self?.beginCapture(annotate: $0) },
                openLibrary: { [weak self] in self?.showLibrary() }, navigation: navigation,
                quitApp: { [weak self] in self?.quitAction() },
                restartApp: { [weak self] in self?.restartApplication() },
                catalog: launcherCatalog,
                resultsChanged: { [weak self] in self?.resizeSearch(for: $0) }))
        }
        NSApp.activate(ignoringOtherApps: true)
        searchPanel?.makeKeyAndOrderFront(nil)
        let unavailable = shortcuts.setMovementEnabled(true)
        if !unavailable.isEmpty {
            statusItem.button?.toolTip = "seenX · \(unavailable.joined(separator: ", ")) is in use. Drag the search panel to move it."
        }
        NotificationCenter.default.post(name: Notification.Name("seenX.focusSearch"), object: "search")
    }

    private func toggleSearch() {
        guard !capturing else { return }
        if searchPanel?.isVisible == true { hideSearch() }
        else { showSearch() }
    }

    private func hideSearch() {
        searchPanel?.orderOut(nil)
        _ = shortcuts.setMovementEnabled(false)
    }

    private func moveSearch(_ direction: OverlayDirection) {
        guard let panel = searchPanel, panel.isVisible,
              let display = panel.screen ?? NSScreen.main else { return }
        panel.setFrame(direction.moving(panel.frame, inside: display.visibleFrame), display: true)
    }

    private func searchHeight(for count: Int) -> CGFloat { CGFloat(142 + (count == 0 ? 3 : min(count, 5)) * 52) }

    private func resizeSearch(for count: Int) {
        launcherResultCount = count
        guard navigation.screen == .search else { return }
        resizeLauncher(for: .search, count: count)
    }

    private func resizeLauncher(for screen: LauncherScreen, count: Int? = nil) {
        guard let panel = searchPanel else { return }
        var frame = panel.frame
        let top = frame.maxY
        switch screen {
        case .search: frame.size.height = searchHeight(for: count ?? launcherResultCount)
        case .library, .detail, .catalogDetail: frame.size.height = 500
        }
        if let display = panel.screen ?? NSScreen.main { frame.size.height = min(frame.height, display.visibleFrame.height - 48) }
        frame.origin.y = top - frame.height
        if let display = panel.screen ?? NSScreen.main { frame.origin.y = max(frame.minY, display.visibleFrame.minY + 16) }
        panel.setFrame(frame, display: true)
    }

    private func showLibrary() {
        guard !capturing else { return }
        showSearch()
        navigation.showLibrary()
    }

    private func setOpacity(_ value: Double) {
        opacity = min(max(value, 0.25), 0.85)
        UserDefaults.standard.set(opacity, forKey: "glassBackgroundOpacity")
    }

    private func confirmDiscard() -> Bool {
        guard session != nil else { return true }
        let alert = NSAlert()
        alert.messageText = "Discard this screenshot?"
        alert.informativeText = "This capture and its annotations have not been saved."
        alert.addButton(withTitle: "Keep Editing")
        alert.addButton(withTitle: "Discard")
        guard alert.runModal() == .alertSecondButtonReturn else { return false }
        closeEditor()
        return true
    }

    func beginCapture(annotate: Bool) {
        guard !capturing, !saving else { return }
        capturing = true
        Task { @MainActor in
            do {
                try await NativeServices.checkCaptureAccess()
                guard confirmDiscard() else { capturing = false; return }
                permissionDenied = false
                hideSearch()
                onboardingPanel?.orderOut(nil)
                editorPanel?.orderOut(nil)
                engineBrowser?.window?.orderOut(nil)
                // Give WindowServer a frame to remove the panels before the system picker.
                try? await Task.sleep(nanoseconds: 180_000_000)
                guard let url = try await NativeServices.capture() else { capturing = false; return }
                capturing = false
                if annotate { openEditor(url) }
                else {
                    do {
                        let capture = try store.save(image: url, note: "", boxes: [], highlights: [])
                        Task { @MainActor in
                            defer { try? FileManager.default.removeItem(at: url) }
                            do { try store.updateOCR(id: capture.id, boxes: try await NativeServices.recognize(url)) }
                            catch { showError("Screenshot saved, but its text could not be indexed.\n\(error.localizedDescription)") }
                        }
                    } catch {
                        openEditor(url)
                        session?.error = "Could not save: \(error.localizedDescription). Your screenshot is still open; try Save again."
                    }
                }
            } catch {
                capturing = false
                if NativeServices.isScreenPermissionError(error) {
                    pendingCaptureMode = annotate
                    permissionDenied = true
                    showOnboarding()
                } else {
                    showError("Screenshot capture failed. No screenshot was saved.\n\(error.localizedDescription)")
                    showSearch()
                }
            }
        }
    }

    private func openEditor(_ url: URL) {
        guard let image = NSImage(contentsOf: url) else { showError("The screenshot could not be opened."); return }
        let model = AnnotationSession(url: url, image: image)
        session = model
        let panel = makePanel(title: "Annotate screenshot", size: NSSize(width: 1050, height: 740), resizable: true)
        panel.isMovableByWindowBackground = false
        panel.minSize = NSSize(width: min(760, panel.frame.width), height: min(540, panel.frame.height))
        editorPanel = panel
        present(panel, content: AnnotationView(session: model,
            submit: { [weak self] in self?.submitAnnotation() }, cancel: { [weak self] in _ = self?.confirmDiscard() },
            focusCanvas: { [weak panel] in panel?.makeFirstResponder(nil) }))
        Task { @MainActor in
            do { model.boxes = try await NativeServices.recognize(url) }
            catch { model.error = "Text recognition failed. You can still add a note and save.\n\(error.localizedDescription)" }
            model.recognizing = false
        }
    }

    private func submitAnnotation() {
        guard let model = session, !saving else { return }
        guard model.submit() == .save else { return }
        saving = true
        defer { saving = false }
        do {
            let capture = try store.save(image: model.imageURL, note: model.note, boxes: model.boxes, highlights: model.state.highlights,
                                         ocrComplete: !model.recognizing && model.error == nil)
            let pendingOCR = model.recognizing
            let sourceURL = model.imageURL
            closeEditor(removeTemporary: !pendingOCR)
            if pendingOCR {
                Task { @MainActor in
                    defer { try? FileManager.default.removeItem(at: sourceURL) }
                    do { try store.updateOCR(id: capture.id, boxes: try await NativeServices.recognize(sourceURL)) }
                    catch { showError("Screenshot saved, but text indexing failed.\n\(error.localizedDescription)") }
                }
            }
        } catch { model.error = "Could not save: \(error.localizedDescription). Your annotations are still here; try again." }
    }

    private func closeEditor(removeTemporary: Bool = true) {
        if removeTemporary, let url = session?.imageURL { try? FileManager.default.removeItem(at: url) }
        session = nil
        editorPanel?.orderOut(nil)
        editorPanel = nil
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if sender === searchPanel { hideSearch(); return false }
        if sender === editorPanel { return confirmDiscard() }
        return true
    }

    private func handleKey(_ event: NSEvent) -> NSEvent? {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        if flags == .command, event.keyCode == 12 {
            quitAction()
            return nil
        }
        if flags == [.command, .shift], searchPanel?.isVisible == true,
           let direction = OverlayDirection.allCases.first(where: { $0.keyCode == UInt32(event.keyCode) }) {
            moveSearch(direction)
            return nil
        }
        if flags == .command, event.keyCode == 40 {
            if NSApp.keyWindow === searchPanel {
                NotificationCenter.default.post(name: Notification.Name("seenX.focusSearch"), object: "search")
            } else { showSearch() }
            return nil
        }
        guard NSApp.keyWindow === editorPanel, let model = session else {
            if event.keyCode == 53, NSApp.keyWindow === searchPanel {
                if !navigation.handleEscape() { hideSearch() }
                return nil
            }
            if event.keyCode == 53, NSApp.keyWindow === onboardingPanel { pendingCaptureMode = nil; completeSetup(); showSearch(); return nil }
            return event
        }
        if flags.contains(.command), event.keyCode == 36 {
            guard !event.isARepeat else { return nil }
            submitAnnotation()
            return nil
        }
        if flags.contains(.command), [51, 117].contains(event.keyCode) {
            model.deleteHighlight()
            return nil
        }
        if flags.contains(.command), event.keyCode == 6, !(editorPanel?.firstResponder is NSTextView) {
            if flags.contains(.shift) { model.undoManager.redo() } else { model.undoManager.undo() }
            return nil
        }
        if event.keyCode == 53 {
            if !model.cancelPending() { _ = confirmDiscard() }
            return nil
        }
        return event
    }

    private func showError(_ message: String) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "seenX"
        alert.informativeText = message
        alert.runModal()
    }
}
