"""Getting in: sign up, sign in (with the second step), password reset, finishing a new profile."""
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from apps.core.languages import normalize_language

from .. import signup

from ..forms import CompleteProfileForm, FamilyStartForm, LoginForm, PasswordResetForm, RegisterForm, SetPasswordForm

logger = logging.getLogger(__name__)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegisterForm(request.POST or None)
    ready = signup.email_ready()
    if request.method == "POST" and form.is_valid():
        if not ready:
            form.add_error(None, _("Signing up with an email address is not available yet. Continue with Google."))
        else:
            try:
                signup.start(request, form, normalize_language(translation.get_language()) or "uz")
            except Exception:  # noqa: BLE001 - the mail server may refuse; tell the person instead of failing
                logger.exception("Could not send the sign-up code")
                form.add_error("email", _("The code could not be sent to this address. Check it and try again."))
            else:
                if request.POST.get("next"):
                    request.session["signup_next"] = request.POST["next"]
                return redirect("accounts:verify_email")
    return render(request, "accounts/auth/register.html", {"form": form, "next": request.GET.get("next", ""),
                                                           "email_ready": ready})


def verify_email(request):
    """Step two of signing up: the code from the email."""
    item = signup.pending(request)
    if request.user.is_authenticated or not item:
        return redirect("home" if request.user.is_authenticated else "accounts:register")
    error = ""
    if request.method == "POST" and request.POST.get("resend"):
        if signup.resend(request):
            messages.success(request, _("A new code has been sent."))
        else:
            messages.error(request, _("Please wait a minute before asking for a new code."))
        return redirect("accounts:verify_email")
    if request.method == "POST":
        result = signup.confirm(request, request.POST.get("code", ""))
        if isinstance(result, str):
            error = result
        else:
            login(request, result, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, _("Welcome! Your account has been created."))
            target = request.session.pop("signup_next", "")
            if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
                return redirect(target)
            return redirect(_after_sign_in(request))
    return render(request, "accounts/auth/verify_email.html", {"email": item["data"]["email"], "error": error})


def _after_sign_in(request, default="home"):
    """Where to go after signing in or up: a safe ?next, else an invite that
    was opened before, else the home page."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    token = request.session.get("invite")
    if token:
        return reverse("accounts:invite", args=[token])
    return default


class LoginView(auth_views.LoginView):
    template_name = "accounts/auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        token = self.request.session.get("invite")
        return reverse("accounts:invite", args=[token]) if token else super().get_default_redirect_url()

    def form_valid(self, form):
        user = form.get_user()
        if user.totp_enabled:
            # Second step: the password was right, now the code from the app.
            self.request.session["2fa_user"] = user.pk
            self.request.session["2fa_next"] = self.get_success_url()
            return redirect("accounts:two_factor")
        response = super().form_valid(form)
        # Switch to the account's language straight away.
        lang = normalize_language(user.preferred_language)
        if lang:
            translation.activate(lang)
        return response


def two_factor(request):
    """Second step of signing in: a code from the authenticator app, or a recovery code."""
    from django.contrib.auth import get_user_model
    from django.core.cache import cache

    from .. import totp
    from ..forms import CodeForm

    user = get_user_model().objects.filter(pk=request.session.get("2fa_user"), is_active=True).first()
    if user is None:
        return redirect("accounts:login")
    form = CodeForm(request.POST or None)
    key = f"2fa-fail:{user.pk}"
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        if cache.get(key, 0) >= 8:
            form.add_error("code", _("Too many attempts. Please try again in 15 minutes."))
        elif totp.verify(user.totp_secret, code) or totp.use_recovery_code(user, code):
            cache.delete(key)
            target = request.session.pop("2fa_next", "") or "home"
            request.session.pop("2fa_user", None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(target)
        else:
            cache.set(key, cache.get(key, 0) + 1, 15 * 60)
            form.add_error("code", _("The code is not correct."))
    return render(request, "accounts/auth/two_factor.html", {"form": form})


password_reset = auth_views.PasswordResetView.as_view(
    form_class=PasswordResetForm,
    template_name="accounts/auth/password_reset.html",
    email_template_name="registration/password_reset_email.txt",
    subject_template_name="registration/password_reset_subject.txt",
    success_url=reverse_lazy("accounts:password_reset_done"),
)
password_reset_done = auth_views.PasswordResetDoneView.as_view(template_name="accounts/auth/password_reset_done.html")
password_reset_confirm = auth_views.PasswordResetConfirmView.as_view(
    form_class=SetPasswordForm,
    template_name="accounts/auth/password_reset_confirm.html",
    success_url=reverse_lazy("accounts:password_reset_complete"),
)
password_reset_complete = auth_views.PasswordResetCompleteView.as_view(
    template_name="accounts/auth/password_reset_complete.html"
)


@login_required
def complete_profile(request):
    if request.user.person_id:
        return redirect("home")
    form = CompleteProfileForm(request.POST or None, initial={
        "first_name": request.user.first_name, "last_name": request.user.last_name,
    })
    if request.method == "POST" and form.is_valid():
        form.save(request.user)
        messages.success(request, _("Welcome! Your account has been created."))
        return redirect(_after_sign_in(request))
    return render(request, "accounts/auth/complete_profile.html", {"form": form})


@login_required
def family_start(request):
    """Before the first look around: who are your father, mother and grandparents? The tree starts from them."""
    from django.db import transaction

    from apps.genealogy import history
    from apps.genealogy.models import Change, Marriage, Person
    from apps.genealogy.relations import attach

    user = request.user
    me = Person.objects.filter(pk=user.home_person_id, owner=user).first()
    target = request.GET.get("next") or request.POST.get("next") or ""
    done = target if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()) \
        else reverse("genealogy:tree")
    if user.family_started or me is None or me.father_id or me.mother_id:
        if not user.family_started:
            user.family_started = True
            user.save(update_fields=["family_started"])
        return redirect(done)
    form = FamilyStartForm(request.POST or None)
    if request.method == "POST" and request.POST.get("skip"):
        user.family_started = True
        user.save(update_fields=["family_started"])
        return redirect(done)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            def add(anchor, name, last, gender, relation):
                if not name:
                    return None
                person = Person.objects.create(owner=user, first_name=name, last_name=last, gender=gender)
                attach(anchor, person, relation, user)
                history.record(user, user, Change.Action.CREATED, person,
                               details={"relation": relation, "to": anchor.short_name})
                return person

            def couple(husband, wife):
                if husband and wife:
                    Marriage.objects.get_or_create(owner=user, husband=husband, wife=wife)

            father = add(me, data["father"], data["father_last"], "male", "father")
            me.refresh_from_db()
            mother = add(me, data["mother"], data["mother_last"], "female", "mother")
            couple(father, mother)
            if father:
                couple(add(father, data["grandfather"], "", "male", "father"),
                       add(Person.objects.get(pk=father.pk), data["grandmother"], "", "female", "mother"))
            if mother:
                couple(add(mother, data["mother_father"], "", "male", "father"),
                       add(Person.objects.get(pk=mother.pk), data["mother_mother"], "", "female", "mother"))
            user.family_started = True
            user.save(update_fields=["family_started"])
        messages.success(request, _("Your family tree has started. Add brothers, sisters and others from here."))
        return redirect(done)
    return render(request, "accounts/auth/family_start.html", {"form": form, "next": target, "me": me})
