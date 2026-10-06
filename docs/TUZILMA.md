# Loyiha xaritasi — nima qayerda

Bu hujjat bitta savolga javob beradi: **«X ni qayerdan topaman?»**
Har bir mavzu hamma joyda bir xil nom bilan ataladi: sahifa kodi `views/people.py` da boʻlsa, uning
shablonlari `templates/genealogy/people/` da, testlari `tests/test_people.py` da turadi.

## 1. Papkalar

```
family/
├── README.md              loyiha haqida, ishga tushirish, til tizimi
├── manage.py              Django buyruqlari
├── requirements.txt       Python kutubxonalari (versiyalari bilan)
├── vercel.json            Vercel: migratsiya, 24 ta cron, hudud
├── Dockerfile, docker-compose.yml, deploy/Caddyfile     oʻz serveringiz uchun (muqobil)
│
├── config/                sozlamalar: settings.py, urls.py (bosh manzillar), wsgi.py, sana formatlari
├── apps/                  saytning butun kodi — 6 ta ilova (2-boʻlim)
├── templates/             HTML sahifalar (3-boʻlim)
├── static/                css/app.css · js/app.js, js/tree.js · img/ (belgilar) · manifest
├── locale/                tarjimalar: uz, uz_Cyrl, ru, en (django.po, djangojs.po)
├── fonts/                 DejaVu Sans — PDF ichiga joylanadigan shrift
│
├── tests/                 testlar, mavzu boʻyicha (4-boʻlim)
├── tools/                 yordamchi skriptlar: i18n_audit.py (til auditi), make_icons.py (belgilar)
├── macos/                 Mac ilovasi (SwiftUI) — oʻz README’si bor
├── docs/                  hujjatlar: TUZILMA.md (shu fayl), DEPLOY.md (serverga joylash)
└── archive/prototype/     eski bir faylli prototip (ishlatilmaydi, tarix uchun)
```

Faqat sizning kompyuteringizda boʻladigan, gitga kirmaydigan narsalar: `.venv/` (Python muhiti),
`db.sqlite3` (lokal baza), `.env`, `.env.local`, `.vercel/`, `macos/build/`.

## 2. `apps/` — kod

### `apps/genealogy/` — shajara (asosiy qism)

| Fayl | Vazifasi |
|---|---|
| `models.py` | Jadvallar: `Person`, `Marriage`, `Story`, `Event`, `Media` (albom), `Change` (tarix) |
| `urls.py` | Manzillar, mavzu boʻyicha guruhlangan |
| `forms.py` | Formalar va tekshiruvlar (sana, ota-ona, dublikat ogohlantirishi) |
| `access.py` | Kim koʻra oladi / tahrirlay oladi |
| `kinship.py` | Qarindoshlikni hisoblash (aka, amma, kelin…), avlodlar, tarmoqlar |
| `terminology.py` | **Qarindoshlik atamalari lugʻati** — yagona manba |
| `tree.py` | Shajara chizmasining joylashuvi (sayt va PDF uchun umumiy) |
| `pdf.py` | PDF: tarjimai hol, daraxt, devoriy plakat, muqovali kitob |
| `history.py` | Oʻzgarishlarni yozish va ortga qaytarish |
| `duplicates.py` | Dublikatlarni topish va birlashtirish |
| `gedcom.py` | GEDCOM eksport va import |
| `archive_io.py` | Arxivni JSON faylga chiqarish va qayta yuklash |
| `management/commands/` | `seed_demo` (namuna oila), `import_archive` (JSON’dan tiklash) |

Sahifalar — `views/` papkasida, har bir mavzu alohida faylda:

