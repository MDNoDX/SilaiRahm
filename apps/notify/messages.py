"""Reminder texts, rendered in the reader's language when shown or sent."""
from django.conf import settings
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.utils.translation import ngettext, npgettext, pgettext

from apps.core.dates import format_date
from apps.core.muchal import ANIMALS
from apps.genealogy.models import Event

from .occasions import ICONS


def when(days_left):
    if days_left == 0:
        return pgettext("reminder", "Today")
    if days_left == 1:
        return pgettext("reminder", "Tomorrow")
    return ngettext("In %(days)d day", "In %(days)d days", days_left) % {"days": days_left}


def years_phrase(n):
    """ "42 years" / "42 года" / "5 лет": for languages whose sentences need the noun."""
    return npgettext("duration", "%(count)d year", "%(count)d years", n) % {"count": n}


def render_parts(kind, params, days_left=0):
    """{"title", "body", "icon"} for an occasion or a stored notification.

    Sentences get both the bare number ({age}, {years}) and the number with
    its noun ({age_phrase}, {years_phrase}); each language uses what its
    grammar needs.
    """
    w = when(days_left)
    # A stored notification may predate a field: missing values must not break the page.
    params = {"name": "", "names": "", "whose": "", **(params or {})}
    age, years = params.get("age"), params.get("years")
    n = {"when": w, "age": age, "years": years,
         "age_phrase": years_phrase(age) if age else "", "years_phrase": years_phrase(years) if years else ""}
    if kind == "birthday":
        title = _("Birthday: {name}").format(name=params["name"])
        # Translators: placeholders {when} {age} {age_phrase}
        # xgettext:no-python-brace-format
        body = (_("{when} they turn {age}.").format(**n) if age
                else _("{when} is their birthday.").format(**n))
    elif kind == "friend_birthday":
        title = _("Friend's birthday: {name}").format(name=params["name"])
        # Translators: placeholders {when} {age} {age_phrase}
        # xgettext:no-python-brace-format
        body = (_("{when} they turn {age}.").format(**n) if age
                else _("{when} is their birthday.").format(**n))
        body += " " + _("Friend of {whose}.").format(whose=params["whose"])
    elif kind == "memorial":
        title = _("Memorial day: {name}").format(name=params["name"])
        # Translators: placeholders {when} {years} {years_phrase}
        # xgettext:no-python-brace-format
        body = (_("{when} it will be {years_phrase} since they passed away.").format(**n) if years
                else _("{when} is the day they passed away.").format(**n))
    elif kind == "anniversary":
        title = _("Wedding anniversary: {names}").format(names=params["names"])
        # Translators: placeholders {when} {years} {years_phrase}
        # xgettext:no-python-brace-format
        body = (_("{when} they will have been married for {years_phrase}.").format(**n) if years
                else _("{when} is their wedding anniversary.").format(**n))
    elif kind == "event":
        kind_label = dict(Event.Kind.choices).get(params.get("kind"), "")
        title = params.get("title") or str(kind_label)
        body = _("{when}.").format(when=w)
        if years:
            # Translators: placeholders {when} {years} {years_phrase}
            # xgettext:no-python-brace-format
            body = _("{when} it will be {years_phrase} since then.").format(**n)
        if params.get("place"):
            body += " " + _("Place: {place}.").format(place=params["place"])
    elif kind == "muchal" and isinstance(params.get("animal"), int) and 0 <= params["animal"] < len(ANIMALS):
        animal = str(ANIMALS[params["animal"]][1])
        title = _("Muchal year: {animal}").format(animal=animal)
        body = _("A {animal} year begins at Navroʻz. It is the muchal year of: {names}.").format(
            animal=animal, names=", ".join(params["names"] or []))
    elif kind == "connection_request":
        title = _("{name} wants to connect with you").format(name=params["name"])
        body = _("Open Connections to answer.")
    elif kind == "connection_accepted":
        title = _("{name} accepted your request").format(name=params["name"])
        body = (_("You are friends now.") if params.get("kind") == "friend"
                else _("Your family trees are connected."))
    else:
        title, body = params.get("title", ""), ""
    return {"title": title, "body": body, "icon": ICONS.get(kind, "📅")}


def render(notification):
    parts = render_parts(notification.kind, notification.params, notification.params.get("days_left", 0))
    if notification.occasion_date:
        parts["date"] = format_date(notification.occasion_date)
    return parts


def telegram_text(notification):
    parts = render(notification)
    lines = [f"{parts['icon']} <b>{escape(parts['title'])}</b>", escape(parts["body"])]
    if parts.get("date"):
        lines.append(f"<i>{escape(parts['date'])}</i>")
    if notification.url and settings.SITE_URL.startswith("http"):
        link = settings.SITE_URL.rstrip("/") + notification.url
        lines.append(f'<a href="{escape(link)}">{escape(_("Open in Shajara"))}</a>')
    return "\n".join(lines)
