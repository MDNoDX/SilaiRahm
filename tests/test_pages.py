"""Pages: tree data, quick add, timeline, dashboard, events, friends, calculator, PDFs, admin."""
import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.friends.models import Contact
from apps.genealogy import gedcom
from apps.genealogy.kinship import Archive
from apps.genealogy.models import Event, Person

from .helpers import make_family


class ViewsTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_card(self):
        card = self.client.get(reverse("genealogy:person_card", args=[self.p["me"].pk])).json()
        self.assertTrue(card["is_me"])
        self.assertEqual(card["can_add"], {"father": False, "mother": False, "spouse": True, "child": True, "sibling": True})
        self.assertEqual(card["child_surname"], {"son": "Rustamov", "daughter": "Nurmatov"})

    def test_quick_add_warns_about_duplicates(self):
        url = reverse("genealogy:quick_add", args=[self.p["me"].pk])
        response = self.client.post(url, {"relation": "child", "first_name": "Samir", "last_name": "Nurmatov", "gender": "male"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["duplicates"][0]["name"], "Samir Nurmatov")
        response = self.client.post(url, {"relation": "child", "first_name": "Samir", "last_name": "Nurmatov",
                                          "gender": "male", "confirm_duplicate": "on"})
        self.assertTrue(response.json()["ok"])
        child = Person.objects.get(pk=response.json()["id"])
        self.assertEqual((child.father, child.mother), (self.p["me"], self.p["wife"]))   # the only spouse is the mother

    def test_people_by_generation_timeline_and_dashboard(self):
        page = self.client.get(reverse("genealogy:people"))
        titles = [title for title, _rows in page.context["groups"]]
        self.assertEqual(len(titles), 5)                                      # grandparents … grandchildren
        self.assertEqual(page.context["groups"][0][1][0][0], self.p["grandpa"])
        women = self.client.get(reverse("genealogy:people") + "?f=female")
        self.assertTrue(all(row[0].gender == "female" for _t, rows in women.context["groups"] for row in rows))
        timeline = self.client.get(reverse("genealogy:timeline"))
        self.assertContains(timeline, "Karim Nurmatov")
        self.assertEqual(timeline.context["decades"][0][0], 2010)             # newest decade first
        with mock.patch("apps.core.views.timezone.localdate", return_value=datetime.date(2026, 9, 27)):
            home = self.client.get(reverse("home"))
        self.assertEqual(home.context["today_items"][0]["person"], self.p["me"])
        self.assertTrue(home.context["today_items"][0]["share"].startswith("tg://msg?text="))

    def test_service_worker_and_offline(self):
        sw = self.client.get("/sw.js")
        self.assertEqual(sw["Service-Worker-Allowed"], "/")
        self.assertIn("showNotification", sw.content.decode())
        self.assertEqual(self.client.get(reverse("offline")).status_code, 200)


class EventsFriendsTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_create_future_event(self):
        response = self.client.post(reverse("genealogy:event_create"), {
            "kind": "wedding", "title": "Samirning to'yi", "people": [self.p["son"].pk],
            "event_day": "15", "event_month": "8", "event_year": str(datetime.date.today().year + 1),
        })
        event = Event.objects.get()
        self.assertRedirects(response, event.get_absolute_url())
        self.assertEqual(event.title, "Samirning toʻyi")
        self.assertEqual(list(event.people.all()), [self.p["son"]])

    def test_every_year_needs_day_and_month(self):
        response = self.client.post(reverse("genealogy:event_create"), {
            "kind": "memorial", "every_year": "on", "event_year": "2001",
        })
        self.assertContains(response, "Har yili eslatilishi uchun kun va oyni kiriting.")

    def test_friend_of_father(self):
        response = self.client.post(reverse("friends:create"), {
            "person": self.p["father"].pk, "name": "Baxtiyor", "how_met": "army", "birth_day": "3", "birth_month": "5",
        })
        self.assertEqual(response.status_code, 302)
        contact = Contact.objects.get()
        self.assertEqual((contact.person, contact.birth_year, contact.birth_month), (self.p["father"], None, 5))
        html = self.client.get(reverse("genealogy:person", args=[self.p["father"].pk])).content.decode()
        self.assertIn("Baxtiyor", html)
        self.assertIn("Harbiy xizmatdosh", html)

    def test_calculator_and_person_page(self):
        html = self.client.get(reverse("genealogy:calculator"),
                               {"a": self.p["me"].pk, "b": self.p["cousin"].pk}).content.decode()
        self.assertIn("Ammavachcha", html)
        html = self.client.get(reverse("genealogy:person", args=[self.p["me"].pk])).content.decode()
        self.assertIn("Muchali", html)
        self.assertIn("Sichqon", html)  # 1984

    def test_gedcom(self):
        text = gedcom.export(Archive(self.user), "Timur")
        self.assertTrue(text.startswith("0 HEAD"))
        self.assertIn(f"0 @I{self.p['me'].pk}@ INDI", text)
        self.assertIn("2 DATE 27 SEP 1984", text)
        self.assertIn(f"1 CHIL @I{self.p['me'].pk}@", text)
        self.assertTrue(text.rstrip().endswith("0 TRLR"))
        response = self.client.get(reverse("genealogy:gedcom"))
        self.assertIn(".ged", response["Content-Disposition"])

    def test_path(self):
        a = Archive(self.user)
        chain = a.path(self.p["me"].pk, self.p["cousin"].pk)
        self.assertEqual(chain[0], self.p["me"].pk)
        self.assertEqual(chain[-1], self.p["cousin"].pk)
        self.assertEqual(len(chain), 5)  # me → father → grandpa → aunt → cousin

    def test_son_surname_suggestion(self):
        html = self.client.get(reverse("genealogy:relative_add", args=[self.p["me"].pk]) + "?relation=child").content.decode()
        self.assertIn('data-son-surname="Rustamov"', html)


class PdfTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family(cyrillic=True)
        self.client.force_login(self.user)

    def assert_pdf(self, response, filename):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(b"DejaVuSans", response.content)  # Unicode font embedded
        self.assertIn(filename, response["Content-Disposition"])

    def test_pdfs_follow_language(self):
        # User prefers Cyrillic: file names are Cyrillic too (RFC 5987 encoded).
        self.assert_pdf(self.client.get(reverse("genealogy:tree_pdf_for", args=[self.user.username])),
                        "%D1%88%D0%B0%D0%B6%D0%B0%D1%80%D0%B0.pdf")  # шажара.pdf
        self.assert_pdf(self.client.get(reverse("genealogy:family_book")), "%D1%88%D0%B0%D0%B6%D0%B0%D1%80%D0%B0")
        self.assert_pdf(self.client.get(reverse("genealogy:person_pdf", args=[self.p["grandpa"].pk])), ".pdf")
        self.user.preferred_language = "uz"
        self.user.save()
        self.assert_pdf(self.client.get(reverse("genealogy:tree_pdf_for", args=[self.user.username])), "shajara.pdf")


class AdminTests(TestCase):
    def test_admin_pages_open(self):
        user, p = make_family()
        user.is_staff = user.is_superuser = True
        user.save()
        self.client.force_login(user)
        for url in ("/admin/", f"/admin/accounts/user/{user.pk}/change/", "/admin/accounts/user/",
                    "/admin/accounts/membership/", "/admin/accounts/invite/", "/admin/genealogy/person/",
                    "/admin/genealogy/media/", "/admin/genealogy/change/", f"/admin/genealogy/person/{p['me'].pk}/change/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
