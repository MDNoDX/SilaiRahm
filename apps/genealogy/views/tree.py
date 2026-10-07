"""The family tree: the page, its data (tree and fan), the side sheet with quick add, PDFs and the book."""
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import pgettext
from django.views.decorators.http import require_POST

from apps.core.text import surname_from_name

from ..access import archive_owner, can_edit, can_see_stories, person_for_edit, person_for_view, viewer_person
from ..kinship import Archive
from ..relations import wife_is_married
from ..models import Event
from ..terminology import ADD_RELATION, BRANCHES
from ..tree import build_tree
from ._common import _focus_for, _pdf_response, _tree_state
from .people import _relative_form, _save_relative


@login_required
def tree_page(request, username=None):
    owner = archive_owner(request, username)
    archive = Archive(owner)
    focus = _focus_for(request, archive, request.GET.get("person"))
    editable = can_edit(request.user, owner)
    return render(request, "genealogy/tree.html", {
        "owner": owner,
        "is_owner": editable,
        "is_active_archive": owner.pk == request.archive.pk,
        "focus": archive.people.get(focus),
        "data_url": reverse("genealogy:tree_data_for", args=[owner.username]),
        "pdf_url": reverse("genealogy:tree_pdf_for", args=[owner.username]),
        "add_relation": ADD_RELATION,
        "branches": BRANCHES,
    })


@login_required
def tree_data(request, username):
    owner = archive_owner(request, username)
    archive = Archive(owner)
    focus = _focus_for(request, archive, request.GET.get("person"))
    if focus is None:
        return JsonResponse({"nodes": [], "lines": [], "rows": [], "width": 0, "height": 0, "focus": None})
    return JsonResponse(build_tree(archive, focus, viewer_person=viewer_person(request, archive),
                                   **_tree_state(request)))


@login_required
def person_card(request, pk):
    """What the side panel of the tree shows about one person."""
    person = person_for_view(request, pk)
    archive = Archive(person.owner)
    me = viewer_person(request, archive)
    editable = can_edit(request.user, person.owner)
    has_parents = bool(person.father_id or person.mother_id)
    can_add = {"father": not person.father_id, "mother": not person.mother_id,
               "spouse": person.is_male or not wife_is_married(person), "child": True,
               "sibling": has_parents} if editable else {}
    return JsonResponse({
        "id": person.pk, "name": person.short_name, "full_name": person.full_name, "initials": person.initials,
        "gender": person.gender, "years": person.lifespan, "deceased": person.is_deceased,
        "born": person.birth_date_display, "birth_place": person.birth_place,
        "died": person.death_date_display, "occupation": person.occupation,
        "label": archive.label(me, person.pk) if me and me != person.pk else "",
        "is_me": person.pk == request.user.person_id,
        "photo": f"{person.photo.url}?s=t" if person.photo else "", "url": person.get_absolute_url(),
        "edit_url": reverse("genealogy:person_edit", args=[person.pk]) if editable else "",
        "more_url": reverse("genealogy:relative_add", args=[person.pk]) if editable else "",
        "add_url": reverse("genealogy:quick_add", args=[person.pk]) if editable else "",
        "can_add": can_add, "last_name": person.last_name,
        # A relative with an account of their own: their family tree is one click away.
        "account": ({"name": f"@{person.linked_user.username}",
                     "url": reverse("network:profile", args=[person.linked_user.username])}
                    if person.linked_user_id else None),
        "child_surname": _child_surname(archive, person),
        "counts": {"children": len(archive.children.get(person.pk, [])),
                   "siblings": len(archive.siblings(person.pk)), "spouses": len(archive.spouses(person.pk))},
    })


def _child_surname(archive, person):
    """Surnames suggested for a child of `person`: a son takes the name of his
    paternal grandfather (Madaminjon → Madaminov), a daughter her father's surname."""
    father = person
    if not person.is_male:
        spouses = archive.spouses(person.pk)
        father = archive.people[spouses[0]] if len(spouses) == 1 else None
    if father is None:
        return {"son": "", "daughter": ""}
    grandfather = archive.people.get(father.father_id)
    return {"son": surname_from_name(grandfather.first_name) if grandfather else father.last_name,
            "daughter": father.last_name}


