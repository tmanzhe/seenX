import AppKit
import SwiftUI

enum LauncherAction: String, CaseIterable, Identifiable {
    case capture, annotate, library
    var id: String { rawValue }
    var title: String {
        switch self {
        case .capture: return "Capture Screenshot"
        case .annotate: return "Capture with Note"
        case .library: return "Browse Library"
        }
    }
    var symbol: String {
        switch self {
        case .capture: return "camera"
        case .annotate: return "square.and.pencil"
        case .library: return "square.grid.2x2"
        }
    }
    var shortcut: String {
        switch self {
        case .capture: return "⌘⇧="
        case .annotate: return "⌘⇧−"
        case .library: return "↩"
        }
    }
    func matches(_ query: String) -> Bool {
        let aliases: String
        switch self {
        case .capture: aliases = "capture screenshot screen region save"
        case .annotate: aliases = "capture screenshot screen region note annotate thought"
        case .library: aliases = "browse library files saved memories"
        }
        let searchable = title + " " + aliases
        return query.split(whereSeparator: \.isWhitespace).allSatisfy { searchable.localizedCaseInsensitiveContains(String($0)) }
    }
}

private enum LauncherRow: Identifiable {
    case saved(SavedCapture)
    case action(LauncherAction)
    var id: String {
        switch self {
        case .saved(let capture): return capture.id.uuidString
        case .action(let action): return action.id
        }
    }
}

