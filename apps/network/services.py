"""Finding people on the site and connecting accounts.

    search(viewer, query)           accounts the viewer may find
    send(...) / accept(...)         a request, and what accepting it does
    decline / cancel / disconnect   the other ways a request or connection ends
"""
import datetime
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import Membership
from apps.accounts.sharing import can_edit
from apps.core.names import gender_of
from apps.core.text import search_tokens
from apps.friends.models import Contact
from apps.genealogy import history
from apps.genealogy.kinship import Archive
from apps.genealogy.models import Change, Person
from apps.genealogy.relations import RELATIONS, attach, problem

from .merge import copy_person, link_match
from .models import Connection, PersonMatch

log = logging.getLogger(__name__)
MAX_PENDING = 20                         # unanswered requests one account may have out at a time
ASK_AGAIN_AFTER = datetime.timedelta(days=7)


class Refused(Exception):
    """A request that cannot be sent or answered; the message says why."""


def self_record(user, tree):
    """The record that is `user` in the family tree of `tree` (an account), or None."""
    if tree is None:
        return None
    if tree.pk == user.pk:
        pk = user.home_person_id
    elif user.active_archive_id == tree.pk:
        pk = user.person_id
    else:
        pk = Membership.objects.filter(owner=tree, member=user).values_list("person_id", flat=True).first()
    return Person.objects.filter(pk=pk, owner=tree).first() if pk else None


def working_tree(request):
    """The family tree the user works in for connections: the one open now if
    they may edit it, else their own."""
    return request.archive if getattr(request, "can_edit", False) else request.user


# ---- search ----------------------------------------------------------------
def search(viewer, query, limit=30):
    """Accounts matching `query`. Someone who chose not to be found shows up
    only for their exact username or e-mail, or for those already connected."""
    query = (query or "").strip()
    if len(query) < 2:
        return []
    users = get_user_model().objects.filter(is_active=True).exclude(pk=viewer.pk)
    exact = Q(username__iexact=query.lstrip("@"))
    if "@" in query[1:]:
        exact |= Q(email__iexact=query)
    connected = connected_ids(viewer)
    by_name = Q(discoverable=True) | Q(pk__in=connected)
    named = users
    for token in search_tokens(query):
        named = named.filter(search_key__contains=token)
    found = list(users.filter(exact)[:5]) + list(named.filter(by_name).order_by("first_name", "last_name")[:limit])
    seen, out = set(), []
    for user in found:
        if user.pk not in seen:
            seen.add(user.pk)
            out.append(user)
    return out[:limit]


def connected_ids(user):
    """The accounts `user` is connected with."""
    rows = Connection.objects.filter(Q(sender=user) | Q(recipient=user), status=Connection.Status.ACCEPTED)
    return {r if s == user.pk else s for s, r in rows.values_list("sender_id", "recipient_id")}


def between(a, b):
    """The open or accepted connection between two accounts, if any."""
    return (Connection.objects.filter(Q(sender=a, recipient=b) | Q(sender=b, recipient=a),
                                      status__in=[Connection.Status.PENDING, Connection.Status.ACCEPTED])
            .order_by("-created_at").first())


def statuses(viewer, users):
    """For each user: "connected", "sent", "received" or "" (for the search results)."""
    rows = Connection.objects.filter(
        Q(sender=viewer, recipient__in=users) | Q(recipient=viewer, sender__in=users),
        status__in=[Connection.Status.PENDING, Connection.Status.ACCEPTED])
    out = {}
    for c in rows:
        other = c.recipient_id if c.sender_id == viewer.pk else c.sender_id
        if c.status == Connection.Status.ACCEPTED:
            out[other] = "connected"
        else:
            out.setdefault(other, "sent" if c.sender_id == viewer.pk else "received")
    return out


# ---- placing someone in a tree ---------------------------------------------
def check_place(user, tree, other, person=None, relation="", anchor=None):
    """Why this place for `other` in `tree` is not possible, or None."""
    if person is None and not relation:
        return None
    if tree is None or not can_edit(user, tree):
        return _("You do not have permission to change this information.")
    if person is not None:
        if person.owner_id != tree.pk:
            return _("Choose a person from your family tree.")
        if person.linked_user_id and person.linked_user_id != other.pk:
            return _("This record already belongs to another account.")
        return None
    if relation not in RELATIONS or anchor is None or anchor.owner_id != tree.pk:
        return _("Choose who they are related to.")
    return problem(anchor, Person(gender=gender_of(other)), relation)


