"""Connections: find people on the site, connect, compare and merge family trees."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.sharing import can_edit, can_see_stories, can_view
from apps.genealogy.access import person_for_view
from apps.genealogy.models import Person

from . import merge, services
from .forms import AnswerForm, RequestForm
from .models import Connection


def _mark_read(user):
    from apps.notify.models import Notification

    Notification.objects.filter(user=user, read_at=None, kind__in=[
        "connection_request", "connection_accepted", "follow_request", "new_follower", "follow_accepted",
    ]).update(read_at=timezone.now())


def hub(request):
    """Everything about people on the site, shown on the Friends page: search,
    requests, connections, followers and the accounts one follows."""
    from .models import Follow

    user = request.user
    query = request.GET.get("odam", "").strip()
    results = services.search(user, query) if query else []
    states = services.statuses(user, results) if results else {}
    mine = Connection.objects.filter(Q(sender=user) | Q(recipient=user)).select_related(
        "sender", "recipient", "sender_person", "recipient_person", "sender_anchor", "sender_tree", "recipient_tree")
    incoming = [c for c in mine if c.recipient_id == user.pk and c.status == Connection.Status.PENDING]
    outgoing = [c for c in mine if c.sender_id == user.pk and c.status == Connection.Status.PENDING]
    connected = []
    for c in mine:
        if c.status != Connection.Status.ACCEPTED:
            continue
        other, record = c.other(user), c.person_for(user)
        connected.append({"connection": c, "user": other, "record": record,
                          "label": services.label_in_tree(c.tree_of(user), record, user)})
    follows = Follow.objects.filter(Q(follower=user) | Q(followed=user)).select_related("follower", "followed")
    _mark_read(user)
    return {
        "people_query": query, "people_results": [(u, states.get(u.pk, "")) for u in results],
        "incoming": incoming, "outgoing": outgoing, "connected": connected,
        "follow_requests": [f for f in follows if f.followed_id == user.pk and not f.approved],
        "followers": [f.follower for f in follows if f.followed_id == user.pk and f.approved],
        "following": [f.followed for f in follows if f.follower_id == user.pk],
    }


@login_required
def index(request):
    """The old address of Connections: it lives on the Friends page now."""
    query = request.GET.get("q", "").strip()
    return redirect(reverse("friends:list") + (f"?odam={query}" if query else "") + "#people")


@login_required
def search_json(request):
    """Accounts while typing (for the live search on the Friends page)."""
    query = request.GET.get("q", "").strip()
    users = services.search(request.user, query, limit=8)
    states = services.statuses(request.user, users)
    names = {"connected": _("Connected"), "sent": _("Request sent"), "received": _("Wants to connect")}
    return JsonResponse({"results": [{
        "name": u.display_name, "label": " · ".join(x for x in (f"@{u.username}", str(names.get(states.get(u.pk), "")))
                                                     if x),
        "initials": (u.first_name[:1] + u.last_name[:1]).upper() or u.username[:1].upper(),
        "url": reverse("network:profile", args=[u.username]), "branch": "own",
    } for u in users]})


@login_required
def profile(request, username):
    """An account's page: who they are, follow, connect, their family tree."""
    other = get_object_or_404(get_user_model(), username=username, is_active=True)
    if other.pk == request.user.pk:
        return redirect("accounts:settings")
    from .models import Follow

    sees_tree, sees_stories = can_view(request.user, other), can_see_stories(request.user, other)
    record = Person.objects.filter(pk=other.home_person_id).first()
    mine = services.working_tree(request)
    in_my_tree = Person.objects.filter(owner=mine, linked_user=other).first()
    return render(request, "network/profile.html", {
        "other": other, "record": record if sees_tree else None, "sees_tree": sees_tree,
        "sees_stories": sees_stories, "follow": services.follow_state(request.user, other),
        "followers": Follow.objects.filter(followed=other, approved=True).count(),
        "following": Follow.objects.filter(follower=other, approved=True).count(),
        "people": Person.objects.filter(owner=other).count() if sees_tree else None,
        "connection": services.between(request.user, other),
        "in_my_tree": in_my_tree, "label": services.label_in_tree(mine, in_my_tree, request.user),
        "mine": mine, "can_take": sees_tree and can_edit(request.user, mine),
    })


