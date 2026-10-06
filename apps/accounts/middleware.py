from django.shortcuts import redirect
from django.urls import reverse

from .sharing import role_in

# Paths a user without a profile may still open.
ALLOWED_PREFIXES = ("/profilni-toldirish/", "/chiqish/", "/til/", "/static/", "/media/",
                    "/accounts/", "/admin/", "/salomatlik/", "/cron/", "/telegram/", "/ilova/", "/taklif/",
                    "/sw.js", "/sozlamalar/oila/")


class ArchiveMiddleware:
    """Sets `request.archive` (the family archive in use) and `request.role`
    ("owner", "editor" or "viewer"); falls back to the user's own archive if
    access to a shared one has been taken away."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            owner = user.archive_owner
            role = role_in(user, owner)
            if role is None or not owner.is_active:
                user.active_archive = None  # membership was removed
                user.person = user.own_person
                user.save(update_fields=["active_archive", "person"])
                owner, role = user, "owner"
            request.archive = owner
            request.role = role
            request.can_edit = role in ("owner", "editor")
        return self.get_response(request)


class ProfileCompletionMiddleware:
    """A user without a record in their own tree (e.g. just signed up with
    Google) is asked for the few details the tree needs before anything else.
    In a shared tree the record is optional: the user picks themselves later."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (user is not None and user.is_authenticated and not user.person_id and not user.active_archive_id
                and not user.is_staff and not request.path.startswith(ALLOWED_PREFIXES)):
            return redirect(f"{reverse('accounts:complete_profile')}?next={request.get_full_path()}")
        return self.get_response(request)