struct SearchView: View {
    @ObservedObject var store: CaptureStore
    @State var opacity: Double
    let setOpacity: (Double) -> Void
    let capture: (Bool) -> Void
    let openLibrary: () -> Void
    @ObservedObject var navigation: LauncherNavigation
    var quitApp: (() -> Void)? = nil
    var restartApp: (() -> Void)? = nil
    @Environment(\.colorScheme) private var scheme
    @State private var focusToken = 0
    private var theme: SeenXTheme { SeenXTheme(scheme: scheme) }
    private var query: Binding<String> {
        Binding(get: { navigation.query }, set: { navigation.query = $0; navigation.selectedIndex = 0 })
    }
    private var rows: [LauncherRow] {
        let saved = Array(store.results(for: navigation.query).prefix(5)).map(LauncherRow.saved)
        if navigation.query.isEmpty { return saved.isEmpty ? LauncherAction.allCases.map(LauncherRow.action) : saved }
        return saved + LauncherAction.allCases.filter { $0.matches(navigation.query) }.map(LauncherRow.action)
    }
    private var libraryResults: [SavedCapture] { store.results(for: navigation.query) }
    private var selectedCapture: SavedCapture? {
        switch navigation.screen {
        case .detail(let item): return item
        case .library:
            return libraryResults.indices.contains(navigation.selectedIndex) ? libraryResults[navigation.selectedIndex] : nil
        case .search:
            guard rows.indices.contains(navigation.selectedIndex), case .saved(let item) = rows[navigation.selectedIndex] else { return nil }
            return item
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            switch navigation.screen {
            case .search: searchResults
            case .library:
                InlineLibraryGrid(store: store, results: libraryResults, selectedIndex: $navigation.selectedIndex,
                                  open: { navigation.open($0) })
            case .detail(let item): CapturePreviewContent(capture: item, url: store.imageURL(for: item))
            }
            Rectangle().fill(theme.border.opacity(0.35)).frame(height: 1)
            footer
        }
        .frame(minWidth: 520, minHeight: 148).foregroundStyle(theme.primary).tint(theme.accent).seenXGlass(opacity: opacity)
        .task { focusToken += 1 }
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("seenX.focusSearch"))) { notification in
            guard notification.object as? String == "search" else { return }
            if case .detail = navigation.screen { navigation.back() }
            focusToken += 1
        }
        .onChange(of: navigation.screen) { _, screen in
            if case .detail = screen { return }
            focusToken += 1
        }
        .onChange(of: rows.map(\.id)) { _, _ in
            if navigation.screen == .search { navigation.selectedIndex = min(navigation.selectedIndex, max(0, rows.count - 1)) }
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            if navigation.screen == .search {
                Image(systemName: "magnifyingglass").font(.system(size: 17)).foregroundStyle(theme.secondary)
            } else {
                Button { navigation.back() } label: { Image(systemName: "chevron.left").font(.system(size: 14, weight: .medium)) }
                    .buttonStyle(.plain).foregroundStyle(theme.secondary).help("Back · Esc").accessibilityLabel("Back")
            }
            if case .detail(let item) = navigation.screen {
                Text(item.title).font(.system(size: 14, weight: .medium)).lineLimit(1)
                Spacer()
                Text(item.createdAt.formatted(date: .abbreviated, time: .shortened))
                    .font(.system(size: 10)).foregroundStyle(theme.secondary)
            } else {
                SearchInput(text: query, placeholder: navigation.screen == .library ? "Search library…" : "Search screenshots or commands…",
                            focusToken: focusToken, fontSize: 16, move: moveSelection, submit: runSelected)
                if !navigation.query.isEmpty {
                    Button { navigation.query = ""; navigation.selectedIndex = 0; focusToken += 1 } label: { Image(systemName: "xmark.circle.fill") }
                        .buttonStyle(.plain).foregroundStyle(theme.secondary).accessibilityLabel("Clear search")
                }
                ShortcutBadge(text: "⌘K")
            }
        }.padding(.horizontal, 20).frame(height: 56)
    }

    private var searchResults: some View {
        ScrollViewReader { proxy in
            ScrollView {
                if rows.isEmpty {
                    VStack(spacing: 8) {
                        Text("No matching screenshots.").font(.system(size: 14, weight: .medium))
                        Text("Try another word, or type Capture to save something new.")
                            .font(.system(size: 12)).foregroundStyle(theme.secondary)
                    }.frame(maxWidth: .infinity).padding(.vertical, 32)
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                            Button { navigation.selectedIndex = index; runSelected() } label: {
                                switch row {
                                case .saved(let item):
                                    SearchResultRow(capture: item, url: store.imageURL(for: item), selected: index == navigation.selectedIndex)
                                case .action(let action): LauncherActionRow(action: action, selected: index == navigation.selectedIndex)
                                }
                            }.buttonStyle(.plain).onHover { if $0 { navigation.selectedIndex = index } }.id(index)
                        }
                    }.padding(.horizontal, 8).padding(.vertical, 8)
                }
            }.scrollIndicators(.hidden)
                .onChange(of: navigation.selectedIndex) { _, index in proxy.scrollTo(index) }
        }
    }

    private var footer: some View {
        HStack(spacing: 10) {
            Image(systemName: "viewfinder").font(.system(size: 11)).foregroundStyle(theme.secondary)
            Text("⌘⇧ + arrows").font(.system(size: 10, design: .monospaced)).foregroundStyle(theme.secondary)
                .help("Hold Command and Shift, then press the arrow keys to move the overlay")
            Spacer()
            Button(action: runSelected) { HStack(spacing: 5) { Text(primaryTitle); ShortcutBadge(text: "↩") } }
                .buttonStyle(.plain).keyboardShortcut(.defaultAction).disabled(!canRun)
            Rectangle().fill(theme.border.opacity(0.45)).frame(width: 1, height: 12).padding(.horizontal, 2)
            Button { navigation.actionsPresented.toggle() } label: { HStack(spacing: 5) { Text("Actions"); Image(systemName: "ellipsis") } }
                .buttonStyle(.plain).foregroundStyle(theme.secondary)
                .popover(isPresented: $navigation.actionsPresented) { actions }
        }.font(.system(size: 11)).padding(.horizontal, 16).frame(height: 32)
    }

    private var actions: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(LauncherAction.allCases) { action in
                Button { navigation.actionsPresented = false; perform(action) } label: {
                    HStack(spacing: 12) {
                        Image(systemName: action.symbol).frame(width: 16)
                        Text(action.title)
                        Spacer()
                        ShortcutBadge(text: action.shortcut)
                    }.padding(8).contentShape(Rectangle())
                }.buttonStyle(.plain)
            }
            if let item = selectedCapture {
                Divider().padding(.vertical, 4)
                Button("Reveal in Finder") { NSWorkspace.shared.activateFileViewerSelecting([store.imageURL(for: item)]); navigation.actionsPresented = false }
                    .buttonStyle(.plain).padding(8)
            }
            Divider().padding(.vertical, 4)
            HStack {
                Text("Glass opacity").font(.system(size: 11)).foregroundStyle(theme.secondary)
                Spacer()
                Slider(value: $opacity, in: 0.25...0.85).frame(width: 100).accessibilityLabel("Glass background opacity")
                    .onChange(of: opacity) { _, value in setOpacity(value) }
            }.padding(8)
            if restartApp != nil || quitApp != nil {
                Divider().padding(.vertical, 4)
                if let restartApp {
                    Button { navigation.actionsPresented = false; restartApp() } label: {
                        HStack(spacing: 12) {
                            Image(systemName: "arrow.clockwise").frame(width: 16)
                            Text("Restart seenX")
                            Spacer()
                        }.padding(8).contentShape(Rectangle())
                    }.buttonStyle(.plain)
                }
                if let quitApp {
                    Button { navigation.actionsPresented = false; quitApp() } label: {
                        HStack(spacing: 12) {
                            Image(systemName: "power").frame(width: 16)
                            Text("Quit seenX")
                            Spacer()
                            ShortcutBadge(text: "⌘Q")
                        }.padding(8).contentShape(Rectangle())
                    }.buttonStyle(.plain)
                }
            }
        }.font(.system(size: 12)).foregroundStyle(theme.primary).padding(8).frame(width: 290)
    }

    private var canRun: Bool {
        switch navigation.screen {
        case .detail: return true
        case .library: return selectedCapture != nil
        case .search: return rows.indices.contains(navigation.selectedIndex)
        }
    }
    private var primaryTitle: String {
        if case .detail = navigation.screen { return "Open image" }
        guard navigation.screen == .search, rows.indices.contains(navigation.selectedIndex),
              case .action(let action) = rows[navigation.selectedIndex] else { return "Open" }
        return action == .library ? "Browse" : "Capture"
    }
    private func moveSelection(_ direction: Int) {
        let count = navigation.screen == .library ? libraryResults.count : rows.count
        navigation.selectedIndex = min(max(navigation.selectedIndex + direction, 0), max(0, count - 1))
    }
    private func runSelected() {
        if case .detail(let item) = navigation.screen { NSWorkspace.shared.open(store.imageURL(for: item)); return }
        if navigation.screen == .library { if let item = selectedCapture { navigation.open(item) }; return }
        guard rows.indices.contains(navigation.selectedIndex) else { return }
        switch rows[navigation.selectedIndex] {
        case .saved(let item): navigation.open(item)
        case .action(let action): perform(action)
        }
    }
    private func perform(_ action: LauncherAction) {
        switch action {
        case .capture: capture(false)
        case .annotate: capture(true)
        case .library: navigation.showLibrary()
        }
    }
}

