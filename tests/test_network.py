"""Connections between accounts, and comparing and merging family trees."""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Invite, Membership, User
from apps.core.models import StoredFile
from apps.core.names import guess_gender
from apps.friends.models import Contact
from apps.genealogy.models import Change, Marriage, Person
from apps.network import merge, services
from apps.network.models import Connection, PersonMatch
from apps.notify.models import Notification

from .helpers import PASSWORD, make_family


def cousin_account(username="kamila"):
    """An account of the cousin, with a small tree of her own: her husband's side."""
    user = User.objects.create_user(username, f"{username}@example.com", PASSWORD, first_name="Kamila",
                                    last_name="Aliyeva", gender="female")
    me = Person.objects.create(owner=user, first_name="Kamila", last_name="Aliyeva", gender="female",
                               birth_year=1985, birth_month=4, birth_day=2, birth_place="Andijon")
    dad = Person.objects.create(owner=user, first_name="Sherzod", last_name="Aliyev", gender="male", birth_year=1957,
                                occupation="Muhandis")
    mum = Person.objects.create(owner=user, first_name="Dilnoza", last_name="Aliyeva", gender="female",
                                birth_year=1961)  # one year off: a difference, not a different person
    husband = Person.objects.create(owner=user, first_name="Bobur", last_name="Karimov", gender="male", birth_year=1983)
    son = Person.objects.create(owner=user, first_name="Ali", last_name="Karimov", gender="male", birth_year=2010,
                                father=husband, mother=me)
    me.father, me.mother = dad, mum
    me.save()
    Marriage.objects.create(owner=user, husband=dad, wife=mum)
    Marriage.objects.create(owner=user, husband=husband, wife=me, year=2008)
    user.person = me
    user.save()
    return user, {"me": me, "dad": dad, "mum": mum, "husband": husband, "son": son}


class SearchTests(TestCase):
    def setUp(self):
        self.timur, _ = make_family()
        self.kamila, _ = cousin_account()

    def test_found_by_name_unless_hidden(self):
        self.assertEqual(services.search(self.timur, "Kamila"), [self.kamila])
        self.assertEqual(services.search(self.timur, "Камила"), [self.kamila])  # either script
        self.assertEqual(services.search(self.kamila, "Kamila"), [])            # never yourself
        self.kamila.discoverable = False
        self.kamila.save()
        self.assertEqual(services.search(self.timur, "Aliyeva"), [])
        self.assertEqual(services.search(self.timur, "@kamila"), [self.kamila])
        self.assertEqual(services.search(self.timur, "kamila@example.com"), [self.kamila])

    def test_page_lists_results_with_their_state(self):
        self.client.force_login(self.timur)
        page = self.client.get(reverse("friends:list"), {"odam": "Kamila"})
        self.assertContains(page, "@kamila")
        self.assertContains(page, reverse("network:profile", args=["kamila"]))
        live = self.client.get(reverse("network:search_json"), {"q": "Kami"}).json()
        self.assertEqual(live["results"][0]["url"], reverse("network:profile", args=["kamila"]))


