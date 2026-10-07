# Saytni internetga joylash

Hozirgi ishlab turgan manzil: **https://silairahm.vercel.app** (eski https://shajara-liard.vercel.app ham shu loyihaga ulangan) (Vercel + Neon PostgreSQL, Frankfurt).
GitHub’dagi `main` tarmogʻiga har bir `git push` saytni avtomatik yangilaydi.

Barcha maʼlumotlar — odamlar, voqealar, doʻstlar, eslatmalar **va rasmlar** — bitta PostgreSQL
bazasida saqlanadi. Shuning uchun boshqa serverga koʻchish = bazani koʻchirish (quyida, 3-boʻlim).

---

## 1. Vercel (hozirgi usul)

| Qism | Qayerda |
|---|---|
| Sayt (Django) | Vercel Python funksiyasi (`config/wsgi.py`), hudud `fra1` |
| Baza | Neon PostgreSQL (Vercel Marketplace orqali ulangan, `DATABASE_URL`) |
| Rasmlar | Bazaning `core_storedfile` jadvalida (`apps/core/storage.py`) |
| Eslatmalar | Vercel Cron → `/cron/kunlik/` **har soatda** (24 ta kunlik yozuv — bepul rejimda shunday qilinadi); har kimga oʻzi tanlagan soatda, oʻz vaqt mintaqasida yuboriladi — Telegramga va push qilib |
| Haftalik zaxira | Oʻsha cron: administratorning Telegramiga butun baza bitta fayl boʻlib boradi (`/boshqaruv/` da yoqiladi) |
| Telegram bot | Webhook → `/telegram/webhook/` (uzilib qolsa, cron har soatda oʻzi tiklaydi) |
| Migratsiyalar | Har bir deploy’da avtomatik (`vercel.json` → `buildCommand`) |

### Muhit oʻzgaruvchilari (Vercel → Project → Settings → Environment Variables)

| Nom | Majburiy | Izoh |
|---|---|---|
| `DATABASE_URL`, `DATABASE_URL_UNPOOLED` | ha | Neon integratsiyasi oʻzi qoʻshadi |
| `DJANGO_SECRET_KEY` | ha | uzun tasodifiy qator |
| `CRON_SECRET` | ha | Vercel Cron shu kalit bilan keladi |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google orqali kirish uchun | quyida |
| `TELEGRAM_BOT_TOKEN` | Telegram eslatmalari uchun | quyida. Bot nomi tokenning oʻzidan olinadi; `TELEGRAM_BOT_USERNAME` shart emas |
| `GEMINI_API_KEY` | AI yordamchi va ovozni matnga aylantirish uchun | quyida. `GEMINI_MODEL` shart emas (standart `gemini-flash-latest` — har doim eng yangi Flash; u yopilsa yoki band boʻlsa, sayt zaxira modelga oʻtadi) |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | push-bildirishnomalar uchun | quyida. `VAPID_SUBJECT` shart emas (sayt manzili olinadi) |
| `EMAIL_*`, `DJANGO_EMAIL_BACKEND` | parolni tiklash xatlari uchun | `.env.example` ga qarang |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | faqat oʻz domeningiz boʻlsa | `*.vercel.app` manzillari avtomatik qoʻshiladi |

Oʻzgaruvchi qoʻshilgach, **Deployments → Redeploy** qiling.

### AI yordamchi (Google Gemini, bepul)

1. https://aistudio.google.com/apikey → Google hisobingiz bilan kiring → **Create API key**.
2. Kalitni Vercel’ga `GEMINI_API_KEY` qilib yozing (Production) → **Redeploy**. Kalitni hech kimga yubormang.
3. Bepul tarifda daqiqasiga va kuniga soʻrovlar soni cheklangan; sayt har foydalanuvchiga soatiga 40 ta soʻrov beradi.
   Bepul tarifda Google yuborilgan matnlardan oʻz mahsulotlarini yaxshilash uchun foydalanishi mumkin — yordamchi
   sahifasida bu haqda yozilgan. Toʻlovli tarifga (Billing) oʻtsangiz, bu ishlatilmaydi.
