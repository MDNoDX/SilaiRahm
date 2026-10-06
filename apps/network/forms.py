from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.genealogy.models import Person
from apps.genealogy.terminology import ADD_RELATION

from . import services
from .models import Connection

PLACES = [
    ("existing", _("Already in my family tree")),
    ("new", _("Add to my family tree")),
    ("none", _("Not in my family tree")),
]


class PlaceForm(forms.Form):
    """Where the other account stands in my family tree."""

    place = forms.ChoiceField(label=_("In your family tree"), choices=PLACES, widget=forms.RadioSelect,
                              initial="existing", required=False)
    person = forms.ModelChoiceField(label=_("Who are they in your family tree?"), queryset=Person.objects.none(),
                                    required=False)
    relation = forms.ChoiceField(label=_("Relation"), choices=[("", "—")] + list(ADD_RELATION.items()),
                                 required=False)
    anchor = forms.ModelChoiceField(label=_("Whose?"), queryset=Person.objects.none(), required=False)
    share = forms.BooleanField(label=_("Let us see each other's family trees"), required=False, initial=True)
    befriend = forms.BooleanField(label=_("Add to my friends (their birthday will be remembered)"), required=False)

    def __init__(self, *args, user, tree, other, **kwargs):
        super().__init__(*args, **kwargs)
        self.user, self.tree, self.other = user, tree, other
        people = Person.objects.filter(owner=tree) if tree is not None else Person.objects.none()
        self.fields["person"].queryset = people
        self.fields["anchor"].queryset = people

    def placement(self):
        data = self.cleaned_data
        if data.get("place") == "existing":
            return {"person": data.get("person")}
        if data.get("place") == "new":
            return {"relation": data.get("relation") or "", "anchor": data.get("anchor")}
        return {}

    def clean(self):
        data = super().clean()
        if not self.needs_place():
            return data
        place = data.get("place")
        if place == "existing" and not data.get("person"):
            self.add_error("person", _("Choose a person from your family tree."))
        elif place == "new":
            if not data.get("relation"):
                self.add_error("relation", _("Choose the relation."))
            if not data.get("anchor"):
                self.add_error("anchor", _("Choose who they are related to."))
        if not self.errors:
            error = services.check_place(self.user, self.tree, self.other, **self.placement())
            if error:
                self.add_error(None, error)
        return data

    def needs_place(self):
        return True


class RequestForm(PlaceForm):
    kind = forms.ChoiceField(
        label=_("Who are they to you?"), widget=forms.RadioSelect, initial=Connection.Kind.RELATIVE,
        choices=[(Connection.Kind.RELATIVE, pgettext_lazy("connection", "A relative")),
                 (Connection.Kind.FRIEND, pgettext_lazy("connection", "A friend"))])
    message = forms.CharField(label=_("A few words (optional)"), required=False, max_length=300,
                              widget=forms.Textarea(attrs={"rows": 3}))
    field_order = ["kind", "place", "person", "relation", "anchor", "share", "befriend", "message"]

    def needs_place(self):
        return self.cleaned_data.get("kind") == Connection.Kind.RELATIVE

    def placement(self):
        return super().placement() if self.needs_place() else {}


class AnswerForm(PlaceForm):
    """Accepting a request: where the sender stands in my tree."""