class ConnectionTests(TestCase):
    def setUp(self):
        self.timur, self.p = make_family()
        self.kamila, self.k = cousin_account()

    def send(self, **extra):
        self.client.force_login(self.timur)
        data = {"kind": "relative", "place": "existing", "person": self.p["cousin"].pk, "share": "on",
                "befriend": "on", "message": "Salom!"}
        data.update(extra)
        return self.client.post(reverse("network:request", args=["kamila"]), data)

    def test_request_accept_and_what_it_does(self):
        self.assertRedirects(self.send(), reverse("friends:list") + "#people", fetch_redirect_response=False)
        connection = Connection.objects.get()
        self.assertEqual(connection.sender_person, self.p["cousin"])
        note = Notification.objects.get(user=self.kamila, kind="connection_request")
        self.assertIn("Timur", note.text["title"])

        # Kamila answers: Timur is new in her tree, the son of her mother's brother… here simply a cousin by her mother.
        self.client.force_login(self.kamila)
        page = self.client.get(reverse("network:answer", args=[connection.pk]))
        self.assertContains(page, "Kamila")  # how Timur placed her
        response = self.client.post(reverse("network:answer", args=[connection.pk]), {
            "place": "new", "relation": "sibling", "anchor": self.k["me"].pk, "share": "on", "befriend": "on"})
        self.assertRedirects(response, reverse("network:connection", args=[connection.pk]))
        connection.refresh_from_db()
        self.assertEqual(connection.status, "accepted")
        timur_in_hers = connection.recipient_person
        self.assertEqual((timur_in_hers.owner, timur_in_hers.first_name, timur_in_hers.linked_user),
                         (self.kamila, "Timur", self.timur))
        self.assertEqual(timur_in_hers.birth_year, 1984)  # taken from Timur's own record
        self.assertTrue(Change.objects.filter(owner=self.kamila, person=timur_in_hers, action="created").exists())
        self.p["cousin"].refresh_from_db()
        self.assertEqual(self.p["cousin"].linked_user, self.kamila)
        # Each can open the other's tree, named from their own place in it.
        self.assertEqual(Membership.objects.get(owner=self.timur, member=self.kamila).person, self.p["cousin"])
        self.assertEqual(Membership.objects.get(owner=self.kamila, member=self.timur).person, timur_in_hers)
        tree = self.client.get(reverse("genealogy:tree_data_for", args=["timur"])).json()
        labels = {n["id"]: n["label"] for n in tree["nodes"]}
        self.assertEqual(labels[self.p["cousin"].pk], "Siz")
        self.assertEqual(labels[self.p["aunt"].pk], "Ona")  # Timur's aunt is Kamila's mother
        # Friends both ways, and the records known to be the same person.
        self.assertTrue(Contact.objects.filter(owner=self.timur, linked_user=self.kamila, birth_day=2).exists())
        self.assertTrue(Contact.objects.filter(owner=self.kamila, linked_user=self.timur).exists())
        self.assertEqual(PersonMatch.objects.filter(rejected=False).count(), 2)
        self.assertTrue(Notification.objects.filter(user=self.timur, kind="connection_accepted").exists())

        # Ending it removes the access it gave, keeps the people.
        self.client.post(reverse("network:disconnect", args=[connection.pk]))
        self.assertFalse(Membership.objects.exists())
        self.assertTrue(Person.objects.filter(pk=timur_in_hers.pk, linked_user=None).exists())
        self.assertFalse(Connection.objects.exists())

    def test_rules_for_requests(self):
        self.send()
        self.assertRedirects(self.send(), reverse("network:index"), fetch_redirect_response=False)  # no second request
        self.assertEqual(Connection.objects.count(), 1)
        self.client.force_login(self.kamila)
        connection = Connection.objects.get()
        # The other side sending one meets the waiting request instead.
        self.assertRedirects(self.client.get(reverse("network:request", args=["timur"])),
                             reverse("network:answer", args=[connection.pk]))
        self.client.post(reverse("network:answer", args=[connection.pk]), {"decline": "1"})
        connection.refresh_from_db()
        self.assertEqual(connection.status, "declined")
        self.assertContains(self.send(), "yaqinda rad etilgan")
        # A record that is someone else's account cannot stand for Kamila.
        other, _ = make_family(username="boshqa")
        self.p["cousin"].linked_user = other
        self.p["cousin"].save()
        connection.delete()
        self.assertContains(self.send(), "boshqa hisobga bogʻlangan")

    def test_friend_only_and_cancel(self):
        self.send(kind="friend", place="", person="")
        connection = Connection.objects.get()
        self.assertEqual((connection.kind, connection.sender_person), ("friend", None))
        self.client.post(reverse("network:cancel", args=[connection.pk]))
        self.assertFalse(Connection.objects.exists())


