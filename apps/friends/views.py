import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.text import search_tokens
from apps.genealogy.access import require_edit
from apps.genealogy.models import Person
from apps.notify.messages import render_parts
from apps.notify.occasions import occasions

from .forms import ContactForm
from .models import Contact


# ---------------------------------------------------------------------------
# Friends: people on the site (follow, connect) and friends of the family
# ---------------------------------------------------------------------------
@login_required
def friends_list(request):
    owner = request.archive
    contacts = Contact.objects.filter(owner=owner).select_related("person", "linked_user")
    whose = request.GET.get("kimning", "")
    query = request.GET.get("q", "").strip()
    if whose.isdigit():
        contacts = contacts.filter(person_id=int(whose))
    for token in search_tokens(query):
        contacts = contacts.filter(search_key__contains=token)
    groups = {}
    for c in contacts.order_by("person__first_name", "name"):
        groups.setdefault(c.person, []).append(c)
    # The user's own friends first.
    ordered = sorted(groups.items(), key=lambda kv: (kv[0].pk != request.user.person_id, kv[0].first_name))
    people_with_friends = Person.objects.filter(owner=owner, friends__isnull=False).distinct()
    today = timezone.localdate()
    upcoming = [o for o in occasions(owner, today, today + datetime.timedelta(days=45))
                if o.kind == "friend_birthday"]
    context = {"groups": ordered, "whose": whose, "query": query, "total": Contact.objects.filter(owner=owner).count()}
    if request.GET.get("partial"):  # the live search above the list
        return render(request, "friends/_groups.html", context)
    from apps.network.views import hub

    return render(request, "friends/list.html", {
        **context, **hub(request), "people_with_friends": people_with_friends,
        "upcoming": [(o, render_parts(o.kind, o.params, (o.date - today).days)) for o in upcoming],
    })


@login_required
def contact_create(request):
    owner = require_edit(request)
    initial = {}
    if request.GET.get("kimning", "").isdigit():
        initial["person"] = int(request.GET["kimning"])
    form = ContactForm(request.POST or None, owner=owner, default_person=request.user.person_id, initial=initial)
    if request.method == "POST" and form.is_valid():
        contact = form.save()
        messages.success(request, _("The friend has been added."))
        return redirect(f"{reverse('friends:list')}?kimning={contact.person_id}")
    return render(request, "friends/contact_form.html", {"form": form, "is_new": True})


def _contact(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    require_edit(request, contact.owner)
    return contact


@login_required
def contact_edit(request, pk):
    contact = _contact(request, pk)
    form = ContactForm(request.POST or None, instance=contact, owner=contact.owner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The information has been saved."))
        return redirect("friends:list")
    return render(request, "friends/contact_form.html", {"form": form, "contact": contact, "is_new": False})


@login_required
def contact_delete(request, pk):
    contact = _contact(request, pk)
    if request.method == "POST":
        contact.delete()
        messages.success(request, _("The record has been deleted."))
        return redirect("friends:list")
    return render(request, "genealogy/confirm_delete.html", {
        "object_name": contact.name, "cancel_url": reverse("friends:list"),
    })
