"""Signing up with an email address: the account is made only after the code sent there is typed in.

The details wait in the session (the password only as a hash) until then, so unconfirmed
addresses never become accounts. Google sign-in skips this: Google has already confirmed the address.
"""
import secrets
import time

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.utils.translation import gettext as _

from apps.genealogy.models import Person

from .models import User

KEY = "signup"
LIFETIME = 15 * 60       # a code is good for 15 minutes
MAX_TRIES = 5            # wrong codes before a new one must be sent
RESEND_AFTER = 60        # seconds between two codes
FIELDS = ("first_name", "last_name", "username", "email", "gender")


def email_ready():
    """Can the site send mail? (On the developer's computer the code is printed in the console.)"""
    return settings.DEBUG or "console" not in settings.EMAIL_BACKEND


def _send(pending, code):
    send_mail(
        _("Your Silai Rahm code: %(code)s") % {"code": code},
        _("Hello, %(name)s!\n\nYour code to finish signing up on Silai Rahm: %(code)s\n\n"
          "It is valid for 15 minutes. If you did not sign up, ignore this email.") % {
            "name": pending["data"]["first_name"], "code": code},
        None, [pending["data"]["email"]],
    )


def start(request, form, language):
    """Keep the checked form in the session and send the first code."""
    data = {f: form.cleaned_data[f] for f in FIELDS}
    pending = {"data": data, "password": make_password(form.cleaned_data["password1"]), "language": language}
    request.session[KEY] = pending
    resend(request, force=True)


def pending(request):
    return request.session.get(KEY)


def resend(request, force=False):
    """A new code; False if the last one was sent less than a minute ago."""
    item = request.session.get(KEY)
    if not item or (not force and time.time() - item.get("sent", 0) < RESEND_AFTER):
        return False
    code = f"{secrets.randbelow(10 ** 6):06d}"
    item.update(code=make_password(code), sent=time.time(), tries=0)
    request.session[KEY] = item
    _send(item, code)
    return True


def confirm(request, code):
    """The new user if `code` is right; otherwise an error message (str)."""
    item = request.session.get(KEY)
    if not item:
        return _("Start signing up again.")
    if time.time() - item["sent"] > LIFETIME:
        return _("The code has expired. Ask for a new one.")
    if item["tries"] >= MAX_TRIES:
        return _("Too many wrong codes. Ask for a new one.")
    if not check_password(code.strip().replace(" ", ""), item["code"]):
        item["tries"] += 1
        request.session[KEY] = item
        return _("The code is not right. Check the email and try again.")
    data = item["data"]
    if User.objects.filter(username__iexact=data["username"]).exists():
        return _("This username was taken in the meantime. Start signing up again.")
    if User.objects.filter(email__iexact=data["email"]).exists():
        return _("An account with this email address already exists.")
    user = User(**data, preferred_language=item["language"], family_started=False)
    user.password = item["password"]
    user.save()
    user.person = Person.objects.create(owner=user, first_name=user.first_name, last_name=user.last_name,
                                        gender=user.gender)
    user.save(update_fields=["person"])
    del request.session[KEY]
    return user
