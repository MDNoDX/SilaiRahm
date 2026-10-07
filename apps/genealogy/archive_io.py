"""Complete export and import of one user's family archive (JSON).

The export holds everything the user entered — people (with photos),
marriages, events (with their stories) and friends — so the archive can be kept as a
backup or moved to another server or account:

    python manage.py import_archive silairahm.json --user <username>
"""
import base64
import datetime

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.friends.models import Contact

from .models import Event, Marriage, Media, Person

FORMAT = "shajara-archive-1"  # kept from the old name, so earlier exports still load
PERSON_FIELDS = [
    "first_name", "last_name", "patronymic", "gender", "birth_year", "birth_month", "birth_day", "birth_place",
    "is_deceased", "death_year", "death_month", "death_day", "death_place", "burial_place", "occupation",
    "education", "biography", "life_story",
]


def _file(field):
    if not field:
        return None
    try:
        with field.open("rb") as f:
            data = f.read()
    except Exception:  # noqa: BLE001 - a missing file must not stop the export
        return None
    return {"name": field.name.rsplit("/", 1)[-1], "data": base64.b64encode(data).decode()}


def _photo(person):
    return _file(person.photo)


def export_archive(user):
    people = Person.objects.filter(owner=user).order_by("pk")
    return {
        "format": FORMAT,
        "exported_at": timezone.now().isoformat(),
        "owner": {"username": user.username, "first_name": user.first_name, "last_name": user.last_name,
                  "self": user.home_person_id},
        "people": [{"id": p.pk, "father": p.father_id, "mother": p.mother_id, "photo": _photo(p),
                    **{f: getattr(p, f) for f in PERSON_FIELDS}} for p in people],
        "marriages": [{"husband": m.husband_id, "wife": m.wife_id, "year": m.year, "month": m.month, "day": m.day}
                      for m in Marriage.objects.filter(owner=user)],
        "events": [{"kind": e.kind, "title": e.title, "year": e.year, "month": e.month, "day": e.day,
                    "place": e.place, "description": e.description, "every_year": e.every_year,
                    "recording": _file(e.recording), "people": list(e.people.values_list("pk", flat=True))}
                   for e in Event.objects.filter(owner=user).prefetch_related("people")],
        "friends": [{"person": c.person_id, "name": c.name, "how_met": c.how_met, "phone": c.phone,
                     "birth_year": c.birth_year, "birth_month": c.birth_month, "birth_day": c.birth_day,
                     "note": c.note} for c in Contact.objects.filter(owner=user)],
        "album": [{"person": m.person_id, "kind": m.kind, "caption": m.caption, "year": m.year,
                   "in_story": m.in_story, "file": _file(m.file)} for m in Media.objects.filter(owner=user)],
    }


@transaction.atomic
def import_archive(user, data):
    """Add everything from an export to `user`'s archive. Returns counts."""
    if data.get("format") != FORMAT:
        raise ValueError("Not a Silai Rahm archive file.")
    ids = {}
    for row in data["people"]:
        person = Person(owner=user, **{f: row.get(f) if row.get(f) is not None else Person._meta.get_field(f).get_default()
                                       for f in PERSON_FIELDS})
        person.save()
        if row.get("photo"):
            person.photo.save(row["photo"]["name"], ContentFile(base64.b64decode(row["photo"]["data"])), save=True)
        ids[row["id"]] = person
    for row in data["people"]:
        person = ids[row["id"]]
        person.father = ids.get(row.get("father"))
        person.mother = ids.get(row.get("mother"))
        person.save()
    for row in data.get("marriages", []):
        if row["husband"] in ids and row["wife"] in ids:
            Marriage.objects.get_or_create(owner=user, husband=ids[row["husband"]], wife=ids[row["wife"]],
                                           defaults={"year": row.get("year"), "month": row.get("month"),
                                                     "day": row.get("day")})
    kinds = dict(Event.Kind.choices)
    for row in data.get("events", []):
        people = [ids[i] for i in row.pop("people", []) if i in ids]
        recording = row.pop("recording", None)
        if row.get("kind") not in kinds:  # a type no longer offered: kept as a memory
            row["kind"] = Event.Kind.OTHER
        event = Event.objects.create(owner=user, **row)
        event.people.set(people)
        if recording:
            event.recording.save(recording["name"], ContentFile(base64.b64decode(recording["data"])), save=True)
    for row in data.get("stories", []):  # archives from before stories became events
        event = Event.objects.create(owner=user, kind=Event.Kind.OTHER, title=row["title"][:200],
                                     description=row["body"], year=row.get("year"))
        if ids.get(row.get("person")):
            event.people.add(ids[row["person"]])
    for row in data.get("friends", []):
        if row.get("person") in ids:
            Contact.objects.create(owner=user, **{**row, "person": ids[row["person"]]})
    for row in data.get("album", []):
        if row.get("person") in ids and row.get("file"):
            item = Media(owner=user, person=ids[row["person"]], kind=row.get("kind") or "photo",
                         caption=row.get("caption") or "", year=row.get("year"), in_story=bool(row.get("in_story")))
            item.file.save(row["file"]["name"], ContentFile(base64.b64decode(row["file"]["data"])), save=True)
    own = data.get("owner", {}).get("self")
    if own in ids and not user.person_id:
        user.person = ids[own]
        user.save(update_fields=["person"])
    return {"people": len(ids), "marriages": len(data.get("marriages", [])),
            "events": len(data.get("events", [])) + len(data.get("stories", [])), "friends": len(data.get("friends", []))}


def export_filename():
    return f"silairahm-{datetime.date.today().isoformat()}.json"
