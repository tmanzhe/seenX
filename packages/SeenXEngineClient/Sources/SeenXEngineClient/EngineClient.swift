import Foundation
import Darwin

/// One trusted local library per process. No network or write methods are exposed.
public final class EngineClient: @unchecked Sendable {
    public struct Configuration: Sendable {
        public var executableURL: URL
        public var arguments: [String]
        public var currentDirectoryURL: URL?
        public var environment: [String: String]?
        public var requestTimeout: TimeInterval

        public init(executableURL: URL, arguments: [String] = [], currentDirectoryURL: URL? = nil,
                    environment: [String: String]? = nil, requestTimeout: TimeInterval = 15) {
            self.executableURL = executableURL
            self.arguments = arguments
            self.currentDirectoryURL = currentDirectoryURL
            self.environment = environment
            self.requestTimeout = requestTimeout
        }
    }

    public let info: EngineInfo
    private let transport: Transport

    private init(transport: Transport, info: EngineInfo) {
        self.transport = transport
        self.info = info
    }

    /// Launch and handshake away from the main actor. No process diagnostics are retained.
    public static func launch(configuration: Configuration) async throws -> EngineClient {
        let transport = Transport(configuration: configuration)
        do {
            let info: EngineInfo = try await transport.request(method: "engine.info", params: [:])
            guard info.protocolVersion == 1 else { throw EngineClientError.unsupportedVersion(info.protocolVersion) }
            guard info.readOnlyRequests,
                  Set(["engine.info", "memory.search", "memory.fetch", "region.fetch"]).isSubset(of: Set(info.methods))
            else { throw EngineClientError.invalidResponse }
            return EngineClient(transport: transport, info: info)
        } catch {
            await transport.close()
            throw error
        }
    }

    public func search(_ query: String, match: SearchMatch = .phrase, limit: Int = 20,
                       assetID: String? = nil, revisionID: String? = nil, currentOnly: Bool = false) async throws -> [SearchHit] {
        var params: [String: Any] = ["query": query, "match": match.rawValue, "limit": limit, "current_only": currentOnly]
        params["asset_id"] = assetID
        params["revision_id"] = revisionID
        return try await transport.request(method: "memory.search", params: params)
    }

    public func fetchMemory(assetID: String, revisionID: String? = nil, includeImage: Bool = false) async throws -> Memory {
        var params: [String: Any] = ["asset_id": assetID, "include_image": includeImage]
        params["revision_id"] = revisionID
        return try await transport.request(method: "memory.fetch", params: params)
    }

    public func fetchRegion(assetID: String, revisionID: String, target: RegionReference,
                            includeImage: Bool = false) async throws -> RegionEvidence {
        var params: [String: Any] = ["asset_id": assetID, "revision_id": revisionID, "include_image": includeImage]
        switch target {
        case .region(let id): params["region_id"] = id
        case .observation(let id): params["observation_id"] = id
        }
        return try await transport.request(method: "region.fetch", params: params)
    }

    /// Finishes any active bounded request, closes stdin, then reaps the helper.
    public func close() async { await transport.close() }
}

private final class Cancellation: @unchecked Sendable {
    private let lock = NSLock()
    private var value = false
    func cancel() { lock.lock(); value = true; lock.unlock() }
    var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return value }
}

/// All mutable process and pipe state belongs to the serial worker queue.
private final class Transport: @unchecked Sendable {
    private let queue = DispatchQueue(label: "com.seenx.engine-client", qos: .userInitiated)
    private let configuration: EngineClient.Configuration
    private var process: Process?
    private var input: FileHandle?
    private var output: FileHandle?
    private var closed = false
    private var pending = Data()
    private let terminated = DispatchSemaphore(value: 0)
    private static let requestLimit = 65_536
    private static let responseLimit = 8 * 1024 * 1024

    init(configuration: EngineClient.Configuration) { self.configuration = configuration }

    deinit {
        // No pending worker can coexist with deinit: each closure retains this object.
        let process = self.process, input = self.input, output = self.output, terminated = self.terminated
        queue.async { Self.reap(process: process, input: input, output: output, terminated: terminated) }
    }