private struct LauncherActionRow: View {
    let action: LauncherAction
    let selected: Bool
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        let theme = SeenXTheme(scheme: scheme)
        HStack(spacing: 12) {
            Image(systemName: action.symbol).font(.system(size: 16)).foregroundStyle(theme.accent)
                .frame(width: 36, height: 36).background(theme.panel.opacity(0.12), in: RoundedRectangle(cornerRadius: 8))
            Text(action.title).font(.system(size: 13, weight: .medium)).foregroundStyle(theme.primary)
            Spacer()
            ShortcutBadge(text: action.shortcut)
        }.padding(.horizontal, 12).frame(height: 52)
            .background(selected ? theme.panel.opacity(0.18) : .clear, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(selected ? theme.border.opacity(0.65) : .clear, lineWidth: 1))
            .contentShape(Rectangle())
    }
}

private struct InlineLibraryGrid: View {
    @ObservedObject var store: CaptureStore
    let results: [SavedCapture]
    @Binding var selectedIndex: Int
    let open: (SavedCapture) -> Void
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        let theme = SeenXTheme(scheme: scheme)
        GeometryReader { geometry in
            ScrollViewReader { proxy in
                ScrollView {
                    if results.isEmpty {
                        Text("No saved screenshots here yet.").font(.system(size: 13)).foregroundStyle(theme.secondary)
                            .frame(maxWidth: .infinity).padding(.vertical, 48)
                    } else {
                        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 12) {
                            ForEach(Array(results.enumerated()), id: \.element.id) { index, item in
                                Button { selectedIndex = index; open(item) } label: {
                                    VStack(alignment: .leading, spacing: 8) {
                                        CaptureThumbnail(url: store.imageURL(for: item)).frame(height: min(154, (geometry.size.width - 56) / 3 * 0.52))
                                            .clipShape(RoundedRectangle(cornerRadius: 8))
                                        Text(item.title).font(.system(size: 12, weight: .medium)).lineLimit(1)
                                    }.padding(6).foregroundStyle(theme.primary)
                                        .background(theme.panel.opacity(index == selectedIndex ? 0.18 : 0.06), in: RoundedRectangle(cornerRadius: 10))
                                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(index == selectedIndex ? theme.brand.opacity(0.7) : theme.border.opacity(0.3), lineWidth: 1))
                                }.buttonStyle(.plain).onHover { if $0 { selectedIndex = index } }.id(index)
                            }
                        }.padding(16)
                    }
                }.scrollIndicators(.hidden)
                    .onChange(of: selectedIndex) { _, index in proxy.scrollTo(index) }
            }
        }
    }
}

