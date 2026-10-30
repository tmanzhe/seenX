import AppKit
import Combine
import SeenXEngineClient
import SwiftUI

/// An explicit development-library browser. CaptureStore remains the capture owner.
@MainActor
final class EngineBrowserController: NSWindowController, NSWindowDelegate {
    let model = EngineBrowserModel()

    init() {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 980, height: 680),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "seenX · Python Library"
        window.minSize = NSSize(width: 740, height: 480)
        window.isReleasedWhenClosed = false
        super.init(window: window)
        window.delegate = self
        window.contentView = NSHostingView(rootView: EngineLibraryView(model: model))
        window.center()
    }

    required init?(coder: NSCoder) { nil }
    func windowWillClose(_ notification: Notification) { model.disconnect() }
}

@MainActor
final class EngineBrowserModel: ObservableObject {
    @Published var query = ""
    @Published private(set) var hits: [SearchHit] = []
    @Published private(set) var selected: SearchHit?
    @Published private(set) var memory: Memory?
    @Published private(set) var image: NSImage?
    @Published private(set) var showingCrop = false
    @Published private(set) var busy = false
    @Published private(set) var connected = false
    @Published private(set) var searched = false
    @Published private(set) var error: String?
    private var client: EngineClient?
    // Closing/reconnecting invalidates outstanding completions before they touch UI.
    private var generation = UUID()
    private var searchDebounce: Task<Void, Never>?
    private var pendingSearch = false

    func chooseLibrary() {
        guard !busy else { return }
        let project = NSOpenPanel()
        project.title = "Select the seenX repository"
        project.message = "Choose the project where you ran uv sync --project python."
        project.canChooseDirectories = true
        project.canChooseFiles = false
        project.allowsMultipleSelection = false
        guard project.runModal() == .OK, let repository = project.url else { return }
        let interpreter = repository.appendingPathComponent("python/.venv/bin/python")
        guard FileManager.default.isExecutableFile(atPath: interpreter.path) else {
            error = "This folder needs its Python environment. Run uv sync --project python in the repository, then reconnect."
            return
        }
        let library = NSOpenPanel()
        library.title = "Select an existing Python library"
        library.message = "Choose the folder containing catalog.sqlite3. Native captures won't be moved."
        library.directoryURL = repository.appendingPathComponent("python/library")
        library.canChooseDirectories = true
        library.canChooseFiles = false
        library.allowsMultipleSelection = false
        guard library.runModal() == .OK, let directory = library.url else { return }
        guard FileManager.default.fileExists(atPath: directory.appendingPathComponent("catalog.sqlite3").path) else {
            error = "Choose an existing Python catalog folder. No library was created or imported."
            return
        }
        connect(interpreter: interpreter, repository: repository, library: directory)
    }

    func connect(interpreter: URL, repository: URL, library: URL) {
        connect(configuration: .init(executableURL: interpreter,
            arguments: ["-m", "seenx.engine_stdio", "--library", library.path, "--trusted-local"], currentDirectoryURL: repository))
    }

    func connect(configuration: EngineClient.Configuration) {
        disconnect()
        busy = true
        let token = generation
        Task {
            do {
                let session = try await EngineClient.launch(configuration: configuration)
                guard generation == token else { await session.close(); return }
                client = session
                connected = true
            } catch {
                guard generation == token else { return }
                report(error)
            }
            guard generation == token else { return }
            finishRequest()
        }
    }

    func disconnect() {
        generation = UUID()
        searchDebounce?.cancel()
        pendingSearch = false
        let previous = client
        client = nil
        connected = false
        busy = false
        hits = []
        selected = nil
        memory = nil
        image = nil
        showingCrop = false
        searched = false
        error = nil
        Task { await previous?.close() }
    }

