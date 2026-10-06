"""Shared family trees: who may see or change an archive, and which archive
an account is working in.

Every account owns one archive. A relative who joins through an invite gets
a Membership (viewer or editor) and can make that archive their "active" one:
they then see the same tree, named from their own place in it.
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Invite, Membership, Role


def role_in(user, owner):
    """"owner", "editor", "viewer" or None."""
    if not getattr(user, "is_authenticated", False) or owner is None:
        return None
    if user.pk == owner.pk:
        return "owner"
    cache = user.__dict__.setdefault("_roles", {})
    if owner.pk not in cache:
        cache[owner.pk] = Membership.objects.filter(owner=owner, member=user).values_list("role", flat=True).first()
    return cache[owner.pk]


def can_view(user, owner):
    return role_in(user, owner) is not None


def can_edit(user, owner):
    return role_in(user, owner) in ("owner", Role.EDITOR)


def _remember_identity(user):
    """Store who the user is in the archive they are leaving."""
    if user.active_archive_id:
        Membership.objects.filter(owner_id=user.active_archive_id, member=user).update(person=user.person)
    else:
        user.own_person = user.person


@transaction.atomic
def switch_archive(user, owner):
    """Make `owner`'s archive (or the user's own) the one the user works in."""
    if owner.pk != user.pk and not can_view(user, owner):
        return False
    _remember_identity(user)
    if owner.pk == user.pk:
        user.active_archive = None
        person = user.own_person
    else:
        membership = Membership.objects.get(owner=owner, member=user)
        user.active_archive = owner
        person = membership.person
    # A person can belong to one account only.
    if person is not None and get_user_model().objects.filter(person=person).exclude(pk=user.pk).exists():
        person = None
    user.person = person
    user.save(update_fields=["active_archive", "person", "own_person"])
    return True


@transaction.atomic
def accept_invite(invite, user):
    """Join the archive of an invite. Returns the membership, or None if the
    link is used up, expired or the user's own."""
    if not invite.is_open or invite.owner_id == user.pk:
        return None
    membership, created = Membership.objects.get_or_create(
        owner=invite.owner, member=user, defaults={"role": invite.role})
    if not created and invite.role == Role.EDITOR and membership.role != Role.EDITOR:
        membership.role = Role.EDITOR
    person = invite.person
    if person is not None and (get_user_model().objects.filter(person=person).exclude(pk=user.pk).exists()
                               or Membership.objects.filter(person=person).exclude(pk=membership.pk).exists()):
        person = None  # someone else already is this relative
    if person is not None:
        membership.person = person
    membership.save()
    invite.accepted_by = user
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_by", "accepted_at"])
    user.__dict__.pop("_roles", None)
    own = user.home_person_id
    switch_archive(user, invite.owner)
    if membership.person_id and own:
        remember_same_person(own, membership.person_id, user)
    return membership


def remember_same_person(a_pk, b_pk, user):
    """The joining relative's own record and their record in the shared tree are
    one person: the two trees can then be compared and merged from there."""
    from apps.genealogy.models import Person
    from apps.network.merge import link_match

    a, b = Person.objects.filter(pk=a_pk).first(), Person.objects.filter(pk=b_pk).first()
    if a is not None and b is not None:
        link_match(a, b, user)


def leave(user, owner):
    """Stop being a member of `owner`'s archive."""
    if user.active_archive_id == owner.pk:
        switch_archive(user, user)
    Membership.objects.filter(owner=owner, member=user).delete()
    user.__dict__.pop("_roles", None)


def remove_member(owner, member):
    if member.active_archive_id == owner.pk:
        switch_archive(member, member)
    Membership.objects.filter(owner=owner, member=member).delete()


def archives_of(user):
    """Memberships of archives the user has joined (for the switcher)."""
    return list(Membership.objects.filter(member=user).select_related("owner"))


def open_invites(owner):
    cutoff = timezone.now() - timezone.timedelta(days=Invite.VALID_DAYS)
    return Invite.objects.filter(owner=owner, accepted_at=None, created_at__gt=cutoff).select_related("person")