def place(user, tree, other, person=None, relation="", anchor=None):
    """The record of `other` in `tree`: an existing one, or a new one made
    from `other`'s own record and attached as `relation` of `anchor`."""
    if check_place(user, tree, other, person, relation, anchor) is not None:
        return None
    if person is not None:
        return person
    if not relation:
        return None
    source = Person.objects.filter(pk=other.home_person_id).first()
    if source is not None:
        new = copy_person(source, tree)
    else:
        new = Person.objects.create(owner=tree, first_name=other.first_name or other.username,
                                    last_name=other.last_name, gender=gender_of(other) or "male")
    if problem(anchor, new, relation, Archive(tree)):
        new.delete()
        return None
    before = history.snapshot(anchor)
    attach(anchor, new, relation, tree)
    history.record(tree, user, Change.Action.CREATED, new, details={"relation": relation, "to": anchor.short_name})
    anchor.refresh_from_db()
    history.record_update(user, anchor, before)
    return new


def label_in_tree(tree, person, viewer):
    """What `person` is to `viewer` in `tree` ("Cousin"), or ""."""
    if tree is None or person is None:
        return ""
    me = self_record(viewer, tree)
    if me is None or me.pk == person.pk:
        return ""
    return Archive(tree).label(me.pk, person.pk)


# ---- requests -----------------------------------------------------------------
@transaction.atomic
def send(sender, recipient, tree, kind, person=None, relation="", anchor=None, share=True, befriend=False,
         message=""):
    if recipient.pk == sender.pk:
        raise Refused(_("This is your own account."))
    existing = between(sender, recipient)
    if existing is not None:
        if existing.status == Connection.Status.ACCEPTED:
            raise Refused(_("You are already connected."))
        if existing.sender_id == recipient.pk:
            raise Refused(_("{name} has already sent you a request: answer it below.").format(
                name=recipient.display_name))
        raise Refused(_("Your request is already waiting for an answer."))
    if Connection.objects.filter(sender=sender, recipient=recipient, status=Connection.Status.DECLINED,
                                 answered_at__gte=timezone.now() - ASK_AGAIN_AFTER).exists():
        raise Refused(_("This request was declined recently. You can ask again in a few days."))
    if Connection.objects.filter(sender=sender, status=Connection.Status.PENDING).count() >= MAX_PENDING:
        raise Refused(_("You have many unanswered requests. Wait for answers before sending more."))
    if kind == Connection.Kind.FRIEND:
        person, relation, anchor = None, "", None
    error = check_place(sender, tree, recipient, person, relation, anchor)
    if error:
        raise Refused(error)
    connection = Connection.objects.create(
        sender=sender, recipient=recipient, kind=kind, sender_tree=tree, sender_person=person,
        sender_relation=relation if person is None else "", sender_anchor=anchor if person is None else None,
        share_trees=share, befriend=befriend, message=message.strip()[:300])
    notify(recipient, "connection_request", {"name": sender.display_name}, f"connection:{connection.pk}:request")
    return connection


@transaction.atomic
def accept(connection, user, tree, person=None, relation="", anchor=None, share=None, befriend=None):
    if connection.recipient_id != user.pk or connection.status != Connection.Status.PENDING:
        raise Refused(_("This request is no longer waiting for an answer."))
    sender = connection.sender
    error = check_place(user, tree, sender, person, relation, anchor)
    if error:
        raise Refused(error)
    connection.share_trees = connection.share_trees if share is None else share
    connection.befriend = connection.befriend if befriend is None else befriend
    # The recipient in the sender's tree (chosen by the sender), and the sender in the recipient's tree.
    theirs = place(sender, connection.sender_tree, user, connection.sender_person, connection.sender_relation,
                   connection.sender_anchor)
    mine = place(user, tree, sender, person, relation, anchor)
    connection.sender_person, connection.recipient_person, connection.recipient_tree = theirs, mine, tree
    connection.status, connection.answered_at = Connection.Status.ACCEPTED, timezone.now()
    connection.save()
    for record, account in ((theirs, user), (mine, sender)):
        if record is not None and record.linked_user_id != account.pk:
            record.linked_user = account
            record.save(update_fields=["linked_user"])
    # Each of them is the same person as their own record in their own tree.
    for record, account, account_tree in ((theirs, user, tree), (mine, sender, connection.sender_tree)):
        own = self_record(account, account_tree)
        if record is not None and own is not None:
            link_match(record, own, user)
    if connection.share_trees:
        made = [share_tree(owner, member, record)
                for owner, member, record in ((connection.sender_tree, user, theirs), (tree, sender, mine))]
        connection.shared_memberships = [m.pk for m in made if m is not None]
        connection.save(update_fields=["shared_memberships"])
    if connection.befriend:
        befriend_accounts(sender, user)
        befriend_accounts(user, sender)
    notify(sender, "connection_accepted", {"name": user.display_name, "kind": connection.kind},
           f"connection:{connection.pk}:accepted")
    return connection