private struct CapturePreviewContent: View {
    let capture: SavedCapture
    let url: URL
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        let theme = SeenXTheme(scheme: scheme)
        VStack(alignment: .leading, spacing: 12) {
            if let image = NSImage(contentsOf: url) {
                ScreenshotCanvas(image: image, boxes: [], highlights: capture.highlights, pending: [], selected: nil, select: nil)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView("Original image is missing", systemImage: "photo.badge.exclamationmark",
                                       description: Text("Your saved note and text remain available below."))
            }
            if !capture.note.isEmpty || !capture.highlights.isEmpty || !capture.text.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        if !capture.note.isEmpty { Text(capture.note).font(.system(size: 13)).textSelection(.enabled) }
                        ForEach(capture.highlights) { highlight in
                            Label(highlight.text, systemImage: "highlighter").font(.system(size: 12)).textSelection(.enabled)
                        }
                        if capture.note.isEmpty && capture.highlights.isEmpty {
                            Text(capture.text).font(.system(size: 12)).foregroundStyle(theme.secondary).textSelection(.enabled)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }.frame(maxHeight: 96)
            }
        }.padding(16)
    }
}

private struct SearchResultRow: View {
    let capture: SavedCapture
    let url: URL
    let selected: Bool
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        let theme = SeenXTheme(scheme: scheme)
        HStack(spacing: 12) {
            CaptureThumbnail(url: url).frame(width: 36, height: 36).clipShape(RoundedRectangle(cornerRadius: 8))
            VStack(alignment: .leading, spacing: 3) {
                Text(capture.title).font(.system(size: 13, weight: .medium)).foregroundStyle(theme.primary).lineLimit(1)
                if capture.ocrComplete != true {
                    Text("Text indexing pending").font(.system(size: 10)).foregroundStyle(theme.secondary)
                }
            }
            Spacer(minLength: 8)
            Text(shortDate(capture.createdAt)).font(.system(size: 12)).foregroundStyle(theme.secondary)
        }
        .padding(.horizontal, 12).frame(height: 52)
        .background(selected ? theme.panel.opacity(0.18) : .clear, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(selected ? theme.border.opacity(0.65) : .clear, lineWidth: 1))
        .contentShape(Rectangle())
    }

    private func shortDate(_ date: Date) -> String {
        let elapsed = max(0, Date().timeIntervalSince(date))
        if elapsed < 60 { return "now" }
        if elapsed < 3600 { return "\(Int(elapsed / 60))m" }
        if Calendar.current.isDateInToday(date) { return date.formatted(date: .omitted, time: .shortened) }
        if Calendar.current.isDateInYesterday(date) { return "Yesterday" }
        return date.formatted(.dateTime.weekday(.abbreviated))
    }
}

