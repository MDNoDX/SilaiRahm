"""Settings → Family members: invitation links, members and their rights, switching between family trees."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.genealogy.models import Person


@login_required
def family_view(request):
    """Settings → Family: who may see or edit my archive, and the trees I take part in."""
    from ..forms import InviteForm
    from ..models import Invite
    from ..sharing import archives_of, open_invites

    user = request.user
    form = InviteForm(request.POST or None, owner=user)
    new_invite = None
    if request.method == "POST" and form.is_valid():
        invite = form.save(commit=False)
        invite.owner = invite.created_by = user
        invite.save()
        return redirect(f"{reverse('accounts:family')}?yangi={invite.pk}#invites")
    if request.GET.get("yangi", "").isdigit():
        new_invite = Invite.objects.filter(owner=user, pk=int(request.GET["yangi"])).first()
    return render(request, "accounts/settings/family.html", {
        "form": form, "new_invite": new_invite if new_invite and new_invite.is_open else None,
        "new_link": request.build_absolute_uri(reverse("accounts:invite", args=[new_invite.token])) if new_invite else "",
        "invites": open_invites(user),
        "members": user.members.select_related("member", "person"),
        "archives": archives_of(user),
        "own_people": Person.objects.filter(owner=user).count(),
        "settings_tab": "family",
    })


@require_POST
@login_required
def invite_revoke(request, pk):
    from ..models import Invite

    Invite.objects.filter(owner=request.user, pk=pk, accepted_at=None).delete()
    messages.info(request, _("The invitation link no longer works."))
    return redirect(reverse("accounts:family") + "#invites")


@require_POST
@login_required
def member_update(request, pk):
    """Change a member's access, or remove them."""
    from ..models import Membership, Role
    from ..sharing import remove_member

    membership = Membership.objects.filter(owner=request.user, pk=pk).select_related("member").first()
    if membership is None:
        return redirect("accounts:family")
    if "remove" in request.POST:
        remove_member(request.user, membership.member)
        messages.info(request, _("Access has been removed."))
    elif request.POST.get("role") in Role.values:
        membership.role = request.POST["role"]
        membership.save(update_fields=["role"])
        messages.success(request, _("The information has been saved."))
    return redirect(reverse("accounts:family") + "#members")


@require_POST
@login_required
def archive_switch(request, user_id):
    """Work in another family tree (or back in my own)."""
    from django.contrib.auth import get_user_model

    from ..sharing import switch_archive

    owner = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if owner is None or not switch_archive(request.user, owner):
        messages.error(request, _("Access denied."))
        return redirect("accounts:family")
    return redirect("home")


@require_POST
@login_required
def archive_leave(request, user_id):
    from django.contrib.auth import get_user_model

    from ..sharing import leave

    owner = get_user_model().objects.filter(pk=user_id).first()
    if owner is not None:
        leave(request.user, owner)
        messages.info(request, _("You have left this family tree."))
    return redirect("accounts:family")


def invite_view(request, token):
    """The page an invitation link opens: sign in or up, then join."""
    from ..models import Invite
    from ..sharing import accept_invite, role_in

    invite = Invite.objects.filter(token=token).select_related("owner", "person").first()
    if invite is None or not invite.is_open:
        if invite and request.user.is_authenticated and role_in(request.user, invite.owner):
            return redirect("home")  # already joined with this link
        return render(request, "accounts/invite/invite.html", {"invite": None}, status=410)
    if not request.user.is_authenticated:
        request.session["invite"] = token
        return render(request, "accounts/invite/invite.html", {"invite": invite, "next": request.path})
    if invite.owner_id == request.user.pk:
        messages.info(request, _("This is your own invitation link: send it to a relative."))
        return redirect("accounts:family")
    if request.method == "POST":
        membership = accept_invite(invite, request.user)
        request.session.pop("invite", None)
        if membership is None:
            return render(request, "accounts/invite/invite.html", {"invite": None}, status=410)
        messages.success(request, _("You have joined the family tree."))
        if not request.user.person_id:
            return redirect("accounts:who_am_i")
        return redirect(_merge_or_home(request.user, invite.owner))
    return render(request, "accounts/invite/invite.html", {
        "invite": invite, "own_people": Person.objects.filter(owner=request.user).count(),
    })


def _merge_or_home(user, owner):
    """After joining: a relative who already has a family tree of their own is
    offered to merge it into the shared one (only what is ticked is taken)."""
    from django.urls import reverse

    from apps.accounts.sharing import can_edit

    if can_edit(user, owner) and Person.objects.filter(owner=user).count() > 1:
        return f"{reverse('network:merge')}?from={user.username}&to={owner.username}"
    return reverse("home")


@login_required
def who_am_i(request):
    """After joining a shared tree: find your own record in it (optional)."""
    from ..models import Membership

    owner = request.archive
    if request.method == "POST":
        from ..sharing import remember_same_person

        person = Person.objects.filter(owner=owner, pk=request.POST.get("person") or 0).first()
        if person is not None and not hasattr(person, "account"):
            request.user.person = person
            request.user.save(update_fields=["person"])
            Membership.objects.filter(owner=owner, member=request.user).update(person=person)
            if request.user.own_person_id:
                remember_same_person(request.user.own_person_id, person.pk, request.user)
            return redirect(_merge_or_home(request.user, owner))
        return redirect("home")
    return render(request, "accounts/invite/who_am_i.html", {"owner": owner})
