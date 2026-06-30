import AppKit
import SwiftUI
import Combine

class ContentViewController: NSViewController, NSTabViewDelegate {
    let connectionManager = ConnectionManager()

    private let tabView = NSTabView()
    private let statusDot = NSView()
    private let statusLabel = NSTextField(labelWithString: "Disconnected")
    private let statusBar = NSView()
    private var cancellables = Set<AnyCancellable>()

    override func loadView() {
        view = NSView()
        view.frame = NSRect(x: 0, y: 0, width: 900, height: 620)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        observeConnectionManager()
    }

    private func setupUI() {
        statusBar.translatesAutoresizingMaskIntoConstraints = false
        statusBar.wantsLayer = true
        statusBar.layer?.backgroundColor = NSColor.controlBackgroundColor.cgColor
        view.addSubview(statusBar)

        statusDot.translatesAutoresizingMaskIntoConstraints = false
        statusDot.wantsLayer = true
        statusDot.layer?.cornerRadius = 5
        statusDot.layer?.backgroundColor = NSColor.systemRed.cgColor
        statusBar.addSubview(statusDot)

        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.font = NSFont.systemFont(ofSize: 12)
        statusLabel.textColor = NSColor.secondaryLabelColor
        statusBar.addSubview(statusLabel)

        let connectButton = NSButton(title: "Connect", target: self, action: #selector(toggleConnection))
        connectButton.translatesAutoresizingMaskIntoConstraints = false
        connectButton.bezelStyle = .smallSquare
        connectButton.controlSize = .small
        statusBar.addSubview(connectButton)

        NSLayoutConstraint.activate([
            statusBar.topAnchor.constraint(equalTo: view.topAnchor),
            statusBar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            statusBar.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            statusBar.heightAnchor.constraint(equalToConstant: 28),

            statusDot.centerYAnchor.constraint(equalTo: statusBar.centerYAnchor),
            statusDot.leadingAnchor.constraint(equalTo: statusBar.leadingAnchor, constant: 12),
            statusDot.widthAnchor.constraint(equalToConstant: 10),
            statusDot.heightAnchor.constraint(equalToConstant: 10),

            statusLabel.centerYAnchor.constraint(equalTo: statusBar.centerYAnchor),
            statusLabel.leadingAnchor.constraint(equalTo: statusDot.trailingAnchor, constant: 8),
            statusLabel.trailingAnchor.constraint(lessThanOrEqualTo: connectButton.leadingAnchor, constant: -8),

            connectButton.centerYAnchor.constraint(equalTo: statusBar.centerYAnchor),
            connectButton.trailingAnchor.constraint(equalTo: statusBar.trailingAnchor, constant: -12),
        ])

        tabView.translatesAutoresizingMaskIntoConstraints = false
        tabView.tabViewType = .topTabsBezelBorder
        tabView.delegate = self
        view.addSubview(tabView)

        NSLayoutConstraint.activate([
            tabView.topAnchor.constraint(equalTo: statusBar.bottomAnchor),
            tabView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            tabView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            tabView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        let chatTab = makeTab(label: "Chat", rootView: ChatView(manager: connectionManager))
        let dashTab = makeTab(label: "Dashboard", rootView: DashboardView(manager: connectionManager))
        let settingsTab = makeTab(label: "Settings", rootView: SettingsView(manager: connectionManager))
        tabView.addTabViewItem(chatTab)
        tabView.addTabViewItem(dashTab)
        tabView.addTabViewItem(settingsTab)
    }

    private func makeTab<V: View>(label: String, rootView: V) -> NSTabViewItem {
        let item = NSTabViewItem(identifier: label)
        item.label = label
        let hosting = NSHostingView(rootView: rootView)
        hosting.autoresizingMask = [.width, .height]
        item.view = hosting
        return item
    }

    func switchToTab(index: Int) {
        guard index >= 0, index < tabView.numberOfTabViewItems else { return }
        tabView.selectTabViewItem(at: index)
    }

    @objc private func toggleConnection() {
        switch connectionManager.connectionState {
        case .connected, .connecting:
            connectionManager.disconnect()
        case .disconnected:
            connectionManager.connect()
        }
    }

    private func observeConnectionManager() {
        connectionManager.$connectionState
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                guard let self else { return }
                let color: NSColor
                switch state {
                case .connected: color = .systemGreen
                case .connecting: color = .systemYellow
                case .disconnected: color = .systemRed
                }
                self.statusDot.layer?.backgroundColor = color.cgColor
            }
            .store(in: &cancellables)

        connectionManager.$statusText
            .receive(on: DispatchQueue.main)
            .sink { [weak self] text in
                self?.statusLabel.stringValue = text
            }
            .store(in: &cancellables)
    }
}