@require_POST
@login_required
def follow_view(request, username):
    other = get_object_or_404(get_user_model(), username=username, is_active=True)
    if request.POST.get("stop"):
        services.unfollow(request.user, other)
    else:
        try:
            item = services.follow(request.user, other)
        except services.Refused as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("You follow {name}.").format(name=other.display_name) if item.approved
                             else _("Request sent. {name} will decide.").format(name=other.display_name))
    return redirect("network:profile", username=other.username)


@require_POST
@login_required
def follow_answer(request, pk):
    try:
        services.answer_follow(request.user, pk, approve=request.POST.get("approve") == "1")
    except services.Refused as exc:
        messages.error(request, str(exc))
    return redirect(reverse("friends:list") + "#people")


@require_POST
@login_required
def follower_remove(request, username):
    from .models import Follow

    Follow.objects.filter(follower__username=username, followed=request.user).delete()
    return redirect(reverse("friends:list") + "#people")


def _account(username, viewer):
    other = get_object_or_404(get_user_model(), username=username, is_active=True)
    if other.pk == viewer.pk:
        raise PermissionDenied(_("This is your own account."))
    return other


@login_required
def request_view(request, username):
    other = _account(username, request.user)
    existing = services.between(request.user, other)
    if existing is not None:
        if existing.status == Connection.Status.PENDING and existing.recipient_id == request.user.pk:
            return redirect("network:answer", pk=existing.pk)
        return redirect("network:index")
    tree = services.working_tree(request)
    initial = {}
    if request.GET.get("person", "").isdigit():
        initial = {"place": "existing", "person": int(request.GET["person"])}
    form = RequestForm(request.POST or None, user=request.user, tree=tree, other=other, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            services.send(request.user, other, tree, data["kind"], share=data["share"], befriend=data["befriend"],
                          message=data["message"], **form.placement())
        except services.Refused as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, _("The request has been sent. {name} will see it on the site and in Telegram.")
                             .format(name=other.display_name))
            return redirect(reverse("friends:list") + "#people")
    return render(request, "network/request.html", {"other": other, "form": form, "tree": tree})


def _pending_for(request, pk):
    connection = get_object_or_404(Connection.objects.select_related("sender", "sender_person", "sender_anchor",
                                                                     "sender_tree"), pk=pk)
    if connection.recipient_id != request.user.pk:
        raise PermissionDenied(_("Access denied."))
    return connection


@login_required
def answer(request, pk):
    connection = _pending_for(request, pk)
    if connection.status != Connection.Status.PENDING:
        return redirect("network:index")
    if request.method == "POST" and "decline" in request.POST:
        services.decline(connection, request.user)
        messages.success(request, _("The request has been declined."))
        return redirect("network:index")
    tree = services.working_tree(request)
    initial = {"share": connection.share_trees, "befriend": connection.befriend,
               "place": "existing" if connection.kind == Connection.Kind.RELATIVE else "none"}
    form = AnswerForm(request.POST or None, user=request.user, tree=tree, other=connection.sender, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            services.accept(connection, request.user, tree, share=data["share"], befriend=data["befriend"],
                            **form.placement())
        except services.Refused as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, _("You are connected with {name}.").format(name=connection.sender.display_name))
            return redirect("network:connection", pk=connection.pk)
    said = ""
    if connection.sender_person is not None:
        said = services.label_in_tree(connection.sender_tree, connection.sender_person, connection.sender)
    return render(request, "network/answer.html", {
        "connection": connection, "form": form, "tree": tree, "said": said,
    })


@require_POST
@login_required
def cancel(request, pk):
    connection = get_object_or_404(Connection, pk=pk, sender=request.user)
    try:
        services.cancel(connection, request.user)
    except services.Refused as exc:
        messages.error(request, str(exc))
    return redirect("network:index")


