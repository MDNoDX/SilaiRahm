"""Search: the results page and the live search used by pickers and the command palette."""
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from apps.core.text import search_tokens

from ..access import archive_owner
from ..kinship import Archive
from ..models import Person
from ._common import _focus_for, _search


def _ranked(queryset, query, limit):
    """People matching every word of `query`, best matches first.

    A match at the start of the first name ranks highest, then at the start
    of any name, then anywhere; ties are ordered by name.
    """
    tokens = search_tokens(query)
    if not tokens:
        return []
    found = list(_search(queryset, query)[:400])

    def score(p):
        words = p.search_key.split()
        sc = 0
        if words and words[0].startswith(tokens[0]):
            sc -= 4
        if all(any(w.startswith(t) for w in words) for t in tokens):
            sc -= 2
        return (sc, p.first_name.lower(), p.last_name.lower())

    return sorted(found, key=score)[:limit]


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        archive = Archive(request.archive)
        focus = _focus_for(request, archive)
        branches = archive.branches(focus) if focus else {}
        found = _ranked(Person.objects.filter(owner=request.archive), query, 120)
        results = [(p, archive.label(focus, p.pk) if focus else "", branches.get(p.pk, "other")) for p in found]
    template = "genealogy/search/_results.html" if request.GET.get("partial") else "genealogy/search/page.html"
    return render(request, template, {"query": query, "results": results})


@login_required
def search_json(request):
    """Live search for the command palette, the pickers and the tree."""
    owner = archive_owner(request, request.GET.get("owner"))
    query = request.GET.get("q", "").strip()
    archive = Archive(owner)
    focus = _focus_for(request, archive)
    branches = archive.branches(focus) if focus else {}
    people = Person.objects.filter(owner=owner)
    if request.GET.get("gender") in ("male", "female"):
        people = people.filter(gender=request.GET["gender"])
    found = _ranked(people, query, 8) if query else []
    return JsonResponse({"results": [{
        "id": p.pk, "name": p.short_name, "years": p.lifespan,
        "label": archive.label(focus, p.pk) if focus and p.pk != focus else "",
        "url": p.get_absolute_url(), "initials": p.initials, "gender": p.gender,
        "branch": branches.get(p.pk, "other"),
        "photo": f"{p.photo.url}?s=t" if p.photo else "",
    } for p in found], "all_url": f"{reverse('genealogy:search')}?q={quote(query)}"})
