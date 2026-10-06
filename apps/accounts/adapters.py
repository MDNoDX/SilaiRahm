from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils.translation import get_language

from apps.core.languages import LATIN, normalize_language
from apps.core.names import guess_gender
from apps.core.text import normalize_apostrophes


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """New accounts from Google get their name and the current interface language."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.first_name = normalize_apostrophes((data.get("first_name") or "").strip())[:150]
        user.last_name = normalize_apostrophes((data.get("last_name") or "").strip())[:150]
        user.preferred_language = normalize_language(get_language()) or LATIN
        user.gender = guess_gender(user.first_name, user.last_name)
        return user

    def is_open_for_signup(self, request, sociallogin):
        return True


class AccountAdapter(DefaultAccountAdapter):
    """The site shows its own (translated) messages; allauth's are not used."""

    def add_message(self, *args, **kwargs):
        return None

    def get_login_redirect_url(self, request):
        # An invitation opened before signing in with Google is not forgotten.
        token = request.session.get("invite")
        if token:
            from django.urls import reverse

            return reverse("accounts:invite", args=[token])
        return super().get_login_redirect_url(request)
