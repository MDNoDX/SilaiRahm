"""Sign-in bridge for the macOS app.

Google refuses to show its sign-in page inside an embedded web view, so the
app opens /ilova/kirish/boshlash/ in the system's authentication window
(ASWebAuthenticationSession). After signing in there, the site redirects to
silairahm://kirish?token=… with a short-lived, single-use token; the app then
opens /ilova/kirish/?token=… in its own web view, which signs it in.
"""
import secrets

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

SALT = "silairahm.app-login"
MAX_AGE = 120  # seconds


class AppSchemeRedirect(HttpResponseRedirect):
    allowed_schemes = ["silairahm"]


def start(request):
    """Opened in the system sign-in window: choose Google or a password."""
    finish = reverse("app_login_finish")
    if request.user.is_authenticated:
        return redirect(finish)
    return render(request, "accounts/auth/app_login_start.html", {
        "finish": finish, "provider": request.GET.get("provider", ""),
    })


@login_required
def finish(request):
    nonce = secrets.token_urlsafe(16)
    cache.set(f"app-login:{nonce}", request.user.pk, MAX_AGE)
    token = signing.dumps({"n": nonce}, salt=SALT)
    return AppSchemeRedirect(f"silairahm://kirish?token={token}")


def consume(request):
    """Opened inside the app's web view with the token from the redirect."""
    try:
        data = signing.loads(request.GET.get("token", ""), salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return HttpResponseBadRequest()
    key = f"app-login:{data.get('n')}"
    user_id = cache.get(key)
    cache.delete(key)  # single use
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first() if user_id else None
    if user is None:
        return redirect("accounts:login")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("home")
