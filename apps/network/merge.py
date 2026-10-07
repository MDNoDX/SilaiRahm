"""Comparing two family trees and taking over what one knows into the other.

`analyse(source, target)` walks both trees outwards from people known to be
the same person in both (the confirmed matches): fathers with fathers,
mothers with mothers, spouses and children by name. The result is a plan:

  matches    pairs that are one person (remembered as such once applied)
  additions  relatives the target does not have yet — copied with their links
  fills      details the target leaves empty and the source knows
  conflicts  details or links that differ — shown as warnings, never overwritten

`apply(source, target, keys, actor)` recomputes the plan and carries out the
chosen items (all of them by default) in one transaction. Every new record
and every change is written to the history, so each one can be undone.
"""
from collections import deque
from dataclasses import dataclass, field

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.core.text import search_key
from apps.genealogy import history
from apps.genealogy.kinship import Archive
from apps.genealogy.models import Change, Marriage, Person
from apps.genealogy.relations import attach, problem

from .models import PersonMatch

# Details a copy takes over, and details an existing record may be completed with.
COPY_FIELDS = ["first_name", "last_name", "patronymic", "gender", "birth_year", "birth_month", "birth_day",
               "birth_place", "is_deceased", "death_year", "death_month", "death_day", "death_place", "burial_place",
               "occupation", "education", "biography", "life_story"]
FILL_FIELDS = ["last_name", "patronymic", "birth_year", "birth_month", "birth_day", "birth_place", "death_year",
               "death_month", "death_day", "death_place", "burial_place", "occupation", "education", "biography",
               "life_story"]
STORY_FIELDS = ["biography", "life_story"]
DATE_FIELDS = ["birth_year", "birth_month", "birth_day", "death_year", "death_month", "death_day"]


# ---- telling whether two records are one person ---------------------------
def _name(person):
    return search_key(person.first_name).replace(" ", "")