| `views/…` | Sahifalar | Shablonlar (`templates/genealogy/…`) |
|---|---|---|
| `people.py` | Qarindoshlar roʻyxati, odam sahifasi, qoʻshish / tahrirlash / oʻchirish, nikoh, «bu men» | `people/` |
| `album.py` | Albom: surat, hujjat, ovozli yozuv yuklash va oʻchirish | `people/detail.html` ichida |
| `changes.py` | Dublikatlar, birlashtirish, oʻzgarishlar tarixi, ortga qaytarish | `changes/` |
| `tree.py` | Shajara sahifasi, maʼlumotlari (daraxt, yelpigʻich), yon panel, tezkor qoʻshish, PDF, kitob | `tree.html` |
| `timeline.py` | Vaqt chizigʻi | `timeline.html` |
| `events.py` | Oilaviy voqealar, yaqinlashayotgan sanalar | `events/` |
| `stories.py` | Hikoyalar | `stories/` |
| `search.py` | Qidiruv sahifasi va tezkor qidiruv (⌘K, tanlagichlar) | `search/` |
| `calculator.py` | «Kim kimga kim?» | `calculator.html` |
| `exchange.py` | GEDCOM va JSON eksport / import | — |
| `_common.py` | Bir nechta sahifa ishlatadigan yordamchilar | — |

### `apps/accounts/` — hisob, kirish, oila aʼzolari

| Fayl | Vazifasi |
|---|---|
| `models.py` | `User` (til, vaqt mintaqasi, 2 bosqich), `Membership` (aʼzolik), `Invite` (taklif havolasi) |
| `forms.py` | Roʻyxatdan oʻtish, kirish (cheklov bilan), sozlamalar, taklif formalari |
| `sharing.py` | Umumiy shajara qoidalari: huquqlar, taklifni qabul qilish, arxivlar orasida almashish |
| `totp.py` | Ikki bosqichli kirish: kodlar va tiklash kodlari |
| `middleware.py` | Qaysi arxivda ishlanayotgani (`request.archive`), profilni toʻldirish talabi |
| `adapters.py`, `app_bridge.py` | Google orqali kirish; Mac ilovasi uchun kirish koʻprigi |

| `views/…` | Sahifalar | Shablonlar (`templates/accounts/…`) |
|---|---|---|
| `auth.py` | Roʻyxatdan oʻtish, kirish, ikkinchi bosqich kodi, parolni tiklash | `auth/` |
| `profile.py` | Sozlamalar → Umumiy, Maʼlumotlaringiz, hisobni oʻchirish | `settings/general.html`, `data.html`, `delete_account.html` |
| `security.py` | Sozlamalar → Xavfsizlik: parol, ikki bosqich, qurilmalar, Google | `settings/security.html`, `two_factor_*.html` |
| `family.py` | Sozlamalar → Oila aʼzolari, taklif havolasi, «shajarada men kimman» | `settings/family.html`, `invite/` |

### `apps/notify/` — eslatmalar

| Fayl | Vazifasi |
|---|---|
| `occasions.py` | Qaysi sanalar eslatiladi (tugʻilgan kun, yillik, xotira kuni, voqea, muchal) |
| `messages.py` | Eslatma matnlari (oʻquvchining tilida) |
| `service.py` | Eslatmalarni yaratish va yuborish, haftalik zaxira |
| `telegram.py` | Telegram bot: ulash kodi, buyruqlar, webhook |
| `push.py` | Telefon va brauzerga push-bildirishnoma |
| `views.py` | Bildirishnomalar roʻyxati, Eslatma sozlamalari, cron (`/cron/kunlik/`), webhook |
| `management/commands/` | `run_worker` (Docker uchun), `telegram_webhook` |

### `apps/core/` — umumiy narsalar

| Fayl | Vazifasi |
|---|---|
| `views.py` | Bosh sahifa (mehmon / «Bugun»), Boshqaruv paneli, zaxira, surat berish, xato sahifalari |
| `languages.py`, `middleware.py` | Tillar va foydalanuvchi tilini yoqish |
| `dates.py`, `text.py`, `timezones.py` | Sanalar, apostrof va lotin↔kirill qidiruv kaliti, vaqt mintaqalari |
| `muchal.py` | Muchal yillari |
| `storage.py`, `images.py` | Fayllarni bazada saqlash, suratlarni kichraytirish |
| `backup.py` | Toʻliq zaxira nusxa |
| `django_messages.py` | Django’ning oʻz xabarlari (qayta tarjima uchun) |
| `templatetags/uz.py` | Shablonlardagi yordamchi teglar |

