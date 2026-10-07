import SwiftUI
import WebKit

/// Silai Rahm for macOS: the family-tree site in a native window, with system
/// notifications (and their own sound), a dock badge and menu, a menu-bar
/// bell, file downloads, printing and Google sign-in. Menus follow the
/// language chosen on the site: Uzbek (Latin / Cyrillic), Russian or English.
@main
struct SilaiRahmApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var browser = Browser.shared
    @StateObject private var notifier = Notifier.shared
    @AppStorage("menuBar") private var showMenuBar = true

    var body: some Scene {
        let lang = browser.language
        Window("Silai Rahm", id: "main") {
            ContentView()
                .environmentObject(browser)
                .frame(minWidth: 1040, minHeight: 640)
        }
        .defaultSize(width: 1320, height: 860)
        .windowToolbarStyle(.unifiedCompact(showsTitle: false))
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(replacing: .printItem) {
                Button(L.t("print", lang)) { browser.printPage() }.keyboardShortcut("p")
            }
            CommandGroup(before: .toolbar) {
                Button(L.t("reload", lang)) { browser.reload() }.keyboardShortcut("r")
                Button(L.t("back", lang)) { browser.goBack() }.keyboardShortcut("[")
                Button(L.t("forward", lang)) { browser.goForward() }.keyboardShortcut("]")
                Button(L.t("home", lang)) { browser.goHome() }.keyboardShortcut("h", modifiers: [.command, .shift])
                Divider()
                Button(L.t("zoomIn", lang)) { browser.zoom(by: 0.1) }.keyboardShortcut("+")
                Button(L.t("zoomOut", lang)) { browser.zoom(by: -0.1) }.keyboardShortcut("-")
                Button(L.t("actualSize", lang)) { browser.resetZoom() }.keyboardShortcut("0")
                Divider()
            }
            CommandMenu(L.t("appMenu", lang)) {
                Button(L.t("myTree", lang)) { browser.open(path: "/shajara/") }.keyboardShortcut("1")
                Button(L.t("relatives", lang)) { browser.open(path: "/qarindoshlar/") }.keyboardShortcut("2")
                Button(L.t("events", lang)) { browser.open(path: "/voqealar/") }.keyboardShortcut("3")
                Button(L.t("friends", lang)) { browser.open(path: "/dostlar/") }.keyboardShortcut("4")
                Button(L.t("timeline", lang)) { browser.open(path: "/vaqt-chizigi/") }.keyboardShortcut("5")
                Button(L.t("search", lang)) { browser.openSearch() }.keyboardShortcut("f")
                Button(L.t("addRelative", lang)) { browser.open(path: "/qarindoshlar/yangi/") }.keyboardShortcut("n")
                Divider()
                Button(L.t("notifications", lang)) { browser.open(path: "/xabarlar/") }.keyboardShortcut("b", modifiers: [.command, .shift])
                Button(L.t("siteSettings", lang)) { browser.open(path: "/sozlamalar/") }
                Button(L.t("openInBrowser", lang)) { browser.openInBrowser() }
            }
        }

        MenuBarExtra(isInserted: $showMenuBar) {
            MenuBarContent().environmentObject(browser).environmentObject(notifier)
        } label: {
            Image(systemName: notifier.unread > 0 ? "bell.badge.fill" : "bell")
        }
        .menuBarExtraStyle(.menu)

        Settings {
            SettingsView().environmentObject(browser).environmentObject(notifier)
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    /// Opens the main window when it has been closed (set by SwiftUI views).
    static var openMain: (() -> Void)?

    static func showMainWindow() {
        if let window = NSApp.windows.first(where: { $0.identifier?.rawValue.hasPrefix("main") == true }), window.isVisible {
            window.makeKeyAndOrderFront(nil)
        } else {
            openMain?()
        }
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        Notifier.shared.start()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        !(UserDefaults.standard.object(forKey: "keepRunning") as? Bool ?? true)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { AppDelegate.showMainWindow() }
        return true
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        Notifier.shared.checkSoon()
        Notifier.shared.refreshPermission()
    }

    // Right-click on the dock icon: quick links.
    func applicationDockMenu(_ sender: NSApplication) -> NSMenu? {
        let menu = NSMenu()
        for (key, path) in [("myTree", "/shajara/"), ("relatives", "/qarindoshlar/"), ("events", "/voqealar/"),
                            ("search", "/qidiruv/"), ("addRelative", "/qarindoshlar/yangi/")] {
            let item = NSMenuItem(title: L.t(key), action: #selector(openPath(_:)), keyEquivalent: "")
            item.representedObject = path
            item.target = self
            menu.addItem(item)
        }
        return menu
    }

    @objc private func openPath(_ sender: NSMenuItem) {
        guard let path = sender.representedObject as? String else { return }
        AppDelegate.showMainWindow()
        Browser.shared.open(path: path)
    }
}

struct ContentView: View {
    @EnvironmentObject var browser: Browser
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let lang = browser.language
        ZStack(alignment: .top) {
            WebView(browser: browser)
            if browser.isLoading {
                ProgressView(value: browser.progress)
                    .progressViewStyle(.linear)
                    .tint(Color(red: 0.85, green: 0.62, blue: 0.14))
                    .frame(height: 2)
            }
            if let message = browser.errorMessage {
                OfflineView(message: message, lang: lang) { browser.reload() }
            }
        }
        .navigationTitle(browser.title.isEmpty ? L.t("appMenu", lang) : browser.title)
        .onAppear {
            AppDelegate.openMain = { openWindow(id: "main") }
            DispatchQueue.main.async { browser.applyTheme() }
        }
        .toolbar {
            ToolbarItemGroup(placement: .navigation) {
                Button(action: browser.goBack) { Image(systemName: "chevron.left") }
                    .disabled(!browser.canGoBack).help(L.t("back", lang))
                Button(action: browser.goForward) { Image(systemName: "chevron.right") }
                    .disabled(!browser.canGoForward).help(L.t("forward", lang))
            }
            // The site has its own sidebar: the window only adds what a page cannot do.
            ToolbarItem(placement: .primaryAction) {
                Button(action: browser.reload) { Image(systemName: "arrow.clockwise") }.help(L.t("reload", lang))
            }
        }
    }
}

