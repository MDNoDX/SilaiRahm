"""What the assistant knows: the family archive the person is working in.

Only the archive the signed-in user may already see is described, and stories
only when they may read them. Ids let the model refer to people exactly.
"""
from django.conf import settings
from django.utils import timezone
from django.utils.translation import get_language

from apps.accounts.sharing import can_edit, can_see_stories
from apps.core.languages import LANGUAGE_LABELS, normalize_language
from apps.genealogy.access import viewer_person
from apps.genealogy.kinship import Archive
from apps.genealogy.models import Event

LIMIT = 90_000  # characters of family data; the Flash models read far more, but answers stay quick

SITE_HELP = """\
Sections of the site (menu on the left; on phones, at the bottom):
- Home: today's dates, recent changes, quick actions.
- Tree: the family tree; click a person for their card; buttons for the family book (PDF). The book can be the
  whole family, the father's side, the mother's side, or one person's life book.
- Relatives (People): list with search and filters (men, women, living, deceased); a person's page has their life
  story, events and memories in one place, written like a book; "Add a relative" adds father, mother, spouse,
  child, brother or sister. A woman can have one marriage at a time; a man can have several; a marriage can be
  marked as divorced.
- Events: weddings, births, celebrations and memories, each told like a story; reminders every year.
- Timeline, Kinship calculator (how two people are related), History (every change can be undone).
- Friends: friends of the family, and other users: search them, follow them, connect ("this is my relative"),
  compare and merge trees.
- Settings: profile (family name used on book titles), privacy (public or private account, who sees the tree and
  the stories), family members and invitations, notifications (Telegram, push), language, data export and import.
"""


def _years(p):
    born = p.birth_year and str(p.birth_year) or ""
    died = p.death_year and str(p.death_year) or ("?" if p.is_deceased else "")
    return f"{born}–{died}" if died else born


def _clip(text, size):
    text = " ".join((text or "").split())
    return text if len(text) <= size else text[:size].rsplit(" ", 1)[0] + "…"


def describe(request):
    owner = request.archive
    user = request.user
    archive = Archive(owner)
    me = viewer_person(request, archive)
    stories = can_see_stories(user, owner)
    lines = []
    for pk, p in sorted(archive.people.items()):
        bits = [f"#{pk} {p.full_name}", "man" if p.is_male else "woman"]
        if _years(p):
            bits.append(_years(p))
        if p.is_deceased and not p.death_year:
            bits.append("deceased")
        if me and me != pk:
            label = archive.label(me, pk)
            if label:
                bits.append(f"to the user: {label}")
        elif me == pk:
            bits.append("THIS IS THE USER")
        parents = [f"#{x}" for x in (p.father_id, p.mother_id) if x in archive.people]
        if parents:
            bits.append("parents " + ", ".join(parents))
        spouses = []
        for other, marriage in archive.unions.get(pk, []):
            spouses.append(f"#{other}" + (" (divorced)" if marriage.is_divorced else ""))
        if spouses:
            bits.append("spouse " + ", ".join(spouses))
        for field, name in (("birth_place", "born in"), ("occupation", "work"), ("education", "studied"),
                            ("death_place", "died in")):
            if getattr(p, field):
                bits.append(f"{name} {getattr(p, field)}")
        if stories and (p.life_story or p.biography):
            bits.append("life: " + _clip(p.life_story or p.biography, 400))
        lines.append("; ".join(bits))
    if stories:
        events = Event.objects.filter(owner=owner).prefetch_related("people").order_by("year", "month", "day", "pk")
        for e in events:
            who = ", ".join(f"#{x.pk}" for x in e.people.all())
            when = "-".join(str(x) for x in (e.year, e.month, e.day) if x)
            lines.append(f"EVENT {e.get_kind_display()} “{e.display_title}” {when} {who}"
                         + (f" at {e.place}" if e.place else "")
                         + (": " + _clip(e.description, 500) if e.description else ""))
    data = "\n".join(lines)
    if len(data) > LIMIT:
        data = data[:LIMIT] + "\n… (the rest of the archive is not shown)"
    language = LANGUAGE_LABELS.get(normalize_language(get_language()) or settings.LANGUAGE_CODE, "Oʻzbekcha")
    editing = can_edit(user, owner)
    today = timezone.localdate()
    return f"""You are the helper inside "{settings.SITE_NAME}", a family tree site ("silai rahm" means keeping the
ties of kinship). You help {user.get_full_name() or user.username} with their family archive
"{owner.family_name or owner.get_full_name() or owner.username}" and with using the site.

Rules:
- Answer in the user's language: {language} (if they write in another language, answer in theirs). Be warm,
  short and clear. Use Uzbek kinship words correctly (ota, ona, aka, uka, opa, singil, amaki, togʻa, xola, amma,
  buva, buvi, kelin, kuyov, jiyan, nevara...).
- Write Uzbek only in the Uzbek Latin alphabet (oʻ, gʻ, sh, ch, ʼ) — never Azerbaijani or Turkish letters such
  as ə, ı, ş, ç, ğ, ö, ü — or in Uzbek Cyrillic when the user writes in Cyrillic.
- Use only the family data below. If something is not there, say so; never invent people, dates or stories.
- Unknown surnames stay empty. A grandson usually takes his paternal grandfather's name as his surname
  (Madaminjon → Madaminov), but only suggest this, never assume it.
- {"You can propose changes with the tools: add_event (for stories and memories too), add_relative, update_person. "
   "Nothing is saved until the user presses the button under your proposal, so propose only what they told you or "
   "agreed to, ask first when something is unclear (who it is about, the year), and say briefly what you propose. "
   "When they share a story, edit its spelling and flow lightly, keep their voice and every fact, add nothing."
   if editing else "The user can only view this archive, so you cannot change anything; tell them who can."}
- Refer to people by name, not by #id. Today's date is {today.isoformat()} (day {today.day}, month {today.month},
  year {today.year}); count ages from it.

{SITE_HELP}
Family data (one person per line; #id, name, gender, years, relation to the user, parents, spouses, details;
EVENT lines are events and memories):
{data or "(the archive is empty)"}
"""
