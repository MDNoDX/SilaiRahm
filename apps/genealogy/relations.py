"""Putting one person next to another in a family tree.

The same rules serve the "Add a relative" form, the quick add of the tree,
accepting a connection with another account and copying relatives from a
linked family tree.
"""
from django.utils.translation import gettext as _

from .models import Marriage

RELATIONS = ("father", "mother", "spouse", "child", "sibling")


def problem(anchor, person, relation, archive=None):
    """Why `person` cannot become `anchor`'s `relation`, or None if they can.
    `person` may be unsaved (a new record) or already in the tree."""
    if relation == "father":
        if anchor.father_id and anchor.father_id != person.pk:
            return _("This person already has a father in the tree.")
        if person.gender and person.gender != "male":
            return _("The father must be a man.")
    elif relation == "mother":
        if anchor.mother_id and anchor.mother_id != person.pk:
            return _("This person already has a mother in the tree.")
        if person.gender and person.gender != "female":
            return _("The mother must be a woman.")
    elif relation == "sibling":
        if not anchor.father_id and not anchor.mother_id:
            return _("To add a brother or sister, first add this person's father or mother.")
    elif relation == "child" and person.pk:
        taken = person.father_id if anchor.is_male else person.mother_id
        if taken and taken != anchor.pk:
            return (_("This person already has a father in the tree.") if anchor.is_male
                    else _("This person already has a mother in the tree."))
    elif relation == "spouse":
        if person.gender and person.gender == anchor.gender:
            return _("A husband and wife must be a man and a woman.")
    if person.pk and archive is not None and relation in ("father", "mother", "child"):
        parent, child = (anchor, person) if relation == "child" else (person, anchor)
        if parent.pk == child.pk or parent.pk in archive.descendants(child.pk):
            return _("This link would make a person their own ancestor.")
    return None


def attach(anchor, person, relation, owner, other_parent=None, wedding=None):
    """Make the saved `person` `anchor`'s `relation`. `other_parent` is the
    child's second parent; `wedding` a Marriage whose date a new marriage copies."""
    if relation == "father":
        anchor.father = person
        anchor.save()
    elif relation == "mother":
        anchor.mother = person
        anchor.save()
    elif relation == "child":
        if anchor.is_male:
            person.father, spouse_field = anchor, "mother"
        else:
            person.mother, spouse_field = anchor, "father"
        if other_parent is not None and getattr(person, f"{spouse_field}_id") is None:
            setattr(person, spouse_field, other_parent)
        person.save()
    elif relation == "sibling":
        person.father = person.father or anchor.father
        person.mother = person.mother or anchor.mother
        person.save()
    elif relation == "spouse":
        husband, wife = (anchor, person) if anchor.is_male else (person, anchor)
        marriage, created = Marriage.objects.get_or_create(owner=owner, husband=husband, wife=wife)
        if created and wedding is not None:
            marriage.year, marriage.month, marriage.day = wedding.year, wedding.month, wedding.day
            marriage.save(update_fields=["year", "month", "day"])
    return person
