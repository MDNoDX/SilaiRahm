"""Every page, as every kind of visitor: nothing may fail with a server error.

The crawl walks the URL list itself, so a new page is covered the day it is
added. Each visitor is a different state of an account: the owner of a
family tree, a newcomer with an empty tree, someone who has not finished the
profile, a relative who can only view a shared tree, one who can edit it,
and a guest.
"""
import datetime
import traceback

from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver

from apps.accounts.models import Invite, Membership, User
from apps.accounts.sharing import switch_archive
from apps.friends.models import Contact
from apps.genealogy import history
from apps.genealogy.models import Event, Marriage, Media, Person
from apps.notify.models import Notification

from .helpers import PASSWORD, make_family

# Pages that are not for people (or not ours): skipped.
SKIP_PREFIXES = ("admin/", "accounts/", "cron/", "telegram/", "ilova/kirish/tugatish/")
# Pages that only answer POST requests: a GET must be turned away, not crash.
OK = {200, 301, 302, 303, 400, 403, 404, 405, 410}


def patterns(resolver=None, prefix=""):
    for p in (resolver or get_resolver()).url_patterns:
        if isinstance(p, URLResolver):
            yield from patterns(p, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


class CrawlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.p = make_family()
        cls.owner.is_superuser = True
        cls.owner.save()
        me = cls.p["me"]
        cls.marriage = Marriage.objects.filter(husband=me).first()
        cls.event = Event.objects.create(owner=cls.owner, kind="wedding", year=2010, month=5, day=1)
        cls.event.people.add(me)
        cls.contact = Contact.objects.create(owner=cls.owner, person=me, name="Doʻst", birth_month=3, birth_day=8)
        cls.media = Media.objects.create(owner=cls.owner, person=me, kind="document", file="albom/x.pdf",
                                         uploaded_by=cls.owner)
        cls.change = history.record(cls.owner, cls.owner, "updated", person=me)
        cls.notification = Notification.objects.create(user=cls.owner, key="k", kind="birthday",
                                                       occasion_date=datetime.date(2026, 9, 27))
        cls.invite = Invite.objects.create(owner=cls.owner, created_by=cls.owner, role="editor")

        cls.newcomer = User.objects.create_user("yangi", "yangi@example.com", PASSWORD, first_name="Yangi",
                                                gender="male")
        cls.newcomer.person = Person.objects.create(owner=cls.newcomer, first_name="Yangi", gender="male")
        cls.newcomer.save()
        cls.unfinished = User.objects.create_user("chala", "chala@example.com", PASSWORD)

        cls.viewer, _ = make_family(username="korar")
        cls.editor, _ = make_family(username="tahrir")
        for user, role, person in ((cls.viewer, "viewer", cls.p["cousin"]), (cls.editor, "editor", None)):
            Membership.objects.create(owner=cls.owner, member=user, role=role, person=person)
            switch_archive(user, cls.owner)
        cls.membership = Membership.objects.get(member=cls.viewer)

    def args_for(self, route, name):
        """Real objects for the <int:pk> and other parts of a route."""
        values = {
            "genealogy:marriage_edit": {"pk": self.marriage.pk},
            "genealogy:media_delete": {"pk": self.media.pk},
            "genealogy:media_portrait": {"pk": self.media.pk},
            "genealogy:history_undo": {"pk": self.change.pk},
            "accounts:invite_revoke": {"pk": self.invite.pk},
            "accounts:member_update": {"pk": self.membership.pk},
            "notify:open": {"pk": self.notification.pk},
        }.get(name)
        if values:
            return values
        out = {}
        if "<int:pk>" in route:
            out["pk"] = (self.event.pk if route.startswith("voqealar/")
                         else self.contact.pk if route.startswith("dostlar/") else self.p["me"].pk)
        if "<int:user_id>" in route:
            out["user_id"] = self.owner.pk
        if "<str:username>" in route:
            out["username"] = self.owner.username
        if "<str:token>" in route:
            out["token"] = self.invite.token if name == "accounts:invite" else "yoq"
        if "<token>" in route:
            out["token"] = "yoq-yoq"
        if "<uidb64>" in route:
            out["uidb64"] = "MQ"
        if "<path:name>" in route:
            out["name"] = "albom/x.pdf"
        return out

    def crawl(self, user, label):
        from django.urls import reverse

        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        failures = []
        for route, pattern in patterns():
            if route.startswith(SKIP_PREFIXES) or not pattern.name:
                continue
            name = self.qualified(pattern)
            try:
                url = reverse(name, kwargs=self.args_for(route, name))
            except Exception as exc:  # noqa: BLE001 - a route the crawl cannot build is a failure too
                failures.append(f"{label}: cannot build {route} ({exc})")
                continue
            for query in ("", "?q=a&person=1&a=1&b=2&relation=child&f=nodate&tartib=abc&all=1"):
                try:
                    response = self.client.get(url + query)
                except Exception as exc:  # noqa: BLE001 - report every crash, not just the first
                    tb = traceback.extract_tb(exc.__traceback__)
                    ours = [f for f in tb if "/apps/" in f.filename or "/templates/" in f.filename] or tb
                    where = f"{ours[-1].filename.split('/family/')[-1]}:{ours[-1].lineno}"
                    failures.append(f"{label}: GET {url}{query} raised {type(exc).__name__}: {exc} ({where})")
                    continue
                if response.status_code not in OK:
                    failures.append(f"{label}: GET {url}{query} → {response.status_code}")
        return failures

    def qualified(self, pattern):
        for ns, names in self.namespaces.items():
            if pattern in names:
                return f"{ns}:{pattern.name}"
        return pattern.name

    @property
    def namespaces(self):
        if not hasattr(self, "_ns"):
            self._ns = {}
            for p in get_resolver().url_patterns:
                if isinstance(p, URLResolver) and p.namespace:
                    self._ns[p.namespace] = set(self._walk(p))
        return self._ns

    def _walk(self, resolver):
        for p in resolver.url_patterns:
            if isinstance(p, URLResolver):
                yield from self._walk(p)
            else:
                yield p

    def post_crawl(self, user, label):
        from django.urls import reverse

        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        failures = []
        for route, pattern in patterns():
            if route.startswith(SKIP_PREFIXES) or not pattern.name or pattern.name in ("logout", "set_language"):
                continue
            name = self.qualified(pattern)
            try:
                url = reverse(name, kwargs=self.args_for(route, name))
                response = self.client.post(url, {"q": "a", "role": "editor", "relation": "child"})
            except Exception as exc:  # noqa: BLE001
                tb = traceback.extract_tb(exc.__traceback__)
                ours = [f for f in tb if "/apps/" in f.filename] or tb
                failures.append(f"{label}: POST {route} raised {type(exc).__name__}: {exc} "
                                f"({ours[-1].filename.split('/family/')[-1]}:{ours[-1].lineno})")
                continue
            if response.status_code not in OK:
                failures.append(f"{label}: POST {url} → {response.status_code}")
        return failures

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_forms_turn_away_who_may_not(self):
        failures = self.post_crawl(None, "guest") + self.post_crawl(self.viewer, "viewer")
        self.assertEqual(failures, [], "\n".join(failures))
        self.assertTrue(Person.objects.filter(pk=self.p["me"].pk).exists())

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_no_page_fails(self):
        failures = []
        for user, label in ((self.owner, "owner"), (self.newcomer, "newcomer"), (self.unfinished, "unfinished"),
                            (self.viewer, "viewer"), (self.editor, "editor"), (None, "guest")):
            failures += self.crawl(user, label)
        self.assertEqual(failures, [], "\n".join(failures))
