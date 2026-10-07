"""Family events and upcoming dates."""
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.notify.messages import render_parts
from apps.notify.occasions import occasions

from .. import history
from ..access import can_edit, can_see_stories, require_edit
from ..forms import EventForm
from ..models import Change, Event


@login_required
def upcoming(request):
    today = timezone.localdate()
    days = 120
    items = [(o, render_parts(o.kind, o.params, (o.date - today).days), (o.date - today).days)
             for o in occasions(request.archive, today, today + datetime.timedelta(days=days))]
    events = Event.objects.filter(owner=request.archive).prefetch_related("people")
    by_year = {}
    for e in events:
        by_year.setdefault(e.year, []).append(e)
    return render(request, "genealogy/events/list.html", {
        "items": items, "days": days, "by_year": sorted(by_year.items(), key=lambda kv: -(kv[0] or 0)),
        "kinds": Event.Kind.choices,
    })


@login_required
def event_detail(request, pk):
    event = get_object_or_404(Event.objects.prefetch_related("people"), pk=pk)
    if not can_see_stories(request.user, event.owner):
        raise PermissionDenied(_("Access denied."))
    return render(request, "genealogy/events/detail.html", {
        "event": event, "is_owner": can_edit(request.user, event.owner)})


def _own_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    require_edit(request, event.owner)
    return event


@login_required
def event_create(request):
    owner = require_edit(request)
    initial = {}
    if request.GET.get("kind") in dict(Event.Kind.choices):
        initial["kind"] = request.GET["kind"]
    if request.GET.get("person", "").isdigit():
        initial["people"] = [int(request.GET["person"])]
    form = EventForm(request.POST or None, request.FILES or None, owner=owner, initial=initial)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        history.record(owner, request.user, Change.Action.CREATED, subject=event.display_title, what="event")
        messages.success(request, _("The event has been saved."))
        return redirect(event)
    return render(request, "genealogy/events/form.html", {"form": form, "is_new": True})


@login_required
def event_edit(request, pk):
    event = _own_event(request, pk)
    form = EventForm(request.POST or None, request.FILES or None, instance=event, owner=event.owner)
    if request.method == "POST" and form.is_valid():
        form.save()
        history.record(event.owner, request.user, Change.Action.UPDATED, subject=event.display_title, what="event")
        messages.success(request, _("The event has been saved."))
        return redirect(event)
    return render(request, "genealogy/events/form.html", {"form": form, "event": event, "is_new": False})


@login_required
def event_delete(request, pk):
    event = _own_event(request, pk)
    if request.method == "POST":
        history.record(event.owner, request.user, Change.Action.DELETED, subject=event.display_title, what="event")
        if event.recording:
            event.recording.delete(save=False)
        event.delete()
        messages.success(request, _("The event has been deleted."))
        return redirect("genealogy:upcoming")
    return render(request, "genealogy/confirm_delete.html", {
        "object_name": event.display_title, "cancel_url": event.get_absolute_url(),
    })
