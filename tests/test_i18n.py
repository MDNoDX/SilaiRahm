"""Language quality: catalogues, script purity of every page, language choice."""
import json
import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import User
from tools import i18n_audit

from .helpers import PASSWORD, english_msgids, make_family, visible_text

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
UZBEK_ONLY_CYRILLIC = re.compile(r"[ЎўҚқҒғҲҳ]")
# Intentional exceptions: each language in the switcher names itself, the
# search help shows a cross-script example, and brands and formats keep their names.
SELF_NAMES = ("Oʻzbekcha", "Ўзбекча", "Русский", "English", "lotin yozuvi", "кирилл ёзуви", "ЎЗ")
ALLOWED_LATIN_IN_CYRILLIC = {"PDF", "PNG", "MB", "Alisher", "GEDCOM", "Ctrl", "Mac", "Start", "stop", "JSON", "Google",
                             "Telegram", "Web", "UZ", "RU", "EN", "UTC", "MyHeritage", "Ancestry", "Gramps", "URL",
                             "cookie", "next", "Authenticator", "Microsoft", "Push", "iPhone", "iPad", "Esc", "K",
                             "Shajara", "Silai", "Rahm", "Gemini", "GEMINI", "API", "KEY", "AI", "Studio", "Get", "key", "help", "start"}
LANGUAGES = {"uz": "uz-Latn", "uz-cyrl": "uz-Cyrl", "ru": "ru", "en": "en"}


class CatalogueTests(TestCase):
    def test_language_audit_is_clean(self):
        problems = i18n_audit.run_all()
        self.assertEqual(problems, [], "\n".join(problems))

    def test_catalogues_are_compiled(self):
        for loc in ("uz", "uz_Cyrl", "ru", "en"):
            for domain in ("django", "djangojs"):
                mo = settings.BASE_DIR / "locale" / loc / "LC_MESSAGES" / f"{domain}.mo"
                po = mo.with_suffix(".po")
                self.assertTrue(mo.exists(), f"{mo} is missing; run compilemessages")
                self.assertGreaterEqual(mo.stat().st_mtime, po.stat().st_mtime - 1, f"{mo} is older than {po}")

    def test_django_messages_use_project_translations(self):
        with translation.override("uz"):
            self.assertEqual(translation.gettext("This field is required."), "Bu maydonni toʻldirish majburiy.")
        with translation.override("uz-cyrl"):
            self.assertEqual(translation.gettext("This field is required."), "Бу майдонни тўлдириш мажбурий.")
            self.assertEqual(translation.gettext("The two password fields didn’t match."), "Пароллар мос келмади.")
        with translation.override("ru"):
            self.assertEqual(translation.gettext("This field is required."), "Обязательное поле.")


