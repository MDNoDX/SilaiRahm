"""What the assistant may propose, and how a proposal is carried out.

The assistant never changes anything by itself: it proposes an action, the
person sees it as a card and presses "Add". Only then `run()` writes it,
with the same checks and history as the site's own forms.
"""
from django.db import transaction
from django.utils.translation import gettext as _

from apps.core.text import normalize_apostrophes
from apps.genealogy import history
from apps.genealogy.kinship import Archive
from apps.genealogy.models import Change, Event, Person
from apps.genealogy.relations import RELATIONS, attach, problem

EVENT_KINDS = [k for k, _label in Event.Kind.choices]
PERSON_LABELS = {f.name: f.verbose_name for f in Person._meta.fields}
PERSON_LABELS["life_story_append"] = Person._meta.get_field("life_story").verbose_name
PERSON_FIELDS = ["birth_place", "occupation", "education", "death_place", "burial_place", "patronymic", "last_name"]
NUMBER_FIELDS = ["birth_year", "birth_month", "birth_day", "death_year", "death_month", "death_day"]

TOOLS = [
    {"name": "add_event",
     "description": "Propose to add a family event or memory (a story) to the family tree. Use for anything the "
                    "person tells about their life or family: a wedding, a birth, a celebration, a memory.",
     "parameters": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": EVENT_KINDS, "description": "Type; 'other' for memories and stories."},
         "title": {"type": "string", "description": "Short title, in the person's language."},
         "story": {"type": "string", "description": "The story, carefully edited, keeping the person's own words."},
         "people_ids": {"type": "array", "items": {"type": "integer"}, "description": "Ids of the people it is about."},
         "year": {"type": "integer", "description": "Only if the user said the year."},
         "month": {"type": "integer", "description": "Only if the user said the month; never guess."},
         "day": {"type": "integer", "description": "Only if the user said the day; never guess."},
         "place": {"type": "string"}},
         "required": ["kind", "title", "people_ids"]}},
    {"name": "add_relative",
     "description": "Propose to add a new relative to the family tree next to an existing person.",
     "parameters": {"type": "object", "properties": {
         "anchor_id": {"type": "integer", "description": "Id of the existing person."},
         "relation": {"type": "string", "enum": list(RELATIONS),
                      "description": "What the new person is to the anchor."},
         "first_name": {"type": "string"}, "last_name": {"type": "string"},
         "gender": {"type": "string", "enum": ["male", "female"]},
         "birth_year": {"type": "integer"}, "birth_month": {"type": "integer"}, "birth_day": {"type": "integer"},
         "birth_place": {"type": "string"}, "is_deceased": {"type": "boolean"}},
         "required": ["anchor_id", "relation", "first_name", "gender"]}},
    {"name": "update_person",
     "description": "Propose to fill in or correct details of an existing person, or to add text to their life "
                    "story. Only change what the person said.",
     "parameters": {"type": "object", "properties": {
         "person_id": {"type": "integer"},
         "birth_place": {"type": "string"}, "occupation": {"type": "string"}, "education": {"type": "string"},
         "patronymic": {"type": "string"}, "last_name": {"type": "string"},
         "birth_year": {"type": "integer"}, "birth_month": {"type": "integer"}, "birth_day": {"type": "integer"},
         "death_year": {"type": "integer"}, "death_month": {"type": "integer"}, "death_day": {"type": "integer"},
         "death_place": {"type": "string"}, "burial_place": {"type": "string"},
         "life_story_append": {"type": "string", "description": "Text to add at the end of their life story."}},
         "required": ["person_id"]}},
]


class Refused(Exception):
    pass


def _as_id(value):
    """Models send ids as 23, "23" or "#23"."""
    text = str(value).strip().lstrip("#")
    return int(text) if text.isdigit() else None


def clean_args(args):
    """The proposal as it will be shown and saved: ids as numbers, no empty values."""
    out = {k: v for k, v in args.items() if v not in (None, "", [])}
    for key in ("anchor_id", "person_id"):
        if key in out:
            out[key] = _as_id(out[key])
    if "people_ids" in out:
        ids = out["people_ids"] if isinstance(out["people_ids"], list) else [out["people_ids"]]
        out["people_ids"] = [i for i in dict.fromkeys(_as_id(v) for v in ids) if i is not None]
    return out


