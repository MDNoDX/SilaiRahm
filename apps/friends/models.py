from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core.dates import format_partial_date
from apps.core.text import search_key


class Contact(models.Model):
    """A friend of someone in the family tree — the user, their father, anyone.

    Friends do not need an account; they are simply remembered, with their
    birthday for reminders.
    """

    class HowMet(models.TextChoices):
        CLASSMATE = "classmate", pgettext_lazy("how met", "Classmate")
        COURSEMATE = "coursemate", pgettext_lazy("how met", "University friend")
        COLLEAGUE = "colleague", pgettext_lazy("how met", "Colleague")
        NEIGHBOUR = "neighbour", pgettext_lazy("how met", "Neighbour")
        CHILDHOOD = "childhood", pgettext_lazy("how met", "Childhood friend")
        ARMY = "army", pgettext_lazy("how met", "Served together in the army")
        FAMILY_FRIEND = "family", pgettext_lazy("how met", "Family friend")
        OTHER = "other", pgettext_lazy("how met", "Other")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contacts")
    person = models.ForeignKey("genealogy.Person", on_delete=models.CASCADE, related_name="friends",
                               verbose_name=_("whose friend"))
    name = models.CharField(_("full name"), max_length=200)
    how_met = models.CharField(_("how they know each other"), max_length=20, choices=HowMet.choices, blank=True)
    phone = models.CharField(_("phone"), max_length=40, blank=True)
    birth_year = models.PositiveSmallIntegerField(_("year of birth"), null=True, blank=True)
    birth_month = models.PositiveSmallIntegerField(_("month of birth"), null=True, blank=True)
    birth_day = models.PositiveSmallIntegerField(_("day of birth"), null=True, blank=True)
    note = models.TextField(_("notes"), blank=True)
    search_key = models.TextField(editable=False, blank=True, default="")
    # The friend has an account on the site (added through Connections).
    linked_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("friend")
        verbose_name_plural = _("friends")
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.search_key = search_key(self.name)
        super().save(*args, **kwargs)

    @property
    def birth_date_display(self):
        return format_partial_date(self.birth_year, self.birth_month, self.birth_day)

    @property
    def initials(self):
        parts = self.name.split()
        return "".join(p[:1] for p in parts[:2]).upper()