    func request<T: Decodable>(method: String, params: [String: Any]) async throws -> T {
        let cancellation = Cancellation()
        return try await withTaskCancellationHandler {
            try await withCheckedThrowingContinuation { continuation in
                queue.async {
                    do {
                        if cancellation.isCancelled { throw CancellationError() }
                        guard !self.closed else { throw EngineClientError.closed }
                        if self.process == nil { try self.start() }
                        let id = UUID().uuidString
                        var frame = try JSONSerialization.data(withJSONObject: ["version": 1, "id": id, "method": method, "params": params])
                        frame.append(0x0A)
                        guard frame.count <= Self.requestLimit else { throw EngineClientError.requestTooLarge }
                        let timeout = self.configuration.requestTimeout
                        guard timeout.isFinite, timeout > 0 else { throw EngineClientError.timeout }
                        let deadline = ProcessInfo.processInfo.systemUptime + timeout
                        try self.write(frame, deadline: deadline, cancellation: cancellation)
                        let data = try self.read(deadline: deadline, cancellation: cancellation)
                        let header: Header
                        do { header = try Self.decoder().decode(Header.self, from: data) }
                        catch { throw EngineClientError.invalidResponse }
                        guard header.version == 1 else { throw EngineClientError.unsupportedVersion(header.version) }
                        guard header.id == id else { throw EngineClientError.mismatchedResponseID }
                        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                              (object["result"] != nil) != (object["error"] != nil)
                        else { throw EngineClientError.invalidResponse }
                        let envelope: Response<T>
                        do { envelope = try Self.decoder().decode(Response<T>.self, from: data) }
                        catch { throw EngineClientError.invalidResponse }
                        guard envelope.version == 1 else { throw EngineClientError.unsupportedVersion(envelope.version) }
                        guard envelope.id == id else { throw EngineClientError.mismatchedResponseID }
                        guard (envelope.result != nil) != (envelope.error != nil), !envelope.traceID.isEmpty
                        else { throw EngineClientError.invalidResponse }
                        if let error = envelope.error {
                            throw EngineClientError.engine(code: error.code, message: error.message, traceID: envelope.traceID)
                        }
                        guard let result = envelope.result else { throw EngineClientError.invalidResponse }
                        continuation.resume(returning: result)
                    } catch {
                        // Method errors and local preflight limits leave framing intact.
                        if case EngineClientError.engine = error {} else if case EngineClientError.requestTooLarge = error {}
                        else { self.shutdown() }
                        continuation.resume(throwing: error)
                    }
                }
            }
        } onCancel: { cancellation.cancel() }
    }

    func close() async {
        await withCheckedContinuation { continuation in
            queue.async { self.shutdown(); continuation.resume() }
        }
    }

    private func start() throws {
        let process = Process()
        process.executableURL = configuration.executableURL
        process.arguments = configuration.arguments
        process.currentDirectoryURL = configuration.currentDirectoryURL
        var environment = configuration.environment ?? ProcessInfo.processInfo.environment
        if configuration.environment == nil {
            environment.removeValue(forKey: "PYTHONPATH")
            environment.removeValue(forKey: "PYTHONHOME")
        }
        process.environment = environment
        let stdin = Pipe(), stdout = Pipe()
        process.standardInput = stdin
        process.standardOutput = stdout
        // A null sink cannot fill a pipe or accidentally surface private diagnostics.
        process.standardError = FileHandle.nullDevice
        let terminated = self.terminated
        process.terminationHandler = { _ in terminated.signal() }
        do { try process.run() } catch { throw EngineClientError.launchFailed }
        try? stdin.fileHandleForReading.close()
        try? stdout.fileHandleForWriting.close()
        input = stdin.fileHandleForWriting
        output = stdout.fileHandleForReading
        self.process = process
        for handle in [input, output].compactMap({ $0 }) {
            let flags = fcntl(handle.fileDescriptor, F_GETFL)
            guard flags >= 0, fcntl(handle.fileDescriptor, F_SETFL, flags | O_NONBLOCK) >= 0
            else { throw EngineClientError.launchFailed }
        }
        // Writes report EPIPE rather than terminating the app if the child exits.
        guard fcntl(stdin.fileHandleForWriting.fileDescriptor, F_SETNOSIGPIPE, 1) >= 0
        else { throw EngineClientError.launchFailed }
    }

    private func ready(_ fd: Int32, events: Int16, deadline: TimeInterval, cancellation: Cancellation) throws {
        while true {
            if cancellation.isCancelled { throw CancellationError() }
            let remaining = deadline - ProcessInfo.processInfo.systemUptime
            guard remaining > 0 else { throw EngineClientError.timeout }
            var descriptor = pollfd(fd: fd, events: events, revents: 0)
            let result = poll(&descriptor, 1, Int32(min(remaining * 1000, 100).rounded(.up)))
            if result < 0 {
                if errno == EINTR { continue }
                throw exited()
            }
            if result > 0 {
                if descriptor.revents & events != 0 { return }
                if descriptor.revents & Int16(POLLHUP | POLLERR | POLLNVAL) != 0 { throw exited() }
            }
        }
    }

