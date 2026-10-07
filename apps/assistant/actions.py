"""What the assistant may propose, and how a proposal is carried out.

The assistant never changes anything by itself: it proposes an action, the
person sees it as a card and presses the button. Only then `run()` writes it,
with the same checks and history as the site's own forms (a deleted person
can be restored from History, like everywhere else on the site).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.core.text import normalize_apostrophes
from apps.genealogy import history
from apps.genealogy.kinship import Archive
from apps.genealogy.models import Change, Event, Marriage, Person
from apps.genealogy.relations import RELATIONS, attach, problem, wife_is_married

EVENT_KINDS = [k for k, _label in Event.Kind.choices]
PERSON_LABELS = {f.name: f.verbose_name for f in Person._meta.fields}
PERSON_LABELS["life_story_append"] = Person._meta.get_field("life_story").verbose_name
EVENT_LABELS = {f.name: f.verbose_name for f in Event._meta.fields}
PERSON_FIELDS = ["birth_place", "occupation", "education", "death_place", "burial_place", "patronymic", "last_name",
                 "first_name"]
NUMBER_FIELDS = ["birth_year", "birth_month", "birth_day", "death_year", "death_month", "death_day"]
# Proposals that change the family tree need the right to edit it; a message for a relative does not.
EDITING = {"add_event", "update_event", "delete_event", "add_relative", "link_relatives", "update_person",
           "delete_person", "set_divorced"}
DELETING = {"delete_event", "delete_person"}

_DATE = {"year": {"type": "integer", "description": "Only if the user said the year."},
         "month": {"type": "integer", "description": "Only if the user said the month; never guess."},
         "day": {"type": "integer", "description": "Only if the user said the day; never guess."}}

TOOLS = [
    {"name": "add_event",
     "description": "Propose to add a family event or memory (a story). Use for anything the user tells about their "
                    "life or family: a wedding, a birth, a celebration, a trip, a memory.",
     "parameters": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": EVENT_KINDS, "description": "Type; 'other' for memories and stories."},
         "title": {"type": "string", "description": "Short title, in the user's language."},
         "story": {"type": "string", "description": "The story, lightly edited, keeping the user's own words."},
         "people_ids": {"type": "array", "items": {"type": "integer"}, "description": "Ids of the people it is about."},
         **_DATE, "place": {"type": "string"}},
         "required": ["kind", "title", "people_ids"]}},
    {"name": "update_event",
     "description": "Propose to correct an existing event (EVENT #id): its title, story, date, place, type or people. "
                    "Only send what changes. story replaces the text; story_append adds to the end.",
     "parameters": {"type": "object", "properties": {
         "event_id": {"type": "integer"}, "title": {"type": "string"}, "story": {"type": "string"},
         "story_append": {"type": "string"}, "kind": {"type": "string", "enum": EVENT_KINDS},
         "people_ids": {"type": "array", "items": {"type": "integer"}}, **_DATE, "place": {"type": "string"}},
         "required": ["event_id"]}},
    {"name": "delete_event",
     "description": "Propose to delete an event or memory (EVENT #id). Only when the user clearly asks for it.",
     "parameters": {"type": "object", "properties": {"event_id": {"type": "integer"}}, "required": ["event_id"]}},
    {"name": "add_relative",
     "description": "Propose to add a NEW person to the family tree next to an existing person.",
     "parameters": {"type": "object", "properties": {
         "anchor_id": {"type": "integer", "description": "Id of the existing person."},
         "relation": {"type": "string", "enum": list(RELATIONS),
                      "description": "What the new person is to the anchor."},
         "first_name": {"type": "string"}, "last_name": {"type": "string", "description": "Only if known."},
         "gender": {"type": "string", "enum": ["male", "female"]},
         "birth_year": {"type": "integer"}, "birth_month": {"type": "integer"}, "birth_day": {"type": "integer"},
         "birth_place": {"type": "string"}, "is_deceased": {"type": "boolean"}},
         "required": ["anchor_id", "relation", "first_name", "gender"]}},
    {"name": "link_relatives",
     "description": "Propose to connect two people who are BOTH already in the tree: other_id becomes the relation "
                    "(father, mother, spouse, child, sibling) of person_id.",
     "parameters": {"type": "object", "properties": {
         "person_id": {"type": "integer"}, "relation": {"type": "string", "enum": list(RELATIONS)},
         "other_id": {"type": "integer"}},
         "required": ["person_id", "relation", "other_id"]}},
    {"name": "update_person",
     "description": "Propose to fill in or correct details of an existing person, or to add text to their life "
                    "story. Only send what the user said.",
     "parameters": {"type": "object", "properties": {
         "person_id": {"type": "integer"}, "first_name": {"type": "string"},
         "birth_place": {"type": "string"}, "occupation": {"type": "string"}, "education": {"type": "string"},
         "patronymic": {"type": "string"}, "last_name": {"type": "string"},
         "birth_year": {"type": "integer"}, "birth_month": {"type": "integer"}, "birth_day": {"type": "integer"},
         "is_deceased": {"type": "boolean"},
         "death_year": {"type": "integer"}, "death_month": {"type": "integer"}, "death_day": {"type": "integer"},
         "death_place": {"type": "string"}, "burial_place": {"type": "string"},
         "life_story_append": {"type": "string", "description": "Text to add at the end of their life story."}},
         "required": ["person_id"]}},
    {"name": "delete_person",
     "description": "Propose to delete a person from the tree (it can be restored from History). Only when the "
                    "user clearly asks; if several people share the name, ask which one first.",
     "parameters": {"type": "object", "properties": {"person_id": {"type": "integer"}}, "required": ["person_id"]}},
    {"name": "set_divorced",
     "description": "Propose to mark a marriage as divorced, or as not divorced.",
     "parameters": {"type": "object", "properties": {
         "husband_id": {"type": "integer"}, "wife_id": {"type": "integer"}, "divorced": {"type": "boolean"}},
         "required": ["husband_id", "wife_id", "divorced"]}},
    {"name": "leave_message",
     "description": "Propose to leave a message (greetings, a word, a joke) from the user for another family "
                    "member who has an account; it is passed on word for word when they next talk to you.",
     "parameters": {"type": "object", "properties": {
         "recipient": {"type": "string", "description": "Their username (from the ACCOUNT lines), without @."},
         "text": {"type": "string", "description": "The message exactly as the user wants it said."}},
         "required": ["recipient", "text"]}},
]


class Refused(Exception):
    pass


def tools_for(editing):
    return TOOLS if editing else [t for t in TOOLS if t["name"] not in EDITING]


def _as_id(value):
    """Models send ids as 23, "23" or "#23"."""
    text = str(value).strip().lstrip("#")
    return int(text) if text.isdigit() else None


def clean_args(args):
    """The proposal as it will be shown and saved: ids as numbers, no empty values."""
    out = {k: v for k, v in args.items() if v not in (None, "", [])}
    for key in ("anchor_id", "person_id", "other_id", "event_id", "husband_id", "wife_id"):
        if key in out:
            out[key] = _as_id(out[key])
    if "people_ids" in out:
        ids = out["people_ids"] if isinstance(out["people_ids"], list) else [out["people_ids"]]
        out["people_ids"] = [i for i in dict.fromkeys(_as_id(v) for v in ids) if i is not None]
    if "recipient" in out:
        out["recipient"] = str(out["recipient"]).strip().lstrip("@")
    return out


def _person(owner, pk):
    pk = _as_id(pk) if pk is not None else None
    person = Person.objects.filter(owner=owner, pk=pk).first() if pk else None
    if person is None:
        raise Refused(_("Person not found."))
    return person


def _event(owner, pk):
    pk = _as_id(pk) if pk is not None else None
    event = Event.objects.filter(owner=owner, pk=pk).first() if pk else None
    if event is None:
        raise Refused(_("The event was not found."))
    return event


def _number(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _text(value, size=200):
    return normalize_apostrophes(str(value or "").strip())[:size]


def _relation_names():
    from apps.genealogy.terminology import ADD_RELATION

    return dict(ADD_RELATION)


def reachable_accounts(user, owner):
    """Accounts the user may leave a message for: relatives in the open tree, family members, connections, follows."""
    from apps.accounts.models import Membership
    from apps.network.models import Connection, Follow

    ids = set(Person.objects.filter(owner=owner, linked_user__isnull=False).values_list("linked_user_id", flat=True))
    ids |= set(Membership.objects.filter(owner=owner).values_list("member_id", flat=True))
    ids |= set(Membership.objects.filter(member=user).values_list("owner_id", flat=True))
    ids.add(owner.pk)
    # Connected relatives, and those the user has asked to connect with or to follow (not yet answered).
    for a, b in Connection.objects.filter(Q(sender=user, status__in=["accepted", "pending"])
                                          | Q(recipient=user, status="accepted")).values_list("sender_id", "recipient_id"):
        ids |= {a, b}
    for a, b in Follow.objects.filter(Q(follower=user) | Q(followed=user, approved=True)).values_list(
            "follower_id", "followed_id"):
        ids |= {a, b}
    ids.discard(user.pk)
    return get_user_model().objects.filter(pk__in=ids, is_active=True)


def resolve_recipient(user, owner, value):
    """The account meant by "Muhammadqodir", "@Mukhammadkodir" or "akam": username first, then a close name."""
    from apps.core.text import search_key
    from apps.network.merge import _distance

    value = str(value or "").strip().lstrip("@")
    accounts = list(reachable_accounts(user, owner))
    exact = [a for a in accounts if a.username.lower() == value.lower()]
    if exact or not value:
        return exact[0] if exact else None
    key = search_key(value).replace(" ", "")
    scored = []
    for a in accounts:
        for name in (a.username, a.first_name, a.get_full_name()):
            other = search_key(name or "").replace(" ", "")
            if other and (other == key or _distance(other, key) <= max(1, len(key) // 6)):
                scored.append((_distance(other, key), a))
    scored.sort(key=lambda x: x[0])
    return scored[0][1] if scored else None


def describe(owner, name, args):
    """A sentence for the confirmation card, in the reader's language."""
    people = {p.pk: p.short_name for p in Person.objects.filter(owner=owner)}

    def who(key):
        return people.get(args.get(key), "?")

    relation = str(_relation_names().get(args.get("relation"), args.get("relation", "")))
    if name == "add_event":
        names = ", ".join(people.get(i, "?") for i in args.get("people_ids") or [])
        return _("Add the event “{title}” ({who}).").format(title=args.get("title", ""), who=names or "—")
    if name == "update_event":
        event = Event.objects.filter(owner=owner, pk=args.get("event_id")).first()
        fields = [str(EVENT_LABELS.get({"story": "description", "story_append": "description",
                                        "people_ids": "people"}.get(k, k), k)) for k in args if k != "event_id"]
        return _("Change the event “{title}”: {fields}.").format(
            title=event.display_title if event else "?", fields=", ".join(dict.fromkeys(fields)))
    if name == "delete_event":
        event = Event.objects.filter(owner=owner, pk=args.get("event_id")).first()
        return _("Delete the event “{title}”.").format(title=event.display_title if event else "?")
    if name == "add_relative":
        return _("Add {name} as {relation} of {anchor}.").format(
            name=" ".join(x for x in (args.get("first_name"), args.get("last_name")) if x), relation=relation,
            anchor=who("anchor_id"))
    if name == "link_relatives":
        return _("Make {other} the {relation} of {person}.").format(other=who("other_id"), relation=relation,
                                                                    person=who("person_id"))
    if name == "update_person":
        fields = [str(PERSON_LABELS.get(k, k)) for k in args if k != "person_id"]
        return _("Update {name}: {fields}.").format(name=who("person_id"), fields=", ".join(fields))
    if name == "delete_person":
        return _("Delete {name} from the family tree (can be restored from History).").format(name=who("person_id"))
    if name == "set_divorced":
        text = (_("Mark the marriage of {husband} and {wife} as divorced.") if args.get("divorced")
                else _("Mark the marriage of {husband} and {wife} as not divorced."))
        return text.format(husband=who("husband_id"), wife=who("wife_id"))
    if name == "leave_message":
        return _("Leave a message for @{recipient}: “{text}”").format(recipient=args.get("recipient", ""),
                                                                       text=args.get("text", ""))
    return name


