import SwiftUI

struct DashboardView: View {
    @ObservedObject var manager: ConnectionManager

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                systemStatusSection
                quickActionsSection
            }
            .padding()
        }
        .background(BG_COLOR)
        .preferredColorScheme(.dark)
    }

    private var systemStatusSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "square.grid.2x2")
                    .foregroundColor(CYAN)
                Text("System Status")
                    .font(.headline)
                    .foregroundColor(.white)
            }

            if let status = manager.serverStatus {
                VStack(spacing: 0) {
                    DashboardRow(label: "GPU Temp", value: status.gpu_temp.map { "\($0)°C" } ?? "N/A")
                    Divider().background(BORDER_COLOR)
                    DashboardRow(label: "GPU Util", value: status.gpu_util.map { "\($0)%" } ?? "N/A")
                    Divider().background(BORDER_COLOR)
                    DashboardRow(label: "RAM", value: status.ram_percent.map { "\($0)%" } ?? "N/A")
                    Divider().background(BORDER_COLOR)
                    DashboardRow(label: "Disk", value: status.disk_percent.map { "\($0)%" } ?? "N/A")
                    Divider().background(BORDER_COLOR)
                    DashboardRow(label: "Uptime", value: status.uptime ?? "N/A")
                    Divider().background(BORDER_COLOR)
                    DashboardRow(label: "vLLM", value: status.vllm_status ?? "N/A")
                    Divider().background(BORDER_COLOR)
                    DashboardRow(label: "WireGuard", value: status.wg_handshake ?? "N/A")
                }
                .background(SURFACE_COLOR)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(BORDER_COLOR, lineWidth: 1)
                )
            } else {
                HStack {
                    Image(systemName: "questionmark.circle")
                        .foregroundColor(DIM)
                    Text("No status data available. Connect to see system info.")
                        .font(.subheadline)
                        .foregroundColor(DIM)
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(SURFACE_COLOR)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(BORDER_COLOR, lineWidth: 1)
                )
            }
        }
    }

    private var quickActionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "bolt.fill")
                    .foregroundColor(PINK)
                Text("Quick Actions")
                    .font(.headline)
                    .foregroundColor(.white)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                QuickActionButton(
                    title: "Screenshot",
                    icon: "camera.viewfinder",
                    color: CYAN
                ) {
                    manager.takeScreenshot()
                }

                QuickActionButton(
                    title: "Clipboard Sync",
                    icon: "clipboard",
                    color: CYAN
                ) {
                    manager.copyToClipboard()
                }

                QuickActionButton(
                    title: "Open TUI",
                    icon: "terminal",
                    color: CYAN
                ) {
                    manager.openTUI()
                }
            }
        }
    }
}

struct DashboardRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(DIM)
                .frame(width: 80, alignment: .leading)
            Text(value)
                .font(.subheadline)
                .foregroundColor(.white)
            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }
}

struct QuickActionButton: View {
    let title: String
    let icon: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(title)
                    .font(.caption)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(SURFACE_COLOR)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(BORDER_COLOR, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .foregroundColor(color)
    }
}
