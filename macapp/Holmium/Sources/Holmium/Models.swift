import Foundation

struct Message: Identifiable, Codable {
    let id: String
    let role: String
    let content: String
    let timestamp: Date

    init(role: String, content: String) {
        self.id = UUID().uuidString
        self.role = role
        self.content = content
        self.timestamp = Date()
    }
}

struct SystemStatus: Codable {
    var cpu_percent: String?
    var ram_percent: String?
    var gpu_util: String?
    var gpu_temp: String?
    var vram_used_gb: String?
    var vram_total_gb: Float?
    var vllm_status: String?
    var wg_handshake: String?
    var uptime: String?
    var disk_percent: String?
}

struct ToolCall: Identifiable {
    let id = UUID()
    let name: String
}

enum ConnectionState {
    case disconnected
    case connecting
    case connected
}
