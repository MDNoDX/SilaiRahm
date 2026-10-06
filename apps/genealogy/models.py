import datetime
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.accounts.models import Gender
from apps.core.dates import age_between, format_lifespan, format_partial_date, partial_date_key
from apps.core.muchal import muchal
from apps.core.text import search_key


def photo_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"photos/{instance.owner_id}/{uuid.uuid4().hex}.{ext}"


def media_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"album/{instance.owner_id}/{uuid.uuid4().hex}.{ext[:8]}"


class Person(models.Model):
    """One person in a user's family archive.

    Names, places and texts are user content: they are stored exactly as
    entered (apart from normalising Uzbek apostrophes in short fields) and are
    never transliterated. `search_key` is a derived, script-independent copy
    used only for searching.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="people", verbose_name=_("owner")
    )
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100, blank=True)
    patronymic = models.CharField(_("patronymic"), max_length=100, blank=True)
    gender = models.CharField(_("gender"), max_length=10, choices=Gender.choices)

    birth_year = models.PositiveSmallIntegerField(_("year of birth"), null=True, blank=True)
    birth_month = models.PositiveSmallIntegerField(_("month of birth"), null=True, blank=True)
    birth_day = models.PositiveSmallIntegerField(_("day of birth"), null=True, blank=True)
    birth_place = models.CharField(_("place of birth"), max_length=200, blank=True)

    is_deceased = models.BooleanField(_("deceased"), default=False)
    death_year = models.PositiveSmallIntegerField(_("year of death"), null=True, blank=True)
    death_month = models.PositiveSmallIntegerField(_("month of death"), null=True, blank=True)
    death_day = models.PositiveSmallIntegerField(_("day of death"), null=True, blank=True)
    death_place = models.CharField(_("place of death"), max_length=200, blank=True)
    burial_place = models.CharField(_("place of burial"), max_length=250, blank=True)

    occupation = models.CharField(_("occupation"), max_length=200, blank=True)
    education = models.CharField(_("education"), max_length=200, blank=True)
    biography = models.TextField(_("biography"), blank=True)
    life_story = models.TextField(_("life story"), blank=True)
    photo = models.ImageField(_("photo"), upload_to=photo_path, blank=True)

    father = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children_as_father",
        verbose_name=_("father"),
    )
    mother = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children_as_mother",
        verbose_name=_("mother"),
    )

    search_key = models.TextField(editable=False, blank=True, default="", db_index=True)
    # This record is a relative who has an account of their own (set when a
    # connection between the two accounts is accepted).
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tree_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("person")
        verbose_name_plural = _("people")
        ordering = ["last_name", "first_name", "id"]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if self.death_year:
            self.is_deceased = True
        self.search_key = search_key(self.first_name, self.last_name, self.patronymic)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("genealogy:person", args=[self.pk])

    @property
    def full_name(self):
        """Formal name: "Madaminov Nodirbek Xolmatjon oʻgʻli"; in English "Nodirbek Madaminov"."""
        if get_language() == "en":
            return self.short_name
        return " ".join(p for p in (self.last_name, self.first_name, self.patronymic) if p)

    @property
    def short_name(self):
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    @property
    def is_male(self):
        return self.gender == Gender.MALE

    @property
    def birth_date_display(self):
        return format_partial_date(self.birth_year, self.birth_month, self.birth_day)

    @property
    def death_date_display(self):
        return format_partial_date(self.death_year, self.death_month, self.death_day)

    @property
    def lifespan(self):
        return format_lifespan(self.birth_year, self.death_year, self.is_deceased)

    @property
    def birth_key(self):
        return partial_date_key(self.birth_year, self.birth_month, self.birth_day)

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()

    @property
    def age(self):
        """Age today, or at death: {"years", "at_death", "exact"} or None."""
        if self.is_deceased:
            years = age_between(self.birth_year, self.birth_month, self.birth_day,
                                self.death_year, self.death_month, self.death_day)
            exact = bool(self.birth_day and self.death_day)
        else:
            today = datetime.date.today()
            years = age_between(self.birth_year, self.birth_month, self.birth_day, today.year, today.month, today.day)
            exact = bool(self.birth_day)
        if years is None:
            return None
        return {"years": years, "at_death": self.is_deceased, "exact": exact}

    @property
    def muchal(self):
        return muchal(self.birth_year, self.birth_month, self.birth_day)


class Marriage(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marriages")
    husband = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="marriages_as_husband",
                                verbose_name=_("husband"))
    wife = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="marriages_as_wife",
                             verbose_name=_("wife"))
    year = models.PositiveSmallIntegerField(_("year of marriage"), null=True, blank=True)
    month = models.PositiveSmallIntegerField(_("month of marriage"), null=True, blank=True)
    day = models.PositiveSmallIntegerField(_("day of marriage"), null=True, blank=True)
    is_divorced = models.BooleanField(_("divorced"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("marriage")
        verbose_name_plural = _("marriages")
        constraints = [models.UniqueConstraint(fields=["husband", "wife"], name="unique_marriage")]
        ordering = ["year", "id"]

    def partner_of(self, person):
        return self.wife if person.pk == self.husband_id else self.husband

    @property
    def date_display(self):
        return format_partial_date(self.year, self.month, self.day)


class Story(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories")
    person = models.ForeignKey(Person, null=True, blank=True, on_delete=models.SET_NULL, related_name="stories",
                               verbose_name=_("about whom"))
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("text"))
    year = models.PositiveSmallIntegerField(_("year"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("story")
        verbose_name_plural = _("stories")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("genealogy:story", args=[self.pk])


class Event(models.Model):
    """A family event: a wedding, a birth, an expected baby, a memorial day…"""

    class Kind(models.TextChoices):
        WEDDING = "wedding", pgettext_lazy("event", "Wedding")
        ENGAGEMENT = "engagement", pgettext_lazy("event", "Engagement (fotiha)")
        PREGNANCY = "pregnancy", pgettext_lazy("event", "Expecting a baby")
        BIRTH = "birth", pgettext_lazy("event", "Birth of a child")
        BESHIK = "beshik", pgettext_lazy("event", "Cradle celebration (beshik toʻyi)")
        SUNNAT = "sunnat", pgettext_lazy("event", "Circumcision celebration (sunnat toʻyi)")
        GRADUATION = "graduation", pgettext_lazy("event", "Graduation")
        WORK = "work", pgettext_lazy("event", "New job")
        MOVE = "move", pgettext_lazy("event", "Moving house")
        HAJJ = "hajj", pgettext_lazy("event", "Hajj or umrah")
        ANNIVERSARY = "anniversary", pgettext_lazy("event", "Jubilee")
        DEATH = "death", pgettext_lazy("event", "Death")
        MEMORIAL = "memorial", pgettext_lazy("event", "Memorial gathering (yil oshi)")
        OTHER = "other", pgettext_lazy("event", "Other event")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(_("type of event"), max_length=20, choices=Kind.choices, default=Kind.OTHER)
    title = models.CharField(_("title"), max_length=200, blank=True)
    people = models.ManyToManyField(Person, blank=True, related_name="events", verbose_name=_("who"))
    year = models.PositiveSmallIntegerField(_("year"), null=True, blank=True)
    month = models.PositiveSmallIntegerField(_("month"), null=True, blank=True)
    day = models.PositiveSmallIntegerField(_("day"), null=True, blank=True)
    place = models.CharField(_("place"), max_length=200, blank=True)
    description = models.TextField(_("details"), blank=True)
    every_year = models.BooleanField(_("remind every year on this day"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")
        ordering = ["-year", "-month", "-day", "-id"]

    def __str__(self):
        return self.display_title

    def get_absolute_url(self):
        return reverse("genealogy:event", args=[self.pk])

    @property
    def display_title(self):
        return self.title or str(self.get_kind_display())

    @property
    def date_display(self):
        return format_partial_date(self.year, self.month, self.day)

    @property
    def date(self):
        if self.year and self.month and self.day:
            try:
                return datetime.date(self.year, self.month, self.day)
            except ValueError:
                return None
        return None


class Media(models.Model):
    """A photo, document or voice recording in a person's album."""

    class Kind(models.TextChoices):
        PHOTO = "photo", pgettext_lazy("media", "Photo")
        DOCUMENT = "document", pgettext_lazy("media", "Document")
        AUDIO = "audio", pgettext_lazy("media", "Voice recording")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="media")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="media")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PHOTO)
    file = models.FileField(upload_to=media_path)
    caption = models.CharField(_("caption"), max_length=200, blank=True)
    year = models.PositiveSmallIntegerField(_("year"), null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["year", "id"]

    def __str__(self):
        return self.caption or self.file.name


class Change(models.Model):
    """One entry in the history of an archive: who changed what, and what it
    looked like before (so that a mistake can be undone)."""

    class Action(models.TextChoices):
        CREATED = "created", pgettext_lazy("history", "added")
        UPDATED = "updated", pgettext_lazy("history", "changed")
        DELETED = "deleted", pgettext_lazy("history", "deleted")
        LINKED = "linked", pgettext_lazy("history", "linked")
        MERGED = "merged", pgettext_lazy("history", "merged")
        RESTORED = "restored", pgettext_lazy("history", "restored")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="changes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    person = models.ForeignKey(Person, null=True, blank=True, on_delete=models.SET_NULL, related_name="changes")
    subject = models.CharField(max_length=250)
    what = models.CharField(max_length=20, default="person")  # person, event, story, marriage
    action = models.CharField(max_length=10, choices=Action.choices)
    details = models.JSONField(default=dict, blank=True)
    snapshot = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    undone_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def can_undo(self):
        return self.undone_at is None and self.what == "person" and self.snapshot is not None \
            and self.action in (self.Action.UPDATED, self.Action.DELETED)