class PagePurityTests(TestCase):
    """Every page must be entirely in its language: Uzbek Latin, Uzbek Cyrillic, Russian or English."""

    def pages(self, p, user):
        return [
            reverse("home"),
            reverse("genealogy:tree"),
            reverse("genealogy:people"),
            reverse("genealogy:person", args=[p["me"].pk]),
            reverse("genealogy:person", args=[p["grandpa"].pk]),
            reverse("genealogy:person_edit", args=[p["me"].pk]),
            reverse("genealogy:person_create"),
            reverse("genealogy:relative_add", args=[p["me"].pk]) + "?relation=child",
            reverse("genealogy:person_delete", args=[p["aunt"].pk]),
            reverse("assistant:chat"),
            reverse("genealogy:search") + "?q=zzzz",
            reverse("friends:list") + "?q=zzzz",
            reverse("accounts:settings"),
            reverse("accounts:security"),
            reverse("accounts:data"),
            reverse("genealogy:upcoming"),
            reverse("genealogy:event_create"),
            reverse("genealogy:calculator") + f"?a={p['me'].pk}&b={p['cousin'].pk}",
            reverse("friends:list"),
            reverse("friends:create"),
            reverse("accounts:family"),
            reverse("accounts:two_factor_setup"),
            reverse("genealogy:timeline"),
            reverse("genealogy:history"),
            reverse("genealogy:duplicates"),
            reverse("genealogy:people") + "?tartib=abc",
            reverse("control_panel"),
            reverse("offline"),
            reverse("notify:list"),
            reverse("notify:settings"),
            reverse("genealogy:marriage_edit", args=[p["me"].marriages_as_husband.first().pk]),
            "/bunday-sahifa-yoq/",
        ]

    def assert_pure(self, html, language, allowed=()):
        if language is True or language is False:  # old call style: cyrillic flag
            language = "uz-cyrl" if language else "uz"
        text = visible_text(html)
        text = re.sub(r"\S+@\S+\.\w+|@\w+", "", text)  # emails and @usernames
        text = re.sub(r"https?://\S+|python manage\.py \S+ \S+", "", text)  # addresses and commands (control panel)
        text = re.sub(r"\b[A-Z2-7]{4}(?: [A-Z2-7]{4}){3,}\b", "", text)  # the two-step sign-in key
        for token in allowed + SELF_NAMES:
            text = text.replace(token, "")
        if language != "en":
            leaks = [m for m in english_msgids() if m in text]
            self.assertEqual(leaks, [], f"English text on the page: {leaks}")
        if language in ("uz-cyrl", "ru"):
            latin = [w for w in re.findall(r"[A-Za-z]+", text) if w not in ALLOWED_LATIN_IN_CYRILLIC]
            self.assertEqual(latin, [], f"Latin text on a Cyrillic page: {latin}\n{text}")
            if language == "ru":
                self.assertEqual(UZBEK_ONLY_CYRILLIC.findall(text), [], f"Uzbek letters on a Russian page:\n{text}")
        else:
            cyr = [w for w in re.findall(r"\w*[Ѐ-ӿ]\w*", text) if w != "Алишер"]
            self.assertEqual(cyr, [], f"Cyrillic text on a Latin page: {cyr}")
            if language == "en":
                self.assertNotRegex(text, r"[ʻʼ]", "Uzbek text on an English page")

    def check_language(self, language):
        user, p = make_family(language=language)
        user.is_superuser = True  # the control panel is part of the interface too
        user.save()
        self.client.force_login(user)
        for url in self.pages(p, user):
            response = self.client.get(url)
            self.assertIn(response.status_code, (200, 404), url)
            with self.subTest(url=url, language=language):
                self.assert_pure(response.content.decode(), language, allowed=(user.username,))
                self.assertIn(f'lang="{LANGUAGES[language]}"', response.content.decode())

    def test_latin_pages(self):
        self.check_language("uz")

    def test_cyrillic_pages(self):
        self.check_language("uz-cyrl")

    def test_russian_pages(self):
        self.check_language("ru")

    def test_english_pages(self):
        self.check_language("en")

    def test_form_errors_in_cyrillic(self):
        user, p = make_family(cyrillic=True)
        self.client.force_login(user)
        response = self.client.post(reverse("genealogy:person_edit", args=[p["me"].pk]), {
            "first_name": "", "gender": "male", "birth_day": "31", "birth_month": "2", "birth_year": "1984",
            "death_year": "1970",
        })
        html = response.content.decode()
        self.assertIn("Бу майдонни тўлдириш мажбурий.", html)
        self.assertIn("Танланган ойда бундай кун йўқ.", html)
        self.assert_pure(html, "uz-cyrl", allowed=(user.username,))

    def test_anonymous_pages(self):
        for lang, cyrillic in (("uz", "uz"), ("uz-cyrl", "uz-cyrl"), ("ru", "ru"), ("en", "en")):
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
            for url in (reverse("home"), reverse("accounts:login"), reverse("accounts:register"),
                        reverse("accounts:password_reset")):
                with self.subTest(url=url, lang=lang):
                    self.assert_pure(self.client.get(url).content.decode(), cyrillic)
            # Registration with errors: Django's own validation messages too.
            response = self.client.post(reverse("accounts:register"), {
                "first_name": "", "username": "a b", "email": "notanemail", "password1": "123", "password2": "456",
            })
            self.assert_pure(response.content.decode(), cyrillic)
            response = self.client.post(reverse("accounts:login"), {"username": "yoq", "password": "yoq"})
            self.assert_pure(response.content.decode(), cyrillic)

    def test_javascript_catalogue(self):
        """Pages load the static catalogue of their language, and the files match the .po files."""
        from apps.core.management.commands.build_js_catalogs import OUT, catalogue

        for lang, expected in (("uz", "Rostdan ham oʻchirmoqchimisiz?"), ("uz-cyrl", "Ростдан ҳам ўчирмоқчимисиз?"),
                               ("ru", "Вы действительно хотите удалить?")):
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = lang
            self.assertIn(f"js/i18n/{lang}.js", self.client.get(reverse("accounts:login")).content.decode())
            js = (OUT / f"{lang}.js").read_text(encoding="utf-8")
            self.assertTrue(expected in js or json.dumps(expected)[1:-1] in js, lang)
        for lang, _name in settings.LANGUAGES:
            self.assertEqual((OUT / f"{lang}.js").read_bytes(), catalogue(lang),
                             f"static/js/i18n/{lang}.js is out of date: run manage.py build_js_catalogs")

    def test_tree_json_labels_follow_language(self):
        user, p = make_family()
        self.client.force_login(user)
        url = reverse("genealogy:tree_data_for", args=[user.username])
        labels = {n["id"]: n["label"] for n in self.client.get(url).json()["nodes"]}
        self.assertEqual(labels[p["father"].pk], "Ota")
        user.preferred_language = "uz-cyrl"
        user.save()
        labels = {n["id"]: n["label"] for n in self.client.get(url).json()["nodes"]}
        self.assertEqual(labels[p["father"].pk], "Ота")
        self.assertEqual(labels[p["me"].pk], "Сиз")


