"""Settings → General and Your data: name, language, time zone, export and import, deleting the account."""
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext as _

from apps.genealogy.models import Person

from ..forms import ImportArchiveForm, PreferencesForm, ProfileForm


def _save_person_name(user):
    """Keep the user's own record in the tree in step with the account."""
    if user.person:
        user.person.first_name = user.first_name
        user.person.last_name = user.last_name
        user.person.save()


@login_required
def settings_view(request):
    """Settings → General: personal details, language, colours, time zone."""
    user = request.user
    profile_form = ProfileForm(instance=user, prefix="profile")
    prefs_form = PreferencesForm(instance=user, prefix="prefs")
    if request.method == "POST" and "save_profile" in request.POST:
        profile_form = ProfileForm(request.POST, instance=user, prefix="profile")
        if profile_form.is_valid():
            profile_form.save()
            _save_person_name(user)
            messages.success(request, _("The information has been saved."))
            return redirect("accounts:settings")
    elif request.method == "POST" and "save_prefs" in request.POST:
        old_language = user.preferred_language
        prefs_form = PreferencesForm(request.POST, instance=user, prefix="prefs")
        if prefs_form.is_valid():
            prefs_form.save()
            translation.activate(user.preferred_language)
            if user.preferred_language != old_language:
                messages.success(request, _("The interface language has been changed."))
            else:
                messages.success(request, _("The information has been saved."))
            from apps.notify.models import NotificationSettings

            NotificationSettings.objects.filter(user=user).update(last_generated=None)
            return redirect(reverse("accounts:settings") + "#appearance")
    return render(request, "accounts/settings/general.html", {
        "profile_form": profile_form, "prefs_form": prefs_form, "settings_tab": "general",
    })


@login_required
def data_view(request):
    """Settings → Your data: downloads, import, deleting the account."""
    from django.db import transaction

    from apps.genealogy.archive_io import import_archive
    from apps.genealogy.models import Person

    user = request.user
    people = Person.objects.filter(owner=user)
    can_import = people.count() <= 1 and not user.active_archive_id
    form = ImportArchiveForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not can_import:
            messages.error(request, _("An archive can only be imported into an empty family tree."))
            return redirect("accounts:data")
        if form.is_valid():
            with transaction.atomic():
                own = user.person
                user.person = None
                user.own_person = None
                user.save(update_fields=["person", "own_person"])
                if own:
                    own.delete()
                counts = import_archive(user, form.cleaned_data["file"])
            messages.success(request, _("The archive has been imported: %(people)d people.") % counts)
            return redirect("genealogy:tree")
    return render(request, "accounts/settings/data.html", {
        "form": form, "can_import": can_import, "people_count": people.count(),
        "friends_count": user.contacts.count(), "stories_count": user.stories.count(),
        "events_count": user.events.count(),
        "settings_tab": "data",
    })


@login_required
def delete_account(request):
    """Delete the account and the whole family archive, after typing the username."""
    error = ""
    if request.method == "POST":
        if request.POST.get("confirm", "").strip() == request.user.username:
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, _("Your account and all its data have been deleted."))
            return redirect("home")
        error = _("The username does not match.")
    return render(request, "accounts/settings/delete_account.html", {"error": error})
