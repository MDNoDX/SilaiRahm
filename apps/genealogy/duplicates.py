"""Finding people who were probably entered twice, and merging them.

Two records are a likely duplicate when the first names match (in either
script) and the surname or the year of birth matches too.
"""
from django.db import transaction

from apps.core.text import search_key
from apps.friends.models import Contact

from . import history
from .models import Change, Event, Marriage, Media, Person


def _keys(person):
    return search_key(person.first_name), search_key(person.last_name)


def _same(a_first, a_last, a_year, b_first, b_last, b_year):
    if not a_first or a_first != b_first:
        return False
    if a_year and b_year:
        return a_year == b_year and (not a_last or not b_last or a_last == b_last)
    if a_last and b_last:
        return a_last == b_last
    return False


def similar_to(owner, first_name, last_name="", birth_year=None, exclude_pk=None):
    """People already in the archive who look like the one being added."""
    first, last = search_key(first_name or ""), search_key(last_name or "")
    if not first:
        return []
    found = []
    for p in Person.objects.filter(owner=owner, search_key__contains=first).exclude(pk=exclude_pk):
        p_first, p_last = _keys(p)
        if _same(first, last, birth_year, p_first, p_last, p.birth_year):
            found.append(p)
    return found


def pairs(owner):
    """[(a, b), …] likely duplicates in the whole archive, each pair once."""
    people = list(Person.objects.filter(owner=owner).order_by("pk"))
    keyed = [(p, *_keys(p)) for p in people]
    by_first = {}
    for row in keyed:
        by_first.setdefault(row[1], []).append(row)
    out = []
    for group in by_first.values():
        for i, (a, a_first, a_last) in enumerate(group):
            for b, b_first, b_last in group[i + 1:]:
                if _same(a_first, a_last, a.birth_year, b_first, b_last, b.birth_year):
                    out.append((a, b))
    return out


MERGE_FIELDS = ["last_name", "patronymic", "birth_year", "birth_month", "birth_day", "birth_place",
                "death_year", "death_month", "death_day", "death_place", "burial_place", "occupation",
                "education", "biography", "life_story", "father_id", "mother_id"]


@transaction.atomic
def merge(keep, drop, actor):
    """Move everything from `drop` into `keep` and delete `drop`.

    Empty fields of `keep` are filled from `drop`; children, marriages,
    events, friends, album and account links move over.
    """
    if keep.pk == drop.pk or keep.owner_id != drop.owner_id:
        return None
    before = history.snapshot(keep)
    for name in MERGE_FIELDS:
        if not getattr(keep, name) and getattr(drop, name):
            value = getattr(drop, name)
            if name in ("father_id", "mother_id") and value == keep.pk:
                continue
            setattr(keep, name, value)
    if drop.is_deceased:
        keep.is_deceased = True
    if not keep.photo and drop.photo:
        keep.photo = drop.photo.name
    keep.save()

    Person.objects.filter(father=drop).exclude(pk=keep.pk).update(father=keep)
    Person.objects.filter(mother=drop).exclude(pk=keep.pk).update(mother=keep)
    for m in Marriage.objects.filter(husband=drop) | Marriage.objects.filter(wife=drop):
        husband = keep if m.husband_id == drop.pk else m.husband
        wife = keep if m.wife_id == drop.pk else m.wife
        if husband.pk != wife.pk and not Marriage.objects.filter(husband=husband, wife=wife).exists():
            Marriage.objects.filter(pk=m.pk).update(husband=husband, wife=wife)
    for event in Event.objects.filter(people=drop):
        event.people.add(keep)
    Contact.objects.filter(person=drop).update(person=keep)
    Media.objects.filter(person=drop).update(person=keep)
    Change.objects.filter(person=drop).update(person=keep)

    from apps.accounts.models import Membership, User

    if not User.objects.filter(person=keep).exists():
        User.objects.filter(person=drop).update(person=keep)
    User.objects.filter(own_person=drop).update(own_person=keep)
    Membership.objects.filter(person=drop).update(person=keep)

    name = drop.short_name
    drop.delete()
    history.record(keep.owner, actor, Change.Action.MERGED, keep, subject=f"{name} → {keep.short_name}",
                   details={"fields": history.diff(before, keep)})
    return keep
