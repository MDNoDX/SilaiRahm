"""Relatives: the list, a person's page, adding, editing and deleting, marriages, "this is me"."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.muchal import next_muchal_year
from apps.core.text import surname_from_name

from .. import duplicates, history
from ..access import can_edit, can_see_stories, can_view, person_for_edit, person_for_view, require_edit, viewer_person
from ..forms import MarriageForm, PersonForm, RelativeWithSpouseForm
from ..kinship import Archive
from ..relations import wife_is_married
from ..models import Change, Marriage, Media, Person
from ..terminology import ADD_RELATION, SECTION, generation_label
from ._common import _focus_for, _pdf_response
from .search import _ranked


def _filter_people(queryset, show):
    """The chips above the list of people."""
    from django.db.models import Q

    rules = {
        "living": Q(is_deceased=False),
        "deceased": Q(is_deceased=True),
        "male": Q(gender="male"),
        "female": Q(gender="female"),
    }
    return queryset.filter(rules[show]) if show in rules else queryset


@login_required
def people_list(request):
    """Everyone in the archive: by generation and side of the family, or A–Z."""
    query = request.GET.get("q", "").strip()
    show = request.GET.get("f", "")
    order = "abc" if request.GET.get("tartib") == "abc" else "gen"
    archive = Archive(request.archive)
    people = _filter_people(Person.objects.filter(owner=request.archive), show)
    focus = _focus_for(request, archive)
    branches = archive.branches(focus) if focus else {}

    def row(p):
        return (p, archive.label(focus, p.pk) if focus else "", branches.get(p.pk, "other"))

    groups = []
    if query:
        groups = [("", [row(p) for p in _ranked(people, query, 500)])]
    elif order == "abc" or not focus:
        groups = [("", [row(p) for p in people.order_by("first_name", "last_name", "id")])]
    else:
        gens = archive.generations(focus)
        side_order = {"own": 0, "paternal": 1, "maternal": 2, "other": 3}
        by_gen = {}
        for p in people:
            key = max(-3, min(3, gens[p.pk])) if p.pk in gens else None
            by_gen.setdefault(key, []).append(p)
        for key in sorted((k for k in by_gen if k is not None)) + ([None] if None in by_gen else []):
            members = sorted(by_gen[key], key=lambda p: (side_order[branches.get(p.pk, "other")],
                                                         p.birth_key or (9999,), p.first_name))
            label = generation_label(key) if key is not None else _("Not yet linked to the family")
            groups.append((label, [row(p) for p in members]))
    template = "genealogy/people/_grid.html" if request.GET.get("partial") else "genealogy/people/list.html"
    return render(request, template, {
        "groups": groups, "query": query, "total": len(archive.people), "show": show, "order": order,
        "shown": sum(len(rows) for _label, rows in groups),
        "duplicates": len(duplicates.pairs(request.archive)) if request.can_edit and not request.GET.get("partial") else 0,
    })


def _life_path(archive, person):
    """The milestones of one life, oldest first: [{"year", "when", "kind", "text", "url"}]."""
    items = []

    def add(year, month, day, kind, text, url="", story="", recording=None):
        from apps.core.dates import format_partial_date

        items.append({"key": (year or 9999, month or 0, day or 0), "year": year,
                      "when": format_partial_date(year, month, day) if year else "", "kind": kind,
                      "text": text, "url": url, "story": story, "recording": recording})

    if person.birth_year:
        add(person.birth_year, person.birth_month, person.birth_day, "birth",
            _("Born in {place}").format(place=person.birth_place) if person.birth_place else _("Born"))
    for partner_id, m in archive.unions.get(person.pk, []):
        partner = archive.people[partner_id]
        if m.year:
            add(m.year, m.month, m.day, "wedding", _("Married {name}").format(name=partner.short_name),
                partner.get_absolute_url())
    for child_id in archive.children.get(person.pk, []):
        child = archive.people[child_id]
        if child.birth_year:
            text = (_("Son {name} was born") if child.is_male else _("Daughter {name} was born")).format(
                name=child.first_name)
            add(child.birth_year, child.birth_month, child.birth_day, "child", text, child.get_absolute_url())
    for event in person.events.all():  # events and memories, dated or not, with their story
        add(event.year, event.month, event.day, "event", event.display_title, event.get_absolute_url(),
            event.description, event if event.recording else None)
    if person.death_year:
        add(person.death_year, person.death_month, person.death_day, "death",
            _("Passed away in {place}").format(place=person.death_place) if person.death_place else _("Passed away"))
    items.sort(key=lambda i: i["key"])
    if person.birth_year:
        for item in items:
            if item["kind"] not in ("birth",) and item["year"]:
                item["age"] = item["year"] - person.birth_year
    return items


@login_required
def person_detail(request, pk):
    person = person_for_view(request, pk)
    archive = Archive(person.owner)
    editable = can_edit(request.user, person.owner)
    me = viewer_person(request, archive)

    def people(pks):
        return [(archive.people[x], archive.label(person.pk, x)) for x in pks]

    show_stories = can_see_stories(request.user, person.owner)
    media = list(person.media.all()) if show_stories else []
    context = {
        "show_stories": show_stories,
        "person": person,
        "is_owner": editable,
        "relation_to_me": archive.label(me, person.pk) if me and me != person.pk else "",
        "branch": archive.branches(me).get(person.pk, "other") if me else "own",
        "father": archive.people.get(person.father_id),
        "mother": archive.people.get(person.mother_id),
        "spouses": people(archive.spouses(person.pk)),
        "can_add_spouse": person.is_male or not wife_is_married(person),
        "marriages": [m for _sid, m in archive.unions.get(person.pk, [])],
        "children": people(archive.children.get(person.pk, [])),
        "siblings": people(archive.siblings(person.pk)),
        "events": person.events.all() if show_stories else [],
        "friends": person.friends.all() if show_stories else [],
        "photos": [m for m in media if m.kind == Media.Kind.PHOTO],
        "files": [m for m in media if m.kind != Media.Kind.PHOTO],
        "story_recordings": [m for m in media if m.in_story],
        "media_count": len(media),
        "life_path": _life_path(archive, person) if show_stories else [],
        "muchal": person.muchal,
        "next_muchal": next_muchal_year(person.birth_year, person.birth_month, person.birth_day)
        if not person.is_deceased else None,
        "section": SECTION,
        "add_relation": ADD_RELATION,
        "is_me": request.user.person_id == person.pk,
        # "This is me" only for someone not yet known in this tree: a click must
        # never quietly turn an account into another relative.
        "can_be_me": (request.user.person_id is None and person.owner_id == request.archive.pk
                      and not hasattr(person, "account") and not person.linked_user_id),
        "changes": person.changes.select_related("actor")[:5] if editable else [],
        **_across_trees(request, person, editable),
    }
    return render(request, "genealogy/people/detail.html", context)


def _across_trees(request, person, editable):
    """The account a record stands for, and the same person in other family trees."""
    from urllib.parse import quote

    from django.db.models import Q
    from django.urls import reverse

    from apps.network.models import PersonMatch
    from apps.network.services import working_tree

    matches = []
    for m in PersonMatch.objects.filter(Q(first=person) | Q(second=person), rejected=False).select_related(
            "first__owner", "second__owner"):
        other = m.other(person.pk)
        if can_view(request.user, other.owner):
            matches.append({"person": other, "owner": other.owner, "merge_url": (
                f"{reverse('network:merge')}?from={other.owner.username}&to={person.owner.username}"
                if editable else "")})
    mine = working_tree(request)
    account = person.linked_user if person.linked_user_id else None
    return {
        "account": account,
        "matches": matches,
        "my_tree": mine if (person.owner_id != mine.pk and can_edit(request.user, mine)
                            and all(m["owner"].pk != mine.pk for m in matches)) else None,
        "find_url": (f"{reverse('network:index')}?q={quote(person.full_name)}"
                     if editable and account is None and not hasattr(person, "account") and not person.is_deceased
                     else ""),
    }


@login_required
def person_create(request):
    owner = require_edit(request)
    form = PersonForm(request.POST or None, request.FILES or None, owner=owner, archive=Archive(owner))
    if request.method == "POST" and form.is_valid():
        person = form.save()
        history.record(owner, request.user, Change.Action.CREATED, person)
        messages.success(request, _("The person has been added to the family tree."))
        return redirect(person)
    return render(request, "genealogy/people/form.html", {"form": form, "is_new": True})


@login_required
def person_edit(request, pk):
    person = person_for_edit(request, pk)
    archive = Archive(person.owner)
    before = history.snapshot(person)
    form = PersonForm(request.POST or None, request.FILES or None, instance=person, owner=person.owner, archive=archive)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        history.record_update(request.user, person, before)
        # Someone's own record: the account follows its gender.
        get_user_model().objects.filter(person=person).exclude(gender=person.gender).update(gender=person.gender)
        messages.success(request, _("The information has been saved."))
        return redirect(person)
    return render(request, "genealogy/people/form.html", {"form": form, "person": person, "is_new": False})


def _linked_to_account(person):
    from apps.accounts.models import Membership, User

    return (User.objects.filter(person=person).exists() or User.objects.filter(own_person=person).exists()
            or Membership.objects.filter(person=person).exists())


@login_required
def person_delete(request, pk):
    person = person_for_edit(request, pk)
    if request.user.person_id == person.pk:
        messages.error(request, _("Your own record cannot be deleted."))
        return redirect(person)
    if _linked_to_account(person):
        messages.error(request, _("This record belongs to a relative who has an account, so it cannot be deleted."))
        return redirect(person)
    if request.method == "POST":
        history.record_delete(request.user, person)
        person.delete()
        messages.success(request, _("The record has been deleted. It can be restored from the history."))
        return redirect("genealogy:people")
    return render(request, "genealogy/confirm_delete.html", {
        "object_name": person.full_name, "cancel_url": person.get_absolute_url(), "restorable": True,
    })


def _relative_form(request, anchor, data=None, files=None, initial=None):
    archive = Archive(anchor.owner)
    spouses = [archive.people[sp] for sp in archive.spouses(anchor.pk)]
    form = RelativeWithSpouseForm(data, files, owner=anchor.owner, archive=archive, anchor=anchor, spouses=spouses,
                                  initial=initial or {})
    return form, archive, spouses


def _save_relative(request, form, anchor):
    existing = form.cleaned_data.get("existing")
    before = history.snapshot(existing) if existing else None
    anchor_before = history.snapshot(anchor)
    person = form.save()
    if existing:
        history.record(anchor.owner, request.user, Change.Action.LINKED, person,
                       details={"relation": form.cleaned_data["relation"], "to": anchor.short_name},
                       before=None)
        history.record_update(request.user, person, before)
    else:
        history.record(anchor.owner, request.user, Change.Action.CREATED, person,
                       details={"relation": form.cleaned_data["relation"], "to": anchor.short_name})
    anchor.refresh_from_db()
    history.record_update(request.user, anchor, anchor_before)
    return person


@login_required
def relative_add(request, pk):
    anchor = person_for_edit(request, pk)
    initial = {}
    relation = request.GET.get("relation")
    if relation in ADD_RELATION:
        initial["relation"] = relation
        if relation == "father":
            initial["gender"] = "male"
        elif relation == "mother":
            initial["gender"] = "female"
        if relation == "sibling":
            initial["last_name"] = anchor.last_name
    form, archive, spouses = _relative_form(request, anchor, request.POST or None, request.FILES or None, initial)
    if request.method == "POST" and form.is_valid():
        _save_relative(request, form, anchor)
        messages.success(request, _("The person has been added to the family tree."))
        return redirect(anchor)
    # A son takes his paternal grandfather's name as surname (Madaminjon → Madaminov).
    grandfather = archive.people.get(anchor.father_id) if anchor.is_male else None
    return render(request, "genealogy/people/relative_form.html", {
        "form": form, "anchor": anchor, "has_spouses": bool(spouses),
        "son_surname": surname_from_name(grandfather.first_name) if grandfather else "",
        "father_surname": anchor.last_name,
    })


@login_required
def marriage_edit(request, pk):
    marriage = get_object_or_404(Marriage, pk=pk)
    require_edit(request, marriage.owner)
    back = request.GET.get("from") or marriage.husband_id
    form = MarriageForm(request.POST or None, instance=marriage)
    if request.method == "POST":
        names = f"{marriage.husband.short_name} · {marriage.wife.short_name}"
        if "delete" in request.POST:
            marriage.delete()
            history.record(marriage.owner, request.user, Change.Action.DELETED, subject=names, what="marriage")
            messages.success(request, _("The marriage record has been deleted."))
            return redirect("genealogy:person", pk=back)
        if form.is_valid():
            form.save()
            history.record(marriage.owner, request.user, Change.Action.UPDATED, subject=names, what="marriage")
            messages.success(request, _("The information has been saved."))
            return redirect("genealogy:person", pk=back)
    return render(request, "genealogy/people/marriage_form.html", {"form": form, "marriage": marriage, "back": back})


@require_POST
@login_required
def person_story(request, pk):
    """The life story, written on the person's page like a book."""
    from django.core.exceptions import ValidationError

    from .. import recordings

    person = person_for_edit(request, pk)
    upload = request.FILES.get("recording")
    if upload:  # told aloud: kept with the life story (and in the album)
        try:
            content, kind = recordings.clean(upload)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect(person.get_absolute_url() + "#life")
        Media.objects.create(owner=person.owner, person=person, kind=kind, file=content, in_story=True,
                             caption=_("Life story")[:200], uploaded_by=request.user)
        history.record(person.owner, request.user, Change.Action.UPDATED, person, what="album", details={"added": 1})
    before = history.snapshot(person)
    person.life_story = request.POST.get("life_story", "").strip()
    person.save(update_fields=["life_story", "updated_at"])
    history.record_update(request.user, person, before)
    messages.success(request, _("The information has been saved."))
    return redirect(person.get_absolute_url() + "#life")


