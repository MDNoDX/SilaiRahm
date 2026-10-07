"""Who may see and change a family archive.

The owner may change everything. Relatives who joined through an invite may
look at the archive (viewers) or also add and correct people (editors).
`request.archive` is the archive the signed-in user is working in: their own,
or a shared one they switched to.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.translation import gettext as _

from apps.accounts.sharing import can_edit, can_see_stories, can_view

from .models import Person

__all__ = ["can_view", "can_edit", "can_see_stories", "require_edit", "person_for_view", "person_for_edit", "archive_owner",
           "viewer_person"]


def require_edit(request, owner=None):
    """The archive to add to; refuses viewers."""
    owner = owner or request.archive
    if not can_edit(request.user, owner):
        raise PermissionDenied(_("You do not have permission to change this information."))
    return owner


def person_for_view(request, pk):
    person = Person.objects.select_related("owner", "father", "mother").filter(pk=pk).first()
    if person is None:
        raise Http404(_("Person not found."))
    if not can_view(request.user, person.owner):
        raise PermissionDenied(_("Access denied."))
    return person


def person_for_edit(request, pk):
    person = person_for_view(request, pk)
    require_edit(request, person.owner)
    return person


def archive_owner(request, username=None):
    """The user whose archive is being viewed: the active one, or one named in the address."""
    if not username or username == request.archive.username:
        return request.archive
    owner = get_user_model().objects.filter(username=username).first()
    if owner is None:
        raise Http404(_("User not found."))
    if not can_view(request.user, owner):
        raise PermissionDenied(_("Access denied."))
    return owner


def viewer_person(request, archive):
    """The person relationship names are counted from: the viewer's own
    record when it is in this archive (also the record a relative who joined
    or connected is known by there), otherwise the archive owner's."""
    user = request.user
    if user.person_id in archive.people:
        return user.person_id
    if getattr(user, "is_authenticated", False) and archive.owner.pk != user.pk:
        from apps.accounts.models import Membership

        cache = user.__dict__.setdefault("_member_person", {})
        if archive.owner.pk not in cache:
            cache[archive.owner.pk] = (Membership.objects.filter(owner=archive.owner, member=user)
                                       .values_list("person_id", flat=True).first())
        if cache[archive.owner.pk] in archive.people:
            return cache[archive.owner.pk]
    home = archive.owner.home_person_id
    return home if home in archive.people else None