4. Model: `GEMINI_MODEL` (standart `gemini-flash-latest` — tez va bepul). Google eski versiyalarni yopadi (masalan, `gemini-2.5-flash` 2026-yilda yangi foydalanuvchilarga yopildi).

### Google orqali kirish

1. https://console.cloud.google.com → yangi loyiha → **APIs & Services → OAuth consent screen**
   (External, ilova nomi «Silai Rahm», email).
2. **Credentials → Create credentials → OAuth client ID → Web application**.
3. *Authorized redirect URIs*: `https://silairahm.vercel.app/accounts/google/login/callback/` va eskisi
   `https://shajara-liard.vercel.app/accounts/google/login/callback/` (ikkalasi ham boʻlsin)
   (oʻz domeningiz boʻlsa, uni ham qoʻshing).
4. Berilgan *Client ID* va *Client secret* ni Vercel’ga `GOOGLE_CLIENT_ID` va `GOOGLE_CLIENT_SECRET` qilib yozing → Redeploy.

Kirish sahifasida «Google orqali davom etish» tugmasi paydo boʻladi. Google’dagi email mavjud akkaunt
emailiga mos kelsa, oʻsha akkauntga ulanadi; aks holda yangi akkaunt ochiladi va profilni toʻldirish soʻraladi.

### Telegram bot

