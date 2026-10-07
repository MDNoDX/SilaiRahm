"""The history of an archive: who added, changed or deleted what — and undo.

A change to a person stores the values from before the change, so an edit or
a deletion made by mistake (by the owner or a relative who helps) can be put
back with one click.
"""
from django.db import transaction
from django.utils import timezone

from apps.friends.models import Contact

from .models import Change, Event, Marriage, Media, Person

FIELDS = [
    "first_name", "last_name", "patronymic", "gender", "birth_year", "birth_month", "birth_day", "birth_place",
    "is_deceased", "death_year", "death_month", "death_day", "death_place", "burial_place", "occupation",
    "education", "biography", "life_story", "father_id", "mother_id",
]


def snapshot(person):
    data = {name: getattr(person, name) for name in FIELDS}
    data["photo"] = person.photo.name if person.photo else ""
    return data


def diff(before, person):
    """{field: [old, new]} for everything that differs from the snapshot."""
    after = snapshot(person)
    return {name: [before.get(name), value] for name, value in after.items() if before.get(name) != value}


def record(owner, actor, action, person=None, subject="", what="person", details=None, before=None):
    return Change.objects.create(
        owner=owner, actor=actor if getattr(actor, "pk", None) else None, action=action, what=what,
        person=person if person is not None and person.pk else None,
        subject=(subject or (person.short_name if person is not None else ""))[:250],
        details=details or {}, snapshot=before,
    )


def record_update(actor, person, before):
    """Log an edit if anything changed. `before` is snapshot(person) taken earlier."""
    changed = diff(before, person)
    if not changed:
        return None
    return record(person.owner, actor, Change.Action.UPDATED, person, details={"fields": changed},
                  before={name: before.get(name) for name in changed})


def snapshot_for_delete(person):
    """Everything needed to bring a deleted person back with their links."""
    return {
        "pk": person.pk,
        "fields": snapshot(person),
        "children_as_father": list(person.children_as_father.values_list("pk", flat=True)),
        "children_as_mother": list(person.children_as_mother.values_list("pk", flat=True)),
        "marriages": [{"husband": m.husband_id, "wife": m.wife_id, "year": m.year, "month": m.month, "day": m.day}
                      for m in Marriage.objects.filter(owner=person.owner).filter(husband=person)
                      | Marriage.objects.filter(owner=person.owner).filter(wife=person)],
        "events": list(person.events.values_list("pk", flat=True)),
        "contacts": [{"name": c.name, "how_met": c.how_met, "phone": c.phone, "birth_year": c.birth_year,
                      "birth_month": c.birth_month, "birth_day": c.birth_day, "note": c.note}
                     for c in person.friends.all()],
        "media": [{"kind": m.kind, "file": m.file.name, "caption": m.caption, "year": m.year}
                  for m in person.media.all()],
    }


def record_delete(actor, person):
    return record(person.owner, actor, Change.Action.DELETED, None, subject=person.short_name,
                  before=snapshot_for_delete(person))


def _apply(person, values):
    for name, value in values.items():
        if name == "photo":
            person.photo = value or ""
        elif name in ("father_id", "mother_id"):
            ok = value and Person.objects.filter(pk=value, owner=person.owner).exclude(pk=person.pk).exists()
            setattr(person, name, value if ok else None)
        else:
            setattr(person, name, value)


@transaction.atomic
def undo(change, actor):
    """Put back what `change` replaced. Returns the person, or None if not possible."""
    if not change.can_undo:
        return None
    if change.action == Change.Action.UPDATED:
        person = change.person
        if person is None:
            return None
        before = snapshot(person)
        _apply(person, change.snapshot)
        person.save()
        change.undone_at = timezone.now()
        change.save(update_fields=["undone_at"])
        record(person.owner, actor, Change.Action.RESTORED, person, details={"fields": diff(before, person)})
        return person

    data = change.snapshot
    person = Person(owner=change.owner)
    if not Person.objects.filter(pk=data["pk"]).exists():
        person.pk = data["pk"]  # old links and addresses work again
    _apply(person, data["fields"])
    person.save()
    people = Person.objects.filter(owner=change.owner)
    people.filter(pk__in=data["children_as_father"], father=None).update(father=person)
    people.filter(pk__in=data["children_as_mother"], mother=None).update(mother=person)
    for m in data["marriages"]:
        husband = person.pk if m["husband"] == data["pk"] else m["husband"]
        wife = person.pk if m["wife"] == data["pk"] else m["wife"]
        if people.filter(pk__in=[husband, wife]).count() == 2:
            Marriage.objects.get_or_create(owner=change.owner, husband_id=husband, wife_id=wife,
                                           defaults={"year": m["year"], "month": m["month"], "day": m["day"]})
    for event in Event.objects.filter(owner=change.owner, pk__in=data["events"]):
        event.people.add(person)
    for c in data["contacts"]:
        Contact.objects.create(owner=change.owner, person=person, **c)
    for m in data["media"]:
        Media.objects.create(owner=change.owner, person=person, kind=m["kind"], file=m["file"],
                             caption=m["caption"], year=m["year"])
    change.undone_at = timezone.now()
    change.save(update_fields=["undone_at"])
    record(change.owner, actor, Change.Action.RESTORED, person)
    return person
