from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core import timezones
from apps.core.languages import LATIN, language_choices
from apps.core.text import search_key


class Gender(models.TextChoices):
    MALE = "male", pgettext_lazy("gender", "Male")
    FEMALE = "female", pgettext_lazy("gender", "Female")


class Audience(models.TextChoices):
    """Who may see a part of an account."""
    PUBLIC = "public", pgettext_lazy("audience", "Everyone on the site")
    FOLLOWERS = "followers", pgettext_lazy("audience", "My followers")
    FAMILY = "family", pgettext_lazy("audience", "Only family members")


class User(AbstractUser):
    preferred_language = models.CharField(
        _("interface language"), max_length=10, choices=language_choices(), default=LATIN
    )
    gender = models.CharField(_("gender"), max_length=10, choices=Gender.choices, blank=True)
    time_zone = models.CharField(_("time zone"), max_length=40, default=timezones.DEFAULT)
    # The person in the user's own family tree who represents them.
    person = models.OneToOneField(
        "genealogy.Person",
        verbose_name=_("own record in the family tree"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="account",
    )
    # Working in a relative's shared family tree: that archive is "active",
    # `person` is then who the user is in it, and `own_person` remembers the
    # record in the user's own archive.
    active_archive = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name=_("family tree in use"),
    )
    own_person = models.ForeignKey(
        "genealogy.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    # Two-step sign-in (an authenticator app).
    totp_secret = models.CharField(max_length=64, blank=True, editable=False)
    totp_enabled = models.BooleanField(default=False)
    recovery_codes = models.JSONField(default=list, blank=True, editable=False)
    search_key = models.TextField(editable=False, blank=True, default="")
    # How the family is called on the book and the wall poster ("Madaminovlar oilasi").
    family_name = models.CharField(_("name of the family"), max_length=120, blank=True)
    # Others on the site may find this account by name (Connections → search).
    discoverable = models.BooleanField(_("others on Silai Rahm can find me by name"), default=True)
    # Privacy, as on Instagram: a private account approves each follower; the
    # family tree and the stories (life stories, events, album) each have an audience.
    # Family members (invited relatives) always see everything.
    private_account = models.BooleanField(_("private account"), default=True)
    tree_audience = models.CharField(_("who sees my family tree"), max_length=10, choices=Audience.choices,
                                     default=Audience.FOLLOWERS)
    stories_audience = models.CharField(_("who sees life stories, events and the album"), max_length=10,
                                        choices=Audience.choices, default=Audience.FAMILY)

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def save(self, *args, **kwargs):
        self.search_key = search_key(self.first_name, self.last_name, self.username)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def archive_owner(self):
        """The account whose family archive this user is working in."""
        return self.active_archive if self.active_archive_id else self

    @property
    def home_person_id(self):
        """This user's record in their *own* archive (wherever they work now)."""
        return self.own_person_id if self.active_archive_id else self.person_id


class Role(models.TextChoices):
    VIEWER = "viewer", pgettext_lazy("role", "Can view")
    EDITOR = "editor", pgettext_lazy("role", "Can edit")


class Membership(models.Model):
    """Access of one account to another account's family archive."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="members")
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(_("access"), max_length=10, choices=Role.choices, default=Role.VIEWER)
    # Who the member is in the owner's tree (kept while they work elsewhere).
    person = models.ForeignKey("genealogy.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "member"], name="unique_membership")]
        ordering = ["created_at"]


def _invite_token():
    import secrets

    return secrets.token_urlsafe(18)


class Invite(models.Model):
    """A one-time link that lets a relative join a family archive."""

    VALID_DAYS = 14

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invites")
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    token = models.CharField(max_length=40, unique=True, default=_invite_token)
    role = models.CharField(_("access"), max_length=10, choices=Role.choices, default=Role.EDITOR)
    # The relative this link is meant for: they become this person on joining.
    person = models.ForeignKey("genealogy.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                               verbose_name=_("who is invited"))
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def expires_at(self):
        import datetime

        return self.created_at + datetime.timedelta(days=self.VALID_DAYS)

    @property
    def is_open(self):
        from django.utils import timezone

        return self.accepted_at is None and timezone.now() < self.expires_at
