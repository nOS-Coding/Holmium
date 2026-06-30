import Foundation
import AppKit
import Combine

@MainActor
class ConnectionManager: ObservableObject {
    @Published var messages: [Message] = []
    @Published var inputText: String = ""
    @Published var isProcessing = false
    @Published var connectionState: ConnectionState = .disconnected
    @Published var statusText = "Disconnected"
    @Published var serverStatus: SystemStatus?
    @Published var currentToolCall: ToolCall?

    @Published var serverURL: String = "holmium.local"
    @Published var serverPort: Int = 443
    @Published var token: String = ""
    @Published var autoConnect: Bool = false
    @Published var clipboardSync: Bool = false
    @Published var notificationsEnabled: Bool = false

    private var webSocketTask: URLSessionWebSocketTask?
    private var streamBuffer = ""
    private var statusTimer: Timer?
    private var reconnectTimer: Timer?
    private var isReconnecting = false
    private let session: URLSession
    private var cancellables = Set<AnyCancellable>()

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.waitsForConnectivity = false
        session = URLSession(configuration: config)

        loadSettings()
        setupPersistence()
        startStatusPolling()
    }

    private func loadSettings() {
        serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? "holmium.local"
        serverPort = UserDefaults.standard.integer(forKey: "serverPort") != 0
            ? UserDefaults.standard.integer(forKey: "serverPort") : 443
        token = UserDefaults.standard.string(forKey: "token") ?? ""
        autoConnect = UserDefaults.standard.bool(forKey: "autoConnect")
        clipboardSync = UserDefaults.standard.bool(forKey: "clipboardSync")
        notificationsEnabled = UserDefaults.standard.bool(forKey: "notificationsEnabled")
    }

    private func setupPersistence() {
        $serverURL.dropFirst().sink { UserDefaults.standard.set($0, forKey: "serverURL") }.store(in: &cancellables)
        $serverPort.dropFirst().sink { UserDefaults.standard.set($0, forKey: "serverPort") }.store(in: &cancellables)
        $token.dropFirst().sink { UserDefaults.standard.set($0, forKey: "token") }.store(in: &cancellables)
        $autoConnect.dropFirst().sink { UserDefaults.standard.set($0, forKey: "autoConnect") }.store(in: &cancellables)
        $clipboardSync.dropFirst().sink { UserDefaults.standard.set($0, forKey: "clipboardSync") }.store(in: &cancellables)
        $notificationsEnabled.dropFirst().sink { UserDefaults.standard.set($0, forKey: "notificationsEnabled") }.store(in: &cancellables)
    }

    func connect() {
        connectionState = .connecting
        statusText = "Connecting..."

        guard let url = URL(string: "wss://\(serverURL):\(serverPort)/ws/chat") else {
            connectionState = .disconnected
            statusText = "Invalid server URL"
            return
        }

        var request = URLRequest(url: url)
        if !token.isEmpty {
            request.setValue(token, forHTTPHeaderField: "X-Holmium-Token")
        }

        webSocketTask = session.webSocketTask(with: request)
        webSocketTask?.resume()
        receiveMessage()
        connectionState = .connected
        isProcessing = false
        statusText = "Connected"
    }

    func disconnect() {
        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        webSocketTask = nil
        connectionState = .disconnected
        statusText = "Disconnected"
        isReconnecting = false
        reconnectTimer?.invalidate()
        reconnectTimer = nil
    }

    func sendMessage(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }

        guard connectionState == .connected else {
            statusText = "Not connected"
            return
        }

        inputText = ""
        let msg = Message(role: "user", content: trimmed)
        messages.append(msg)
        isProcessing = true
        statusText = "Thinking..."
        streamBuffer = ""

        let dict: [String: String] = ["message": trimmed, "mode": "work"]
        guard let data = try? JSONSerialization.data(withJSONObject: dict) else { return }
        webSocketTask?.send(.data(data)) { _ in }
    }

    func sendImage(_ url: URL) {
        guard connectionState == .connected else { return }
        let msg = Message(role: "user", content: "[\(url.lastPathComponent)]")
        messages.append(msg)

        Task {
            do {
                let imgData = try Data(contentsOf: url)
                let baseURL = "https://\(serverURL):\(serverPort)"
                var req = URLRequest(url: URL(string: "\(baseURL)/upload/\(url.lastPathComponent)")!)
                req.httpMethod = "PUT"
                req.setValue("image/*", forHTTPHeaderField: "Content-Type")
                if !token.isEmpty { req.setValue(token, forHTTPHeaderField: "X-Holmium-Token") }
                req.httpBody = imgData
                let (_, resp) = try await session.data(for: req)
                if let httpResp = resp as? HTTPURLResponse, httpResp.statusCode == 200 {
                    statusText = "Image sent"
                }
            } catch {
                statusText = "Upload failed: \(error.localizedDescription)"
            }
        }
    }

    func disconnectAndQuit() {
        disconnect()
        NSApplication.shared.terminate(nil)
    }

    var connectionColor: NSColor {
        switch connectionState {
        case .connected: return .green
        case .connecting: return .yellow
        case .disconnected: return .red
        }
    }

    func takeScreenshot() {
        guard connectionState == .connected else { return }
        Task {
            let process = Process()
            process.launchPath = "/usr/sbin/screencapture"
            process.arguments = ["-i", "/tmp/holmium_screenshot.png"]
            process.launch()
            process.waitUntilExit()
            let url = URL(fileURLWithPath: "/tmp/holmium_screenshot.png")
            sendImage(url)
        }
    }

    func copyToClipboard() {
        guard connectionState == .connected else { return }
        let pasteboard = NSPasteboard.general
        guard let text = pasteboard.string(forType: .string) else {
            statusText = "No text in clipboard"
            return
        }
        inputText = text
        sendMessage(text)
    }

    func openTUI() {
        guard connectionState == .connected else { return }
        let process = Process()
        process.launchPath = "/usr/bin/open"
        process.arguments = ["-a", "Terminal", "ssh", "-t", "\(serverURL)"]
        process.launch()
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            Task { @MainActor [weak self] in
                guard let self else { return }
                switch result {
                case .success(let message):
                    switch message {
                    case .string(let text):
                        handleMessage(text)
                    case .data(let data):
                        if let text = String(data: data, encoding: .utf8) {
                            handleMessage(text)
                        }
                    @unknown default:
                        break
                    }
                    receiveMessage()
                case .failure(let error):
                    connectionState = .disconnected
                    statusText = "Connection lost: \(error.localizedDescription)"
                    scheduleReconnect()
                }
            }
        }
    }

    private func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        Task { @MainActor in
            let type = json["type"] as? String ?? ""
            switch type {
            case "token":
                let content = json["content"] as? String ?? ""
                streamBuffer += content
                statusText = streamBuffer
            case "done":
                if !streamBuffer.isEmpty {
                    messages.append(Message(role: "assistant", content: streamBuffer))
                }
                streamBuffer = ""
                isProcessing = false
                statusText = "Ready"
            case "error":
                statusText = "Error: \(json["content"] as? String ?? "unknown")"
                isProcessing = false
            case "tool_call":
                currentToolCall = ToolCall(name: json["name"] as? String ?? "?")
                statusText = "⚡ \(json["name"] as? String ?? "?")"
            case "tool_result":
                currentToolCall = nil
            default:
                break
            }
        }
    }

    private func scheduleReconnect() {
        guard !isReconnecting else { return }
        isReconnecting = true
        statusText = "Reconnecting in 5s..."
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: false) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                self.isReconnecting = false
                self.connect()
            }
        }
    }

    private func startStatusPolling() {
        statusTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.fetchStatus()
            }
        }
    }

    func fetchStatus() {
        let baseURL = "https://\(serverURL):\(serverPort)"
        guard let url = URL(string: "\(baseURL)/status") else { return }
        var req = URLRequest(url: url)
        if !token.isEmpty { req.setValue(token, forHTTPHeaderField: "X-Holmium-Token") }
        req.timeoutInterval = 5

        Task {
            do {
                let (data, _) = try await session.data(for: req)
                if let status = try? JSONDecoder().decode(SystemStatus.self, from: data) {
                    Task { @MainActor in
                        self.serverStatus = status
                        self.connectionState = .connected
                        self.statusText = "Connected"
                    }
                }
            } catch {
                // silently ignore, connectionState is already set
            }
        }
    }
}