struct OnboardingView: View {
    let allowAccess: () -> Void
    let trySample: () -> Void
    let skip: () -> Void
    let permissionDenied: Bool
    var retryAccess: (() -> Void)? = nil
    var restartApp: (() -> Void)? = nil
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        let theme = SeenXTheme(scheme: scheme)
        VStack(alignment: .leading, spacing: permissionDenied ? 16 : 24) {
            HStack {
                Text("seenX").font(.system(size: 13, weight: .semibold)).foregroundStyle(theme.secondary)
                Spacer()
                Button(action: skip) { Image(systemName: "xmark") }.buttonStyle(.plain)
                    .foregroundStyle(theme.secondary).accessibilityLabel("Set up later")
            }
            Text("Save what matters.\nRemember why.").font(.system(size: 34, weight: .semibold)).tracking(-0.8)
                .foregroundStyle(theme.primary).fixedSize(horizontal: false, vertical: true)
            Text("seenX only looks at your screen when you ask it to.")
                .font(.system(size: 16)).foregroundStyle(theme.secondary)
            if permissionDenied {
                Text("Enable seenX in System Settings → Privacy & Security → Screen Recording. If it is already enabled, try again or restart seenX to refresh access.")
                    .font(.system(size: 12)).foregroundStyle(theme.secondary).fixedSize(horizontal: false, vertical: true)
            }
            VStack(alignment: .leading, spacing: 16) {
                Button(permissionDenied ? "Open System Settings" : "Allow screen access", action: allowAccess)
                    .buttonStyle(SeenXActionStyle(prominent: true))
                Button("Try a sample image instead", action: trySample).buttonStyle(.plain)
                    .font(.system(size: 14)).foregroundStyle(theme.secondary)
            }
            if permissionDenied {
                HStack(spacing: 12) {
                    if let retryAccess { Button("Try again", action: retryAccess).buttonStyle(SeenXActionStyle()) }
                    if let restartApp { Button("Restart seenX", action: restartApp).buttonStyle(SeenXActionStyle()) }
                }
            }
            Spacer(minLength: 0)
        }.padding(40).frame(minWidth: 560, minHeight: 380).seenXGlass()
    }
}

struct AnnotationView: View {
    @ObservedObject var session: AnnotationSession
    let submit: () -> Void
    let cancel: () -> Void
    let focusCanvas: () -> Void
    @Environment(\.colorScheme) private var scheme
    @State private var showNote = false
    private var theme: SeenXTheme { SeenXTheme(scheme: scheme) }
    private var activeBoxes: [TextBox] {
        if !session.state.pending.isEmpty { return session.state.pending }
        return session.state.highlights.first { $0.id == session.state.selected }?.boxes ?? session.state.highlights.last?.boxes ?? []
    }
    private var noteVisible: Bool { showNote || !activeBoxes.isEmpty || !session.note.isEmpty }
    private var highlightCount: Int { session.state.highlights.count + (session.state.pending.isEmpty ? 0 : 1) }

