import SwiftUI

struct SettingsView: View {
    @ObservedObject var manager: ConnectionManager
    @State private var testResult: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                connectionSection
                generalSection
                aboutSection
            }
            .padding()
        }
        .background(BG_COLOR)
        .preferredColorScheme(.dark)
    }

    private var connectionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "network")
                    .foregroundColor(CYAN)
                Text("Connection")
                    .font(.headline)
                    .foregroundColor(.white)
            }

            VStack(spacing: 0) {
                settingsRow {
                    Text("Server Address")
                        .foregroundColor(DIM)
                        .frame(width: 120, alignment: .leading)
                    TextField("holmium.local", text: $manager.serverURL)
                        .textFieldStyle(.plain)
                        .foregroundColor(.white)
                        .padding(6)
                        .background(SURFACE_COLOR)
                        .cornerRadius(6)
                }
                Divider().background(BORDER_COLOR)
                settingsRow {
                    Text("Port")
                        .foregroundColor(DIM)
                        .frame(width: 120, alignment: .leading)
                    TextField("443", value: $manager.serverPort, format: .number)
                        .textFieldStyle(.plain)
                        .foregroundColor(.white)
                        .padding(6)
                        .background(SURFACE_COLOR)
                        .cornerRadius(6)
                        .frame(width: 80)
                    Spacer()
                }
                Divider().background(BORDER_COLOR)
                settingsRow {
                    Text("Auth Token")
                        .foregroundColor(DIM)
                        .frame(width: 120, alignment: .leading)
                    SecureField("Token", text: $manager.token)
                        .textFieldStyle(.plain)
                        .foregroundColor(.white)
                        .padding(6)
                        .background(SURFACE_COLOR)
                        .cornerRadius(6)
                }
                Divider().background(BORDER_COLOR)
                settingsRow {
                    Spacer()
                    Button("Test Connection") {
                        testConnection()
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(CYAN)
                    .controlSize(.small)

                    if let result = testResult {
                        Text(result)
                            .font(.caption)
                            .foregroundColor(result == "OK" ? .green : .red)
                    }
                }
            }
            .background(SURFACE_COLOR)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(BORDER_COLOR, lineWidth: 1)
            )
        }
    }

    private var generalSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "gearshape")
                    .foregroundColor(PINK)
                Text("General")
                    .font(.headline)
                    .foregroundColor(.white)
            }

            VStack(spacing: 0) {
                Toggle(isOn: $manager.autoConnect) {
                    Text("Auto-connect").foregroundColor(.white)
                }
                .toggleStyle(.switch)
                .controlSize(.small)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                Divider().background(BORDER_COLOR)

                Toggle(isOn: $manager.clipboardSync) {
                    Text("Clipboard Sync").foregroundColor(.white)
                }
                .toggleStyle(.switch)
                .controlSize(.small)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                Divider().background(BORDER_COLOR)

                Toggle(isOn: $manager.notificationsEnabled) {
                    Text("Notifications").foregroundColor(.white)
                }
                .toggleStyle(.switch)
                .controlSize(.small)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            }
            .background(SURFACE_COLOR)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(BORDER_COLOR, lineWidth: 1)
            )
        }
    }

    private var aboutSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "info.circle")
                    .foregroundColor(DIM)
                Text("About")
                    .font(.headline)
                    .foregroundColor(.white)
            }

            VStack(spacing: 4) {
                Text("Holmium")
                    .font(.title3)
                    .foregroundColor(.white)
                Text("Version 1.0.0")
                    .font(.subheadline)
                    .foregroundColor(DIM)
                Text("AI-powered local assistant")
                    .font(.caption)
                    .foregroundColor(DIM)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(SURFACE_COLOR)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(BORDER_COLOR, lineWidth: 1)
            )
        }
    }

    private func settingsRow<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        HStack {
            content()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    private func testConnection() {
        testResult = nil
        manager.disconnect()
        manager.connect()
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            testResult = manager.connectionState == .connected ? "OK" : "Failed"
        }
    }
}