@transaction.atomic
def run(owner, actor, name, args):
    """Carry out one confirmed proposal; returns what to open: an object, or a URL name."""
    if name == "add_event":
        kind = args.get("kind") if args.get("kind") in EVENT_KINDS else Event.Kind.OTHER
        event = Event.objects.create(
            owner=owner, kind=kind, title=_text(args.get("title")), description=str(args.get("story", "")).strip(),
            place=_text(args.get("place")), year=_number(args.get("year"), 1000, 2200),
            month=_number(args.get("month"), 1, 12), day=_number(args.get("day"), 1, 31))
        event.people.set(Person.objects.filter(owner=owner, pk__in=args.get("people_ids") or []))
        history.record(owner, actor, Change.Action.CREATED, subject=event.display_title, what="event")
        return event

    if name == "update_event":
        event = _event(owner, args.get("event_id"))
        if args.get("title"):
            event.title = _text(args["title"])
        if args.get("story"):
            event.description = str(args["story"]).strip()
        if args.get("story_append"):
            event.description = (event.description.rstrip() + "\n\n" + str(args["story_append"]).strip()).strip()
        if args.get("kind") in EVENT_KINDS:
            event.kind = args["kind"]
        if args.get("place"):
            event.place = _text(args["place"])
        for field, low, high in (("year", 1000, 2200), ("month", 1, 12), ("day", 1, 31)):
            value = _number(args.get(field), low, high)
            if value is not None:
                setattr(event, field, value)
        event.save()
        if args.get("people_ids"):
            event.people.set(Person.objects.filter(owner=owner, pk__in=args["people_ids"]))
        history.record(owner, actor, Change.Action.UPDATED, subject=event.display_title, what="event")
        return event

    if name == "delete_event":
        event = _event(owner, args.get("event_id"))
        history.record(owner, actor, Change.Action.DELETED, subject=event.display_title, what="event")
        if event.recording:
            event.recording.delete(save=False)
        event.delete()
        return "genealogy:upcoming"

    if name == "add_relative":
        anchor = _person(owner, args.get("anchor_id"))
        relation = args.get("relation")
        if relation not in RELATIONS:
            raise Refused(_("Choose the relation."))
        new = Person(owner=owner, first_name=_text(args.get("first_name"), 100),
                     last_name=_text(args.get("last_name"), 100),
                     gender=args.get("gender") if args.get("gender") in ("male", "female") else "male",
                     birth_year=_number(args.get("birth_year"), 1000, 2200),
                     birth_month=_number(args.get("birth_month"), 1, 12),
                     birth_day=_number(args.get("birth_day"), 1, 31),
                     birth_place=_text(args.get("birth_place")), is_deceased=bool(args.get("is_deceased")))
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

    if name == "link_relatives":
        person, other = _person(owner, args.get("person_id")), _person(owner, args.get("other_id"))
        relation = args.get("relation")
        if relation not in RELATIONS or person.pk == other.pk:
            raise Refused(_("Choose the relation."))
        error = problem(person, other, relation, Archive(owner))
        if error:
            raise Refused(error)
        befores = {p.pk: history.snapshot(p) for p in (person, other)}
        attach(person, other, relation, owner)
        for p in (person, other):
            p.refresh_from_db()
            history.record_update(actor, p, befores[p.pk])
        history.record(owner, actor, Change.Action.LINKED, other, details={"relation": relation, "to": person.short_name})
        return person

    if name == "update_person":
        person = _person(owner, args.get("person_id"))
        before = history.snapshot(person)
        for field in PERSON_FIELDS:
            if args.get(field):
                setattr(person, field, _text(args[field], 100 if field.endswith("name") else 200))
        for field in NUMBER_FIELDS:
            low, high = (1000, 2200) if field.endswith("year") else (1, 12) if field.endswith("month") else (1, 31)
            value = _number(args.get(field), low, high)
            if value is not None:
                setattr(person, field, value)
        if args.get("is_deceased") is not None or person.death_year:
            person.is_deceased = bool(args.get("is_deceased")) or bool(person.death_year) or person.is_deceased
        if args.get("life_story_append"):
            person.life_story = (person.life_story.rstrip() + "\n\n" + str(args["life_story_append"]).strip()).strip()
        person.save()
        history.record_update(actor, person, before)
        return person

    if name == "delete_person":
        from apps.accounts.models import Membership

        person = _person(owner, args.get("person_id"))
        User = get_user_model()
        if person.pk in (actor.person_id, actor.home_person_id):
            raise Refused(_("Your own record cannot be deleted."))
        if (User.objects.filter(Q(person=person) | Q(own_person=person)).exists()
                or Membership.objects.filter(person=person).exists() or person.linked_user_id):
            raise Refused(_("This record belongs to a relative who has an account, so it cannot be deleted."))
        history.record_delete(actor, person)
        person.delete()
        return "genealogy:history"

    if name == "set_divorced":
        marriage = Marriage.objects.filter(owner=owner, husband_id=_as_id(args.get("husband_id")),
                                           wife_id=_as_id(args.get("wife_id"))).select_related("husband", "wife").first()
        if marriage is None:
            raise Refused(_("This marriage was not found."))
        divorced = bool(args.get("divorced"))
        if not divorced and wife_is_married(marriage.wife, marriage.husband):
            raise Refused(_("She has another marriage now: it cannot be active again."))
        marriage.is_divorced = divorced
        marriage.save(update_fields=["is_divorced"])
        names = f"{marriage.husband.short_name} — {marriage.wife.short_name}"
        history.record(owner, actor, Change.Action.UPDATED, subject=names, what="marriage")
        return marriage.husband

    if name == "leave_message":
        from .models import Note

        recipient = resolve_recipient(actor, owner, args.get("recipient", ""))
        text = str(args.get("text", "")).strip()[:2000]
        if recipient is None:
            raise Refused(_("This person cannot be reached: they need an account linked to your family."))
        if not text:
            raise Refused(_("Write a message."))
        Note.objects.create(author=actor, recipient=recipient, text=text)
        return "assistant:chat"

    raise Refused(_("Access denied."))
