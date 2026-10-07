# Silai Rahm — Mac ilovasi

Saytni alohida, qulay Mac oynasida ochadi va unga Mac’ning oʻz imkoniyatlarini qoʻshadi:

- **Bitta yuza** — oyna ramkasi sahifa rangida (yorugʻ / qorongʻi mavzu sayt bilan birga almashadi), yuqorida faqat
  ixcham satr: orqaga / oldinga va yangilash. Menyu saytning oʻz yon panelida — takrorlanadigan tugmalar yoʻq;
- **Tizim bildirishnomalari** — tugʻilgan kunlar, yilliklar va voqealar haqida, **oʻz ovozi** bilan
  (Silai Rahm qoʻngʻirogʻi / tizim ovozi / ovozsiz); har 10 daqiqada va ilova ochilganda tekshiradi;
- **Menyu satridagi qoʻngʻiroqcha** — oʻqilmagan eslatmalar roʻyxati va tezkor havolalar;
- **Dock belgisi** — oʻqilmagan eslatmalar soni; Dock’da oʻng tugma — tezkor menyu;
- **Fonda ishlash** — oyna yopilsa ham eslatmalar keladi; **kompyuter yoqilganda ishga tushadi** (ixtiyoriy);
- **Sayt tilida** — menyular va sozlamalar saytda tanlangan tilga oʻzi oʻtadi (oʻzbek lotin / kirill, rus, ingliz);
- **Google orqali kirish** — Mac’ning xavfsiz kirish oynasida (Google ilova ichidagi sahifada kirishga ruxsat bermaydi);
- **Telegram** — «@bot ni ochish» tugmasi toʻgʻridan-toʻgʻri Telegram ilovasini ochadi;
- **Yuklab olish** — PDF (kitob, plakat), PNG, GEDCOM va JSON fayllar «Saqlash» oynasi orqali, keyin Finder’da koʻrsatiladi;
- **Chop etish** (⌘P), albomga surat, hujjat va ovozli yozuv tanlash, GEDCOM / JSON import, tasdiqlash oynalari;
  tashqi havolalar oddiy brauzerda ochiladi;
- Oxirgi ochilgan sahifa va masshtab eslab qolinadi;
- Tugmalar: ⌘1 Shajaram, ⌘2 Qarindoshlarim, ⌘3 Voqealar, ⌘4 Doʻstlarim, ⌘5 Vaqt chizigʻi,
  ⌘F yoki ⌘K Tezkor qidiruv (odamlar va sahifalar), ⌘N Qarindosh qoʻshish,
  ⇧⌘B Bildirishnomalar, ⌘R Yangilash, ⌘[ / ⌘] Orqaga / Oldinga, ⌘+ / ⌘− / ⌘0 Masshtab, ⌘, Sozlamalar;
- Internet boʻlmasa — «Qayta urinish» oynasi; tizimga bir marta kirasiz, keyingi safar eslab qoladi.

Telefondagi push-bildirishnomalar saytning oʻzida yoqiladi; Mac ilovasi eslatmalarni oʻzi koʻrsatadi, shuning uchun
ilova ichida «Shu qurilmada» boʻlimi koʻrinmaydi.

macOS 13 (Ventura) va yangilari, Apple Silicon va Intel. Hozirgi versiya: 1.2.

## Yigʻish va oʻrnatish

Xcode (yoki Command Line Tools) oʻrnatilgan boʻlishi kerak.

```bash
cd macos
./build.sh install
```

`build/SilaiRahm.app` yaratiladi va `/Applications` ga nusxalanadi. Launchpad yoki Spotlight’dan «Silai Rahm» deb oching.
Birinchi ochilishda bildirishnomalarga ruxsat soʻraladi — «Ruxsat berish» ni bosing.

Faqat yigʻish (oʻrnatmasdan): `./build.sh`.

## Sozlamalar (⌘,)

- **Umumiy** — sayt manzili (standart `https://silairahm.vercel.app`; saytni boshqa serverga yoki oʻz
  domeningizga koʻchirsangiz, yangi manzilni yozing — ilovani qayta yigʻish shart emas), kirishda ishga tushirish,
  fonda ishlash, menyu satridagi qoʻngʻiroqcha.
- **Bildirishnomalar** — yoqish / oʻchirish, ovozni tanlash, «Sinab koʻrish».
- **Ilova haqida** — versiya.

## Boshqa Mac’larga tarqatish va App Store

`build.sh` ilovani *ad-hoc* imzolaydi: u shu Mac’da ishlaydi. Boshqa kompyuterlarda macOS
«noaniq dasturchi» deb ogohlantiradi (Finder’da oʻng tugma → **Ochish** bilan ochiladi).

Ogohlantirishsiz tarqatish yoki App Store uchun:

1. [Apple Developer Program](https://developer.apple.com/programs/) aʼzoligi (yiliga 99 $).
2. Developer ID bilan imzolash va notarizatsiya:
   ```bash
   SIGN_IDENTITY="Developer ID Application: Ism Familiya (TEAMID)" ./build.sh
   ditto -c -k --keepParent build/SilaiRahm.app SilaiRahm.zip
   xcrun notarytool submit SilaiRahm.zip --apple-id EMAIL --team-id TEAMID --wait
   xcrun stapler staple build/SilaiRahm.app
   ```
3. App Store uchun Xcode’da yangi *macOS App* loyihasi oching, `SilaiRahm/*.swift`, `Info.plist`,
   `SilaiRahm.entitlements` va `Resources/AppIcon.icns` ni qoʻshing, *Signing & Capabilities* da jamoangizni
   tanlang va **Product → Archive → Distribute App → App Store Connect** qiling.

## Tuzilma

| Fayl | Vazifasi |
|---|---|
| `SilaiRahm/SilaiRahmApp.swift` | Ilova, oyna, menyular, menyu satri, Dock menyusi, oflayn oyna |
| `SilaiRahm/Browser.swift` | WebKit oynasi, navigatsiya, mavzu rangi, tezkor qidiruv, Google orqali kirish |
| `SilaiRahm/WebView.swift` | Yuklab olish, fayl tanlash, mikrofon/kamera ruxsati (ovozli va video hikoyalar), tasdiqlash oynalari, tashqi havolalar |
| `SilaiRahm/Notifier.swift` | Bildirishnomalar, ovoz va Dock belgisi (`/xabarlar/holat.json`) |
| `SilaiRahm/SettingsView.swift` | Sozlamalar oynasi |
| `SilaiRahm/L10n.swift` | Ilova matnlari toʻrt tilda |
| `make_sound.py` | Bildirishnoma ovozini yaratadi (`Resources/SilaiRahm.wav`) |
| `../tools/make_icons.py` | Sayt va ilova belgilarini yaratadi (`Resources/AppIcon.icns`) |
| `build.sh` | Universal (arm64 + x86_64) `SilaiRahm.app` yigʻadi va imzolaydi |

Google orqali kirish qanday ishlaydi: ilova `/ilova/kirish/boshlash/` sahifasini Mac’ning kirish oynasida ochadi →
Google’dan keyin sayt bir martalik, 2 daqiqa amal qiladigan kalit bilan `silairahm://kirish?token=…` ga qaytaradi →
ilova shu kalit bilan `/ilova/kirish/` orqali tizimga kiradi.