def _distance(a, b):
    """Edit distance, enough for one typo in a name."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def same_name(a, b):
    x, y = _name(a), _name(b)
    if not x or not y:
        return False
    if x == y:
        return True
    if min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x)):
        return True
    return min(len(x), len(y)) >= 5 and _distance(x, y) <= 1


def similar(a, b):
    """Could these two records be the same person?"""
    if a.gender and b.gender and a.gender != b.gender:
        return False
    if a.birth_year and b.birth_year and abs(a.birth_year - b.birth_year) > 2:
        return False
    return same_name(a, b)


# ---- the plan ---------------------------------------------------------------
@dataclass
class Match:
    source: Person
    target: Person
    why: str

    @property
    def key(self):
        return f"m{self.source.pk}-{self.target.pk}"


@dataclass
class Addition:
    source: Person
    relation: str          # father / mother / spouse / child, from the anchor's side
    anchor_source: int     # the source record of the person it is attached to
    anchor_name: str

    @property
    def key(self):
        return f"a{self.source.pk}"

    @property
    def relation_label(self):
        from apps.genealogy.terminology import ADD_RELATION

        return ADD_RELATION.get(self.relation, "")


@dataclass
class Fill:
    target: Person
    field: str
    value: object
    source: Person

    @property
    def key(self):
        return f"f{self.target.pk}-{self.field}"

    @property
    def label(self):
        if self.field == "photo":
            return _("photo")
        return Person._meta.get_field(self.field).verbose_name


@dataclass
class Plan:
    source_owner: object
    target_owner: object
    anchors: list = field(default_factory=list)      # known pairs (source pk, target pk)
    matches: list = field(default_factory=list)
    additions: list = field(default_factory=list)
    fills: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)    # short sentences
    unreached: int = 0

    @property
    def keys(self):
        return {x.key for x in self.matches + self.additions + self.fills}

    @property
    def in_both(self):
        """How many people are known to be in both trees."""
        return len(self.anchors) + len(self.matches)

    @property
    def empty(self):
        return not (self.matches or self.additions or self.fills)

    @property
    def fits(self):
        """No warnings: the two trees agree wherever they overlap."""
        return not self.conflicts


def known_pairs(source_owner, target_owner):
    """Confirmed matches between the two trees, as (source pk, target pk); and rejected pairs."""
    rows = PersonMatch.objects.filter(
        Q(first__owner=source_owner, second__owner=target_owner) | Q(first__owner=target_owner, second__owner=source_owner)
    ).values_list("first_id", "first__owner_id", "second_id", "rejected")
    pairs, rejected = [], set()
    for first, first_owner, second, is_rejected in rows:
        s, t = (first, second) if first_owner == source_owner.pk else (second, first)
        (rejected.add((s, t)) if is_rejected else pairs.append((s, t)))
    return pairs, rejected


def differs(role):
    return (_("{name}: the father differs — {here} here, {there} there.") if role == "father"
            else _("{name}: the mother differs — {here} here, {there} there."))


def analyse(source_owner, target_owner, anchors=(), with_stories=True):
    """The plan for taking `source_owner`'s tree into `target_owner`'s. Without
    `with_stories` (the source owner keeps their stories to the family) the
    life stories are not copied."""
    S, T = Archive(source_owner), Archive(target_owner)
    plan = Plan(source_owner, target_owner)
    pairs, rejected = known_pairs(source_owner, target_owner)
    pairs = [(s, t) for s, t in list(pairs) + list(anchors) if s in S.people and t in T.people]
    plan.anchors = pairs
    mapped, taken = {}, {}           # source pk -> target pk (or ("new", pk)); target pk -> source pk
    queue = deque()

    def pair(s, t, why=None):
        mapped[s], taken[t] = t, s
        if why is not None:
            plan.matches.append(Match(S.people[s], T.people[t], why))
        queue.append(s)

    for s, t in pairs:
        if s not in mapped and t not in taken:
            pair(s, t)

    def add(s, relation, anchor_s):
        mapped[s] = ("new", s)
        anchor = S.people[anchor_s]
        plan.additions.append(Addition(S.people[s], relation, anchor_s, anchor.short_name))
        queue.append(s)

    def target_of(s):
        t = mapped.get(s)
        return t if isinstance(t, int) else None

    while queue:
        s = queue.popleft()
        sp, t = S.people[s], target_of(s)
        tp = T.people.get(t) if t is not None else None
        # Father and mother.
        for role in ("father", "mother"):
            sr = getattr(sp, f"{role}_id")
            if sr not in S.people:
                continue
            tr = getattr(tp, f"{role}_id") if tp is not None else None
            tr = tr if tr in T.people else None
            if sr in mapped:
                if tp is not None and tr is not None and target_of(sr) not in (None, tr):
                    plan.conflicts.append(differs(role).format(name=tp.short_name, here=T.people[tr].short_name,
                                         there=S.people[sr].short_name))
                continue
            if tr is not None:
                if tr in taken:
                    continue
                if (sr, tr) not in rejected and similar(S.people[sr], T.people[tr]):
                    pair(sr, tr, (_("Father of {name}") if role == "father" else _("Mother of {name}")).format(
                        name=tp.short_name))
                else:
                    plan.conflicts.append(differs(role).format(name=tp.short_name, here=T.people[tr].short_name,
                                         there=S.people[sr].short_name))
                continue
            add(sr, role, s)
        # Husband or wife.
        for spouse in S.spouses(s):
            if spouse in mapped:
                continue
            candidates = [x for x in (T.spouses(t) if t is not None else []) if x not in taken]
            found = next((x for x in candidates if (spouse, x) not in rejected
                          and similar(S.people[spouse], T.people[x])), None)
            if found is not None:
                pair(spouse, found, _("Spouse of {name}").format(name=tp.short_name))
            else:
                add(spouse, "spouse", s)
        # Children: among the children of this person and of the other parent.
        for child in S.children.get(s, []):
            if child in mapped:
                continue
            pool = list(T.children.get(t, [])) if t is not None else []
            cp = S.people[child]
            other = cp.mother_id if cp.father_id == s else cp.father_id
            if target_of(other) is not None:
                pool += T.children.get(target_of(other), [])
            found = next((x for x in pool if x not in taken and (child, x) not in rejected
                          and similar(cp, T.people[x])), None)
            if found is not None:
                pair(child, found, _("Child of {name}").format(name=sp.short_name))
            else:
                add(child, "child", s)

    # Details of people who are in both trees.
    for s, t in mapped.items():
        if not isinstance(t, int):
            continue
        sp, tp = S.people[s], T.people[t]
        for name in FILL_FIELDS:
            if not with_stories and name in STORY_FIELDS:
                continue
            mine, theirs = getattr(tp, name), getattr(sp, name)
            if theirs in (None, "") or mine == theirs:
                continue
            if mine in (None, ""):
                plan.fills.append(Fill(tp, name, theirs, sp))
            elif name in DATE_FIELDS:
                plan.conflicts.append(_("{name}: {field} is {here} here, {there} there.").format(
                    name=tp.short_name, field=Person._meta.get_field(name).verbose_name, here=mine, there=theirs))
        if sp.is_deceased != tp.is_deceased:
            plan.conflicts.append(
                _("{name}: passed away according to the other family tree.").format(name=tp.short_name)
                if sp.is_deceased else
                _("{name}: recorded as passed away here, alive in the other family tree.").format(name=tp.short_name))
        if sp.photo and not tp.photo:
            plan.fills.append(Fill(tp, "photo", sp.photo.name, sp))
    plan.unreached = len([pk for pk in S.people if pk not in mapped])
    return plan


# ---- carrying out the plan ---------------------------------------------------
def copy_person(source, owner, with_stories=True):
    """A new record in `owner`'s tree with `source`'s details (and photo)."""
    fields = [n for n in COPY_FIELDS if with_stories or n not in STORY_FIELDS]
    person = Person(owner=owner, **{name: getattr(source, name) for name in fields})
    person.save()
    if source.photo:
        copy_photo(source, person)
    return person


def copy_photo(source, person):
    try:
        with source.photo.open("rb") as f:
            data = f.read()
    except Exception:  # noqa: BLE001 - a missing file must not stop the merge
        return
    person.photo.save(source.photo.name.rsplit("/", 1)[-1], ContentFile(data), save=True)


def link_match(a, b, actor, rejected=False):
    """Remember that `a` and `b` are (or are not) the same person."""
    if a.owner_id == b.owner_id or a.pk == b.pk:
        return None
    first, second = (a, b) if a.pk < b.pk else (b, a)
    match, _created = PersonMatch.objects.update_or_create(
        first=first, second=second, defaults={"rejected": rejected, "decided_by": actor})
    return match


@transaction.atomic
def apply(source_owner, target_owner, keys=None, actor=None, anchors=(), with_stories=True):
    """Carry out the chosen items of the plan; returns counts for the message."""
    plan = analyse(source_owner, target_owner, anchors, with_stories=with_stories)
    chosen = plan.keys if keys is None else set(keys) & plan.keys
    S = Archive(source_owner)
    done = {"matched": 0, "added": 0, "filled": 0, "linked": 0}
    mapped = dict(plan.anchors)
    for s, t in plan.anchors:
        link_match(S.people[s], Person.objects.get(pk=t), actor)
    for m in plan.matches:
        if m.key in chosen:
            link_match(m.source, m.target, actor)
            mapped[m.source.pk] = m.target.pk
            done["matched"] += 1

    people = {}  # target pk -> fresh Person object (changes accumulate here)

    def person(pk):
        if pk not in people:
            people[pk] = Person.objects.get(pk=pk)
        return people[pk]

    before, created = {}, set()  # snapshots of changed records for the history; new records

    def remember(pk):
        if pk not in before and pk not in created:
            before[pk] = history.snapshot(person(pk))

    for a in plan.additions:
        if a.key not in chosen or a.anchor_source not in mapped:
            continue
        anchor = person(mapped[a.anchor_source])
        new = copy_person(a.source, target_owner, with_stories=with_stories)
        if problem(anchor, new, a.relation, Archive(target_owner)):
            new.delete()
            continue
        other = None
        if a.relation == "child":
            other_source = a.source.mother_id if a.source.father_id == a.anchor_source else a.source.father_id
            if other_source in mapped:
                other = person(mapped[other_source])
        wedding = None
        if a.relation == "spouse":
            wedding = Marriage.objects.filter(Q(husband_id=a.anchor_source, wife=a.source) |
                                              Q(wife_id=a.anchor_source, husband=a.source)).first()
        remember(anchor.pk)
        attach(anchor, new, a.relation, target_owner, other_parent=other, wedding=wedding)
        people[new.pk] = new
        created.add(new.pk)
        mapped[a.source.pk] = new.pk
        link_match(a.source, new, actor)
        history.record(target_owner, actor, Change.Action.CREATED, new,
                       details={"relation": a.relation, "to": anchor.short_name})
        done["added"] += 1

    # Family links between records that are now in both trees.
    archive = Archive(target_owner)
    for s, t in mapped.items():
        sp, tp = S.people.get(s), person(t)
        if sp is None:
            continue
        for role in ("father", "mother"):
            sr = getattr(sp, f"{role}_id")
            if sr in mapped and getattr(tp, f"{role}_id") is None:
                parent = person(mapped[sr])
                if problem(tp, parent, role, archive) is None:
                    remember(tp.pk)
                    setattr(tp, role, parent)
                    tp.save(update_fields=[f"{role}_id"])
                    done["linked"] += 1
    for m in S.marriages:
        if m.husband_id in mapped and m.wife_id in mapped:
            _marriage, made = Marriage.objects.get_or_create(
                owner=target_owner, husband_id=mapped[m.husband_id], wife_id=mapped[m.wife_id],
                defaults={"year": m.year, "month": m.month, "day": m.day})
            done["linked"] += int(made)

    for f in plan.fills:
        if f.key not in chosen:
            continue
        tp = person(f.target.pk)
        if f.field == "photo":
            if not tp.photo:
                copy_photo(f.source, tp)
                done["filled"] += 1
            continue
        if getattr(tp, f.field) in (None, ""):
            remember(tp.pk)
            setattr(tp, f.field, f.value)
            tp.save(update_fields=[f.field])
            done["filled"] += 1
    for pk, snap in before.items():
        history.record_update(actor, person(pk), snap)
    return done