    var body: some View {
        VStack(spacing: 0) {
            GeometryReader { geometry in
                let canvasSize = CGSize(width: max(1, geometry.size.width - 32), height: max(1, geometry.size.height - 64))
                ZStack(alignment: .topLeading) {
                    ScreenshotCanvas(image: session.image, boxes: session.boxes, highlights: session.state.highlights,
                                     pending: session.state.pending, selected: session.state.selected) { boxes in
                        focusCanvas()
                        session.select(boxes)
                    }
                    .frame(width: canvasSize.width, height: canvasSize.height)
                    .position(x: geometry.size.width / 2, y: 48 + canvasSize.height / 2)
                    HStack(spacing: 8) {
                        if session.recognizing { ProgressView().controlSize(.small) }
                        else { Circle().fill(theme.accent).frame(width: 6, height: 6) }
                        if session.state.highlights.isEmpty {
                            Text(session.recognizing ? "Finding text…" : highlightCount == 0 ? "Select text to highlight" : "1 highlight")
                                .font(.system(size: 12)).foregroundStyle(theme.secondary)
                        } else {
                            Menu {
                                ForEach(session.state.highlights) { highlight in
                                    Button(highlight.text) { focusCanvas(); session.selectHighlight(highlight.id) }
                                }
                            } label: { Text("\(highlightCount) highlight\(highlightCount == 1 ? "" : "s")").font(.system(size: 12)) }
                                .menuStyle(.borderlessButton).fixedSize()
                        }
                        Button(action: submit) { ShortcutBadge(text: "⌘↩") }.buttonStyle(.plain)
                            .help(session.state.pending.isEmpty ? "Save screenshot" : "Finish this highlight")
                    }
                    .padding(.horizontal, 12).padding(.vertical, 8).seenXGlass(radius: 20)
                    .position(x: geometry.size.width / 2, y: 28)
                    if noteVisible {
                        noteCard.frame(width: min(340, geometry.size.width - 48), height: 80)
                            .position(notePosition(in: geometry.size, canvasSize: canvasSize))
                    }
                }
            }
            if let error = session.error {
                Text(error).font(.system(size: 12)).foregroundStyle(.red).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 24).padding(.vertical, 8)
            }
            HStack(spacing: 12) {
                Button("Cancel", action: cancel).buttonStyle(.plain).foregroundStyle(theme.secondary)
                ShortcutBadge(text: "esc")
                Spacer()
                ViewThatFits(in: .horizontal) {
                    Text("⌘⌫ clear   ⌘Z undo   ⌘⇧Z redo").font(.system(size: 11)).foregroundStyle(theme.secondary)
                    Text("⌘⌫ clear · ⌘Z undo").font(.system(size: 11)).foregroundStyle(theme.secondary)
                }
                Spacer()
                if !noteVisible {
                    Button { showNote = true } label: { Label("Add a thought…", systemImage: "text.bubble") }
                        .buttonStyle(.plain).foregroundStyle(theme.secondary)
                }
                Button(session.state.pending.isEmpty ? "Save" : "Finish highlight", action: submit)
                    .buttonStyle(SeenXActionStyle(prominent: true))
            }.font(.system(size: 12)).padding(.horizontal, 24).frame(height: 64)
        }.frame(minWidth: 760, minHeight: 540).foregroundStyle(theme.primary).tint(theme.accent).seenXGlass()
    }

    private var noteCard: some View {
        HStack(alignment: .top, spacing: 8) {
            ZStack(alignment: .topLeading) {
                if session.note.isEmpty {
                    Text("Add a thought…").font(.system(size: 14)).foregroundStyle(theme.secondary)
                        .padding(.top, 8).padding(.leading, 5).allowsHitTesting(false)
                }
                NoteEditor(text: $session.note, undoManager: session.undoManager)
            }
            Button(action: submit) { ShortcutBadge(text: "⌘↩") }.buttonStyle(.plain)
                .help(session.state.pending.isEmpty ? "Save screenshot" : "Finish this highlight")
        }.padding(12).seenXGlass(radius: 14)
            .shadow(color: Color.black.opacity(scheme == .dark ? 0.2 : 0.08), radius: 16, y: 8)
    }

    private func notePosition(in size: CGSize, canvasSize: CGSize) -> CGPoint {
        let scale = min(canvasSize.width / session.image.size.width, canvasSize.height / session.image.size.height)
        let fitted = CGSize(width: session.image.size.width * scale, height: session.image.size.height * scale)
        let imageOrigin = CGPoint(x: (size.width - fitted.width) / 2, y: 48 + (canvasSize.height - fitted.height) / 2)
        let bounds = activeBoxes.map(\.rect).reduce(CGRect.null) { $0.union($1) }
        let cardWidth = min(340, size.width - 48)
        let left = bounds.isNull ? 0.06 : bounds.minX
        let bottom = bounds.isNull ? 0.5 : bounds.maxY
        let proposedX = imageOrigin.x + left * fitted.width
        let x = min(max(proposedX, 24), size.width - cardWidth - 24) + cardWidth / 2
        let below = imageOrigin.y + bottom * fitted.height + 12
        let y = below + 80 < size.height - 16 ? below : max(64, imageOrigin.y + (bounds.isNull ? 0.5 : bounds.minY) * fitted.height - 92)
        return CGPoint(x: x, y: y + 40)
    }
}