### `apps/network/` — bogʻlanishlar va shajaralarni birlashtirish

| Fayl | Vazifasi |
|---|---|
| `models.py` | `Connection` (ikki hisob orasidagi soʻrov/bogʻlanish), `PersonMatch` («bu oʻsha odam») |
| `services.py` | Saytdan odam qidirish, soʻrov yuborish, qabul qilish, rad etish, bogʻlanishni tugatish |
| `merge.py` | Ikki shajarani solishtirish (mos odamlar, yetishmayotgan qarindoshlar, toʻldiriladigan maʼlumotlar, farqlar) va birlashtirish |
| `views.py`, `forms.py` | «Bogʻlanishlar» sahifalari; shablonlari `templates/network/` |

### `apps/friends/` — doʻstlar

`models.py` (`Contact`), `views.py`, `forms.py`; shablonlari `templates/friends/`.

## 3. `templates/` — sahifalar

```
templates/
├── base.html            umumiy qolip: yon menyu, telefon menyusi, ⌘K qidiruv
├── partials/            qayta ishlatiladigan boʻlaklar: icon.html (barcha ikonkalar), avatar,
│                        person_card, mini_person, field, date_fields, person_picker, logo.svg …
├── core/                landing (mehmon), dashboard (bosh sahifa), control_panel (boshqaruv)
├── genealogy/
│   ├── people/          list, _grid, detail, form, _fields, relative_form, marriage_form
│   ├── changes/         duplicates, _duplicates_notice, history
│   ├── events/          list, detail, form
│   ├── stories/         list, detail, form
│   ├── search/          page, _results
│   └── tree.html · timeline.html · calculator.html · confirm_delete.html
├── accounts/
│   ├── auth/            login, register, two_factor, password_reset*, complete_profile
│   ├── settings/        base (yon yorliqlar), general, security, data, family, two_factor_*, delete_account
│   └── invite/          invite (taklif sahifasi), who_am_i
├── notify/              list (bildirishnomalar), settings (eslatmalar, Telegram, push)
├── friends/             list, contact_form
├── errors/              400, 403, 403_csrf, 404, 500
├── pwa/                 sw.js (service worker), offline.html
├── registration/        parolni tiklash xati matni
└── account/, socialaccount/     Google orqali kirish sahifalari (nomlari kutubxona talabi)
```

Nomi `_` bilan boshlanadigan shablon — sahifa emas, boshqa sahifa ichiga qoʻyiladigan boʻlak.

## 4. `tests/` — testlar

| Fayl | Nimani tekshiradi |
|---|---|
| `test_kinship.py` | Qarindoshlik nomlari, shajara joylashuvi, muchal, familiya taklifi, sanalar, matn |
| `test_people.py` | Qidiruv, forma tekshiruvlari, dublikatlar, albom, tarix va ortga qaytarish |
| `test_pages.py` | Sahifalar: shajara maʼlumotlari, vaqt chizigʻi, bosh sahifa, voqealar, doʻstlar, PDF, admin |
| `test_sharing.py` | Kim koʻradi va tahrirlaydi: begona, koʻruvchi, tahrirchi, taklif havolasi |
| `test_accounts.py` | Kirish, cheklov, Google, Mac ilovasi koʻprigi, ikki bosqichli kirish |
| `test_reminders.py` | Eslatmalar, Telegram, push, cron, haftalik zaxira |
| `test_import_export.py` | GEDCOM import va eksport |
| `test_network.py` | Saytdan qidirish, bogʻlanish, shajaralarni birlashtirish, kitoblar, kichik suratlar |
| `test_crawl.py` | Har bir sahifani har xil foydalanuvchi nomidan ochib chiqadi: server xatosi boʻlmasligi kerak |
| `test_code.py` | Ishlatilmagan import va aniqlanmagan nomlar yoʻqligi |
| `test_i18n.py` | Har bir sahifa toʻrt tilda toza ekani, til tanlash, kataloglar |
| `helpers.py` | Testlar uchun namuna oila |

