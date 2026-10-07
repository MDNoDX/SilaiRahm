"""Signing in: e-mail and throttling, Google, the Mac app bridge, two-step sign-in."""
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts import totp
from apps.accounts.models import User

from .helpers import PASSWORD, make_family


class GoogleAndAppLoginTests(TestCase):
    def test_profile_completion_for_new_accounts(self):
        from apps.accounts.models import User

        user = User.objects.create_user("googler", "g@example.com")  # as created by Google sign-in
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("accounts:complete_profile") + "?next=/", fetch_redirect_response=False)
        response = self.client.post(reverse("accounts:complete_profile"),
                                    {"first_name": "Nodir", "last_name": "Madaminov", "gender": "male"})
        user.refresh_from_db()
        self.assertEqual((user.person.first_name, user.person.gender), ("Nodir", "male"))
        # Next: who the parents and grandparents are (or "Later").
        self.assertRedirects(self.client.get(reverse("home")), reverse("accounts:family_start") + "?next=/",
                             fetch_redirect_response=False)
        self.client.post(reverse("accounts:family_start"), {"skip": "1"})
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_app_login_bridge(self):
        user, _p = make_family()
        self.client.force_login(user)
        response = self.client.get(reverse("app_login_finish"))
        self.assertTrue(response["Location"].startswith("silairahm://kirish?token="))
        token = response["Location"].split("token=", 1)[1]
        app = self.client_class()  # the app's own web view: a fresh session
        response = app.get(reverse("app_login"), {"token": token})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(int(app.session["_auth_user_id"]), user.pk)
        # The token works only once.
        again = self.client_class().get(reverse("app_login"), {"token": token})
        self.assertRedirects(again, reverse("accounts:login"), fetch_redirect_response=False)

    def test_login_with_email_and_throttle(self):
        from django.core.cache import cache

        from .helpers import PASSWORD

        cache.clear()
        user, _p = make_family()
        response = self.client.post(reverse("accounts:login"), {"username": user.email.upper(), "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        for _i in range(10):
            self.client.post(reverse("accounts:login"), {"username": user.username, "password": "xato"})
        response = self.client.post(reverse("accounts:login"), {"username": user.username, "password": PASSWORD})
        self.assertEqual(response.status_code, 200)  # locked for a while, even with the right password
        self.assertIn("15 daqiqa", response.content.decode())
        cache.clear()

    def test_google_button_only_when_configured(self):
        html = self.client.get(reverse("accounts:login")).content.decode()
        self.assertNotIn("google-form", html)
        providers = {"google": {"APPS": [{"client_id": "x.apps.googleusercontent.com", "secret": "s", "key": ""}],
                                "SCOPE": ["profile", "email"]}}
        with self.settings(GOOGLE_CLIENT_ID="x.apps.googleusercontent.com", SOCIALACCOUNT_PROVIDERS=providers):
            html = self.client.get(reverse("accounts:login")).content.decode()
        self.assertIn("google-form", html)


class TwoFactorTests(TestCase):
    def test_setup_and_sign_in(self):
        user, _p = make_family()
        self.client.force_login(user)
        self.client.get(reverse("accounts:two_factor_setup"))
        secret = self.client.session["totp_new"]
        wrong = self.client.post(reverse("accounts:two_factor_setup"), {"code": "000000"})
        self.assertEqual(wrong.status_code, 200)
        page = self.client.post(reverse("accounts:two_factor_setup"), {"code": totp.code_at(secret, int(__import__("time").time() // 30))})
        user.refresh_from_db()
        self.assertTrue(user.totp_enabled)
        self.assertEqual(len(user.recovery_codes), 8)
        recovery = page.context["codes"][0]

        # The password alone is no longer enough.
        self.client.logout()
        response = self.client.post(reverse("accounts:login"), {"username": user.username, "password": PASSWORD})
        self.assertRedirects(response, reverse("accounts:two_factor"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("home")).context.get("people_count"), None)  # still a guest
        self.client.post(reverse("accounts:two_factor"), {"code": "123456"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:two_factor"), {"code": recovery})       # a recovery code works once
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        user.refresh_from_db()
        self.assertEqual(len(user.recovery_codes), 7)

    def test_codes(self):
        secret = "JBSWY3DPEHPK3PXP"
        self.assertEqual(totp.code_at(secret, 1), "996554")     # RFC 4226-style reference value
        self.assertTrue(totp.verify(secret, totp.code_at(secret, 50), now=50 * 30 + 5))
        self.assertTrue(totp.verify(secret, totp.code_at(secret, 49), now=50 * 30 + 5))   # clock drift
        self.assertFalse(totp.verify(secret, totp.code_at(secret, 40), now=50 * 30 + 5))


class EmailSignupTests(TestCase):
    DATA = {"first_name": "Aziza", "last_name": "Karimova", "gender": "female", "username": "aziza",
            "email": "aziza@example.com", "password1": "Yaxshi-parol-2026", "password2": "Yaxshi-parol-2026"}

    def code(self):
        import re

        from django.core import mail
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body)[1]

    def test_account_is_made_only_after_the_code(self):
        response = self.client.post(reverse("accounts:register"), self.DATA)
        self.assertRedirects(response, reverse("accounts:verify_email"))
        self.assertFalse(User.objects.filter(username="aziza").exists())
        self.assertNotIn("Yaxshi-parol-2026", str(self.client.session.items()))  # only a hash waits
        wrong = "000000" if self.code() != "000000" else "111111"
        self.assertContains(self.client.post(reverse("accounts:verify_email"), {"code": wrong}), "errorlist")
        self.assertFalse(User.objects.filter(username="aziza").exists())
        response = self.client.post(reverse("accounts:verify_email"), {"code": self.code()})
        user = User.objects.get(username="aziza")
        self.assertTrue(user.check_password("Yaxshi-parol-2026"))
        self.assertEqual(user.person.first_name, "Aziza")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_too_many_wrong_codes(self):
        self.client.post(reverse("accounts:register"), self.DATA)
        right = self.code()
        wrong = "000000" if right != "000000" else "111111"
        for _ in range(5):
            self.client.post(reverse("accounts:verify_email"), {"code": wrong})
        self.client.post(reverse("accounts:verify_email"), {"code": right})
        self.assertFalse(User.objects.filter(username="aziza").exists())

    def test_resend_waits_a_minute(self):
        from django.core import mail

        self.client.post(reverse("accounts:register"), self.DATA)
        self.client.post(reverse("accounts:verify_email"), {"resend": "1"})
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_without_a_mail_server_google_is_offered(self):
        response = self.client.post(reverse("accounts:register"), self.DATA)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="aziza").exists())

    def test_step_two_needs_step_one(self):
        self.assertRedirects(self.client.get(reverse("accounts:verify_email")), reverse("accounts:register"))
