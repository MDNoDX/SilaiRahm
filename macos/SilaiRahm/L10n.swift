import Foundation

/// The app speaks the same language as the site: after every page load the
/// page's <html lang> is read and the menus, buttons and settings follow it.
enum AppLanguage: String, CaseIterable {
    case uz, uzCyrl = "uz-cyrl", ru, en

    /// From the page's lang attribute: uz-Latn, uz-Cyrl, ru, en.
    init?(htmlLang: String) {
        switch htmlLang.lowercased() {
        case "uz", "uz-latn": self = .uz
        case "uz-cyrl": self = .uzCyrl
        case let l where l.hasPrefix("ru"): self = .ru
        case let l where l.hasPrefix("en"): self = .en
        default: return nil
        }
    }

    /// First launch: the Mac's own language when it is one of ours.
    static var system: AppLanguage {
        for code in Locale.preferredLanguages {
            let c = code.lowercased()
            if c.hasPrefix("uz") { return c.contains("cyrl") ? .uzCyrl : .uz }
            if c.hasPrefix("ru") { return .ru }
            if c.hasPrefix("en") { return .en }
        }
        return .uz
    }
}

enum L {
    // [uz, uz-cyrl, ru, en]
    private static let table: [String: [String]] = [
        "view": ["Koʻrinish", "Кўриниш", "Вид", "View"],
        "reload": ["Yangilash", "Янгилаш", "Обновить", "Reload"],
        "back": ["Orqaga", "Орқага", "Назад", "Back"],
        "forward": ["Oldinga", "Олдинга", "Вперёд", "Forward"],
        "home": ["Bosh sahifa", "Бош саҳифа", "Главная", "Home"],
        "zoomIn": ["Kattalashtirish", "Катталаштириш", "Увеличить", "Zoom In"],
        "zoomOut": ["Kichiklashtirish", "Кичиклаштириш", "Уменьшить", "Zoom Out"],
        "actualSize": ["Asl oʻlcham", "Асл ўлчам", "Исходный размер", "Actual Size"],
        "appMenu": ["Silai Rahm", "Silai Rahm", "Silai Rahm", "Silai Rahm"],
        "myTree": ["Shajaram", "Шажарам", "Моё древо", "My family tree"],
        "relatives": ["Qarindoshlarim", "Қариндошларим", "Мои родственники", "My relatives"],
        "events": ["Voqealar", "Воқеалар", "События", "Events"],
        "timeline": ["Vaqt chizigʻi", "Вақт чизиғи", "Хронология", "Timeline"],
        "friends": ["Doʻstlarim", "Дўстларим", "Мои друзья", "My friends"],
        "search": ["Qidiruv", "Қидирув", "Поиск", "Search"],
        "addRelative": ["Qarindosh qoʻshish", "Қариндош қўшиш", "Добавить родственника", "Add a relative"],
        "notifications": ["Bildirishnomalar", "Билдиришномалар", "Уведомления", "Notifications"],
        "siteSettings": ["Sayt sozlamalari", "Сайт созламалари", "Настройки сайта", "Site settings"],
        "openInBrowser": ["Brauzerda ochish", "Браузерда очиш", "Открыть в браузере", "Open in Browser"],
        "print": ["Chop etish…", "Чоп этиш…", "Печать…", "Print…"],
        "openWindow": ["Silai Rahmni ochish", "Silai Rahm ойнасини очиш", "Открыть Silai Rahm", "Open Silai Rahm"],
        "quit": ["Chiqish", "Чиқиш", "Выйти", "Quit"],
        "unread": ["Yangi eslatmalar: %d", "Янги эслатмалар: %d", "Новых напоминаний: %d", "New reminders: %d"],
        "noUnread": ["Yangi eslatma yoʻq", "Янги эслатма йўқ", "Новых напоминаний нет", "No new reminders"],
        "cantConnect": ["Saytga ulanib boʻlmadi", "Сайтга уланиб бўлмади", "Не удалось подключиться к сайту", "Could not reach the site"],
        "retry": ["Qayta urinish", "Қайта уриниш", "Повторить", "Try again"],
        "yes": ["Ha", "Ҳа", "Да", "Yes"],
        "cancel": ["Bekor qilish", "Бекор қилиш", "Отмена", "Cancel"],
        "ok": ["OK", "OK", "OK", "OK"],
        "connectGoogleInBrowser": ["Google hisobini ulash brauzerda ochiladi: u yerda saytga kiring va Sozlamalar → Xavfsizlik boʻlimida ulang.",
                                   "Google ҳисобини улаш браузерда очилади: у ерда сайтга киринг ва Созламалар → Хавфсизлик бўлимида уланг.",
                                   "Подключение Google откроется в браузере: войдите там на сайт и подключите в Настройки → Безопасность.",
                                   "Connecting Google opens in your browser: sign in to the site there and connect it in Settings → Security."],
        // Settings window
        "general": ["Umumiy", "Умумий", "Основные", "General"],
        "about": ["Ilova haqida", "Илова ҳақида", "О приложении", "About"],
        "server": ["Sayt manzili", "Сайт манзили", "Адрес сайта", "Site address"],
        "defaultServer": ["Standart manzil", "Стандарт манзил", "Адрес по умолчанию", "Default address"],
        "saveAndOpen": ["Saqlash va ochish", "Сақлаш ва очиш", "Сохранить и открыть", "Save and Open"],
        "serverHelp": ["Saytni boshqa serverga koʻchirsangiz, yangi manzilni shu yerga yozing — ilovani qayta oʻrnatish shart emas.",
                       "Сайтни бошқа серверга кўчирсангиз, янги манзилни шу ерга ёзинг — иловани қайта ўрнатиш шарт эмас.",
                       "Если сайт переедет на другой сервер, впишите сюда новый адрес — переустанавливать приложение не нужно.",
                       "If the site moves to another server, enter the new address here; no need to reinstall the app."],
        "launchAtLogin": ["Kompyuter yoqilganda ishga tushirish", "Компьютер ёқилганда ишга тушириш", "Запускать при входе в систему", "Open at login"],
        "keepRunning": ["Oyna yopilganda fonda ishlashda davom etish", "Ойна ёпилганда фонда ишлашда давом этиш", "Работать в фоне после закрытия окна", "Keep running when the window is closed"],
        "keepRunningHelp": ["Shunda eslatmalar oyna yopiq boʻlsa ham keladi.", "Шунда эслатмалар ойна ёпиқ бўлса ҳам келади.", "Тогда напоминания приходят и при закрытом окне.", "Reminders then arrive even with the window closed."],
        "menuBar": ["Menyu satrida qoʻngʻiroqcha", "Меню сатрида қўнғироқча", "Колокольчик в строке меню", "Bell in the menu bar"],
        "notify": ["Tugʻilgan kunlar va voqealar haqida xabar berish", "Туғилган кунлар ва воқеалар ҳақида хабар бериш", "Сообщать о днях рождения и событиях", "Tell me about birthdays and events"],
        "sound": ["Ovoz", "Овоз", "Звук", "Sound"],
        "soundChime": ["Silai Rahm qoʻngʻirogʻi", "Silai Rahm қўнғироғи", "Колокольчик Silai Rahm", "Silai Rahm chime"],
        "soundSystem": ["Tizim ovozi", "Тизим овози", "Системный звук", "System sound"],
        "soundNone": ["Ovozsiz", "Овозсиз", "Без звука", "Silent"],
        "test": ["Sinab koʻrish", "Синаб кўриш", "Проверить", "Try it"],
        "testTitle": ["Silai Rahm", "Silai Rahm", "Silai Rahm", "Silai Rahm"],
        "testBody": ["Bildirishnomalar ishlayapti 🎉", "Билдиришномалар ишлаяпти 🎉", "Уведомления работают 🎉", "Notifications work 🎉"],
        "notificationsOff": ["Bildirishnomalarga ruxsat berilmagan. Tizim sozlamalari → Bildirishnomalar → Silai Rahm boʻlimida yoqing.",
                             "Билдиришномаларга рухсат берилмаган. Тизим созламалари → Билдиришномалар → Шажара бўлимида ёқинг.",
                             "Уведомления запрещены. Включите их в Системных настройках → Уведомления → Шаджара.",
                             "Notifications are not allowed. Turn them on in System Settings → Notifications → Silai Rahm."],
        "openSystemSettings": ["Tizim sozlamalarini ochish", "Тизим созламаларини очиш", "Открыть Системные настройки", "Open System Settings"],
        "aboutText": ["Oilangiz shajarasi, eslatmalar va hayot tarixlari — Mac uchun.", "Оилангиз шажараси, эслатмалар ва ҳаёт тарихлари — Mac учун.", "Родословное древо, напоминания и истории жизни вашей семьи — для Mac.", "Your family tree, reminders and life stories — for Mac."],
        "version": ["Versiya", "Версия", "Версия", "Version"],
        "loginFailed": ["Kirish amalga oshmadi. Qaytadan urinib koʻring.", "Кириш амалга ошмади. Қайтадан уриниб кўринг.", "Не удалось войти. Попробуйте ещё раз.", "Signing in failed. Please try again."],
    ]

    static func t(_ key: String, _ lang: AppLanguage = Browser.shared.language) -> String {
        guard let row = table[key] else { return key }
        switch lang {
        case .uz: return row[0]
        case .uzCyrl: return row[1]
        case .ru: return row[2]
        case .en: return row[3]
        }
    }
}