class MergeTests(TestCase):
    def setUp(self):
        self.timur, self.p = make_family()
        self.kamila, self.k = cousin_account()
        # Timur's cousin and Kamila's own record are one person.
        merge.link_match(self.p["cousin"], self.k["me"], self.timur)

    def test_analysis(self):
        plan = merge.analyse(self.kamila, self.timur)
        matched = {(m.source.pk, m.target.pk) for m in plan.matches}
        self.assertIn((self.k["dad"].pk, self.p["uncle_in_law"].pk), matched)   # Sherzod = Sherzod
        self.assertIn((self.k["mum"].pk, self.p["aunt"].pk), matched)           # Dilnoza = Dilnoza
        added = {a.source.first_name for a in plan.additions}
        self.assertEqual(added, {"Bobur", "Ali"})                              # husband and son are new
        fills = {(f.target.pk, f.field) for f in plan.fills}
        self.assertIn((self.p["cousin"].pk, "birth_place"), fills)
        self.assertIn((self.p["uncle_in_law"].pk, "occupation"), fills)
        self.assertTrue(any("1960" in c and "1961" in c for c in plan.conflicts))  # the aunt's year differs
        self.assertFalse(plan.fits)

    def test_apply_everything_then_nothing_is_left(self):
        done = merge.apply(self.kamila, self.timur, actor=self.timur)
        self.assertEqual(done["added"], 2)
        bobur = Person.objects.get(owner=self.timur, first_name="Bobur")
        ali = Person.objects.get(owner=self.timur, first_name="Ali")
        self.assertEqual((ali.father, ali.mother), (bobur, self.p["cousin"]))
        self.assertTrue(Marriage.objects.filter(owner=self.timur, husband=bobur, wife=self.p["cousin"], year=2008)
                        .exists())
        self.p["cousin"].refresh_from_db()
        self.assertEqual(self.p["cousin"].birth_place, "Andijon")
        self.p["aunt"].refresh_from_db()
        self.assertEqual(self.p["aunt"].birth_year, 1960)                       # a difference is never overwritten
        self.assertTrue(Change.objects.filter(owner=self.timur, person=ali, action="created").exists())
        again = merge.analyse(self.kamila, self.timur)
        self.assertEqual((again.additions, again.fills), ([], []))

    def test_only_what_is_ticked(self):
        plan = merge.analyse(self.kamila, self.timur)
        bobur = next(a for a in plan.additions if a.source.first_name == "Bobur")
        merge.apply(self.kamila, self.timur, keys=[bobur.key], actor=self.timur)
        self.assertTrue(Person.objects.filter(owner=self.timur, first_name="Bobur").exists())
        self.assertFalse(Person.objects.filter(owner=self.timur, first_name="Ali").exists())
        self.p["cousin"].refresh_from_db()
        self.assertEqual(self.p["cousin"].birth_place, "")

    def test_page_and_permissions(self):
        url = reverse("network:merge") + "?from=kamila&to=timur"
        self.client.force_login(self.timur)
        self.assertEqual(self.client.get(url).status_code, 403)               # Kamila's tree is not shared
        Membership.objects.create(owner=self.kamila, member=self.timur, role="viewer")
        page = self.client.get(url)
        self.assertContains(page, "Bobur")
        self.assertContains(page, "Dilnoza")
        response = self.client.post(reverse("network:merge"), {"from": "kamila", "to": "timur",
                                                               "item": [k for k in merge.analyse(self.kamila, self.timur).keys]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Person.objects.filter(owner=self.timur, first_name="Ali").exists())


class InviteMergeTests(TestCase):
    def test_relative_with_own_tree_is_offered_the_merge(self):
        timur, p = make_family()
        kamila, k = cousin_account()
        invite = Invite.objects.create(owner=timur, created_by=timur, role="editor", person=p["cousin"])
        self.client.force_login(kamila)
        response = self.client.post(reverse("accounts:invite", args=[invite.token]))
        self.assertRedirects(response, reverse("network:merge") + "?from=kamila&to=timur",
                             fetch_redirect_response=False)
        self.assertTrue(PersonMatch.objects.filter(first__in=[p["cousin"], k["me"]], second__in=[p["cousin"], k["me"]])
                        .exists())
        self.assertContains(self.client.get(response["Location"]), "Bobur")


class SmallFixesTests(TestCase):
    def test_this_is_me_cannot_change_who_you_are(self):
        user, p = make_family()
        self.client.force_login(user)
        page = self.client.get(reverse("genealogy:person", args=[p["older_brother"].pk]))
        self.assertNotContains(page, reverse("genealogy:set_self", args=[p["older_brother"].pk]))
        self.assertEqual(self.client.post(reverse("genealogy:set_self", args=[p["older_brother"].pk])).status_code, 403)
        user.refresh_from_db()
        self.assertEqual(user.person, p["me"])

    def test_one_menu_item_lights_up(self):
        user, _p = make_family()
        self.client.force_login(user)
        for name in ("friends:create", "genealogy:person_create", "genealogy:event_create", "friends:list"):
            html = self.client.get(reverse(name)).content.decode()
            nav = html.split('<nav class="sb-nav">', 1)[1].split("</nav>", 1)[0]
            self.assertEqual(nav.count('aria-current="page"'), 1, name)

    def test_photo_thumbnails(self):
        user, p = make_family()
        self.client.force_login(user)
        buf = BytesIO()
        Image.new("RGB", (1600, 1200), (200, 120, 40)).save(buf, "JPEG")
        p["me"].photo.save("katta.jpg", SimpleUploadedFile("katta.jpg", buf.getvalue(), "image/jpeg"))
        url = p["me"].photo.url
        small = self.client.get(url + "?s=t")
        self.assertEqual(small["Content-Type"], "image/jpeg")
        self.assertLess(len(small.content), len(self.client.get(url).content))
        self.assertEqual(max(Image.open(BytesIO(small.content)).size), 320)
        self.assertTrue(StoredFile.objects.filter(name=f"thumbs/{p['me'].photo.name}").exists())
        self.assertIn("?s=t", self.client.get(reverse("genealogy:people")).content.decode())
        name = p["me"].photo.name
        p["me"].photo.delete()
        self.assertFalse(StoredFile.objects.filter(name__in=[name, f"thumbs/{name}"]).exists())

    def test_gender_comes_from_the_tree(self):
        self.assertEqual(guess_gender("Muqaddamxon"), "female")
        self.assertEqual(guess_gender("Bobur", "Karimov"), "male")
        self.assertEqual(guess_gender("Zarina", "", "Karim qizi"), "female")
        user, p = make_family()
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("accounts:settings")), 'name="profile-gender"')
        data = {"first_name": "Timur", "last_name": "Nurmatov", "gender": "female", "birth_year": "1984"}
        self.client.post(reverse("genealogy:person_edit", args=[p["me"].pk]), data)
        user.refresh_from_db()
        self.assertEqual(user.gender, "female")


