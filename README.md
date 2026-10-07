# Silai Rahm — qarindoshlik rishtalarini asraydigan oilaviy shajara (Django)

*Silai rahm* — qarindoshlik aloqalarini uzmaslik. Sayt oilaning shajarasi, hayot tarixlari, voqea va xotiralarini bir joyda saqlaydi.

Asosiy til — **Oʻzbekcha (lotin)**; toʻliq tarjimalar: **Ўзбекча (kirill)**, **Русский** va **English**.
Hammasi Django’ning rasmiy i18n tizimi orqali ishlaydi (`gettext`, `.po` → `.mo`,
`LocaleMiddleware`, `JavaScriptCatalog`).

> Nima qayerda joylashgani: **[docs/TUZILMA.md](docs/TUZILMA.md)** · Serverga joylash: [docs/DEPLOY.md](docs/DEPLOY.md) ·
> Mac ilovasi: [macos/README.md](macos/README.md)

## Imkoniyatlar

- **Shajara daraxti** — bitta bogʻlangan chizma. Tarmoqlar rang bilan ajratilgan (oʻz oilasi, ota tomoni,
  ona tomoni), toʻgʻri ajdodlar chizigʻi zarhal; chapda avlod nomlari, burchakda kichik xarita;
  uzoqlashtirganda kartalar soddalashadi. Kartani bosganda yon panel ochiladi va qarindosh **shu yerning oʻzida**
  qoʻshiladi.
- **Roʻyxatdan oʻtish** — Google orqali (parolsiz) yoki email bilan: email bilan oʻtganda hisob faqat emailga
  yuborilgan 6 xonali kod kiritilgach ochiladi. Kirishdan oldin otasi, onasi va bobo-buvilari soʻraladi — shajara
  ulardan boshlanadi.
- **Jonli yangilanish** — yangi soʻrov, kuzatuvchi yoki qabul qilingan soʻrov sahifani yangilamasdan koʻrinadi
  (belgilar, xabar oynasi, «Doʻstlar» roʻyxati).
- **Shajarani oʻtkazish** — akangiz (yoki boshqa qarindosh) sizning shajarangizni oʻzinikiga bir bosishda oladi;
  u tuzib qoʻygan qismlar saqlanadi, farqlar oldindan koʻrsatiladi.
- **Birgalikda tuzish** — qarindoshni havola orqali taklif qilasiz (koʻrish yoki tahrirlash huquqi bilan);
  u shajarani oʻz oʻrnidan nomlangan holda koʻradi. **Oʻzgarishlar tarixi**: kim nimani qoʻshgani koʻrinadi,
  xato oʻzgarish yoki oʻchirish ortga qaytariladi.
- **Kuzatish va maxfiylik (Instagram kabi)** — hisob ochiq yoki yopiq; yopiq hisobda har bir kuzatuvchini egasi tasdiqlaydi.
  Shajarani va hikoyalarni (hayot tarixi, voqealar, albom) kim koʻrishini alohida tanlanadi: saytdagi hamma /
  kuzatuvchilar / faqat oila aʼzolari. Har bir hisobning sahifasi: kuzatish, «bu mening qarindoshim», shajarasini ochish.
- **Doʻstlar va bogʻlanishlar bitta boʻlimda** — odamlarni yozayotganda taklif qilinadigan qidiruv (Enter shart emas),
  «u menga kim» deb belgilab soʻrov yuborish; qabul qilinganda har biri boshqasining shajarasida joylashadi, shajaralar koʻrinadi, xohlasa doʻstlar
  roʻyxatiga qoʻshiladi. **Solishtirish va birlashtirish**: ikki shajaradagi bir xil odamlar topiladi, farqlar haqida
  ogohlantiriladi, yetishmayotgan qarindoshlar va maʼlumotlar bir bosishda qoʻshiladi (har biri «Tarix»da qaytariladi).
- **Dublikatlar** — qoʻshayotganda ogohlantirish, topilgan juftlarni birlashtirish (maʼlumot yoʻqolmaydi).
- **Albom** — har bir odamga suratlar, hujjatlar (PDF), ovozli yozuvlar va videolar; suratlar yuklashda kichraytiriladi.
- **Ovozli va video hikoyalar** — voqea, xotira va hayot tarixini yozish oʻrniga brauzerning oʻzida ovozli yoki video xabar
  qilib aytib berish mumkin (4 MB gacha: ~25 daqiqa ovoz yoki ~1 daqiqa video); yordamchi uni matnga ham aylantiradi.