@require_POST
@login_required
def disconnect(request, pk):
    connection = get_object_or_404(Connection, Q(sender=request.user) | Q(recipient=request.user), pk=pk)
    services.disconnect(connection, request.user)
    messages.success(request, _("The connection has ended. The people stay in both family trees."))
    return redirect("network:index")


@login_required
def connection_view(request, pk):
    user = request.user
    connection = get_object_or_404(
        Connection.objects.select_related("sender", "recipient", "sender_person", "recipient_person", "sender_tree",
                                          "recipient_tree"),
        Q(sender=user) | Q(recipient=user), pk=pk, status=Connection.Status.ACCEPTED)
    other = connection.other(user)
    my_tree, their_tree = connection.tree_of(user), connection.tree_of(other)
    plan = None
    if my_tree is not None and their_tree is not None and my_tree.pk != their_tree.pk \
            and can_edit(user, my_tree) and can_view(user, their_tree):
        plan = merge.analyse(their_tree, my_tree)
    record = connection.person_for(user)
    return render(request, "network/connection.html", {
        "connection": connection, "other": other, "record": record, "plan": plan,
        "label": services.label_in_tree(my_tree, record, user), "my_tree": my_tree, "their_tree": their_tree,
        "their_person": services.self_record(other, their_tree) if their_tree is not None else None,
    })


def _tree(username, default):
    if not username:
        return default
    return get_object_or_404(get_user_model(), username=username)


@login_required
def merge_view(request):
    """Compare another family tree with mine and take over what it knows."""
    source = _tree(request.GET.get("from") or request.POST.get("from"), None)
    target = _tree(request.GET.get("to") or request.POST.get("to"), services.working_tree(request))
    if source is None or source.pk == target.pk:
        return redirect("network:index")
    if not can_view(request.user, source) or not can_edit(request.user, target):
        raise PermissionDenied(_("Access denied."))
    back = reverse("network:merge") + f"?from={source.username}&to={target.username}"
    if request.method == "POST" and "anchor" in request.POST:
        a = Person.objects.filter(pk=request.POST.get("source_person"), owner=source).first()
        b = Person.objects.filter(pk=request.POST.get("target_person"), owner=target).first()
        if a and b:
            merge.link_match(a, b, request.user)
        return redirect(back)
    me_source, me_target = services.self_record(request.user, source), services.self_record(request.user, target)
    # The user is in both trees (their own record, and the one the other owner made for them): start from there.
    anchors = [(me_source.pk, me_target.pk)] if me_source and me_target else []
    if request.method == "POST":
        done = merge.apply(source, target, keys=request.POST.getlist("item"), actor=request.user, anchors=anchors,
                           with_stories=can_see_stories(request.user, source))
        messages.success(request, _("Done: {added} added, {matched} matched, {filled} details filled in, "
                                    "{linked} family links made. Every change can be undone in History.")
                         .format(**done))
        return redirect(reverse("genealogy:tree") if target.pk == request.archive.pk else back)
    plan = merge.analyse(source, target, anchors=anchors, with_stories=can_see_stories(request.user, source))
    return render(request, "network/merge.html", {
        "plan": plan, "source": source, "target": target, "me_source": me_source, "me_target": me_target,
    })


@require_POST
@login_required
def match(request):
    """"This is the same person" (or "a different person") for two records in two trees."""
    ids = [request.POST.get("a", ""), request.POST.get("b", "")]
    if not all(x.isdigit() for x in ids):
        return redirect("network:index")
    a, b = person_for_view(request, ids[0]), person_for_view(request, ids[1])
    if not (can_edit(request.user, a.owner) or can_edit(request.user, b.owner)):
        raise PermissionDenied(_("Access denied."))
    merge.link_match(a, b, request.user, rejected=request.POST.get("rejected") == "1")
    messages.success(request, _("The information has been saved."))
    nxt = request.POST.get("next", "")
    safe = url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure())
    return redirect(nxt if nxt and safe else a.get_absolute_url())