1. Telegramda [@BotFather](https://t.me/BotFather) → `/newbot` → nom va foydalanuvchi nomi.
2. Tokenni Vercel’ga `TELEGRAM_BOT_TOKEN` qilib yozing → Redeploy.
3. Saytda **Boshqaruv paneli** (`/boshqaruv/`) → **«Botni saytga ulash»** tugmasi (bosmasangiz ham, bir soat ichida cron oʻzi ulaydi).
   Panelda botning haqiqiy nomi (`@…`) va webhook holati koʻrinadi.
4. Foydalanuvchilar **Sozlamalar → Eslatmalar** sahifasida ulanadi: «@bot ni ochish» tugmasi Telegram **ilovasini** ochadi
   (brauzerdagi Telegram Web emas), telefonda QR-kod, yoki botga sahifadagi 8 belgili kodni yozib yuborish.
   Sahifa ulanganini oʻzi sezadi; «Sinov xabarini yuborish» tugmasi bilan tekshiriladi.
5. Botdagi buyruqlar: `/next` — yaqin sanalar, `/stop` — oʻchirish, `/start` — qayta yoqish.

### Push-bildirishnomalar (telefon va brauzer)

Kalit juftligi bir marta yaratiladi va Vercel’ga yoziladi (hozirgi saytda allaqachon qoʻshilgan):

```bash
.venv/bin/python - <<'PY'
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
key = ec.generate_private_key(ec.SECP256R1())
print("VAPID_PRIVATE_KEY=" + b64(key.private_numbers().private_value.to_bytes(32, "big")))
print("VAPID_PUBLIC_KEY=" + b64(key.public_key().public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))
PY
```

Foydalanuvchi **Sozlamalar → Eslatmalar → Shu qurilmada → Yoqish** ni bosadi. iPhone/iPad’da avval saytni
bosh ekranga qoʻshish kerak (Ulashish → Bosh ekranga qoʻshish). Kalitlarni almashtirsangiz, hamma qayta yoqishi kerak boʻladi.

### Haftalik zaxira nusxa

`/boshqaruv/` → **Avtomatik zaxira nusxa** → «har hafta» ni yoqing (avval Telegramni ulang). Har 7 kunda butun baza
(suratlar bilan, siqilgan `.json.gz`) Telegramingizga keladi; «Hozir yuborish» bilan darhol ham olinadi.
Telegram botlar 50 MB gacha fayl yubora oladi — baza bundan oshsa, xabar keladi va nusxa paneldan yuklab olinadi.
Tiklash: `gunzip shajara-….json.gz && python manage.py loaddata shajara-….json`.

### Oʻz domeningiz

Vercel → Project → **Domains** → domenni qoʻshing va koʻrsatilgan DNS yozuvlarini registratorda kiriting.
Keyin `DJANGO_ALLOWED_HOSTS=shajara.uz`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://shajara.uz` va `SITE_URL=https://shajara.uz` qoʻshing,
Google’dagi redirect URI’ni yangilang va Telegram webhookni qayta oʻrnating. Push-bildirishnomalar domenga bogʻlangan:
yangi manzilda har kim ularni qayta yoqadi; Mac ilovasida *Sozlamalar → Sayt manzili* ni oʻzgartiring.

### Bepul rejim cheklovlari

Neon bepul rejimi: 0,5 GB baza — bir necha ming odam va yuzlab rasm uchun yetarli (suratlar yuklashda
1800 piksel atrofiga kichraytiriladi; hujjat va ovozli yozuvlar 12 MB gacha). Hajmni Boshqaruv panelida kuzating.

---

## 2. Boshqaruv (administrator)

* **`/boshqaruv/`** — statistika, foydalanuvchilar, rasmlar hajmi, Telegram va Cron holati,
  **toʻliq zaxira** yuklab olish. Faqat superuser koʻradi (foydalanuvchi menyusida havola bor).
* **`/admin/`** — Django admin: istalgan yozuvni koʻrish va tahrirlash.
* Yangi administrator: `python manage.py createsuperuser` (lokal, production bazaga ulangan holda) yoki
  admin’da foydalanuvchiga *Superuser status* belgisini qoʻying.

---

## 3. Zaxira nusxa va boshqa serverga koʻchish

Maʼlumotlar yoʻqolmasligi uchun bir necha yoʻl bor — bittasini muntazam qiling:

| Usul | Nima saqlanadi | Qanday |
|---|---|---|
| **Haftalik avtomatik zaxira** (tavsiya) | Butun sayt, har hafta Telegramga | `/boshqaruv/` → *Avtomatik zaxira nusxa* |
| **Toʻliq zaxira** (qoʻlda) | Butun sayt: foydalanuvchilar, parollar, arxivlar, rasmlar, eslatmalar | `/boshqaruv/` → *Toʻliq zaxira nusxa (JSON)* |
| Oila arxivi | Bitta foydalanuvchining shajarasi (rasmlar bilan) | *Sozlamalar → Maʼlumotlaringiz → Maʼlumotlarimni yuklab olish (JSON)* |
| `pg_dump` | Bazaning aynan nusxasi | `pg_dump "$DATABASE_URL_UNPOOLED" > shajara.sql` |

### Yangi serverga tiklash

```bash
# yangi serverda (Docker yoki boshqa hosting), bazani yaratib:
python manage.py migrate
python manage.py loaddata shajara-zaxira-2026-09-30.json      # toʻliq zaxira
# yoki bitta oila arxivi:
python manage.py import_archive arxiv.json --user MDNoDX
# yoki pg_dump nusxasi:
psql "$DATABASE_URL" < shajara.sql
```

Rasmlar bazada boʻlgani uchun alohida koʻchirish shart emas. Parollar ham koʻchadi.

---

## 4. Docker bilan oʻz serveringizda (muqobil)

Istalgan Linux VPS (1 vCPU, 1–2 GB RAM, Ubuntu 22.04/24.04): Hetzner, DigitalOcean, Ahost.uz va boshqalar.

| Xizmat | Vazifasi |
|---|---|
| `web` | Django + gunicorn |
| `worker` | Eslatmalar (Telegram, push), haftalik zaxira va Telegram bot (*long polling*, webhook shart emas) |
| `db` | PostgreSQL 17 (maʼlumotlar va rasmlar) |
| `caddy` | HTTPS (Let’s Encrypt) avtomatik |

```bash
ssh root@SERVER_IP
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
git clone https://github.com/MDNoDX/SilaiRahm.git silairahm && cd silairahm
cp .env.example .env && nano .env         # DOMAIN, DJANGO_SECRET_KEY, POSTGRES_PASSWORD …
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

DNS’da domenning **A-yozuvi** server IP’ga yoʻnaltirilgan boʻlishi kerak. Tekshirish: `https://DOMEN/salomatlik/` → `{"status": "ok"}`.

Yangilash: `git pull && docker compose up -d --build` (migratsiyalar avtomatik).

Zaxira:

```bash
docker compose exec -T db pg_dump -U shajara shajara | gzip > backup-$(date +%F).sql.gz
gunzip -c backup-2026-09-30.sql.gz | docker compose exec -T db psql -U shajara shajara   # tiklash
```

Vercel’dan koʻchganda Telegram webhookni oʻchiring (`docker compose exec web python manage.py telegram_webhook --delete`) — shunda `worker` botni oʻzi tinglaydi — va Google redirect URI’ni yangi domenga moslang.

---

## 5. Muammolar

| Belgi | Sabab |
|---|---|
| `400 Bad Request` | `DJANGO_ALLOWED_HOSTS` da domen yoʻq |
| Forma yuborilganda 403 | `DJANGO_CSRF_TRUSTED_ORIGINS` da `https://DOMEN` yoʻq |
| Google tugmasi yoʻq | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` berilmagan yoki Redeploy qilinmagan |
| Google «redirect_uri_mismatch» | Google Console’dagi redirect URI sayt manziliga mos emas |
| Telegram javob bermayapti | Token notoʻgʻri yoki webhook oʻrnatilmagan (`/boshqaruv/`) |
| Eslatmalar kelmayapti | `CRON_SECRET` yoʻq; Vercel → Project → **Cron Jobs** loglarini koʻring. Foydalanuvchi tanlagan soat hali kelmagan boʻlishi ham mumkin |
| Push yoqilmayapti | `VAPID_*` kalitlari yoʻq (boʻlim koʻrinmaydi); brauzerda bildirishnomalar bloklangan; iPhone’da sayt bosh ekranga qoʻshilmagan |
| Haftalik zaxira kelmadi | `/boshqaruv/` da yoqilmagan, Telegram ulanmagan yoki fayl 50 MB dan katta |
| Ikki bosqichli kirishda telefon yoʻqoldi | Tiklash kodlaridan biri bilan kiring; kodlar ham yoʻq boʻlsa, administrator `/admin/` da foydalanuvchining `totp_enabled` belgisini olib tashlaydi |
| Telegram brauzerda ochilyapti | «@bot ni ochish» tugmasi `tg://` havolasi — Telegram ilovasi oʻrnatilgan boʻlishi kerak; aks holda kodni botga qoʻlda yuboring |

Loglar: Vercel → Project → **Logs** (yoki `vercel logs`), Docker’da `docker compose logs -f web`.

## Xavfsizlik

- `DJANGO_DEBUG=0` (Vercel’da standart), HTTPS, HSTS, xavfsiz cookie yoqilgan.
- Maxfiy kalitlar faqat Vercel/`.env` da; `.env` gitga qoʻshilmaydi.
- Suratlar va albom fayllari faqat arxiv egasiga va u taklif qilgan aʼzolarga beriladi (mehmonlarga — yoʻq).
- Taklif havolasi bir martalik, 14 kun amal qiladi va istalgan payt bekor qilinadi; aʼzoning huquqi
  (koʻrish / tahrirlash) *Sozlamalar → Oila aʼzolari* da oʻzgartiriladi yoki olib tashlanadi.
- Ikki bosqichli kirish: *Sozlamalar → Xavfsizlik*. Administrator hisobida albatta yoqing.
- Har bir oʻzgarish tarixga yoziladi (kim, qachon) va ortga qaytariladi.
- Bitta hisobga 10 marta notoʻgʻri parol kiritilsa, kirish 15 daqiqaga toʻxtatiladi.
- `seed_demo` foydalanuvchilarining paroli repozitoriyda ochiq — ularni production’ga yuklamang.