private struct CaptureThumbnail: View {
    let url: URL
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        GeometryReader { geometry in
            if let image = NSImage(contentsOf: url) {
                Image(nsImage: image).resizable().scaledToFill().frame(width: geometry.size.width, height: geometry.size.height).clipped()
            } else {
                ZStack {
                    SeenXTheme(scheme: scheme).surface
                    Image(systemName: "photo.badge.exclamationmark").foregroundStyle(SeenXTheme(scheme: scheme).secondary)
                }
            }
        }
    }
}

/// One fitted coordinate space is shared by the bitmap, OCR boxes and hit testing.
struct ScreenshotCanvas: View {
    let image: NSImage
    let boxes: [TextBox]
    let highlights: [Highlight]
    let pending: [TextBox]
    let selected: UUID?
    let select: (([TextBox]) -> Void)?
    @Environment(\.colorScheme) private var scheme
    @State private var drag: CGRect?

    var body: some View {
        GeometryReader { geometry in
            let scale = min(geometry.size.width / image.size.width, geometry.size.height / image.size.height)
            let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
            ZStack(alignment: .topLeading) {
                Image(nsImage: image).resizable().frame(width: size.width, height: size.height)
                ForEach(highlights) { highlight in
                    ForEach(highlight.boxes) { box in boxView(box, size: size, emphasized: highlight.id == selected) }
                }
                ForEach(pending) { box in boxView(box, size: size, emphasized: true) }
                if let drag {
                    ForEach(boxes.filter { $0.rect.intersects(drag) }) { box in boxView(box, size: size, emphasized: true) }
                    RoundedRectangle(cornerRadius: 4).stroke(SeenXTheme(scheme: scheme).brand, style: StrokeStyle(lineWidth: 1, dash: [4]))
                        .frame(width: drag.width * size.width, height: drag.height * size.height)
                        .offset(x: drag.minX * size.width, y: drag.minY * size.height)
                }
            }
            .frame(width: size.width, height: size.height).contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { value in
                    guard select != nil else { return }
                    drag = selectionRect(start: value.startLocation, end: value.location, size: size)
                }
                .onEnded { value in
                    guard let select else { return }
                    let selection = selectionRect(start: value.startLocation, end: value.location, size: size)
                    select(boxes.filter { $0.rect.intersects(selection) })
                    drag = nil
                })
            .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
            .accessibilityLabel(select == nil ? "Saved screenshot with text highlights" : "Screenshot. Click a word or drag across words to select a highlight.")
        }
    }

    private func selectionRect(start: CGPoint, end: CGPoint, size: CGSize) -> CGRect {
        let x = min(max(min(start.x, end.x) / size.width, 0), 1)
        let y = min(max(min(start.y, end.y) / size.height, 0), 1)
        let right = min(max(max(start.x, end.x) / size.width, 0), 1)
        let bottom = min(max(max(start.y, end.y) / size.height, 0), 1)
        return CGRect(x: x, y: y, width: max(right - x, 0.002), height: max(bottom - y, 0.002))
    }

    private func boxView(_ box: TextBox, size: CGSize, emphasized: Bool) -> some View {
        // Multiply keeps the original screenshot's ink readable in either app appearance.
        let blue = SeenXTheme(scheme: .light).brand
        return RoundedRectangle(cornerRadius: 3).fill(blue.opacity(0.18)).blendMode(.multiply)
            .overlay(RoundedRectangle(cornerRadius: 3).stroke(blue, lineWidth: emphasized ? 1.5 : 1))
            .frame(width: box.width * size.width, height: box.height * size.height)
            .offset(x: box.x * size.width, y: box.y * size.height).allowsHitTesting(false)
    }
}