def share_tree(owner, member, record):
    """Let `member` open `owner`'s tree (as a viewer, unless they already may more)."""
    if owner is None or owner.pk == member.pk:
        return None
    membership, created = Membership.objects.get_or_create(
        owner=owner, member=member, defaults={"role": "viewer", "person": record})
    if not created and record is not None and membership.person_id is None:
        membership.person = record
        membership.save(update_fields=["person"])
    return membership if created else None


def befriend_accounts(owner, friend):
    """`friend` in `owner`'s list of friends (with their birthday for reminders)."""
    me = Person.objects.filter(pk=owner.home_person_id).first()
    if me is None or Contact.objects.filter(owner=owner, linked_user=friend).exists():
        return None
    record = Person.objects.filter(pk=friend.home_person_id).first()
    return Contact.objects.create(
        owner=owner, person=me, linked_user=friend, name=friend.display_name, how_met="",
        birth_year=getattr(record, "birth_year", None), birth_month=getattr(record, "birth_month", None),
        birth_day=getattr(record, "birth_day", None))


def decline(connection, user):
    if connection.recipient_id != user.pk or connection.status != Connection.Status.PENDING:
        raise Refused(_("This request is no longer waiting for an answer."))
    connection.status, connection.answered_at = Connection.Status.DECLINED, timezone.now()
    connection.save(update_fields=["status", "answered_at"])


def cancel(connection, user):
    if connection.sender_id != user.pk or connection.status != Connection.Status.PENDING:
        raise Refused(_("This request is no longer waiting for an answer."))
    connection.delete()


@transaction.atomic
def disconnect(connection, user):
    """End a connection: the trees are no longer shared through it and the
    records stop pointing at the accounts. The people stay in both trees."""
    if user.pk not in (connection.sender_id, connection.recipient_id):
        raise Refused(_("Access denied."))
    # Only the view access this connection gave; a role raised by hand since then stays.
    Membership.objects.filter(pk__in=connection.shared_memberships or [], role="viewer").delete()
    pair = [connection.sender_id, connection.recipient_id]
    Person.objects.filter(pk__in=[connection.sender_person_id, connection.recipient_person_id],
                          linked_user_id__in=pair).update(linked_user=None)
    Contact.objects.filter(owner_id__in=pair, linked_user_id__in=pair).update(linked_user=None)
    trees = [t for t in (connection.sender_tree_id, connection.recipient_tree_id) if t]
    if len(trees) == 2:
        PersonMatch.objects.filter(Q(first__owner_id=trees[0], second__owner_id=trees[1]) |
                                   Q(first__owner_id=trees[1], second__owner_id=trees[0])).delete()
    connection.delete()


# ---- telling the other side --------------------------------------------------
def notify(user, kind, params, key):
    """A notification on the site, sent at once to Telegram and to phones."""
    from apps.notify.models import Notification
    from apps.notify.service import deliver_now

    notification, _created = Notification.objects.update_or_create(
        user=user, key=key, defaults={"kind": kind, "params": params, "url": reverse("network:index"),
                                      "read_at": None})
    try:
        deliver_now(notification)
    except Exception as exc:  # noqa: BLE001 - the request itself must not fail because of Telegram
        log.warning("Could not deliver %s to user %s: %s", kind, user.pk, exc)
    return notification
