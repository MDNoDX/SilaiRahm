from django import forms
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import password_validation
from django.utils import translation
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.core import timezones
from apps.core.languages import LATIN, language_choices, normalize_language
from apps.core.names import guess_gender
from apps.core.text import normalize_apostrophes
from apps.genealogy.models import Person

from .models import Gender, Invite, Role, User

USERNAME_HELP = _("Letters, digits and the characters @ . + - _ only.")


def _password_help():
    return password_validation.password_validators_help_text_html()


class RegisterForm(auth_forms.UserCreationForm):
    first_name = forms.CharField(label=_("First name"), max_length=100)
    last_name = forms.CharField(label=_("Last name"), max_length=100)
    email = forms.EmailField(label=_("Email"))
    gender = forms.ChoiceField(label=_("Gender"), choices=Gender.choices, widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "gender")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Username")
        self.fields["username"].help_text = USERNAME_HELP
        self.fields["password1"].label = _("Password")
        self.fields["password1"].help_text = _password_help()
        self.fields["password2"].label = _("Confirm password")
        self.fields["password2"].help_text = _("Enter the same password again.")
        self.fields["username"].widget.attrs["autocomplete"] = "username"

    def clean_first_name(self):
        return normalize_apostrophes(self.cleaned_data["first_name"].strip())

    def clean_last_name(self):
        return normalize_apostrophes(self.cleaned_data["last_name"].strip())

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this email address already exists."))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.preferred_language = normalize_language(get_language()) or LATIN
        if commit:
            user.save()
            person = Person.objects.create(
                owner=user, first_name=user.first_name, last_name=user.last_name, gender=user.gender,
            )
            user.person = person
            user.save(update_fields=["person"])
        return user