/// The bell in the menu bar: unread reminders and quick links.
struct MenuBarContent: View {
    @EnvironmentObject var browser: Browser
    @EnvironmentObject var notifier: Notifier
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let lang = browser.language
        Text(notifier.unread > 0 ? String(format: L.t("unread", lang), notifier.unread) : L.t("noUnread", lang))
        ForEach(notifier.items.prefix(8)) { item in
            Button("\(item.icon) \(item.title)") { notifier.open(item.url) }
        }
        Divider()
        Button(L.t("openWindow", lang)) { show() }
        Button(L.t("myTree", lang)) { show(); browser.open(path: "/shajara/") }
        Button(L.t("events", lang)) { show(); browser.open(path: "/voqealar/") }
        Divider()
        Button(L.t("quit", lang)) { NSApp.terminate(nil) }.keyboardShortcut("q")
            .onAppear { AppDelegate.openMain = { openWindow(id: "main") }; notifier.checkSoon() }
    }

    private func show() {
        openWindow(id: "main")
        NSApp.activate(ignoringOtherApps: true)
    }
}

struct OfflineView: View {
    let message: String
    let lang: AppLanguage
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "wifi.exclamationmark").font(.system(size: 44)).foregroundStyle(.secondary)
            Text(L.t("cantConnect", lang)).font(.title2.bold())
            Text(message).foregroundStyle(.secondary).multilineTextAlignment(.center).frame(maxWidth: 420)
            Button(L.t("retry", lang), action: retry).keyboardShortcut(.defaultAction)
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.background)
    }
}
