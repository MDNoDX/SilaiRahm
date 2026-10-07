"""Dates worth remembering in a user's family archive.

`occasions(user, start, end)` lists birthdays, memorial days, wedding
anniversaries, friends' birthdays, family events and the muchal year (at
Navroʻz) that fall between two dates. It feeds the reminders, the dashboard
and the "Upcoming dates" page.
"""
import calendar
import datetime
from dataclasses import dataclass, field

from django.urls import reverse

from apps.core.muchal import animal_index, muchal
from apps.friends.models import Contact
from apps.genealogy.models import Event, Marriage, Person

ICONS = {
    "birthday": "🎂", "friend_birthday": "🎈", "memorial": "🕯️", "anniversary": "💍",
    "event": "📅", "muchal": "🌱", "connection_request": "🤝", "connection_accepted": "🤝",
    "follow_request": "👤", "new_follower": "👤", "follow_accepted": "👤",
}


@dataclass
class Occasion:
    kind: str
    date: datetime.date
    key: str
    params: dict = field(default_factory=dict)
    url: str = ""
    person: int | None = None  # the relative it is about (for their photo)

    @property
    def icon(self):
        return ICONS.get(self.kind, "📅")


def on(year, month, day):
    """The date in `year`; 29 February falls on the 28th in other years."""
    if month == 2 and day == 29 and not calendar.isleap(year):
        day = 28
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _yearly(month, day, start, end):
    for year in range(start.year, end.year + 1):
        d = on(year, month, day)
        if d and start <= d <= end:
            yield d


def occasions(user, start, end, prefs=None, archive=None):
    """All occasions in the archive owned by `user` from `start` to `end`
    (inclusive), sorted by date. A page that has already loaded the archive
    (`kinship.Archive`) passes it in, so the people are not read twice."""
    want = (lambda name: getattr(prefs, name, True)) if prefs else (lambda name: True)
    out = []
    people = list(archive.people.values()) if archive is not None else list(Person.objects.filter(owner=user))
    by_pk = {p.pk: p for p in people}

    for p in people:
        if want("birthdays") and not p.is_deceased and p.birth_month and p.birth_day:
            for d in _yearly(p.birth_month, p.birth_day, start, end):
                age = d.year - p.birth_year if p.birth_year else None
                out.append(Occasion("birthday", d, f"birthday:{p.pk}:{d.year}",
                                    {"name": p.short_name, "age": age}, p.get_absolute_url(), p.pk))
        if want("memorials") and p.is_deceased and p.death_month and p.death_day:
            for d in _yearly(p.death_month, p.death_day, start, end):
                years = d.year - p.death_year if p.death_year else None
                if years == 0:
                    continue
                out.append(Occasion("memorial", d, f"memorial:{p.pk}:{d.year}",
                                    {"name": p.short_name, "years": years}, p.get_absolute_url(), p.pk))

    if want("anniversaries"):
        if archive is not None:
            marriages = [m for m in archive.marriages if not m.is_divorced]
            for m in marriages:  # the people are already here: no second query
                m.husband, m.wife = by_pk.get(m.husband_id) or m.husband, by_pk.get(m.wife_id) or m.wife
        else:
            marriages = Marriage.objects.filter(owner=user, is_divorced=False).select_related("husband", "wife")
        for m in marriages:
            if not (m.month and m.day) or m.husband.is_deceased or m.wife.is_deceased:
                continue
            for d in _yearly(m.month, m.day, start, end):
                years = d.year - m.year if m.year else None
                if years == 0:
                    continue
                out.append(Occasion("anniversary", d, f"anniversary:{m.pk}:{d.year}",
                                    {"names": f"{m.husband.short_name} · {m.wife.short_name}", "years": years},
                                    m.husband.get_absolute_url(), m.husband_id))

    if want("friends"):
        for c in Contact.objects.filter(owner=user).select_related("person"):
            if c.birth_month and c.birth_day:
                for d in _yearly(c.birth_month, c.birth_day, start, end):
                    age = d.year - c.birth_year if c.birth_year else None
                    out.append(Occasion("friend_birthday", d, f"friend:{c.pk}:{d.year}",
                                        {"name": c.name, "whose": c.person.short_name, "age": age},
                                        reverse("friends:list")))

    if want("events"):
        for e in Event.objects.filter(owner=user).exclude(month=None).exclude(day=None):
            if e.every_year:
                dates = list(_yearly(e.month, e.day, start, end))
            else:
                dates = [e.date] if e.date and start <= e.date <= end else []
            for d in dates:
                years = d.year - e.year if e.every_year and e.year else None
                out.append(Occasion("event", d, f"event:{e.pk}:{d.year}",
                                    {"title": e.title, "kind": e.kind, "years": years or None,
                                     "place": e.place}, e.get_absolute_url()))

    if want("muchal"):
        for year in range(start.year, end.year + 1):
            d = datetime.date(year, 3, 21)
            if not start <= d <= end:
                continue
            animal = animal_index(year)
            names = [p.short_name for p in people
                     if not p.is_deceased and p.birth_year and p.birth_year < year
                     and (info := muchal(p.birth_year, p.birth_month, p.birth_day))
                     and animal_index(info["year"]) == animal]
            if names:
                out.append(Occasion("muchal", d, f"muchal:{year}", {"animal": animal, "names": names},
                                    reverse("genealogy:upcoming")))

    out.sort(key=lambda o: (o.date, o.kind, o.key))
    return out
