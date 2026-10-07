import AppKit
import UserNotifications

/// Checks the site for unread reminders (birthdays, events …), shows them as
/// macOS notifications with the chosen sound, and keeps the dock badge and the
/// menu-bar bell up to date.
final class Notifier: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = Notifier()

    struct Item: Decodable, Identifiable, Equatable {
        let id: Int
        let url: String
        let title: String
        let body: String
        let icon: String
    }

    enum Sound: String, CaseIterable, Identifiable {
        case chime, system, none
        var id: String { rawValue }
        var label: String {
            switch self {
            case .chime: return L.t("soundChime")
            case .system: return L.t("soundSystem")
            case .none: return L.t("soundNone")
            }
        }
    }

    @Published private(set) var unread = 0
    @Published private(set) var items: [Item] = []
    @Published private(set) var allowed = true

    private var timer: Timer?
    private var pending: DispatchWorkItem?
    private let seenKey = "seenNotificationIDs"
    private let center = UNUserNotificationCenter.current()

    var enabled: Bool {
        get { UserDefaults.standard.object(forKey: "notifications") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "notifications"); if newValue { requestPermission() } }
    }

    var sound: Sound {
        get { Sound(rawValue: UserDefaults.standard.string(forKey: "sound") ?? "") ?? .chime }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: "sound") }
    }

    func start() {
        center.delegate = self
        if enabled { requestPermission() }
        timer = Timer.scheduledTimer(withTimeInterval: 10 * 60, repeats: true) { [weak self] _ in self?.check() }
        timer?.tolerance = 60
    }

    func requestPermission() {
        center.requestAuthorization(options: [.alert, .sound, .badge]) { [weak self] granted, _ in
            DispatchQueue.main.async { self?.allowed = granted }
        }
    }

    func refreshPermission() {
        center.getNotificationSettings { [weak self] settings in
            DispatchQueue.main.async { self?.allowed = settings.authorizationStatus != .denied }
        }
    }

    /// Several triggers (page loads, app activation) are merged into one check.
    func checkSoon() {
        pending?.cancel()
        let work = DispatchWorkItem { [weak self] in self?.check() }
        pending = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 2, execute: work)
    }

    func check() {
        let js = """
        const r = await fetch('/xabarlar/holat.json', {credentials: 'same-origin', headers: {Accept: 'application/json'}});
        if (!r.ok || r.redirected) return null;
        return await r.text();
        """
        Browser.shared.webView.callAsyncJavaScript(js, arguments: [:], in: nil, in: .page) { [weak self] result in
            guard let self, case .success(let value) = result, let text = value as? String,
                  let data = text.data(using: .utf8),
                  let status = try? JSONDecoder().decode(Status.self, from: data) else { return }
            self.unread = status.unread
            self.items = status.items
            NSApp.dockTile.badgeLabel = status.unread > 0 ? String(status.unread) : nil
            guard self.enabled else { return }
            var seen = Set(UserDefaults.standard.array(forKey: self.seenKey) as? [Int] ?? [])
            for item in status.items where !seen.contains(item.id) {
                self.post(id: "silairahm-\(item.id)", title: "\(item.icon) \(item.title)", body: item.body, url: item.url)
                seen.insert(item.id)
            }
            UserDefaults.standard.set(Array(seen.sorted().suffix(500)), forKey: self.seenKey)
        }
    }

    func sendTest() {
        requestPermission()
        post(id: "silairahm-test-\(Date().timeIntervalSince1970)", title: L.t("testTitle"), body: L.t("testBody"), url: nil)
    }

    private func post(id: String, title: String, body: String, url: String?) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        switch sound {
        case .chime: content.sound = UNNotificationSound(named: UNNotificationSoundName("SilaiRahm.wav"))
        case .system: content.sound = .default
        case .none: content.sound = nil
        }
        if let url { content.userInfo = ["url": url] }
        center.add(UNNotificationRequest(identifier: id, content: content, trigger: nil))
    }

    /// Opens a reminder in the app (from a notification or the menu-bar bell).
    func open(_ link: String) {
        guard let url = URL(string: link) else { return }
        NSApp.activate(ignoringOtherApps: true)
        AppDelegate.showMainWindow()
        Browser.shared.load(url)
        checkSoon()
    }

    // Clicking a notification opens it in the app.
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        if let link = response.notification.request.content.userInfo["url"] as? String {
            DispatchQueue.main.async { self.open(link) }
        } else {
            DispatchQueue.main.async { NSApp.activate(ignoringOtherApps: true); AppDelegate.showMainWindow() }
        }
        completionHandler()
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .list])
    }

    private struct Status: Decodable {
        let unread: Int
        let items: [Item]
    }
}
