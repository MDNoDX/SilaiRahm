"""People: search, form checks, duplicates and merging, the album, history and undo."""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Membership, User
from apps.genealogy import duplicates, history
from apps.genealogy.models import Change, Marriage, Media, Person

from .helpers import make_family


class SearchAndStorageTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_cyrillic_query_finds_latin_name_and_back(self):
        Person.objects.create(owner=self.user, first_name="Олим", last_name="Содиқов", gender="male")
        html = self.client.get(reverse("genealogy:search"), {"q": "Лайло"}).content.decode()
        self.assertIn("Laylo Nurmatova", html)
        html = self.client.get(reverse("genealogy:search"), {"q": "olim sodiqov"}).content.decode()
        self.assertIn("Олим Содиқов", html)

    def test_names_are_stored_as_typed(self):
        self.client.post(reverse("genealogy:person_create"), {
            "first_name": "Гулчеҳра", "last_name": "Ra'noyeva", "gender": "female",
        })
        person = Person.objects.get(first_name="Гулчеҳра")
        self.assertEqual(person.last_name, "Raʼnoyeva")  # apostrophe normalised, letters untouched


class LiveSearchTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def search(self, q, **extra):
        return self.client.get(reverse("genealogy:search_json"), {"q": q, **extra}).json()["results"]

    def test_cross_script_and_ranking(self):
        Person.objects.create(owner=self.user, first_name="Olim", last_name="Laylov", gender="male")
        names = [r["name"] for r in self.search("Лайло")]
        self.assertEqual(names[0], "Laylo Nurmatova")          # first-name match first
        self.assertIn("Olim Laylov", names)
        first = self.search("lay")[0]
        self.assertEqual((first["label"], first["url"]), ("Singil", self.p["younger_sister"].get_absolute_url()))

    def test_partial_pages(self):
        html = self.client.get(reverse("genealogy:search"), {"q": "kam", "partial": 1}).content.decode()
        self.assertNotIn("<html", html)
        self.assertIn("Kamila Aliyeva", html)
        html = self.client.get(reverse("genealogy:people"), {"q": "aziza", "partial": 1}).content.decode()
        self.assertIn("Aziza Nurmatova", html)
        self.assertNotIn("Kamila", html)

    def test_other_archives_are_private(self):
        from apps.accounts.models import User

        stranger = User.objects.create_user("begona2", "b2@example.com", "x-parol-12345")
        response = self.client.get(reverse("genealogy:search_json"), {"q": "a", "owner": stranger.username})
        self.assertEqual(response.status_code, 403)

    def test_one_husband_at_a_time_and_divorce(self):
        wife = self.p["wife"]
        url = reverse("genealogy:relative_add", args=[wife.pk])
        data = {"relation": "spouse", "first_name": "Ikkinchi", "gender": "male"}
        self.assertContains(self.client.post(url, data), "avval oldingi nikohni")
        m = self.p["me"].marriages_as_husband.get(wife=wife)
        self.client.post(reverse("genealogy:marriage_edit", args=[m.pk]), {"is_divorced": "on"})
        m.refresh_from_db()
        self.assertTrue(m.is_divorced)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        # A man may have more than one wife.
        url = reverse("genealogy:relative_add", args=[self.p["me"].pk])
        self.assertEqual(self.client.post(url, {"relation": "spouse", "first_name": "Zuhra", "gender": "female"})
                         .status_code, 302)


class FormValidationTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def post_relative(self, **data):
        base = {"relation": "child", "first_name": "Yangi", "gender": "male"}
        base.update(data)
        return self.client.post(reverse("genealogy:relative_add", args=[self.p["me"].pk]), base)

    def test_add_child_with_other_parent(self):
        response = self.post_relative(other_parent=self.p["wife"].pk)
        self.assertEqual(response.status_code, 302)
        child = Person.objects.get(first_name="Yangi")
        self.assertEqual((child.father, child.mother), (self.p["me"], self.p["wife"]))

    def test_cannot_add_second_father(self):
        response = self.post_relative(relation="father")
        self.assertContains(response, "Bu odamning otasi shajarada allaqachon bor.")

    def test_cycle_is_rejected(self):
        response = self.post_relative(relation="child", existing=self.p["grandpa"].pk, first_name="")
        self.assertContains(response, "odam oʻzining ajdodiga aylanib qoladi")

    def test_future_date_and_invalid_day(self):
        response = self.client.post(reverse("genealogy:person_create"), {
            "first_name": "Sinov", "gender": "male", "birth_year": "2999",
        })
        self.assertContains(response, "Qiymat eng koʻpi")
        response = self.client.post(reverse("genealogy:person_create"), {
            "first_name": "Sinov", "gender": "male", "birth_year": "2001", "birth_month": "2", "birth_day": "29",
        })
        self.assertContains(response, "Tanlangan oyda bunday kun yoʻq.")


class DuplicateTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_adding_a_likely_duplicate_asks_first(self):
        data = {"first_name": "Дилноза", "last_name": "Алиева", "gender": "female"}  # the aunt, in Cyrillic
        response = self.client.post(reverse("genealogy:person_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dilnoza Aliyeva")
        self.assertEqual(Person.objects.filter(owner=self.user, gender="female", birth_year=None).count(), 0)
        response = self.client.post(reverse("genealogy:person_create"), {**data, "confirm_duplicate": "on"})
        self.assertEqual(response.status_code, 302)

    def test_merge_keeps_everything(self):
        aunt = self.p["aunt"]
        twin = Person.objects.create(owner=self.user, first_name="Dilnoza", last_name="Aliyeva", gender="female",
                                     birth_place="Andijon", occupation="Shifokor")
        child = Person.objects.create(owner=self.user, first_name="Bola", gender="male", mother=twin)
        self.assertEqual(duplicates.pairs(self.user), [(aunt, twin)])
        page = self.client.get(reverse("genealogy:duplicates"))
        self.assertContains(page, "Dilnoza Aliyeva")
        self.client.post(reverse("genealogy:merge"), {"keep": aunt.pk, "drop": twin.pk})
        aunt.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual((aunt.birth_place, aunt.occupation, aunt.birth_year), ("Andijon", "Shifokor", 1960))
        self.assertEqual(child.mother, aunt)
        self.assertFalse(Person.objects.filter(pk=twin.pk).exists())
        self.assertEqual(duplicates.pairs(self.user), [])


def png(size=(60, 40), colour="#27357e"):
    buf = BytesIO()
    Image.new("RGB", size, colour).save(buf, "PNG")
    return SimpleUploadedFile("rasm.png", buf.getvalue(), content_type="image/png")


class AlbumTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_upload_shrinks_and_is_private(self):
        person = self.p["grandpa"]
        big = png((3000, 1500))
        note = SimpleUploadedFile("xat.txt", b"salom", content_type="text/plain")
        self.client.post(reverse("genealogy:media_upload", args=[person.pk]),
                         {"files": [big, note], "caption": "Toʻy kuni", "year": "1955"})
        item = Media.objects.get(person=person)                 # the text file is refused
        self.assertEqual((item.kind, item.caption, item.year), ("photo", "Toʻy kuni", 1955))
        served = self.client.get(item.file.url)
        self.assertEqual(served.status_code, 200)
        self.assertLessEqual(max(Image.open(BytesIO(served.content)).size), 1800)
        page = self.client.get(person.get_absolute_url()).content.decode()
        self.assertIn(item.file.url, page)
        # Use it as the main photo; then delete it.
        self.client.post(reverse("genealogy:media_portrait", args=[item.pk]))
        person.refresh_from_db()
        self.assertEqual(person.photo.name, item.file.name)
        self.client.logout()
        self.assertEqual(self.client.get(item.file.url).status_code, 404)
        self.client.force_login(self.user)
        self.client.post(reverse("genealogy:media_delete", args=[item.pk]))
        person.refresh_from_db()
        self.assertFalse(person.photo)
        self.assertFalse(Media.objects.exists())

    def test_photos_appear_in_the_pdfs(self):
        person = self.p["me"]
        self.client.post(reverse("genealogy:person_edit", args=[person.pk]), {
            "first_name": person.first_name, "gender": "male", "birth_year": "1984", "photo": png()})
        book = self.client.get(reverse("genealogy:family_book"))
        self.assertTrue(book.content.startswith(b"%PDF"))
        self.assertIn(b"/Image", book.content)
        poster = self.client.get(reverse("genealogy:tree_pdf_for", args=[self.user.username]) + "?size=A2&all=1")
        self.assertTrue(poster.content.startswith(b"%PDF"))
        self.assertIn(b"/Image", poster.content)
        self.assertIn("A2", poster["Content-Disposition"])


class HistoryTests(TestCase):
    def setUp(self):
        self.user, self.p = make_family()
        self.client.force_login(self.user)

    def test_edit_is_logged_and_undone(self):
        person = self.p["aunt"]
        self.client.post(reverse("genealogy:person_edit", args=[person.pk]), {
            "first_name": "Dilnoza", "last_name": "Yangi", "gender": "female", "birth_year": "1961",
            "father": person.father_id, "mother": person.mother_id})
        person.refresh_from_db()
        self.assertEqual((person.last_name, person.birth_year), ("Yangi", 1961))
        change = Change.objects.get(person=person, action="updated")
        self.assertEqual(set(change.details["fields"]), {"last_name", "birth_year"})
        self.assertEqual(change.details["fields"]["last_name"], ["Aliyeva", "Yangi"])
        page = self.client.get(reverse("genealogy:history")).content.decode()
        self.assertIn("Dilnoza Yangi", page)
        self.client.post(reverse("genealogy:history_undo", args=[change.pk]))
        person.refresh_from_db()
        self.assertEqual((person.last_name, person.birth_year), ("Aliyeva", 1960))
        change.refresh_from_db()
        self.assertFalse(change.can_undo)

    def test_delete_is_restored_with_links(self):
        aunt, cousin = self.p["aunt"], self.p["cousin"]
        husband = self.p["uncle_in_law"]
        pk = aunt.pk
        self.client.post(reverse("genealogy:person_delete", args=[pk]))
        self.assertFalse(Person.objects.filter(pk=pk).exists())
        cousin.refresh_from_db()
        self.assertIsNone(cousin.mother)
        change = Change.objects.get(action="deleted")
        self.client.post(reverse("genealogy:history_undo", args=[change.pk]))
        restored = Person.objects.get(pk=pk)                      # the same address works again
        cousin.refresh_from_db()
        self.assertEqual(cousin.mother, restored)
        self.assertEqual(restored.father, self.p["grandpa"])
        self.assertTrue(Marriage.objects.filter(husband=husband, wife=restored).exists())

    def test_viewers_cannot_undo(self):
        other, _p = make_family(username="mehmon")
        Membership.objects.create(owner=self.user, member=other, role="viewer")
        change = history.record(self.user, self.user, Change.Action.UPDATED, self.p["aunt"],
                                details={"fields": {"last_name": ["Eski", "Aliyeva"]}}, before={"last_name": "Eski"})
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("genealogy:history_undo", args=[change.pk])).status_code, 403)
