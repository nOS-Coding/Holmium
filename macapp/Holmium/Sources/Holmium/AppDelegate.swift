import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var contentViewController: ContentViewController!

    func applicationDidFinishLaunching(_ notification: Notification) {
        contentViewController = ContentViewController()

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 900, height: 620),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.center()
        window.title = "Holmium"
        window.contentMinSize = NSSize(width: 700, height: 400)
        window.contentViewController = contentViewController
        window.makeKeyAndOrderFront(nil)

        setupMenuBar()

        if contentViewController.connectionManager.autoConnect {
            contentViewController.connectionManager.connect()
        }
    }

    private func setupMenuBar() {
        let mainMenu = NSMenu()

        let appMenuItem = NSMenuItem()
        appMenuItem.submenu = NSMenu(title: "Holmium")
        appMenuItem.submenu?.items = [
            NSMenuItem(title: "About Holmium", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""),
            NSMenuItem.separator(),
            NSMenuItem(title: "Settings...", action: #selector(showSettings), keyEquivalent: ","),
            NSMenuItem.separator(),
            NSMenuItem(title: "Quit Holmium", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"),
        ]
        mainMenu.addItem(appMenuItem)

        let fileMenuItem = NSMenuItem()
        fileMenuItem.submenu = NSMenu(title: "File")
        fileMenuItem.submenu?.items = [
            NSMenuItem(title: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w"),
        ]
        mainMenu.addItem(fileMenuItem)

        let editMenuItem = NSMenuItem()
        editMenuItem.submenu = NSMenu(title: "Edit")
        editMenuItem.submenu?.items = [
            NSMenuItem(title: "Undo", action: #selector(UndoManager.undo), keyEquivalent: "z"),
            NSMenuItem(title: "Redo", action: #selector(UndoManager.redo), keyEquivalent: "Z"),
            NSMenuItem.separator(),
            NSMenuItem(title: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x"),
            NSMenuItem(title: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c"),
            NSMenuItem(title: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v"),
            NSMenuItem(title: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a"),
        ]
        mainMenu.addItem(editMenuItem)

        let viewMenuItem = NSMenuItem()
        viewMenuItem.submenu = NSMenu(title: "View")
        viewMenuItem.submenu?.items = [
            NSMenuItem(title: "Enter Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f"),
        ]
        mainMenu.addItem(viewMenuItem)

        let windowMenuItem = NSMenuItem()
        windowMenuItem.submenu = NSMenu(title: "Window")
        windowMenuItem.submenu?.items = [
            NSMenuItem(title: "Minimize", action: #selector(NSWindow.miniaturize(_:)), keyEquivalent: "m"),
            NSMenuItem(title: "Zoom", action: #selector(NSWindow.zoom(_:)), keyEquivalent: ""),
        ]
        mainMenu.addItem(windowMenuItem)

        let helpMenuItem = NSMenuItem()
        helpMenuItem.submenu = NSMenu(title: "Help")
        helpMenuItem.submenu?.items = [
            NSMenuItem(title: "Holmium Help", action: nil, keyEquivalent: ""),
        ]
        mainMenu.addItem(helpMenuItem)

        NSApplication.shared.mainMenu = mainMenu
    }

    @objc func showSettings() {
        contentViewController?.switchToTab(index: 2)
        window.makeKeyAndOrderFront(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