class BookTests(TestCase):
    def setUp(self):
        from apps.genealogy.models import Event

        self.user, self.p = make_family()
        memory = Event.objects.create(owner=self.user, title="Tugʻilishim", year=1984,
                                      description="Birinchi xatboshi.\n\nIkkinchi xatboshi.")
        memory.people.add(self.p["me"])
        Event.objects.create(owner=self.user, kind="wedding", title="Toʻy", description="Oila haqida.")
        self.client.force_login(self.user)

    def test_choices_page_and_every_kind_of_book(self):
        page = self.client.get(reverse("genealogy:book"))
        self.assertContains(page, 'value="ota"')
        sizes = {}
        for part in ("", "ota", "ona", "odam"):
            response = self.client.get(reverse("genealogy:family_book"), {"person": self.p["me"].pk, "qism": part})
            self.assertEqual(response["Content-Type"], "application/pdf", part)
            self.assertTrue(response.content.startswith(b"%PDF"))
            sizes[part] = len(response.content)
        self.assertLess(sizes["ota"], sizes[""])          # one side is a smaller book
        life = self.client.get(reverse("genealogy:person_pdf", args=[self.p["me"].pk]))
        self.assertTrue(life.content.startswith(b"%PDF"))

    def test_one_side_keeps_own_family_and_that_side(self):
        from apps.genealogy import pdf
        from apps.genealogy.kinship import Archive

        archive = Archive(self.user)
        paternal = pdf.book_people(archive, self.p["me"].pk, "paternal")
        self.assertIn(self.p["grandpa"].pk, paternal)
        self.assertIn(self.p["me"].pk, paternal)
        self.assertIn(self.p["cousin"].pk, paternal)
        self.assertNotIn(self.p["grandpa"].pk, pdf.book_people(archive, self.p["me"].pk, "maternal"))