    /// The launcher types ahead while a bounded request finishes. Only the latest query is shown.
    func updateSearchQuery(_ value: String) {
        searchDebounce?.cancel()
        pendingSearch = false
        query = value
        hits = []
        selected = nil
        memory = nil
        image = nil
        searched = false
        if connected { error = nil }
        guard !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        let token = generation
        searchDebounce = Task {
            do { try await Task.sleep(nanoseconds: 250_000_000) }
            catch { return }
            guard generation == token else { return }
            pendingSearch = true
            if !busy { search() }
        }
    }

    func search() {
        guard !busy, let client, !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        pendingSearch = false
        let token = generation
        let requestedQuery = query
        busy = true
        error = nil
        hits = []
        searched = true
        selected = nil
        memory = nil
        image = nil
        Task {
            do {
                let results = try await client.search(requestedQuery, limit: 30)
                guard generation == token else { return }
                if query == requestedQuery { hits = results }
            } catch {
                guard generation == token else { return }
                report(error)
            }
            guard generation == token else { return }
            finishRequest()
        }
    }

    func open(_ hit: SearchHit, crop: Bool = false) {
        guard !busy, let client else { return }
        let token = generation
        busy = true
        error = nil
        selected = hit
        image = nil
        memory = nil
        showingCrop = crop
        Task {
            do {
                if crop {
                    let reference: RegionReference
                    if let region = hit.regionID { reference = .region(region) }
                    else if let observation = hit.observationID { reference = .observation(observation) }
                    else { throw EngineClientError.invalidResponse }
                    let result = try await client.fetchRegion(assetID: hit.assetID, revisionID: hit.revisionID,
                                                              target: reference, includeImage: true)
                    guard generation == token else { return }
                    image = try decodeImage(result.image)
                } else {
                    let result = try await client.fetchMemory(assetID: hit.assetID, revisionID: hit.revisionID, includeImage: true)
                    guard generation == token else { return }
                    memory = result
                    image = try decodeImage(result.image)
                }
            } catch {
                guard generation == token else { return }
                report(error)
            }
            guard generation == token else { return }
            finishRequest()
        }
    }

    private func finishRequest() {
        busy = false
        if pendingSearch, connected { search() }
    }

    private func report(_ failure: Error) {
        error = failure.localizedDescription
        if case EngineClientError.engine = failure { return }
        if case EngineClientError.requestTooLarge = failure { return }
        // A timed-out/corrupt transport cannot safely reuse request framing.
        connected = false
        let previous = client
        client = nil
        Task { await previous?.close() }
    }

    private func decodeImage(_ attachment: ImageAttachment?) throws -> NSImage {
        guard let attachment, attachment.mediaType == "image/png", attachment.encoding == "base64",
              let image = NSImage(data: attachment.data),
              image.representations.contains(where: { $0.pixelsWide == attachment.width && $0.pixelsHigh == attachment.height })
        else { throw EngineClientError.invalidResponse }
        // Use catalog pixel dimensions rather than embedded display-resolution metadata.
        image.size = NSSize(width: attachment.width, height: attachment.height)
        return image
    }
}