def _person(owner, pk):
    person = Person.objects.filter(owner=owner, pk=pk).first() if str(pk).isdigit() else None
    if person is None:
        raise Refused(_("Person not found."))
    return person


def _number(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def describe(owner, name, args):
    """A sentence for the confirmation card, in the reader's language."""
    people = {p.pk: p.short_name for p in Person.objects.filter(owner=owner)}
    if name == "add_event":
        who = ", ".join(people.get(i, "?") for i in args.get("people_ids") or [])
        return _("Add the event “{title}” ({who}).").format(title=args.get("title", ""), who=who or "—")
    if name == "add_relative":
        return _("Add {name} as {relation} of {anchor}.").format(
            name=" ".join(x for x in (args.get("first_name"), args.get("last_name")) if x),
            relation=str(dict(_relation_names()).get(args.get("relation"), args.get("relation", ""))),
            anchor=people.get(args.get("anchor_id"), "?"))
    if name == "update_person":
        fields = [str(PERSON_LABELS.get(k, k)) for k in args if k != "person_id"]
        return _("Update {name}: {fields}.").format(name=people.get(args.get("person_id"), "?"),
                                                    fields=", ".join(fields))
    return name


def _relation_names():
    from apps.genealogy.terminology import ADD_RELATION

    return ADD_RELATION.items()


@transaction.atomic
def run(owner, actor, name, args):
    """Carry out one confirmed proposal; returns the object to open."""
    if name == "add_event":
        kind = args.get("kind") if args.get("kind") in EVENT_KINDS else Event.Kind.OTHER
        event = Event.objects.create(
            owner=owner, kind=kind, title=normalize_apostrophes(str(args.get("title", "")))[:200],
            description=str(args.get("story", "")), place=normalize_apostrophes(str(args.get("place", "")))[:200],
            year=_number(args.get("year"), 1000, 2200), month=_number(args.get("month"), 1, 12),
            day=_number(args.get("day"), 1, 31))
        event.people.set(Person.objects.filter(owner=owner, pk__in=[i for i in args.get("people_ids") or []
                                                                     if str(i).isdigit()]))
        history.record(owner, actor, Change.Action.CREATED, subject=event.display_title, what="event")
        return event
    if name == "add_relative":
        anchor = _person(owner, args.get("anchor_id"))
        relation = args.get("relation")
        if relation not in RELATIONS:
            raise Refused(_("Choose the relation."))
        new = Person(owner=owner, first_name=normalize_apostrophes(str(args.get("first_name", "")).strip())[:100],
                     last_name=normalize_apostrophes(str(args.get("last_name", "")).strip())[:100],
                     gender=args.get("gender") if args.get("gender") in ("male", "female") else "male",
                     birth_year=_number(args.get("birth_year"), 1000, 2200),
                     birth_month=_number(args.get("birth_month"), 1, 12), birth_day=_number(args.get("birth_day"), 1, 31),
                     birth_place=normalize_apostrophes(str(args.get("birth_place", "")))[:200],
                     is_deceased=bool(args.get("is_deceased")))
        if not new.first_name:
            raise Refused(_("Choose an existing person or enter the new person's first name."))
        error = problem(anchor, new, relation, Archive(owner))
        if error:
            raise Refused(error)
        new.save()
        before = history.snapshot(anchor)
        attach(anchor, new, relation, owner)
        history.record(owner, actor, Change.Action.CREATED, new, details={"relation": relation, "to": anchor.short_name})
        anchor.refresh_from_db()
        history.record_update(actor, anchor, before)
        return new
    if name == "update_person":
        person = _person(owner, args.get("person_id"))
        before = history.snapshot(person)
        for field in PERSON_FIELDS:
            if args.get(field):
                setattr(person, field, normalize_apostrophes(str(args[field]))[:200])
        for field in NUMBER_FIELDS:
            if args.get(field) is not None:
                low, high = (1000, 2200) if field.endswith("year") else (1, 12) if field.endswith("month") else (1, 31)
                value = _number(args[field], low, high)
                if value is not None:
                    setattr(person, field, value)
        if args.get("life_story_append"):
            person.life_story = (person.life_story.rstrip() + "\n\n" + str(args["life_story_append"]).strip()).strip()
        person.save()
        history.record_update(actor, person, before)
        return person
    raise Refused(_("Access denied."))
