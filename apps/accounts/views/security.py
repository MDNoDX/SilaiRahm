"""Settings → Security: password, two-step sign-in, other devices, Google."""
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from ..forms import PasswordChangeForm, SetPasswordForm


@login_required
def security_view(request):
    """Settings → Security: password, Google, other devices."""
    user = request.user
    has_password = user.has_usable_password()
    form_class = PasswordChangeForm if has_password else SetPasswordForm
    form = form_class(user, request.POST or None) if "save_password" in request.POST else form_class(user)
    if request.method == "POST" and "save_password" in request.POST and form.is_valid():
        form.save()
        update_session_auth_hash(request, user)
        messages.success(request, _("Your password has been changed.") if has_password
                         else _("The password has been set. You can now sign in with it too."))
        return redirect(reverse("accounts:security") + "#password")
    google = user.socialaccount_set.filter(provider="google").first()
    return render(request, "accounts/settings/security.html", {
        "form": form, "has_password": has_password, "google_account": google,
        "google_email": (google.extra_data or {}).get("email", "") if google else "",
        "other_sessions": _other_sessions(request).count(), "settings_tab": "security",
        "recovery_left": len(user.recovery_codes or []),
    })


@login_required
def two_factor_setup(request):
    """Turn two-step sign-in on: scan the QR code, confirm with a code."""
    from apps.notify.telegram import qr_svg

    from .. import totp
    from ..forms import CodeForm

    user = request.user
    if user.totp_enabled:
        return redirect(reverse("accounts:security") + "#two-step")
    secret = request.session.get("totp_new") or totp.new_secret()
    request.session["totp_new"] = secret
    form = CodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if totp.verify(secret, form.cleaned_data["code"]):
            codes, hashes = totp.new_recovery_codes()
            user.totp_secret, user.totp_enabled, user.recovery_codes = secret, True, hashes
            user.save(update_fields=["totp_secret", "totp_enabled", "recovery_codes"])
            request.session.pop("totp_new", None)
            return render(request, "accounts/settings/two_factor_codes.html", {"codes": codes, "settings_tab": "security"})
        form.add_error("code", _("The code is not correct."))
    return render(request, "accounts/settings/two_factor_setup.html", {
        "form": form, "secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)),
        "qr": qr_svg(totp.uri(secret, user.email or user.username)), "settings_tab": "security",
    })


@require_POST
@login_required
def two_factor_off(request):
    from .. import totp

    user = request.user
    code = request.POST.get("code", "")
    if user.totp_enabled and (totp.verify(user.totp_secret, code) or totp.use_recovery_code(user, code)):
        user.totp_secret, user.totp_enabled, user.recovery_codes = "", False, []
        user.save(update_fields=["totp_secret", "totp_enabled", "recovery_codes"])
        messages.info(request, _("Two-step sign-in has been turned off."))
    else:
        messages.error(request, _("The code is not correct."))
    return redirect(reverse("accounts:security") + "#two-step")


@require_POST
@login_required
def two_factor_codes(request):
    """New recovery codes (the old ones stop working)."""
    from .. import totp

    user = request.user
    if not user.totp_enabled or not totp.verify(user.totp_secret, request.POST.get("code", "")):
        messages.error(request, _("The code is not correct."))
        return redirect(reverse("accounts:security") + "#two-step")
    codes, hashes = totp.new_recovery_codes()
    user.recovery_codes = hashes
    user.save(update_fields=["recovery_codes"])
    return render(request, "accounts/settings/two_factor_codes.html", {"codes": codes, "settings_tab": "security"})


def _other_sessions(request):
    from django.contrib.sessions.models import Session

    keys = []
    for session in Session.objects.filter(expire_date__gt=timezone.now()).exclude(
            session_key=request.session.session_key).iterator():
        if str(session.get_decoded().get("_auth_user_id")) == str(request.user.pk):
            keys.append(session.session_key)
    return Session.objects.filter(session_key__in=keys)


@require_POST
@login_required
def sign_out_others(request):
    count, _details = _other_sessions(request).delete()
    messages.success(request, _("You have been signed out on your other devices."))
    return redirect(reverse("accounts:security") + "#devices")


@require_POST
@login_required
def google_disconnect(request):
    user = request.user
    if not user.has_usable_password():
        messages.error(request, _("Set a password first, otherwise you could not sign in any more."))
    else:
        user.socialaccount_set.filter(provider="google").delete()
        messages.info(request, _("Google has been disconnected from your account."))
    return redirect(reverse("accounts:security") + "#google")

