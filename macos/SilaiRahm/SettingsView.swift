import ServiceManagement
import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var browser: Browser
    @EnvironmentObject var notifier: Notifier

    var body: some View {
        let lang = browser.language
        TabView {
            GeneralSettings().tabItem { Label(L.t("general", lang), systemImage: "gearshape") }
            NotificationSettings().tabItem { Label(L.t("notifications", lang), systemImage: "bell") }
            AboutView().tabItem { Label(L.t("about", lang), systemImage: "info.circle") }
        }
        .frame(width: 560)
        .padding(.vertical, 8)
    }
}

private struct GeneralSettings: View {
    @EnvironmentObject var browser: Browser
    @AppStorage("server") private var server = Browser.defaultServer
    @AppStorage("keepRunning") private var keepRunning = true
    @AppStorage("menuBar") private var menuBar = true
    @State private var launchAtLogin = SMAppService.mainApp.status == .enabled
    @State private var loginError: String?

    var body: some View {
        let lang = browser.language
        Form {
            Section {
                TextField(L.t("server", lang), text: $server, prompt: Text(Browser.defaultServer))
                    .textFieldStyle(.roundedBorder)
                HStack {
                    Button(L.t("defaultServer", lang)) { server = Browser.defaultServer }
                    Spacer()
                    Button(L.t("saveAndOpen", lang)) { browser.goHome() }.keyboardShortcut(.defaultAction)
                }
            } footer: {
                Text(L.t("serverHelp", lang)).font(.caption).foregroundStyle(.secondary)
            }
            Section {
                Toggle(L.t("launchAtLogin", lang), isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { on in
                        do {
                            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
                            loginError = nil
                        } catch {
                            loginError = error.localizedDescription
                            launchAtLogin = SMAppService.mainApp.status == .enabled
                        }
                    }
                if let loginError { Text(loginError).font(.caption).foregroundStyle(.red) }
                Toggle(L.t("keepRunning", lang), isOn: $keepRunning)
                Text(L.t("keepRunningHelp", lang)).font(.caption).foregroundStyle(.secondary)
                Toggle(L.t("menuBar", lang), isOn: $menuBar)
            }
        }
        .formStyle(.grouped)
    }
}

private struct NotificationSettings: View {
    @EnvironmentObject var browser: Browser
    @EnvironmentObject var notifier: Notifier
    @AppStorage("notifications") private var enabled = true
    @AppStorage("sound") private var sound = Notifier.Sound.chime.rawValue

    var body: some View {
        let lang = browser.language
        Form {
            Section {
                Toggle(L.t("notify", lang), isOn: $enabled)
                    .onChange(of: enabled) { value in notifier.enabled = value }
                Picker(L.t("sound", lang), selection: $sound) {
                    ForEach(Notifier.Sound.allCases) { Text($0.label).tag($0.rawValue) }
                }
                .onChange(of: sound) { _ in SoundPreview.play(Notifier.shared.sound) }
                HStack {
                    Spacer()
                    Button(L.t("test", lang)) { notifier.sendTest() }
                }
            }
            if !notifier.allowed {
                Section {
                    Text(L.t("notificationsOff", lang)).foregroundStyle(.secondary)
                    Button(L.t("openSystemSettings", lang)) {
                        NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.notifications")!)
                    }
                }
            }
        }
        .formStyle(.grouped)
        .onAppear { notifier.refreshPermission() }
    }
}

/// Plays the chosen sound when it is picked in Settings.
enum SoundPreview {
    static func play(_ sound: Notifier.Sound) {
        switch sound {
        case .chime: NSSound(named: "SilaiRahm")?.play()
        case .system: NSSound.beep()
        case .none: break
        }
    }
}

private struct AboutView: View {
    @EnvironmentObject var browser: Browser

    var body: some View {
        let lang = browser.language
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        VStack(spacing: 10) {
            Image(nsImage: NSApp.applicationIconImage).resizable().frame(width: 96, height: 96)
            Text(L.t("appMenu", lang)).font(.title.bold())
            Text(L.t("aboutText", lang)).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Text("\(L.t("version", lang)) \(version)").font(.caption).foregroundStyle(.secondary)
            Link(Browser.defaultServer.replacingOccurrences(of: "https://", with: ""), destination: browser.server)
        }
        .padding(28)
        .frame(maxWidth: .infinity)
    }
}
