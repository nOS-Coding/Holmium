import SwiftUI

let BG_COLOR = Color(red: 0.05, green: 0.05, blue: 0.05)
let SURFACE_COLOR = Color(red: 0.08, green: 0.08, blue: 0.10)
let BORDER_COLOR = Color(red: 0.10, green: 0.10, blue: 0.18)
let CYAN = Color(red: 0.0, green: 0.74, blue: 0.83)
let PINK = Color(red: 1.0, green: 0.41, blue: 0.71)
let DIM = Color(red: 0.4, green: 0.4, blue: 0.4)

struct ChatView: View {
    @ObservedObject var manager: ConnectionManager
    @State private var showFilePicker = false

    var body: some View {
        VStack(spacing: 0) {
            if manager.messages.isEmpty && !manager.isProcessing {
                emptyState
            } else {
                messageList
            }

            Divider().background(BORDER_COLOR)

            inputArea
        }
        .background(BG_COLOR)
        .preferredColorScheme(.dark)
        .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [.image]) { result in
            if case .success(let url) = result {
                manager.sendImage(url)
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "brain.head.profile")
                .font(.system(size: 48))
                .foregroundColor(DIM)
            Text("Ask Holmium anything")
                .font(.title3)
                .foregroundColor(DIM)
            Text("Type a message below to start chatting")
                .font(.caption)
                .foregroundColor(DIM.opacity(0.7))
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(manager.messages) { msg in
                        MessageBubble(message: msg)
                    }
                    if manager.isProcessing {
                        TypingBubble(text: manager.statusText)
                    }
                    if let tool = manager.currentToolCall {
                        HStack {
                            Image(systemName: "bolt.fill")
                                .font(.caption)
                                .foregroundColor(PINK)
                            Text("Tool: \(tool.name)")
                                .font(.caption)
                                .foregroundColor(DIM)
                        }
                        .padding(.horizontal)
                    }
                }
                .padding()
            }
            .onChange(of: manager.messages.count) { _, _ in
                if let last = manager.messages.last {
                    proxy.scrollTo(last.id, anchor: .bottom)
                }
            }
        }
    }

    private var inputArea: some View {
        HStack(spacing: 8) {
            Button(action: { showFilePicker = true }) {
                Image(systemName: "paperclip")
                    .foregroundColor(CYAN)
            }
            .buttonStyle(.plain)
            .help("Attach file or image")

            TextField("Ask Holmium anything...", text: $manager.inputText)
                .textFieldStyle(.plain)
                .foregroundColor(.white)
                .padding(8)
                .background(SURFACE_COLOR)
                .cornerRadius(8)
                .onSubmit {
                    manager.sendMessage(manager.inputText)
                }

            Button(action: { manager.sendMessage(manager.inputText) }) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
                    .foregroundColor(
                        manager.inputText.trimmingCharacters(in: .whitespaces).isEmpty
                            ? DIM : CYAN
                    )
            }
            .buttonStyle(.plain)
            .disabled(manager.inputText.trimmingCharacters(in: .whitespaces).isEmpty)
            .help("Send message (Enter)")
        }
        .padding()
        .background(BG_COLOR)
    }
}

struct MessageBubble: View {
    let message: Message
    var isUser: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if isUser { Spacer() }
            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                Text(isUser ? "You" : "Holmium")
                    .font(.caption2)
                    .foregroundColor(isUser ? CYAN : .white)
                Text(message.content)
                    .font(.system(size: 14))
                    .foregroundColor(.white)
                    .padding(12)
                    .background(isUser ? CYAN.opacity(0.2) : SURFACE_COLOR)
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(isUser ? CYAN.opacity(0.3) : BORDER_COLOR, lineWidth: 1)
                    )
            }
            .frame(maxWidth: 600, alignment: isUser ? .trailing : .leading)
            if !isUser { Spacer() }
        }
    }
}

struct TypingBubble: View {
    let text: String

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Holmium")
                    .font(.caption2)
                    .foregroundColor(.white)
                Text(text)
                    .font(.system(size: 14))
                    .foregroundColor(DIM)
                    .padding(12)
                    .background(SURFACE_COLOR)
                    .cornerRadius(12)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(BORDER_COLOR, lineWidth: 1)
                    )
            }
            .frame(maxWidth: 600, alignment: .leading)
            Spacer()
        }
    }
}