@require_POST
@login_required
def quick_add(request, pk):
    """Add a relative from the tree itself (name, gender and birth year are enough)."""
    anchor = person_for_edit(request, pk)
    data = request.POST.copy()
    archive = Archive(anchor.owner)
    spouses = archive.spouses(anchor.pk)
    if data.get("relation") == "child" and not data.get("other_parent") and len(spouses) == 1:
        data["other_parent"] = str(spouses[0])
    form, _archive, _spouses = _relative_form(request, anchor, data)
    if form.is_valid():
        person = _save_relative(request, form, anchor)
        return JsonResponse({"ok": True, "id": person.pk, "name": person.short_name})
    errors = {name: [str(e) for e in errs] for name, errs in form.errors.items()}
    return JsonResponse({
        "ok": False, "errors": errors,
        "duplicates": [{"id": p.pk, "name": p.short_name, "years": p.lifespan, "url": p.get_absolute_url()}
                       for p in form.duplicates],
    }, status=400)


@login_required
def tree_pdf(request, username):
    from .. import pdf  # reportlab loads only when a PDF is asked for

    owner = archive_owner(request, username)
    archive = Archive(owner)
    focus = _focus_for(request, archive, request.GET.get("person"))
    if focus is None:
        raise Http404(_("The family tree is empty."))
    layout = build_tree(archive, focus, photo_urls=False, viewer_person=viewer_person(request, archive),
                        **_tree_state(request))
    person = archive.people[focus]
    subtitle = _("Centred on %(name)s. Relationship names are given as seen from this person.") % {
        "name": person.full_name}
    size = request.GET.get("size", "").upper()
    data = pdf.tree_pdf(layout, _("Family tree"), subtitle, poster=size if size in pdf.POSTER_SIZES else None,
                        family=_family_name(archive, focus), photos=pdf.tree_photos(archive, layout))
    name = pgettext("file name", "family-tree") + (f"-{size}" if size in pdf.POSTER_SIZES else "")
    return _pdf_response(data, name + ".pdf")


def _family_name(archive, focus):
    """The name the book and the poster are titled with: the one chosen in
    Settings, else made from the surname of the person in the centre."""
    if archive.owner.family_name:
        return archive.owner.family_name
    person = archive.people.get(focus)
    if person is None:
        return ""
    if person.last_name:
        return _("The {name} family").format(name=person.last_name)
    return person.first_name


@login_required
def family_book(request, username=None):
    from .. import pdf

    owner = archive_owner(request, username)
    archive = Archive(owner)
    focus = _focus_for(request, archive, request.GET.get("person"))
    if focus is None:
        raise Http404(_("The family tree is empty."))
    part = request.GET.get("qism", "")
    if part == "odam":  # the book of one life
        from .people import person_pdf

        return person_pdf(request, focus)
    side = {"ota": "paternal", "ona": "maternal"}.get(part)
    with_stories = can_see_stories(request.user, owner)
    stories = sorted(Event.objects.filter(owner=owner).prefetch_related("people"),
                     key=lambda e: (e.year or 9999, e.month or 0, e.day or 0, e.created_at)) if with_stories else []
    data = pdf.family_book_pdf(archive, focus, owner.display_name,
                               viewer_is_owner=viewer_person(request, archive) == focus,
                               family=_family_name(archive, focus), side=side, stories=stories,
                               with_stories=with_stories)
    name = pgettext("file name", "family-book") + {"ota": "-1", "ona": "-2"}.get(part, "")
    return _pdf_response(data, name + ".pdf")


@login_required
def book_page(request):
    """Choose what the book is about: the whole family, one side of it, or one person."""
    archive = Archive(request.archive)
    focus = _focus_for(request, archive, request.GET.get("person"))
    return render(request, "genealogy/book.html", {
        "focus": archive.people.get(focus), "owner": request.archive,
        "branches": BRANCHES, "stories": Event.objects.filter(owner=request.archive).count(),
    })