    private func exited() -> EngineClientError {
        .processExited(process.flatMap { $0.isRunning ? nil : $0.terminationStatus })
    }

    private func write(_ data: Data, deadline: TimeInterval, cancellation: Cancellation) throws {
        guard let input else { throw EngineClientError.closed }
        try data.withUnsafeBytes { bytes in
            var offset = 0
            while offset < bytes.count {
                try ready(input.fileDescriptor, events: Int16(POLLOUT), deadline: deadline, cancellation: cancellation)
                let count = Darwin.write(input.fileDescriptor, bytes.baseAddress!.advanced(by: offset), bytes.count - offset)
                if count > 0 { offset += count }
                else if count < 0 && (errno == EINTR || errno == EAGAIN) { continue }
                else { throw exited() }
            }
        }
    }

    private func read(deadline: TimeInterval, cancellation: Cancellation) throws -> Data {
        guard let output else { throw EngineClientError.closed }
        var searchOffset = pending.startIndex
        while true {
            if let end = pending[searchOffset...].firstIndex(of: 0x0A) {
                let frame = pending.prefix(upTo: end)
                guard frame.count <= Self.responseLimit else { throw EngineClientError.responseTooLarge }
                let result = Data(frame)
                pending.removeSubrange(...end)
                // The server must not send an unsolicited second response.
                guard pending.isEmpty else { throw EngineClientError.invalidResponse }
                return result
            }
            searchOffset = pending.endIndex
            guard pending.count <= Self.responseLimit else { throw EngineClientError.responseTooLarge }
            try ready(output.fileDescriptor, events: Int16(POLLIN), deadline: deadline, cancellation: cancellation)
            var buffer = [UInt8](repeating: 0, count: 16_384)
            let count = Darwin.read(output.fileDescriptor, &buffer, buffer.count)
            if count > 0 { pending.append(contentsOf: buffer.prefix(count)) }
            else if count < 0 && (errno == EINTR || errno == EAGAIN) { continue }
            else { throw exited() }
        }
    }

    private func shutdown() {
        guard !closed else { return }
        closed = true
        Self.reap(process: process, input: input, output: output, terminated: terminated)
        input = nil
        output = nil
        process = nil
        pending.removeAll()
    }

    private static func reap(process: Process?, input: FileHandle?, output: FileHandle?, terminated: DispatchSemaphore) {
        try? input?.close()
        if let process {
            let deadline = ProcessInfo.processInfo.systemUptime + 0.5
            while process.isRunning && ProcessInfo.processInfo.systemUptime < deadline { Thread.sleep(forTimeInterval: 0.01) }
            if process.isRunning {
                process.terminate()
                let grace = ProcessInfo.processInfo.systemUptime + 0.2
                while process.isRunning && ProcessInfo.processInfo.systemUptime < grace { Thread.sleep(forTimeInterval: 0.01) }
                if process.isRunning { kill(process.processIdentifier, SIGKILL) }
            }
            // Process reaps through its termination handler. waitUntilExit can wait
            // on Foundation's pipe bookkeeping after manual descriptor reads.
            // Keep shutdown bounded, including a helper that needs SIGKILL.
            _ = terminated.wait(timeout: .now() + 1)
        }
        try? output?.close()
    }

    private struct Response<Result: Decodable>: Decodable {
        let version: Int
        let id: String?
        let traceID: String
        let result: Result?
        let error: Failure?
    }
    private struct Header: Decodable { let version: Int; let id: String? }
    private struct Failure: Decodable { let code: String; let message: String }

    private struct Key: CodingKey {
        let stringValue: String
        let intValue: Int? = nil
        init(_ value: String) { stringValue = value }
        init?(stringValue: String) { self.init(stringValue) }
        init?(intValue: Int) { return nil }
    }

    private static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .custom { path in
            let parts = path.last!.stringValue.split(separator: "_")
            return Key(parts.enumerated().map { index, part in
                index == 0 ? String(part) : part == "id" ? "ID" : part.prefix(1).uppercased() + part.dropFirst()
            }.joined())
        }
        return decoder
    }
}
