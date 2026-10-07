"""Reminders: occasions, Telegram, push, the hourly cron, the weekly backup."""
import datetime
import json
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from PIL import Image

from apps.friends.models import Contact
from apps.genealogy.models import Event
from apps.notify import service, telegram
from apps.notify.messages import render_parts
from apps.notify.models import BotState, Notification, NotificationSettings, PushSubscription
from apps.notify.occasions import occasions

from .helpers import make_family


class ReminderTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.today = datetime.date(2026, 9, 26)  # the day before Timur's birthday (27 September)

    def test_occasions_cover_every_kind(self):
        self.p["grandpa"].death_month, self.p["grandpa"].death_day = 9, 30
        self.p["grandpa"].save()
        m = self.p["me"].marriages_as_husband.first()
        m.year, m.month, m.day = 2010, 10, 1
        m.save()
        Contact.objects.create(owner=self.user, person=self.p["me"], name="Jasur", birth_month=9, birth_day=28)
        e = Event.objects.create(owner=self.user, kind="wedding", year=2026, month=9, day=29)
        e.people.add(self.p["son"])
        kinds = {o.kind for o in occasions(self.user, self.today, self.today + datetime.timedelta(days=10))}
        self.assertEqual(kinds, {"birthday", "friend_birthday", "memorial", "anniversary", "event"})

    def test_generate_is_idempotent_and_respects_lead_time(self):
        prefs = NotificationSettings.for_user(self.user)
        prefs.days_before = 1
        prefs.save()
        self.assertEqual(service.generate(self.user, self.today), 1)   # "tomorrow" reminder
        self.assertEqual(service.generate(self.user, self.today), 0)   # not twice
        self.assertEqual(service.generate(self.user, self.today + datetime.timedelta(days=1)), 1)  # "today"
        note = Notification.objects.filter(user=self.user).order_by("created_at").first()
        with translation.override("uz"):
            self.assertEqual(note.text["title"], "Tugʻilgan kun: Timur Nurmatov")
            self.assertEqual(note.text["body"], "Ertaga 42 yoshga toʻladi.")
        with translation.override("uz-cyrl"):
            self.assertEqual(note.text["body"], "Эртага 42 ёшга тўлади.")

    def test_disabled_and_filtered(self):
        prefs = NotificationSettings.for_user(self.user)
        prefs.birthdays = False
        prefs.save()
        self.assertEqual(service.generate(self.user, self.today + datetime.timedelta(days=1)), 0)
        prefs.birthdays, prefs.enabled = True, False
        prefs.save()
        self.assertEqual(service.generate(self.user, self.today + datetime.timedelta(days=1)), 0)

    def test_muchal_at_navroz(self):
        o = [x for x in occasions(self.user, datetime.date(2030, 3, 21), datetime.date(2030, 3, 21)) if x.kind == "muchal"]
        # 2030 is a Dog year: Nigora (1982) is a Dog, Timur (1984) is a Rat.
        self.assertIn("Nigora Karimova", o[0].params["names"])
        self.assertNotIn("Timur Nurmatov", o[0].params["names"])
        o = [x for x in occasions(self.user, datetime.date(2032, 3, 21), datetime.date(2032, 3, 21)) if x.kind == "muchal"]
        self.assertIn("Timur Nurmatov", o[0].params["names"])  # 2032 is a Rat year
        with translation.override("uz"):
            self.assertIn("Sichqon", render_parts("muchal", o[0].params)["title"])

    def test_bell_and_pages(self):
        self.client.force_login(self.user)
        with mock.patch("apps.notify.service.timezone.localdate", return_value=self.today + datetime.timedelta(days=1)):
            html = self.client.get(reverse("home")).content.decode()
        self.assertIn('class="dot-badge"', html)
        note = Notification.objects.get(user=self.user)
        self.client.get(reverse("notify:open", args=[note.pk]))
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)

    def test_status_json_for_the_mac_app(self):
        service.generate(self.user, self.today + datetime.timedelta(days=1))
        self.assertEqual(self.client.get(reverse("notify:status")).status_code, 302)  # signed out
        self.client.force_login(self.user)
        data = self.client.get(reverse("notify:status"), HTTP_ACCEPT_LANGUAGE="uz").json()
        self.assertEqual(data["unread"], 1)
        item = data["items"][0]
        self.assertEqual(set(item), {"id", "kind", "url", "title", "body", "icon"})
        self.assertEqual(data["connections"], 0)
        self.assertTrue(item["url"].startswith("http"))