- **AI yordamchi** (`/yordamchi/`, Google Gemini) — qarindoshlar va sayt haqidagi savollarga javob beradi, aytilgan hikoyani
  tahrirlab voqea sifatida, yangi qarindosh yoki maʼlumotni **taklif qiladi**; hech narsa «Qoʻshish» bosilmaguncha saqlanmaydi.
- **Hayot tarixi kitobdek** — odam sahifasida hayot tarixi, voqealar va xotiralar bitta hikoya boʻlib, sanalar boʻyicha;
  butun oila boʻyicha vaqt chizigʻi.
- **Qarindoshlik nomlari** avtomatik: aka/uka, opa/singil, amaki/amma/togʻa/xola, amakivachcha…,
  kelin/kuyov, qaynota/qaynona, yanga/pochcha, «Buvining ukasi», «Onaning xolavachchasi», «Togʻaning xotini».
- **Muchal** — har bir odamning muchali (yil Navroʻzda almashadi), keyingi muchal yili, Navroʻzda eslatma.
- **Voqealar va xotiralar** (eski «Hikoyalar» shu yerga qoʻshilgan) — toʻy, fotiha, farzand tugʻilishi, beshik toʻyi,
  sunnat toʻyi, aqiqa, tugʻilgan kun, hayit, yangi yil, haj yoki umra, yubiley, vafot, «xotira yoki boshqa voqea»;
  har biri hikoyadek yoziladi va oʻqiladi; kelajakdagi sanalar.
- **Nikoh** — ayolda bir vaqtda bitta nikoh, erkakda bir nechta; nikohni «ajrashgan» deb belgilash mumkin.
- **Doʻstlar** — istalgan kishining (oʻzingiz, dadangiz, buvingiz…) doʻstlari, tugʻilgan kunlari bilan.
- **Eslatmalar** — tugʻilgan kunlar, nikoh yilliklari, xotira kunlari, voqealar, muchal yili: saytda,
  **Telegram bot** orqali va **telefonga push-bildirishnoma** qilib (sayt bosh ekranga qoʻshilganda).
  Bosh sahifadagi «Bugun» blokidan bir bosishda tabrik yuboriladi.
- **Kim kimga kim?** — ikki odam orasidagi qarindoshlik va bogʻlanish zanjiri.
- **Familiya taklifi** — oʻgʻil nevaraga ota tarafdagi bobosining ismidan (Madaminjon → Madaminov).
- **Chop etish** — muqovali **shajara kitobi** (butun oila, ota yoki ona tomoni, voqea va xotiralari bilan; sarlavhasi
  sozlamalardagi «Oila nomi»dan), bitta odam uchun
  **«Hayot kitobi»**, **devoriy plakat** (balandligi 42 yoki 59 sm, uzunligi oilaga qarab),
  tarjimai hol va daraxt PDF; PNG.
- **GEDCOM** — eksport va **import** (MyHeritage, Ancestry, Gramps va boshqalardan).
- **Xavfsizlik** — ikki bosqichli kirish (autentifikator ilovasi + tiklash kodlari), Google orqali kirish,
  boshqa qurilmalardan chiqish, notoʻgʻri parolda vaqtincha toʻxtatish.
- **Zaxira** — har hafta butun baza bitta fayl boʻlib administratorning Telegramiga yuboriladi; qoʻlda ham yuklab olinadi.
- **Dizayn** — «nil va zar» (toʻq koʻk + zarhal, ikat naqshi), Source Serif 4 + Inter, yorugʻ / qorongʻi / tizim
  mavzusi, chap yon menyu (yigʻiladi), telefonda pastki menyu, **⌘K / Ctrl+K** tezkor qidiruv, toʻrt til.
- **Boshqaruv paneli** (`/boshqaruv/`) — holat, foydalanuvchilar, zaxira.
- **Mac ilovasi** — [macos/](macos/README.md): alohida oyna, tizim bildirishnomalari, Dock belgisi.

Sayt: **https://silairahm.vercel.app** (eski manzil ham ishlaydi: https://shajara-liard.vercel.app) · Serverga joylash va koʻchirish: [docs/DEPLOY.md](docs/DEPLOY.md).

