"""Create a demo account with a fictional family (the Nurmatovs) for local testing.

    python manage.py seed_demo            # user "namuna", password below
    python manage.py seed_demo --reset    # delete and recreate the demo users

The family is fictional. One relative is entered in Cyrillic on purpose, to
show that search works across scripts and that stored names are never
transliterated.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Invite, Membership
from apps.genealogy.models import Event, Marriage, Person

DEMO_PASSWORD = "namuna-shajara-2026"  # local development only

PEOPLE = {
    # key: (first, last, patronymic, gender, (birth y, m, d), (death y, m, d) or None, birth place, occupation)
    "tursun": ("Tursun", "Nurmatov", "", "male", (1901, None, None), (1968, None, None), "Qoʻqon", "Dehqon"),
    "zulfiya": ("Zulfiya", "Nurmatova", "", "female", (1905, None, None), (1979, 3, None), "Namangan", ""),
    "karim": ("Karim", "Nurmatov", "Tursunovich", "male", (1928, 3, 14), (2001, 11, 2), "Namangan", "Oʻqituvchi"),
    "malika": ("Malika", "Nurmatova", "", "female", (1931, 6, 1), (2010, 1, 20), "Chust", "Tikuvchi"),
    "saodat": ("Saodat", "Sodiqova", "", "female", (1933, None, None), (2012, None, None), "Namangan", "Hamshira"),
    "hamid": ("Hamid", "Nurmatov", "", "male", (1936, None, None), (1941, None, None), "Namangan", ""),
    "bahodir": ("Bahodir", "Yusupov", "", "male", (1930, None, None), None, "", ""),
    "olim": ("Олим", "Содиқов", "", "male", (1929, None, None), (1995, None, None), "Андижон", "Муҳандис"),
    "rustam": ("Rustam", "Nurmatov", "Karimovich", "male", (1956, 5, 2), None, "Namangan", "Shifokor"),
    "gulnora": ("Gulnora", "Nurmatova", "", "female", (1959, 8, 19), None, "Toshkent", "Muallima"),
    "dilnoza": ("Dilnoza", "Aliyeva", "", "female", (1960, 2, 11), None, "Namangan", "Buxgalter"),
    "sherzod": ("Sherzod", "Aliyev", "", "male", (1957, None, None), None, "Fargʻona", ""),
    "farrukh": ("Farrux", "Nurmatov", "Karimovich", "male", (1965, 10, 30), None, "Namangan", "Muhandis"),
    "anvar": ("Anvar", "Yusupov", "", "male", (1953, None, None), None, "", ""),
    "nodira": ("Nodira", "Sodiqova", "", "female", (1962, None, None), None, "Andijon", ""),
    "timur": ("Timur", "Nurmatov", "Rustamovich", "male", (1984, 9, 27), None, "Toshkent", "Dasturchi"),
    "aziza": ("Aziza", "Nurmatova", "", "female", (1987, 4, 5), None, "Samarqand", "Dizayner"),
    "laylo": ("Laylo", "Nurmatova", "Rustamovna", "female", (1990, 12, 8), None, "Toshkent", "Talaba"),
    "kamila": ("Kamila", "Aliyeva", "", "female", (1985, None, None), None, "Namangan", ""),
    "samir": ("Samir", "Nurmatov", "Timurovich", "male", (2012, 7, 16), None, "Toshkent", ""),
}
PARENTS = {  # child: (father, mother)
    "karim": ("tursun", "zulfiya"), "saodat": ("tursun", "zulfiya"), "hamid": ("tursun", "zulfiya"),
    "rustam": ("karim", "malika"), "dilnoza": ("karim", "malika"), "farrukh": ("karim", "malika"),
    "anvar": ("bahodir", "saodat"), "nodira": ("olim", "saodat"),
    "timur": ("rustam", "gulnora"), "laylo": ("rustam", "gulnora"),
    "kamila": ("sherzod", "dilnoza"), "samir": ("timur", "aziza"),
}
MARRIAGES = [  # (husband, wife, year, divorced)
    ("tursun", "zulfiya", 1924, False), ("karim", "malika", 1953, False),
    ("bahodir", "saodat", 1951, True), ("olim", "saodat", 1958, False),
    ("rustam", "gulnora", 1982, False), ("sherzod", "dilnoza", 1983, False),
    ("timur", "aziza", 2010, False),
]
BIOGRAPHIES = {
    "karim": "Karim Tursunovich Namanganda tugʻilgan. Qirq yil davomida maktabda tarix fanidan dars bergan.",
    "tursun": "Oila rivoyatiga koʻra, Nurmatovlar Namanganga Qoʻqon tomondan koʻchib kelgan.",
}
STORIES = [
    ("Bobomning bogʻi", "karim", 1975, "Har yozda butun oila Chustdagi bogʻda yigʻilardi. Bobom oʻrik koʻchatlarini oʻzi ekkan edi."),
    ("Toʻy haqida xotira", "rustam", 1982, "Otam va onamning toʻyi Toshkentda, kuzning iliq kunida boʻlgan."),
]


class Command(BaseCommand):
    help = "Create demo users with a fictional family tree (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo users first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        names = ["namuna", "dilnoza_a", "anvar_y"]
        if opts["reset"]:
            User.objects.filter(username__in=names).delete()
        if User.objects.filter(username="namuna").exists():
            self.stdout.write("Demo user already exists; use --reset to recreate it.")
            return

        user = User.objects.create_user(
            "namuna", "namuna@example.com", DEMO_PASSWORD,
            first_name="Timur", last_name="Nurmatov", gender="male", preferred_language="uz",
        )
        people = {}
        for key, (first, last, patr, gender, birth, death, place, job) in PEOPLE.items():
            people[key] = Person.objects.create(
                owner=user, first_name=first, last_name=last, patronymic=patr, gender=gender,
                birth_year=birth[0], birth_month=birth[1], birth_day=birth[2], birth_place=place,
                is_deceased=death is not None,
                death_year=death[0] if death else None, death_month=death[1] if death else None,
                death_day=death[2] if death else None,
                occupation=job, biography=BIOGRAPHIES.get(key, ""),
            )
        for child, (father, mother) in PARENTS.items():
            p = people[child]
            p.father, p.mother = people[father], people[mother]
            p.save()
        for husband, wife, year, divorced in MARRIAGES:
            Marriage.objects.create(owner=user, husband=people[husband], wife=people[wife], year=year, is_divorced=divorced)
        for title, key, year, body in STORIES:
            event = Event.objects.create(owner=user, kind=Event.Kind.OTHER, title=title, year=year, description=body)
            event.people.add(people[key])
        user.person = people["timur"]
        user.save()

        # A relative with view access (Cyrillic interface) and an open invite.
        friend = User.objects.create_user(
            "dilnoza_a", "dilnoza@example.com", DEMO_PASSWORD,
            first_name="Дилноза", last_name="Алиева", gender="female", preferred_language="uz-cyrl",
        )
        friend.person = Person.objects.create(owner=friend, first_name="Дилноза", last_name="Алиева", gender="female",
                                              birth_year=1960)
        friend.save()
        Membership.objects.create(owner=user, member=friend, role="viewer")
        other = User.objects.create_user(
            "anvar_y", "anvar@example.com", DEMO_PASSWORD, first_name="Anvar", last_name="Yusupov", gender="male",
        )
        other.person = Person.objects.create(owner=other, first_name="Anvar", last_name="Yusupov", gender="male")
        other.save()
        Invite.objects.create(owner=user, created_by=user, role="editor")

        self.stdout.write(self.style.SUCCESS(
            f"Demo data created: {len(people)} people. Users: namuna, dilnoza_a, anvar_y "
            "(password in apps/genealogy/management/commands/seed_demo.py)."
        ))