/// NSTextView provides normal macOS typing, selection, clipboard and grouped undo.
struct NoteEditor: NSViewRepresentable {
    @Binding var text: String
    let undoManager: UndoManager
    @Environment(\.colorScheme) private var scheme
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        let view = SharedUndoTextView()
        view.sharedUndoManager = undoManager
        view.isRichText = false
        view.allowsUndo = true
        view.drawsBackground = false
        view.font = .systemFont(ofSize: 14)
        view.textColor = SeenXTheme(scheme: scheme).nativePrimary
        view.insertionPointColor = SeenXTheme(scheme: scheme).nativePrimary
        view.textContainerInset = NSSize(width: 3, height: 4)
        view.frame = NSRect(x: 0, y: 0, width: 280, height: 56)
        view.minSize = .zero
        view.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        view.isVerticallyResizable = true
        view.isHorizontallyResizable = false
        view.autoresizingMask = [.width]
        view.textContainer?.widthTracksTextView = true
        view.delegate = context.coordinator
        view.setAccessibilityLabel("Optional screenshot note")
        scroll.documentView = view
        return scroll
    }
    func updateNSView(_ nsView: NSScrollView, context: Context) {
        context.coordinator.parent = self
        guard let view = nsView.documentView as? NSTextView else { return }
        view.textColor = SeenXTheme(scheme: scheme).nativePrimary
        view.insertionPointColor = SeenXTheme(scheme: scheme).nativePrimary
        if view.string != text { view.string = text }
    }
    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: NoteEditor
        init(_ parent: NoteEditor) { self.parent = parent }
        func textDidChange(_ notification: Notification) {
            guard let view = notification.object as? NSTextView else { return }
            parent.text = view.string
        }
    }
}

final class SharedUndoTextView: NSTextView {
    var sharedUndoManager: UndoManager?
    override var undoManager: UndoManager? { sharedUndoManager ?? super.undoManager }
}

/// Field-editor commands keep arrow navigation working while the search input has focus.
private struct SearchInput: NSViewRepresentable {
    @Binding var text: String
    let placeholder: String
    let focusToken: Int
    let fontSize: CGFloat
    let move: (Int) -> Void
    let submit: () -> Void
    @Environment(\.colorScheme) private var scheme
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeNSView(context: Context) -> NSSearchField {
        let field = NSSearchField()
        field.isBezeled = false
        field.drawsBackground = false
        field.focusRingType = .none
        if let cell = field.cell as? NSSearchFieldCell { cell.searchButtonCell = nil; cell.cancelButtonCell = nil }
        field.font = .systemFont(ofSize: fontSize)
        field.delegate = context.coordinator
        field.setAccessibilityLabel("Search saved screenshots and notes")
        return field
    }
    func updateNSView(_ field: NSSearchField, context: Context) {
        context.coordinator.parent = self
        field.textColor = SeenXTheme(scheme: scheme).nativePrimary
        field.placeholderAttributedString = NSAttributedString(string: placeholder, attributes: [.foregroundColor: SeenXTheme(scheme: scheme).nativeSecondary])
        if field.stringValue != text { field.stringValue = text }
        if context.coordinator.lastFocus != focusToken {
            context.coordinator.lastFocus = focusToken
            if focusToken > 0 {
                DispatchQueue.main.async { [weak field] in
                    guard let field, let window = field.window else { return }
                    window.makeFirstResponder(field)
                }
            }
        }
    }
    final class Coordinator: NSObject, NSSearchFieldDelegate {
        var parent: SearchInput
        var lastFocus = -1
        init(_ parent: SearchInput) { self.parent = parent }
        func controlTextDidChange(_ notification: Notification) {
            guard let field = notification.object as? NSSearchField else { return }
            parent.text = field.stringValue
        }
        func control(_ control: NSControl, textView: NSTextView, doCommandBy commandSelector: Selector) -> Bool {
            switch commandSelector {
            case #selector(NSResponder.moveDown(_:)): parent.move(1); return true
            case #selector(NSResponder.moveUp(_:)): parent.move(-1); return true
            case #selector(NSResponder.insertNewline(_:)): parent.submit(); return true
            default: return false
            }
        }
    }
}