class FakeTelegram:
    """Stands in for the Bot API: records messages, answers getMe / webhook calls."""

    def __init__(self, username="silairahm_bot"):
        self.username = username
        self.sent = []
        self.webhook = ""
        self.calls = []

    def __call__(self, method, http_timeout=30, **params):
        self.calls.append(method)
        if method == "getMe":
            return {"id": 1, "is_bot": True, "username": self.username, "first_name": "Shajara"}
        if method == "sendMessage":
            self.sent.append((params["chat_id"], params["text"]))
            return {"message_id": len(self.sent)}
        if method == "getWebhookInfo":
            return {"url": self.webhook, "pending_update_count": 0}
        if method == "setWebhook":
            self.webhook = params["url"]
        return True


def _msg(text, chat=555, update=1, **extra):
    return {"update_id": update, "message": {"text": text, "chat": {"id": chat, "type": "private", **extra}}}


@override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_BOT_USERNAME="wrong_name_bot",
                   SITE_URL="https://shajara.example")
class TelegramTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.prefs = NotificationSettings.for_user(self.user)
        self.tg = FakeTelegram()
        patcher = mock.patch("apps.notify.telegram.call", side_effect=self.tg)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_username_comes_from_the_token(self):
        link = telegram.link_urls(self.prefs)
        self.assertEqual(link["bot"], "silairahm_bot")  # not the misconfigured env value
        self.assertEqual(link["app"], f"tg://resolve?domain=silairahm_bot&start={link['code']}")
        self.assertEqual(link["web"], f"https://t.me/silairahm_bot?start={link['code']}")
        self.assertRegex(link["code"], r"^[A-HJ-NP-Z2-9]{8}$")
        # The same code is reused while it is fresh; getMe is cached.
        self.assertEqual(telegram.link_urls(self.prefs)["code"], link["code"])
        self.assertEqual(self.tg.calls.count("getMe"), 1)

    @mock.patch("apps.notify.service.user_today", return_value=datetime.date(2026, 9, 20))
    def test_link_with_start_button_and_send(self, _today):
        code = telegram.link_code(self.prefs)
        telegram.handle_update(_msg(f"/start {code}", username="timur"))
        self.prefs.refresh_from_db()
        self.assertEqual((self.prefs.telegram_chat_id, self.prefs.telegram_enabled), (555, True))
        self.assertEqual(self.prefs.telegram_name, "timur")
        self.assertIn("Hisobingiz ulandi", self.tg.sent[0][1])
        self.assertIn("Yaqin sanalar", self.tg.sent[1][1])  # upcoming dates right away
        # A code works only once.
        telegram.handle_update(_msg(f"/start {code}", chat=777, update=2))
        self.assertIn("eskirgan", self.tg.sent[-1][1])

        service.generate(self.user, datetime.date(2026, 9, 27))
        at_nine = datetime.datetime(2026, 9, 27, 4, 0, tzinfo=datetime.timezone.utc)  # 09:00 in Tashkent
        at_seven = datetime.datetime(2026, 9, 27, 2, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(service.send_pending_telegram(now=at_seven), 0)  # before the chosen hour (08:00)
        self.assertEqual(service.send_pending_telegram(now=at_nine), 1)
        self.assertIn("<b>Tugʻilgan kun: Timur Nurmatov</b>", self.tg.sent[-1][1])
        self.assertIn('href="https://shajara.example/', self.tg.sent[-1][1])
        self.assertEqual(service.send_pending_telegram(now=at_nine), 0)  # not twice

        telegram.handle_update(_msg("/next", update=3))
        self.assertIn("Timur Nurmatov", self.tg.sent[-1][1])
        telegram.handle_update(_msg("/stop", update=4))
        self.prefs.refresh_from_db()
        self.assertFalse(self.prefs.telegram_enabled)
        telegram.handle_update(_msg("/start", update=5))
        self.prefs.refresh_from_db()
        self.assertTrue(self.prefs.telegram_enabled)

    def test_code_typed_by_hand(self):
        code = telegram.link_code(self.prefs)
        telegram.handle_update(_msg(f" {code[:4].lower()}-{code[4:]} "))
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.telegram_chat_id, 555)

    def test_unknown_chat_gets_instructions(self):
        telegram.handle_update(_msg("salom"))
        self.assertIn("Sozlamalar", self.tg.sent[-1][1])
        telegram.handle_update(_msg("ABCD2345"))
        self.assertIn("eskirgan", self.tg.sent[-1][1])

    def test_hour_uses_the_users_time_zone(self):
        self.user.time_zone = "Europe/Berlin"
        self.user.save()
        self.prefs.telegram_chat_id, self.prefs.telegram_enabled = 555, True
        self.prefs.save()
        service.generate(self.user, datetime.date(2026, 9, 27))
        eight_tashkent = datetime.datetime(2026, 9, 27, 3, 30, tzinfo=datetime.timezone.utc)  # 05:30 in Berlin
        self.assertEqual(service.send_pending_telegram(now=eight_tashkent), 0)
        self.assertEqual(service.send_pending_telegram(now=eight_tashkent + datetime.timedelta(hours=3)), 1)

    def test_settings_page_status_and_test_message(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("notify:settings")).content.decode()
        self.assertIn("tg://resolve?domain=silairahm_bot", html)
        self.assertIn("<svg", html)  # QR code
        status = reverse("notify:telegram_status")
        self.assertEqual(self.client.get(status).json(), {"connected": False, "name": ""})
        telegram.handle_update(_msg(f"/start {telegram.link_code(self.prefs)}", username="timur"))
        self.assertEqual(self.client.get(status).json(), {"connected": True, "name": "timur"})
        self.client.post(reverse("notify:telegram_test"))
        self.assertIn("Sinov xabari", self.tg.sent[-1][1])
        self.client.post(reverse("notify:telegram_toggle"))
        self.prefs.refresh_from_db()
        self.assertFalse(self.prefs.telegram_enabled)

    @override_settings(CRON_SECRET="s3cret")
    def test_cron_repairs_the_webhook(self):
        response = self.client.get(reverse("notify:cron_daily"), HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertTrue(response.json()["webhook_fixed"])
        self.assertEqual(self.tg.webhook, "https://shajara.example/telegram/webhook/")
        self.assertIn("setMyCommands", self.tg.calls)
        response = self.client.get(reverse("notify:cron_daily"), HTTP_AUTHORIZATION="Bearer s3cret")
        self.assertFalse(response.json()["webhook_fixed"])


class PushAndBackupTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_subscribe_and_unsubscribe(self):
        sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k" * 80, "auth": "a" * 20}}
        ok = self.client.post(reverse("notify:push_subscribe"), json.dumps(sub), content_type="application/json")
        self.assertTrue(ok.json()["ok"])
        self.assertEqual(PushSubscription.objects.get().user, self.user)
        bad = self.client.post(reverse("notify:push_subscribe"), "{}", content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        self.client.post(reverse("notify:push_unsubscribe"), json.dumps({"endpoint": sub["endpoint"]}),
                         content_type="application/json")
        self.assertFalse(PushSubscription.objects.exists())

    @override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv")
    def test_due_reminders_are_pushed_once(self):
        PushSubscription.objects.create(user=self.user, endpoint="https://push.example/1", p256dh="k", auth="a")
        service.generate(self.user, datetime.date(2026, 9, 27))
        nine = datetime.datetime(2026, 9, 27, 4, 0, tzinfo=datetime.timezone.utc)
        with mock.patch("apps.notify.push.send", return_value=True) as send:
            self.assertEqual(service.send_pending_push(now=nine), 1)
            self.assertEqual(service.send_pending_push(now=nine), 0)
        payload = send.call_args.args[1]
        self.assertIn("Timur Nurmatov", payload["title"])
        self.assertTrue(payload["url"].startswith("/"))

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc")
    def test_weekly_backup_goes_to_the_admin_once_a_week(self):
        prefs = NotificationSettings.for_user(self.user)
        prefs.telegram_chat_id, prefs.backup_telegram = 555, True
        prefs.save()
        monday = datetime.datetime(2026, 9, 28, 3, 0, tzinfo=datetime.timezone.utc)
        with mock.patch("apps.notify.telegram.send_document") as send:
            self.assertEqual(service.weekly_backup(now=monday), 0)       # not an administrator
            self.user.is_superuser = True
            self.user.save()
            self.assertEqual(service.weekly_backup(now=monday), 1)
            self.assertEqual(service.weekly_backup(now=monday + datetime.timedelta(days=2)), 0)
            self.assertEqual(service.weekly_backup(now=monday + datetime.timedelta(days=7)), 1)
        chat, name, data, _caption = send.call_args.args
        self.assertEqual(chat, 555)
        self.assertTrue(name.endswith(".json.gz"))
        import gzip
        self.assertIn("accounts.user", gzip.decompress(data).decode())
        self.assertTrue(BotState.get("backup_week"))


class ServerlessTests(TestCase):
    def test_cron_requires_secret(self):
        self.assertEqual(self.client.get("/cron/kunlik/").status_code, 401)
        with self.settings(CRON_SECRET="abc"):
            self.assertEqual(self.client.get("/cron/kunlik/", HTTP_AUTHORIZATION="Bearer nope").status_code, 401)
            response = self.client.get("/cron/kunlik/", HTTP_AUTHORIZATION="Bearer abc")
        self.assertEqual(response.status_code, 200)
        self.assertIn("created", response.json())

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc")
    def test_telegram_webhook_checks_secret(self):
        url = reverse("notify:telegram_webhook")
        self.assertEqual(self.client.post(url, "{}", content_type="application/json").status_code, 403)
        with mock.patch("apps.notify.telegram.handle_update") as handle:
            response = self.client.post(url, '{"update_id": 1}', content_type="application/json",
                                        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=telegram.webhook_secret())
        self.assertEqual(response.status_code, 200)
        handle.assert_called_once()

    def test_photos_are_stored_in_the_database(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from apps.core.models import StoredFile

        user, p = make_family()
        self.client.force_login(user)
        buf = BytesIO()
        Image.new("RGB", (40, 40), "#5b47c9").save(buf, "PNG")
        photo = SimpleUploadedFile("men.png", buf.getvalue(), content_type="image/png")
        person = p["me"]
        response = self.client.post(reverse("genealogy:person_edit", args=[person.pk]), {
            "first_name": person.first_name, "gender": "male", "birth_year": "1984", "birth_month": "9",
            "birth_day": "27", "photo": photo,
        })
        self.assertEqual(response.status_code, 302)
        person.refresh_from_db()
        self.assertTrue(StoredFile.objects.filter(name=person.photo.name).exists())
        served = self.client.get(person.photo.url)
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/jpeg")  # photos are shrunk and stored as JPEG
        self.assertIn("private", served["Cache-Control"])
        # Photos are private: not for guests, not for other users.
        self.client.logout()
        self.assertEqual(self.client.get(person.photo.url).status_code, 404)
        stranger, _p = make_family(username="begona")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(person.photo.url).status_code, 404)