class LanguageChoiceTests(TestCase):
    def html_lang(self, response):
        return re.search(r'<html lang="([^"]+)"', response.content.decode()).group(1)

    def test_default_is_uzbek_latin(self):
        self.assertEqual(self.html_lang(self.client.get("/")), "uz-Latn")

    def test_english_and_russian_browsers_get_uzbek_latin(self):
        for header in ("en-US,en;q=0.9", "ru-RU,ru;q=0.9"):
            self.assertEqual(self.html_lang(self.client.get("/", HTTP_ACCEPT_LANGUAGE=header)), "uz-Latn")

    def test_russian_and_english_by_choice(self):
        for code, lang in (("ru", "ru"), ("en", "en")):
            self.client.post(reverse("set_language"), {"language": code, "next": "/"})
            self.assertEqual(self.html_lang(self.client.get("/")), lang)

    def test_browser_preference_for_cyrillic(self):
        self.assertEqual(self.html_lang(self.client.get("/", HTTP_ACCEPT_LANGUAGE="uz-Cyrl-UZ,uz;q=0.8")), "uz-Cyrl")

    def test_anonymous_switch_uses_cookie(self):
        response = self.client.post(reverse("set_language"), {"language": "uz-cyrl", "next": "/"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "uz-cyrl")
        self.assertEqual(self.html_lang(self.client.get("/")), "uz-Cyrl")

    def test_unknown_language_and_foreign_redirect_are_ignored(self):
        response = self.client.post(reverse("set_language"), {"language": "de", "next": "https://evil.example/"})
        self.assertEqual(response["Location"], "/")
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_signed_in_choice_is_saved_to_account(self):
        user, _p = make_family()
        self.client.force_login(user)
        self.client.post(reverse("set_language"), {"language": "uz-cyrl", "next": "/"})
        user.refresh_from_db()
        self.assertEqual(user.preferred_language, "uz-cyrl")

    def test_saved_language_wins_after_login(self):
        user, _p = make_family()
        user.preferred_language = "uz-cyrl"
        user.save()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
        response = self.client.post(reverse("accounts:login"), {"username": user.username, "password": PASSWORD}, follow=True)
        self.assertEqual(self.html_lang(response), "uz-Cyrl")
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, "uz-cyrl")

    def test_settings_form_changes_language(self):
        user, _p = make_family()
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:settings"), {
            "prefs-preferred_language": "uz-cyrl", "prefs-time_zone": "Asia/Tashkent", "prefs-tree_audience": "followers", "prefs-stories_audience": "family",
            "save_prefs": "1"}, follow=True)
        user.refresh_from_db()
        self.assertEqual(user.preferred_language, "uz-cyrl")
        self.assertIn("Интерфейс тили ўзгартирилди.", response.content.decode())

    def test_registration_keeps_current_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz-cyrl"
        self.client.post(reverse("accounts:register"), {
            "first_name": "Алишер", "last_name": "Навоий", "gender": "male", "username": "alisher",
            "email": "alisher@example.com", "password1": "Yaxshi-parol-2026", "password2": "Yaxshi-parol-2026",
        })
        user = User.objects.get(username="alisher")
        self.assertEqual(user.preferred_language, "uz-cyrl")
        self.assertEqual(user.person.first_name, "Алишер")  # stored exactly as typed