## Ishga tushirish

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py compilemessages --ignore=.venv
.venv/bin/python manage.py seed_demo        # namuna oila (ixtiyoriy)
.venv/bin/python manage.py runserver
.venv/bin/python manage.py run_worker      # eslatmalar va Telegram (alohida oynada, ixtiyoriy)
```

`seed_demo` uchta sinov foydalanuvchisini yaratadi: `namuna` (lotin), `dilnoza_a` (kirill, shajarani koʻra oladi)
va `anvar_y` (unga taklif havolasi tayyorlangan). Parol `apps/genealogy/management/commands/seed_demo.py` faylida
yozilgan va faqat lokal ishlab chiqish uchun moʻljallangan.

PostgreSQL uchun `DATABASE_URL=postgres://…` oʻzgaruvchisini bering (qarang: `.env.example`).
Oʻzgaruvchi berilmasa, SQLite ishlatiladi. Rasmlar ham bazada saqlanadi (`apps/core/storage.py`),
shuning uchun bazaning zaxira nusxasi hamma narsani oʻz ichiga oladi.

## Tuzilma

Toʻliq xarita — [docs/TUZILMA.md](docs/TUZILMA.md) («X ni qayerdan topaman?»). Qisqacha:

| Papka | Ichida |
|---|---|
| `config/` | Sozlamalar, bosh manzillar, sana formatlari |
| `apps/genealogy/` | Shajara: odamlar, daraxt, albom, tarix, voqea va xotiralar, ovozli/video yozuvlar, PDF, GEDCOM (`views/` — mavzu boʻyicha) |
| `apps/accounts/` | Hisob, kirish, ikki bosqichli kirish, oila aʼzolari va taklif havolalari |
| `apps/notify/` | Eslatmalar: Telegram, push, cron, haftalik zaxira |
| `apps/core/` | Bosh sahifa, boshqaruv paneli, tillar, sanalar, fayl saqlash |
| `apps/friends/` | Doʻstlar (bogʻlanishlar va kuzatishlar bilan bitta sahifada) |
| `apps/network/` | Saytdagi boshqa hisoblar: kuzatish, profil, bogʻlanish, shajaralarni solishtirish va birlashtirish |
| `apps/assistant/` | AI yordamchi: Gemini mijozi, oila konteksti, taklif → tasdiq → saqlash, ovozni matnga aylantirish |
| `templates/` | Sahifalar — kod bilan bir xil mavzu papkalarida |
| `static/` | `css/app.css` (dizayn tizimi), `js/app.js`, `js/tree.js`, `js/assistant.js`, belgilar |
| `locale/` | Tarjimalar: `uz`, `uz_Cyrl`, `ru`, `en` |
| `fonts/` | DejaVu Sans — PDF ichiga joylanadi (Ў Қ Ғ Ҳ va ʻ ʼ belgilari bor) |
| `tests/` | Testlar, mavzu boʻyicha |
| `tools/` | Til auditi, belgilarni yaratish |
| `macos/` | Mac ilovasi (SwiftUI + WebKit) |
| `docs/` | Loyiha xaritasi va serverga joylash qoʻllanmasi |
| `archive/prototype/` | Eski bir faylli prototip (qarindoshlik mantigʻi va lotin↔kirill qidiruvi oʻsha yerdan koʻchirilgan) |

## Til tizimi

* **Tanlash:** foydalanuvchi menyusi (yon menyu pastida), mehmonlar uchun yuqoridagi globus, hamda *Sozlamalar → Til*.
* **Saqlash:** tizimga kirgan foydalanuvchi uchun `User.preferred_language` (`uz`, `uz-cyrl`, `ru`, `en`)
  maydoniga yoziladi va har safar tizimga kirganda qoʻllanadi. Mehmonlar uchun `til` cookie,
  keyin brauzer tili (faqat oʻzbek lotin/kirill), keyin standart holatda lotin yozuvi ishlatiladi. Rus va ingliz tillari
  faqat foydalanuvchi oʻzi tanlaganda yoqiladi: sayt avval oʻzbek tilida ochiladi.
* **Rus tili grammatikasi:** koʻplik uch shaklda (1 год, 2 года, 5 лет), sanada oy qaratqich kelishigida
  (27 сентября), qarindoshlik zanjiri ham («Младший брат бабушки») — `terminology.KIN_OF`.