struct EngineLibraryView: View {
    @ObservedObject var model: EngineBrowserModel

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Python library").font(.headline)
                Spacer()
                if model.busy { ProgressView().controlSize(.small) }
                Text(model.connected ? "Connected" : "Disconnected").foregroundStyle(.secondary)
                Button(model.connected ? "Change Library…" : "Connect…", action: model.chooseLibrary).disabled(model.busy)
                if model.connected { Button("Disconnect", action: model.disconnect) }
            }.padding()
            if model.connected {
                HStack {
                    TextField("Search saved notes, selections, or recognized text…", text: $model.query)
                        .textFieldStyle(.roundedBorder).onSubmit(model.search)
                    Button("Search", action: model.search)
                        .disabled(model.query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }.disabled(model.busy).padding(.horizontal).padding(.bottom, 12)
            }
            if let error = model.error {
                Text(error).foregroundStyle(.red).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding()
            }
            Divider()
            HSplitView {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        if model.hits.isEmpty {
                            Text(model.connected ? (model.searched ? "No matching evidence found. Try different words."
                                 : "Search for words saved in your library. Matches are evidence, so one image can appear more than once.")
                                 : "Connect an existing Python library to browse it here. Your native captures stay in their current library.")
                                .foregroundStyle(.secondary).padding()
                        }
                        ForEach(model.hits) { hit in
                            Button { model.open(hit) } label: {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(hit.excerpt).lineLimit(4)
                                    Text("\(hit.matchedField) · \(hit.provenance.origin) · \(hit.provenance.confirmation)")
                                        .font(.caption).foregroundStyle(.secondary)
                                    if !hit.isCurrentRevision { Text("Earlier revision").font(.caption).foregroundStyle(.secondary) }
                                }.padding(10).frame(maxWidth: .infinity, alignment: .leading)
                                    .background(model.selected?.id == hit.id ? Color.accentColor.opacity(0.12) : .clear,
                                                in: RoundedRectangle(cornerRadius: 8))
                            }.buttonStyle(.plain).disabled(model.busy)
                        }
                    }.padding(8)
                }.frame(minWidth: 240, idealWidth: 320, maxWidth: 400)
                EngineEvidenceDetail(model: model)
                    .frame(minWidth: 360, maxWidth: .infinity, maxHeight: .infinity)
            }
            Divider()
            Text("Read-only development connection · lexical search · no automatic capture import")
                .font(.caption).foregroundStyle(.secondary).padding(10)
        }
    }
}

struct EngineEvidenceDetail: View {
    @ObservedObject var model: EngineBrowserModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let selected = model.selected {
                Text(model.memory?.asset.sourceName ?? "Saved evidence").font(.headline)
                Text(selected.excerpt).textSelection(.enabled)
                Text("\(selected.matchedField) · \(selected.provenance.origin) · \(selected.provenance.confirmation)")
                    .font(.caption).foregroundStyle(.secondary)
                if !selected.isCurrentRevision { Text("Earlier revision").font(.caption).foregroundStyle(.secondary) }
                HStack {
                    Button("Full image") { model.open(selected) }
                    Button("Saved region") { model.open(selected, crop: true) }
                        .disabled(selected.regionID == nil && selected.observationID == nil)
                    if model.busy { ProgressView().controlSize(.small) }
                }.disabled(model.busy || !model.connected)
                if let image = model.image {
                    EngineEvidenceImage(image: image, target: model.showingCrop ? nil : selected.target)
                    Text(model.showingCrop ? "Saved-region crop" : "Exact saved revision · highlighted match")
                        .font(.caption).foregroundStyle(.secondary)
                } else { Spacer() }
                if let memory = model.memory {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(memory.annotations) { annotation in
                                if !annotation.note.isEmpty { Text(annotation.note).textSelection(.enabled) }
                                if !annotation.selectedText.isEmpty {
                                    Text(annotation.selectedText).foregroundStyle(.secondary).textSelection(.enabled)
                                }
                            }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }.frame(maxHeight: 120)
                }
            } else {
                Text("Select a match to fetch its saved image and context.").foregroundStyle(.secondary)
                Spacer()
            }
        }.padding()
    }
}

private struct EngineEvidenceImage: View {
    let image: NSImage
    let target: NormalizedTarget?

    var body: some View {
        GeometryReader { geometry in
            let scale = min(geometry.size.width / image.size.width, geometry.size.height / image.size.height)
            let width = image.size.width * scale
            let height = image.size.height * scale
            Image(nsImage: image).resizable().frame(width: width, height: height)
                .overlay(alignment: .topLeading) {
                    if let target {
                        if target.kind == "point" {
                            Circle().fill(Color.orange).frame(width: 8, height: 8)
                                .offset(x: target.x * width - 4, y: target.y * height - 4)
                        } else {
                            Rectangle().fill(Color.yellow.opacity(0.18)).border(Color.orange, width: 2)
                                .frame(width: target.width * width, height: target.height * height)
                                .offset(x: target.x * width, y: target.y * height)
                        }
                    }
                }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }.frame(minHeight: 180)
    }
}