class LoginForm(auth_forms.AuthenticationForm):
    """Sign in with a username or an email address; repeated wrong passwords
    for one account are paused for a while."""

    MAX_ATTEMPTS = 10
    LOCK_SECONDS = 15 * 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Username or email")
        self.fields["password"].label = _("Password")

    def _throttle_key(self, username):
        import hashlib

        return "login-fail:" + hashlib.sha256(username.strip().lower().encode()).hexdigest()[:32]

    def clean(self):
        from django.core.cache import cache

        username = self.cleaned_data.get("username") or ""
        if "@" in username:
            match = User.objects.filter(email__iexact=username.strip()).first()
            if match:
                self.cleaned_data["username"] = username = match.username
        key = self._throttle_key(username)
        if username and cache.get(key, 0) >= self.MAX_ATTEMPTS:
            raise forms.ValidationError(_("Too many attempts. Please try again in 15 minutes."))
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            if username:
                cache.set(key, cache.get(key, 0) + 1, self.LOCK_SECONDS)
            raise
        cache.delete(key)
        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        # Gender is not asked again: it is in the person's own record in the tree.
        fields = ("first_name", "last_name", "email", "family_name")
        labels = {"first_name": _("First name"), "last_name": _("Last name"), "email": _("Email"),
                  "family_name": _("Name of the family")}
        help_texts = {"family_name": _("The title of the family book and the wall poster. Empty: made from the surname.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["family_name"].widget.attrs["placeholder"] = _("For example: The Madaminov family")

    def clean_first_name(self):
        return normalize_apostrophes(self.cleaned_data["first_name"].strip())

    def clean_last_name(self):
        return normalize_apostrophes(self.cleaned_data["last_name"].strip())

    def clean_family_name(self):
        return normalize_apostrophes(self.cleaned_data["family_name"].strip())


class PreferencesForm(forms.ModelForm):
    """Language and time zone: how the site speaks and when reminders come."""

    class Meta:
        model = User
        fields = ["preferred_language", "time_zone", "discoverable", "private_account", "tree_audience",
                  "stories_audience"]
        labels = {"preferred_language": _("Language"), "time_zone": _("Time zone"),
                  "discoverable": _("Others on Silai Rahm can find me by name"),
                  "private_account": _("Private account: I approve each follower"),
                  "tree_audience": _("Who sees my family tree"),
                  "stories_audience": _("Who sees life stories, events and the album")}
        help_texts = {"discoverable": _("Off: only someone who knows your exact username or e-mail finds you."),
                      "stories_audience": _("Invited family members always see everything.")}
        widgets = {"preferred_language": forms.RadioSelect, "tree_audience": forms.RadioSelect,
                   "stories_audience": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preferred_language"].choices = language_choices()
        self.fields["time_zone"] = forms.ChoiceField(
            label=_("Time zone"), choices=timezones.choices(),
            help_text=_("Reminders are made for your date and sent at your hour."),
        )


class ImportArchiveForm(forms.Form):
    file = forms.FileField(label=_("Archive file (JSON)"))

    def clean_file(self):
        import json

        upload = self.cleaned_data["file"]
        if upload.size > 20 * 1024 * 1024:
            raise forms.ValidationError(_("The file is too large."))
        try:
            data = json.loads(upload.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise forms.ValidationError(_("This is not a Silai Rahm archive file.")) from None
        if not isinstance(data, dict) or data.get("format") != "shajara-archive-1":
            raise forms.ValidationError(_("This is not a Silai Rahm archive file."))
        return data


class PasswordChangeForm(auth_forms.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = _("Current password")
        self.fields["new_password1"].label = _("New password")
        self.fields["new_password1"].help_text = _password_help()
        self.fields["new_password2"].label = _("Confirm the new password")
        self.fields["new_password2"].help_text = _("Enter the same password again.")


class PasswordResetForm(auth_forms.PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = _("Email")

    def send_mail(self, subject_template_name, email_template_name, context, *args, **kwargs):
        # The email is written in the recipient's own interface language.
        lang = normalize_language(getattr(context.get("user"), "preferred_language", None)) or get_language()
        with translation.override(lang):
            super().send_mail(subject_template_name, email_template_name, context, *args, **kwargs)


class SetPasswordForm(auth_forms.SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = _("New password")
        self.fields["new_password1"].help_text = _password_help()
        self.fields["new_password2"].label = _("Confirm the new password")
        self.fields["new_password2"].help_text = _("Enter the same password again.")


class CompleteProfileForm(forms.Form):
    """For accounts created through Google: the details the family tree needs."""

    first_name = forms.CharField(label=_("First name"), max_length=100)
    last_name = forms.CharField(label=_("Last name"), max_length=100, required=False)
    gender = forms.ChoiceField(label=_("Gender"), choices=Gender.choices, widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Chosen in advance from the name Google gave (the person can change it).
        initial = kwargs.get("initial") or {}
        guess = guess_gender(initial.get("first_name", ""), initial.get("last_name", ""))
        if guess and not self.is_bound:
            self.fields["gender"].initial = guess

    def clean_first_name(self):
        return normalize_apostrophes(self.cleaned_data["first_name"].strip())

    def clean_last_name(self):
        return normalize_apostrophes(self.cleaned_data["last_name"].strip())

    def save(self, user):
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.gender = self.cleaned_data["gender"]
        user.person = Person.objects.create(
            owner=user, first_name=user.first_name, last_name=user.last_name, gender=user.gender,
        )
        user.family_started = False
        user.save()
        return user


class InviteForm(forms.ModelForm):
    """A link for one relative: what they may do and who they are in the tree."""

    class Meta:
        model = Invite
        fields = ["role", "person"]
        widgets = {"role": forms.RadioSelect}
        labels = {"role": _("What may they do?"), "person": _("Who is this relative in the tree?")}
        help_texts = {"person": _("Optional. The tree will then name everyone as seen from them.")}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [(Role.EDITOR, Role.EDITOR.label), (Role.VIEWER, Role.VIEWER.label)]
        self.fields["role"].initial = Role.EDITOR
        self.fields["person"].queryset = Person.objects.filter(owner=owner)
        self.fields["person"].required = False


class CodeForm(forms.Form):
    code = forms.CharField(label=_("Code from the app"), max_length=12,
                           widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code",
                                                         "autofocus": True}))


class FamilyStartForm(forms.Form):
    """Who a new user's father, mother and grandfathers are: their family tree starts from these."""

    father = forms.CharField(label=_("Father’s first name"), max_length=100)
    father_last = forms.CharField(label=_("Father’s surname"), max_length=100, required=False)
    mother = forms.CharField(label=_("Mother’s first name"), max_length=100)
    mother_last = forms.CharField(label=_("Mother’s surname"), max_length=100, required=False)
    grandfather = forms.CharField(label=_("Grandfather (father’s father)"), max_length=100, required=False)
    grandmother = forms.CharField(label=_("Grandmother (father’s mother)"), max_length=100, required=False)
    mother_father = forms.CharField(label=_("Grandfather (mother’s father)"), max_length=100, required=False)
    mother_mother = forms.CharField(label=_("Grandmother (mother’s mother)"), max_length=100, required=False)

    def clean(self):
        data = super().clean()
        for name, value in list(data.items()):
            data[name] = normalize_apostrophes((value or "").strip())
        return data