* **URL:** til prefikssiz (`/uz-cyrl/…` yoʻq): til cookie va akkaunt orqali saqlanadi, havolalar ikkala tilda bir xil.
* **Kirill katalogi:** Django’da `uz_Cyrl` katalogi yoʻq, shuning uchun foydalanuvchi koʻradigan barcha Django
  xabarlari `locale/uz_Cyrl` ichida qayta tarjima qilingan. Lotin katalogida ham Django xabarlari qayta
  yozilgan, chunki Django’ning oʻz tarjimasida apostroflar aralash (o', o‘, oʻ).
* **Apostroflar:** interfeysda `Oʻ oʻ Gʻ gʻ` uchun U+02BB, tutuq belgisi `ʼ` uchun U+02BC ishlatiladi. Ism va joy
  maydonlarida foydalanuvchi yozgan `'`, `‘`, `’`, `` ` `` shu belgilarga keltiriladi; harflar oʻzgarmaydi.
* **Foydalanuvchi maʼlumotlari:** ism, familiya, hikoyalar qanday yozilgan boʻlsa, shunday saqlanadi.
  Transliteratsiya qilinmaydi. Qidiruv uchun alohida `search_key` maydoni bor, shuning uchun
  *Alisher* ↔ *Алишер*, *Jamshid Qodirov* ↔ *Джамшид Кадыров* bir-birini topadi.
* **PDF** foydalanuvchi tanlagan tilda chiqadi, fayl nomi ham (`shajara.pdf` / `шажара.pdf`).

### Yangi matn qoʻshilganda

```bash
.venv/bin/python manage.py makemessages -l uz -l uz_Cyrl -l ru -l en --ignore=.venv --ignore=archive --ignore=files --ignore=macos --no-obsolete
.venv/bin/python manage.py makemessages -d djangojs -l uz -l uz_Cyrl -l ru -l en --ignore=.venv --ignore=archive --ignore=files --ignore=macos --ignore=staticfiles
# locale/uz/… va locale/uz_Cyrl/… dagi .po fayllarni tarjima qiling (fuzzy belgisini olib tashlang)
.venv/bin/python manage.py compilemessages --ignore=.venv
.venv/bin/python tools/i18n_audit.py
```

Manba matnlar (msgid) inglizcha — bu Django’ning odatiy yondashuvi. Foydalanuvchi ularni hech qachon koʻrmaydi:
audit va testlar tarjima qilinmagan satr qolmaganini tekshiradi.

## Til sifati nazorati

`tools/i18n_audit.py` (test ichida ham ishlaydi) quyidagilarni tekshiradi:

1. Har bir katalogda har bir satr tarjima qilingan (ingliz tilida manba matn ishlatilishi mumkin), `fuzzy` yoʻq,
   oʻrin toʻldiruvchilar mos keladi, rus koʻpligi uch shaklda, rus katalogida oʻzbekcha harflar (ў қ ғ ҳ) yoʻq.
2. Lotin katalogida kirill harfi va notoʻgʻri apostrof (`o'`, `o‘`, `g’` …) yoʻq.
3. Kirill katalogida lotin harfi yoʻq (istisnolar: PDF, PNG, MB va qidiruvdagi «Alisher» misoli).
4. Shablonlarda `{% translate %}` dan tashqarida matn qolmagan.
5. JavaScript’dagi jumlalar `gettext()` orqali oʻtadi.
6. Python’dagi `messages.*`, `ValidationError`, `add_error`, `Http404` va `PermissionDenied` chaqiruvlari tarjimasiz qoldirilmagan.

`tests/test_i18n.py` har bir sahifani toʻrt tilda ochadi va quyidagilarni tekshiradi: kirill sahifada lotin
matni, lotin sahifada kirill matni, oʻzbek va rus sahifalarida inglizcha manba matn, rus sahifasida oʻzbekcha harf yoʻq. Tekshiruvga validatsiya xatolari, 404/403 sahifalari,
JS katalogi, shajara JSON va PDF fayl nomlari ham kiradi.

```bash
.venv/bin/python manage.py test
```

## Maʼlum cheklovlar

* Django admin (`/admin/`) oddiy foydalanuvchi uchun emas. Oʻzbek kirill rejimida u Django’ning lotincha tarjimasida qoladi.
* Veb shriftlar (Source Serif 4, Inter) Google Fonts’dan yuklanadi; ikkalasida ham Ў Қ Ғ Ҳ va ʻ ʼ bor.
  Internet boʻlmasa, tizim shrifti ishlatiladi.
* Push-bildirishnomalar iPhone/iPad’da faqat sayt bosh ekranga qoʻshilgandan keyin ishlaydi (iOS 16.4+).
* Umumiy shajarada har bir hisobning oʻz arxivi saqlanadi; ikki alohida arxivni bittaga qoʻshish uchun
  GEDCOM yoki JSON import va dublikatlarni birlashtirish ishlatiladi.
* Qarindoshlik nomlari qon qarindoshlik, nikoh, kelin/kuyov, qaynota/qaynona, yanga/pochcha va oʻgay
  qarindoshlarni qamraydi. Uzoqroq qarindoshlar «Qarindosh» deb koʻrsatiladi.
