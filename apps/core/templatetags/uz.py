from django import template

from apps.core.dates import format_date

register = template.Library()


@register.filter
def uzdate(value):
    """A date or datetime in natural Uzbek, e.g. 27-sentabr 2026-yil / 2026 йил 27 сентябрь."""
    return format_date(value)


@register.filter
def uzmonth(value):
    """Month name of a date: sentabr / сентябрь."""
    from apps.core.dates import month_in_date

    return month_in_date(value.month) if value else ""


@register.filter
def picked_name(bound_field):
    """Name of the person chosen in a person field (for the live-search picker)."""
    value = bound_field.value()
    if not value:
        return ""
    queryset = getattr(bound_field.field, "queryset", None)
    person = queryset.filter(pk=value).first() if queryset is not None and str(value).isdigit() else None
    return person.short_name if person else ""


@register.filter
def thumb(file):
    """URL of the small copy of a photo (avatars, cards, album grid)."""
    return f"{file.url}?s=t" if file else ""
