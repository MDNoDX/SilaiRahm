import AppKit
import SwiftUI
import WebKit

/// The WKWebView plus the native pieces a web page cannot do on its own:
/// confirm dialogs, choosing a photo, saving downloads, opening outside links.
struct WebView: NSViewRepresentable {
    let browser: Browser

    func makeCoordinator() -> Coordinator { Coordinator(browser: browser) }

    func makeNSView(context: Context) -> WKWebView {
        let view = browser.webView
        view.navigationDelegate = context.coordinator
        view.uiDelegate = context.coordinator
        return view
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
        let browser: Browser
        private var downloadTargets: [ObjectIdentifier: URL] = [:]

        init(browser: Browser) { self.browser = browser }

        // MARK: Navigation policy

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = action.request.url, let scheme = url.scheme?.lowercased() else { return decisionHandler(.allow) }
            if action.shouldPerformDownload { return decisionHandler(.download) }
            // Google does not allow its sign-in page inside apps: use the system window.
            if url.host == "accounts.google.com" || url.path.hasPrefix("/accounts/google/login") {
                decisionHandler(.cancel)
                if url.query?.contains("process=connect") == true { browser.connectGoogleInBrowser() }
                else { browser.signInWithGoogle() }
                return
            }
            // tg://, mailto:, tel: … belong to other apps (tg:// opens the Telegram app).
            if !["http", "https", "about", "blob", "data"].contains(scheme) {
                NSWorkspace.shared.open(url)
                return decisionHandler(.cancel)
            }
            if !browser.isOwnSite(url) && (action.navigationType == .linkActivated || action.targetFrame == nil) {
                NSWorkspace.shared.open(url)
                return decisionHandler(.cancel)
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                     decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            let disposition = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
            decisionHandler(disposition.lowercased().hasPrefix("attachment") || !response.canShowMIMEType ? .download : .allow)
        }

        func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
            download.delegate = self
        }

        func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
            download.delegate = self
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            browser.pageLoaded()
            Notifier.shared.checkSoon()
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            let code = (error as NSError).code
            // Cancelled, "frame load interrupted" (downloads) and unsupported schemes are not connection problems.
            if [NSURLErrorCancelled, 102, NSURLErrorUnsupportedURL].contains(code) { return }
            browser.errorMessage = error.localizedDescription
        }

        // If the page's process crashes (e.g. after sleep), load it again.
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            webView.reload()
        }

        // Links that open a new window (target=_blank) load in the same window.
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = action.request.url {
                if browser.isOwnSite(url) { webView.load(action.request) } else { NSWorkspace.shared.open(url) }
            }
            return nil
        }

        // MARK: Microphone and camera (voice and video stories)

        @available(macOS 12.0, *)
        func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                     initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                     decisionHandler: @escaping (WKPermissionDecision) -> Void) {
            // Only our own site; macOS still asks the person once (Info.plist explains why).
            decisionHandler(origin.host == browser.server.host ? .grant : .deny)
        }

        // MARK: JavaScript dialogs

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let alert = NSAlert()
            alert.messageText = message
            alert.addButton(withTitle: L.t("ok"))
            alert.runModal()
            completionHandler()
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let alert = NSAlert()
            alert.messageText = message
            alert.alertStyle = .warning
            alert.addButton(withTitle: L.t("yes"))
            alert.addButton(withTitle: L.t("cancel"))
            completionHandler(alert.runModal() == .alertFirstButtonReturn)
        }

        // <input type="file">: photos, documents and recordings for the album,
        // or an archive (JSON, GEDCOM) to import. The page checks what it accepts.
        func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
            let panel = NSOpenPanel()
            panel.allowsMultipleSelection = parameters.allowsMultipleSelection
            panel.canChooseDirectories = false
            panel.begin { completionHandler($0 == .OK ? panel.urls : nil) }
        }

        // MARK: Downloads (PDF, PNG, GEDCOM, JSON)

        func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                      suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
            let panel = NSSavePanel()
            panel.nameFieldStringValue = suggestedFilename
            panel.canCreateDirectories = true
            panel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
            panel.begin { [weak self] result in
                guard result == .OK, let url = panel.url else { return completionHandler(nil) }
                try? FileManager.default.removeItem(at: url)
                self?.downloadTargets[ObjectIdentifier(download)] = url
                completionHandler(url)
            }
        }

        func downloadDidFinish(_ download: WKDownload) {
            if let url = downloadTargets.removeValue(forKey: ObjectIdentifier(download)) {
                NSWorkspace.shared.activateFileViewerSelecting([url])
            }
        }

        func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
            downloadTargets.removeValue(forKey: ObjectIdentifier(download))
            let alert = NSAlert(error: error)
            alert.runModal()
        }
    }
}