Hammasini ishga tushirish: `.venv/bin/python manage.py test` · bittasini: `… test tests.test_people`.

## 5. «Men … ni oʻzgartirmoqchiman»

| Nimani | Qayerda |
|---|---|
| Sahifadagi matn yoki tarjima | `locale/<til>/LC_MESSAGES/django.po` (JS matnlari — `djangojs.po`), keyin `compilemessages` |
| Ranglar, shrift, radiuslar | `static/css/app.css`, 1-boʻlim (Tokens). Fayl boshida mundarija bor |
| Yon menyu, telefon menyusi | `templates/base.html` |
| Ikonka qoʻshish | `templates/partials/icon.html` |
| Logotip va ilova belgilari | `tools/make_icons.py` (hammasini qayta yaratadi) |
| Qarindoshlik nomi (masalan «pochcha») | `apps/genealogy/terminology.py`; mantigʻi — `kinship.py` |
| Shajara chizmasi koʻrinishi | joylashuv — `apps/genealogy/tree.py`; chizish, masshtab, yon panel — `static/js/tree.js` |
| PDF kitob (butun oila / ota yoki ona tomoni / bitta odamning «Hayot kitobi»), plakat | `apps/genealogy/pdf.py`; tanlash sahifasi `views/tree.py` (`book_page`) |
| Shajaralarni solishtirish va birlashtirish qoidalari | `apps/network/merge.py` |
| Jinsni ismdan taxmin qilish | `apps/core/names.py` |
| Odam sahifasi | `apps/genealogy/views/people.py` + `templates/genealogy/people/detail.html` |
| Bosh sahifa («Bugun», yaqin sanalar) | `apps/core/views.py` (`home`) + `templates/core/dashboard.html` |
| Eslatma matni | `apps/notify/messages.py` |
| Qaysi sanalar eslatilishi | `apps/notify/occasions.py` |
| Telegram bot javoblari | `apps/notify/telegram.py` |
| Eslatma yuboriladigan vaqt | `vercel.json` (cron) va `apps/notify/service.py` |
| Taklif havolasi muddati, huquqlar | `apps/accounts/models.py` (`Invite.VALID_DAYS`), `sharing.py` |
| Kirish cheklovi (10 marta / 15 daqiqa) | `apps/accounts/forms.py` (`LoginForm`) |
| Fayl hajmi chegaralari | `config/settings.py` (`PHOTO_MAX_BYTES`), `apps/genealogy/views/album.py` |
| Muhit oʻzgaruvchilari, serverga joylash | [DEPLOY.md](DEPLOY.md) |
| Mac ilovasi | `macos/Shajara/*.swift`, yigʻish: `macos/build.sh install` |

## 6. Yangi narsa qoʻshganda

1. **Sahifa**: funksiyani mavzusiga mos `views/<mavzu>.py` ga yozing, `views/__init__.py` ga qoʻshing,
   manzilni `urls.py` dagi oʻsha mavzu guruhiga, shablonni oʻsha nomdagi papkaga qoʻying.
2. **Matn**: faqat `{% translate %}` / `gettext` orqali; keyin toʻrt tilda tarjima va
   `tools/i18n_audit.py` (README → «Yangi matn qoʻshilganda»).
3. **Test**: mavzusiga mos `tests/test_<mavzu>.py` ga.
4. **Jadval oʻzgarsa**: `manage.py makemigrations` — migratsiya fayli oʻsha ilovaning `migrations/` papkasiga tushadi.