@login_required
def person_pdf(request, pk):
    from .. import pdf  # reportlab loads only when a PDF is asked for

    person = person_for_view(request, pk)
    if not can_see_stories(request.user, person.owner):
        raise PermissionDenied(_("Access denied."))
    archive = Archive(person.owner)
    events = sorted(person.events.all(), key=lambda e: (e.year or 9999, e.month or 0, e.day or 0, e.created_at))
    data = pdf.person_pdf(archive, person, focus_id=viewer_person(request, archive), stories=events,
                          life_path=_life_path(archive, person))
    return _pdf_response(data, f"{person.short_name}.pdf")


@require_POST
@login_required
def set_self(request, pk):
    """"This is me": the viewer's own record in the archive they work in."""
    person = person_for_view(request, pk)
    if person.owner_id != request.archive.pk or hasattr(person, "account") or person.linked_user_id:
        raise PermissionDenied(_("Access denied."))
    if Person.objects.filter(pk=request.user.person_id, owner=request.archive).exists():
        # Already known in this tree: who you are does not change with one click.
        raise PermissionDenied(_("Access denied."))
    from apps.accounts.models import Membership

    request.user.person = person
    request.user.save(update_fields=["person"])
    if request.user.active_archive_id:
        Membership.objects.filter(owner=request.archive, member=request.user).update(person=person)
    messages.success(request, _("The information has been saved."))
    return redirect(person)
