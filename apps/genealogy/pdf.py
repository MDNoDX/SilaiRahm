"""PDF exports in the reader's interface language.

All text comes from the active gettext catalogue, so a user who works in
Кириллча receives a Cyrillic PDF. DejaVu Sans is embedded because the
standard PDF fonts have no glyphs for Ў Қ Ғ Ҳ or the Uzbek apostrophe ʻ.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A1, A2, A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.core.dates import format_date

from .terminology import BRANCHES, SECTION, generation_label
from .tree import CARD_H, CARD_W

FONT = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
FONT_ITALIC = "DejaVuSans-Oblique"
FONT_BOLD_ITALIC = "DejaVuSans-BoldItalic"

# The brand: indigo and gold on warm paper (static/css/app.css).
INK = colors.HexColor("#171c2b")
MUTED = colors.HexColor("#6f7585")
ACCENT = colors.HexColor("#27357e")
ACCENT_DARK = colors.HexColor("#182152")
ACCENT_SOFT = colors.HexColor("#e8ebf7")
GOLD = colors.HexColor("#d89e24")
GOLD_TEXT = colors.HexColor("#9a6a0c")
LINE = colors.HexColor("#d6cdb9")
PAPER = colors.HexColor("#faf7f0")
TREE_LINE = colors.HexColor("#cbc2ad")
BRANCH = {  # side of the family: (colour, soft background)
    "own": (colors.HexColor("#9a6a0c"), colors.HexColor("#f8edd0")),
    "paternal": (colors.HexColor("#2f4aa6"), colors.HexColor("#e5ebfa")),
    "maternal": (colors.HexColor("#a8433a"), colors.HexColor("#f9e6e2")),
    "other": (colors.HexColor("#586273"), colors.HexColor("#eceef2")),
}
POSTER_SIZES = {"A2": landscape(A2), "A1": landscape(A1)}
POSTER_MAX_WIDTH = 3000 * mm

_registered = False


def register_fonts():
    global _registered
    if _registered:
        return
    base = settings.PDF_FONT_DIR
    pdfmetrics.registerFont(TTFont(FONT, str(base / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(base / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_ITALIC, str(base / "DejaVuSans-Oblique.ttf")))
    # No bold-oblique file is shipped; bold is used for bold italic text.
    pdfmetrics.registerFont(TTFont(FONT_BOLD_ITALIC, str(base / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT_ITALIC, boldItalic=FONT_BOLD_ITALIC)
    _registered = True


def _styles():
    register_fonts()
    return {
        "title": ParagraphStyle("title", fontName=FONT_BOLD, fontSize=21, leading=26, textColor=INK, spaceAfter=3),
        "subtitle": ParagraphStyle("subtitle", fontName=FONT, fontSize=10.5, leading=15, textColor=MUTED, spaceAfter=10),
        "chapter": ParagraphStyle("chapter", fontName=FONT_BOLD, fontSize=17, leading=22, textColor=ACCENT,
                                  spaceBefore=4, spaceAfter=2),
        "eyebrow": ParagraphStyle("eyebrow", fontName=FONT_BOLD, fontSize=8, leading=11, textColor=GOLD_TEXT),
        "h2": ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=12, leading=16, textColor=ACCENT, spaceBefore=13, spaceAfter=5),
        "h3": ParagraphStyle("h3", fontName=FONT_BOLD, fontSize=11.5, leading=15, textColor=INK, spaceBefore=2, spaceAfter=1),
        "rel": ParagraphStyle("rel", fontName=FONT_BOLD, fontSize=8.5, leading=12, textColor=GOLD_TEXT),
        "body": ParagraphStyle("body", fontName=FONT, fontSize=10, leading=15, textColor=INK),
        "small": ParagraphStyle("small", fontName=FONT, fontSize=8.5, leading=12, textColor=MUTED),
        "label": ParagraphStyle("label", fontName=FONT, fontSize=9, leading=12, textColor=MUTED),
        "center": ParagraphStyle("center", fontName=FONT, fontSize=9, leading=12, textColor=MUTED, alignment=TA_CENTER),
        "toc": ParagraphStyle("toc", fontName=FONT, fontSize=11, leading=19, textColor=INK),
        # Long texts (life stories, stories): book-like paragraphs.
        "story": ParagraphStyle("story", fontName=FONT, fontSize=10.5, leading=16.5, textColor=INK,
                                alignment=TA_JUSTIFY, firstLineIndent=6 * mm, spaceAfter=5),
        "story_title": ParagraphStyle("story_title", fontName=FONT_BOLD, fontSize=14, leading=19, textColor=ACCENT,
                                      spaceBefore=14, spaceAfter=2),
        "milestone": ParagraphStyle("milestone", fontName=FONT, fontSize=10, leading=14, textColor=INK),
    }


def _p(text, style):
    """Paragraph from user text: escaped, line breaks kept."""
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def draw_mark(c, x, y, size, colour):
    """The Silai Rahm mark (templates/partials/logo.svg) with its top-left at (x, y + size)."""
    k = size / 32.0

    def pt(px, py):
        return x + px * k, y + (32 - py) * k

    from apps.core import mark

    c.saveState()
    c.setStrokeColor(colour)
    c.setFillColor(colour)
    c.setLineWidth(2 * k)
    c.setLineCap(1)
    c.setLineJoin(1)
    for points in mark.polylines():
        path = c.beginPath()
        path.moveTo(*pt(*points[0]))
        for q in points[1:]:
            path.lineTo(*pt(*q))
        c.drawPath(path, stroke=1, fill=0)
    for cx, cy, r in mark.NODES:
        c.circle(*pt(cx, cy), r * k, stroke=0, fill=1)
    c.restoreState()


def draw_ikat(c, x, y, w, h, colour, step=20 * mm, alpha=0.08):
    """The ikat diamond pattern over a rectangle (cover, poster title band)."""
    c.saveState()
    clip = c.beginPath()
    clip.rect(x, y, w, h)
    c.clipPath(clip, stroke=0, fill=0)
    c.setStrokeColor(colour)
    c.setFillColor(colour)
    c.setStrokeAlpha(alpha)
    c.setFillAlpha(alpha)
    c.setLineWidth(0.5 * mm)
    half = step / 2
    rows, cols = int(h / step) + 2, int(w / step) + 2
    for row in range(rows):
        for col in range(cols):
            cx, cy = x + col * step + half, y + row * step + half
            for r, fill in ((half * 0.9, 0), (half * 0.47, 0), (half * 0.18, 1)):
                d = c.beginPath()
                d.moveTo(cx, cy + r)
                d.lineTo(cx + r, cy)
                d.lineTo(cx, cy - r)
                d.lineTo(cx - r, cy)
                d.close()
                c.drawPath(d, stroke=1 - fill, fill=fill)
    c.restoreState()


class _NumberedCanvas(pdf_canvas.Canvas):
    """Adds "Page 2 of 5", the date and a thin gold rule to every page; an
    optional cover (a callable drawing the first page) gets no footer."""

    def __init__(self, *args, footer="", cover=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []
        self._footer = footer
        self._cover = cover

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for number, state in enumerate(self._saved, start=1):
            self.__dict__.update(state)
            if self._cover and number == 1:
                self._cover(self)
            else:
                self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        w, _h = self._pagesize
        self.setStrokeColor(GOLD)
        self.setLineWidth(0.6)
        self.line(15 * mm, 14 * mm, w - 15 * mm, 14 * mm)
        self.setFont(FONT, 8)
        self.setFillColor(MUTED)
        self.drawString(15 * mm, 9.5 * mm, self._footer)
        page = _("Page %(page)d of %(total)d") % {"page": self._pageNumber, "total": total}
        self.drawRightString(w - 15 * mm, 9.5 * mm, page)


def _paragraphs(text, style):
    """A long text as book paragraphs: a blank line (or a single line break
    between full sentences) starts a new paragraph."""
    import re

    parts = [x.strip() for x in re.split(r"\n\s*\n|\n(?=\S)", str(text or "")) if x.strip()]
    return [Paragraph(escape(x), style) for x in parts]


def _ornament(width):
    """A small gold diamond between sections."""
    return Table([[_p("◆", ParagraphStyle("orn", fontName=FONT, fontSize=8, textColor=GOLD, alignment=TA_CENTER))]],
                 colWidths=[width], style=[("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])


def _story_items(events, st, width):
    """Events and memories, oldest first: a title, the date, the story as paragraphs."""
    items = []
    for event in events:
        block = [_p(event.display_title, st["story_title"])]
        when = " · ".join(x for x in (str(event.get_kind_display()) if event.title else "", event.date_display) if x)
        if when:
            block.append(_p(when, st["rel"]))
        block.append(Spacer(1, 4))
        paras = _paragraphs(event.description, st["story"])
        items.append(KeepTogether(block + paras[:1]))
        items.extend(paras[1:])
    return items


def _footer_text():
    return _("Created on %(date)s") % {"date": format_date(timezone.now())} + f" · {settings.SITE_NAME}"


def _build(story_items, pagesize=A4, title="", cover=None):
    register_fonts()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
        title=title, author=settings.SITE_NAME,
    )
    footer = _footer_text()
    doc.build(story_items, canvasmaker=lambda *a, **k: _NumberedCanvas(*a, footer=footer, cover=cover, **k))
    return buf.getvalue()


def _facts(person):
    rows = []

    def add(label, value):
        if value:
            rows.append((label, value))

    add(_("Gender"), person.get_gender_display())
    add(_("Date of birth"), person.birth_date_display)
    add(_("Place of birth"), person.birth_place)
    if person.is_deceased:
        add(_("Date of death"), person.death_date_display or _("unknown"))
        add(_("Place of death"), person.death_place)
        add(_("Place of burial"), person.burial_place)
    add(_("Occupation"), person.occupation)
    add(_("Education"), person.education)
    return rows


def _facts_table(person, st, width):
    rows = [[_p(k, st["label"]), _p(v, st["body"])] for k, v in _facts(person)]
    if not rows:
        return None
    t = Table(rows, colWidths=[width * 0.32, width * 0.68])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _family_lines(archive, person):
    """[(heading, [names…])] for the person's closest family."""
    def name(pk):
        p = archive.people[pk]
        return f"{p.full_name} ({p.lifespan})" if p.lifespan else p.full_name

    out = []
    if person.father_id in archive.people:
        out.append((str(SECTION["father"]), [name(person.father_id)]))
    if person.mother_id in archive.people:
        out.append((str(SECTION["mother"]), [name(person.mother_id)]))
    spouses = archive.spouses(person.pk)
    if spouses:
        out.append((str(SECTION["spouses"]), [f"{name(s)} — {archive.label(person.pk, s)}" for s in spouses]))
    kids = archive.children.get(person.pk, [])
    if kids:
        out.append((str(SECTION["children"]), [f"{name(k)} — {archive.label(person.pk, k)}" for k in kids]))
    sibs = archive.siblings(person.pk)
    if sibs:
        out.append((str(SECTION["siblings"]), [f"{name(s)} — {archive.label(person.pk, s)}" for s in sibs]))
    return out


def _photo_bytes(person):
    """The person's photo as bytes (photos live in the database), or None."""
    if not person.photo:
        return None
    try:
        with person.photo.open("rb") as f:
            return f.read()
    except Exception:  # noqa: BLE001 - a missing or broken photo must not break the PDF
        return None


def _photo_reader(person):
    data = _photo_bytes(person)
    try:
        return ImageReader(BytesIO(data)) if data else None
    except Exception:  # noqa: BLE001
        return None


def _photo(person, size):
    """The photo `size` high for a page flow, or None."""
    reader = _photo_reader(person)
    if reader is None:
        return None
    iw, ih = reader.getSize()
    return Image(BytesIO(_photo_bytes(person)), width=min(size * 1.1, size * iw / float(ih or 1)), height=size)


def person_pdf(archive, person, focus_id=None, stories=(), life_path=()):
    """The book of one life: a cover with the photo, the person, the milestones,
    the life story, every story about them and their closest family."""
    st = _styles()
    width = A4[0] - 36 * mm - 12
    lines = [person.lifespan] if person.lifespan else []
    if focus_id and focus_id != person.pk:
        rel = archive.label(focus_id, person.pk)
        if rel:
            lines.append(rel)
    if stories:
        lines.append(ngettext("%(count)d event", "%(count)d events", len(stories)) % {"count": len(stories)})
    cover = _cover(_("Life book"), person.full_name, lines, photo=_photo_reader(person))
    items = [Spacer(1, 1), PageBreak()]

    items.append(_p(_("Life book").upper(), st["eyebrow"]))
    items.append(_p(person.full_name, st["title"]))
    if person.lifespan:
        items.append(_p(person.lifespan, st["subtitle"]))
    facts = _facts_table(person, st, width)
    if facts:
        items.append(_p(_("Personal details"), st["h2"]))
        items.append(facts)
    family = _family_lines(archive, person)
    if family:
        items.append(_p(_("Family"), st["h2"]))
        for heading, names in family:
            items.append(KeepTogether([_p(heading, st["h3"])] + [_p(n, st["body"]) for n in names]))

    if life_path:
        items.append(_p(_("Life path"), st["h2"]))
        rows = []
        for step in life_path:
            when = step["when"] + (f" · {step['age']}" if step.get("age") is not None and step["kind"] != "birth" else "")
            rows.append([_p(when, st["label"]), _p(step["text"], st["milestone"])])
        table = Table(rows, colWidths=[width * 0.3, width * 0.7])
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        items.append(table)

    for heading, text in ((_("Biography"), person.biography), (_("Life story"), person.life_story)):
        if text:
            items.append(_p(heading, st["h2"]))
            items.extend(_paragraphs(text, st["story"]))

    if stories:
        items.append(PageBreak())
        items.append(_p(_("Events and memories"), st["chapter"]))
        items.append(HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceAfter=6))
        for i, part in enumerate(_story_items(stories, st, width)):
            items.append(part)
        items.append(_ornament(width))

    close = [pk for pk in [person.father_id, person.mother_id] + archive.spouses(person.pk)
             + archive.children.get(person.pk, []) if pk in archive.people]
    if close:
        items.append(PageBreak())
        items.append(_p(_("Closest family"), st["chapter"]))
        items.append(HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceAfter=10))
        for pk in close:
            items.append(_person_entry(archive, archive.people[pk], person.pk, st, width))
    return _build(items, title=f"{_('Life book')} — {person.full_name}", cover=cover)


def _generation_groups(archive, focus_id):
    """[(heading, [person ids])] oldest generation first, unlinked people last."""
    gens = archive.generations(focus_id)
    groups = {}
    for pk, g in gens.items():
        groups.setdefault(max(-3, min(3, g)), []).append(pk)
    # Oldest generation first inside a chapter too ("great-grandparents and earlier").
    out = [(generation_label(g), sorted(groups[g], key=lambda pk: (gens[pk], archive.people[pk].birth_key or (9999,), pk)))
           for g in sorted(groups)]
    unlinked = sorted((pk for pk in archive.people if pk not in gens), key=lambda pk: archive.people[pk].full_name)
    if unlinked:
        out.append((_("Not yet linked to the family"), unlinked))
    return out


def _cover(title, family, lines, photo=None):
    """Draws the cover of a book on a canvas (with a round photo, if given)."""
    def draw(c):
        w, h = c._pagesize
        c.setFillColor(ACCENT_DARK)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, h * 0.34, w, h * 0.66, stroke=0, fill=1)
        draw_ikat(c, 0, 0, w, h, colors.white, step=22 * mm, alpha=0.07)
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.rect(11 * mm, 11 * mm, w - 22 * mm, h - 22 * mm, stroke=1, fill=0)
        c.setLineWidth(0.5)
        c.rect(13 * mm, 13 * mm, w - 26 * mm, h - 26 * mm, stroke=1, fill=0)
        mark = 34 * mm
        if photo is not None:
            r = 25 * mm
            cx, cy = w / 2, h * 0.64 + mark / 2
            iw, ih = photo.getSize()
            k = 2 * r / min(iw, ih)
            c.saveState()
            path = c.beginPath()
            path.circle(cx, cy, r)
            c.clipPath(path, stroke=0, fill=0)
            c.drawImage(photo, cx - iw * k / 2, cy - ih * k / 2, iw * k, ih * k)
            c.restoreState()
            c.setStrokeColor(GOLD)
            c.setLineWidth(2)
            c.circle(cx, cy, r, stroke=1, fill=0)
        else:
            draw_mark(c, (w - mark) / 2, h * 0.64, mark, GOLD)
        c.setFillColor(colors.white)
        size = 40
        while size > 18 and pdfmetrics.stringWidth(family, FONT_BOLD, size) > w - 50 * mm:
            size -= 2
        c.setFont(FONT_BOLD, size)
        c.drawCentredString(w / 2, h * 0.52, family)
        c.setFillColor(GOLD)
        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(w / 2, h * 0.52 - 12 * mm, title.upper())
        c.setFillColor(colors.HexColor("#d5d9ee"))
        c.setFont(FONT, 10.5)
        y = h * 0.24
        for line in lines:
            c.drawCentredString(w / 2, y, line)
            y -= 6 * mm
    return draw


def book_people(archive, focus_id, side=None):
    """Everyone in the book: the whole tree, or the own family and one side
    (with the husbands and wives who married into it)."""
    if side not in ("paternal", "maternal"):
        return set(archive.people)
    branches = archive.branches(focus_id)
    keep = {pk for pk, b in branches.items() if b in ("own", side)}
    keep |= {sp for pk in list(keep) for sp in archive.spouses(pk) if branches.get(sp, "other") == "other"}
    return keep


def family_book_pdf(archive, focus_id, owner_name, viewer_is_owner=True, family="", side=None, stories=(),
                    with_stories=True):
    """The family as a book: a cover, the contents, then everyone by
    generation with photo, dates, family, life story and their stories;
    stories about no one in particular close the book."""
    st = _styles()
    width = A4[0] - 36 * mm - 12  # the frame of the page has 6 pt of padding on each side
    keep = book_people(archive, focus_id, side)
    groups = [(heading, [pk for pk in members if pk in keep]) for heading, members in _generation_groups(archive, focus_id)]
    groups = [(heading, members) for heading, members in groups if members]
    by_person, loose = {}, []
    order = {pk: i for i, pk in enumerate(pk for _h, members in groups for pk in members)}
    for event in stories:  # an event is told once: next to the first of its people in the book
        people = sorted((p.pk for p in event.people.all() if p.pk in order), key=order.get)
        if people:
            by_person.setdefault(people[0], []).append(event)
        elif side is None and not event.people.all():
            loose.append(event)
    count = sum(len(m) for _h, m in groups)
    part = {"paternal": BRANCHES["paternal"], "maternal": BRANCHES["maternal"]}.get(side)
    lines = [ngettext("%(count)d person", "%(count)d people", count) % {"count": count},
             ngettext("%(count)d generation", "%(count)d generations", len(groups)) % {"count": len(groups)}]
    if stories:
        told = sum(len(v) for v in by_person.values()) + len(loose)
        if told:
            lines.append(ngettext("%(count)d event", "%(count)d events", told) % {"count": told})
    lines.append(format_date(timezone.now()))
    title = _("Family book") + (f" · {part}" if part else "")
    cover = _cover(title, family or owner_name, lines)
    items = [Spacer(1, 1), PageBreak()]  # the cover is drawn on the first page
    items.append(_p(title.upper(), st["eyebrow"]))
    items.append(_p(family or owner_name, st["title"]))
    items.append(_p(_("Compiled by %(name)s") % {"name": owner_name}, st["subtitle"]))
    items.append(_p(_("Contents"), st["h2"]))
    for heading, members in groups:
        items.append(_p(f"{heading} — " + ngettext("%(count)d person", "%(count)d people", len(members))
                        % {"count": len(members)}, st["toc"]))
    if loose:
        items.append(_p(_("Family events"), st["toc"]))
    for heading, members in groups:
        items.append(PageBreak())
        items.append(_p(heading, st["chapter"]))
        items.append(HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceAfter=10))
        for pk in members:
            items.append(_person_entry(archive, archive.people[pk], focus_id, st, width, viewer_is_owner,
                                       with_stories=with_stories))
            if by_person.get(pk):
                items.extend(_story_items(by_person[pk], st, width))
                items.append(_ornament(width))
    if loose:
        items.append(PageBreak())
        items.append(_p(_("Family events"), st["chapter"]))
        items.append(HRFlowable(width="100%", thickness=1.2, color=GOLD, spaceAfter=6))
        items.extend(_story_items(loose, st, width))
    return _build(items, title=f"{title} — {family or owner_name}", cover=cover)


def _person_entry(archive, person, focus_id, st, width, viewer_is_owner=True, with_stories=True):
    text = [_p(person.full_name, st["h3"])]
    label = "" if person.pk == focus_id and not viewer_is_owner else archive.label(focus_id, person.pk)
    sub = " · ".join(x for x in (label, person.lifespan) if x)
    if sub:
        text.append(_p(sub, st["rel"]))
    facts = [f"{k}: {v}" for k, v in _facts(person)[1:]]
    if facts:
        text.append(Spacer(1, 2))
        text.append(_p("; ".join(facts), st["body"]))
    for heading, names in _family_lines(archive, person)[:4]:
        text.append(_p(f"{heading}: " + ", ".join(names), st["small"]))
    for story in (person.biography, person.life_story) if with_stories else ():
        if story:
            text.append(Spacer(1, 3))
            text.extend(_paragraphs(story, st["body"]))
    photo = _photo(person, 24 * mm)
    if photo is not None:
        col = photo.drawWidth + 5 * mm
        table = Table([[photo, text]], colWidths=[col, width - col], hAlign="LEFT")
    else:
        table = Table([[text]], colWidths=[width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]))
    # Long life stories may run over several pages; short entries stay together.
    long_text = len(person.biography or "") + len(person.life_story or "") > 900
    return KeepTogether([table, Spacer(1, 9)]) if not long_text else table


# ---------------------------------------------------------------------------
# Tree chart
# ---------------------------------------------------------------------------
def _wrap(text, font, size, max_w, max_lines):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and pdfmetrics.stringWidth(lines[-1] + "…", font, size) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    # A single word longer than the card is shortened too.
    fixed = []
    for line in lines:
        while pdfmetrics.stringWidth(line, font, size) > max_w and len(line) > 1:
            line = line[:-2] + "…"
        fixed.append(line)
    return fixed


def tree_pdf(layout, title, subtitle, poster=None, family="", photos=None):
    """The chart from tree.build_tree on one landscape page.

    Ordinary: A4 or A3, or one wide page for a large family. poster="A2" /
    "A1": a wall poster with a title band, an ornamental frame and a legend.
    photos: {person id: ImageReader} drawn in the avatar circles.
    """
    register_fonts()
    photos = photos or {}
    lw, lh = layout["width"], layout["height"]
    if poster in POSTER_SIZES:
        # A wall banner: the height of the sheet is fixed (A2: 42 cm, A1: 59 cm,
        # the widths of printing rolls); a wide family makes the sheet longer.
        pw, ph = POSTER_SIZES[poster]
        margin, head_h, foot_h = 22 * mm, 46 * mm, 16 * mm
        fit_h = (ph - 2 * margin - head_h - foot_h) / lh
        scale = min((pw - 2 * margin) / lw, fit_h, 1.6)
        if scale < fit_h and scale < 1.0:
            scale = min(fit_h, 1.0, (POSTER_MAX_WIDTH - 2 * margin) / lw)
            pw = max(pw, lw * scale + 2 * margin)
    else:
        margin, head_h, foot_h = 12 * mm, 20 * mm, 0
        min_scale = 0.5  # below this the card text is too small to read
        for size in (landscape(A4), landscape(A3)):
            pw, ph = size
            scale = min((pw - 2 * margin) / lw, (ph - 2 * margin - head_h) / lh, 0.9)
            if scale >= min_scale:
                break
        else:
            # A large family: one wide page that PDF viewers can zoom.
            scale = min_scale
            pw = lw * scale + 2 * margin
            ph = max(lh * scale + 2 * margin + head_h, landscape(A4)[1])
    pagesize = (pw, ph)
    ox = (pw - lw * scale) / 2
    top = ph - margin - head_h
    if poster in POSTER_SIZES:  # centre the chart in the space under the title
        top -= max(0, (ph - 2 * margin - head_h - foot_h - lh * scale) / 2)

    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=pagesize)
    c.setTitle(title)
    if poster in POSTER_SIZES:
        c.setFillColor(PAPER)
        c.rect(0, 0, pw, ph, stroke=0, fill=1)
        band_y = ph - 12 * mm - head_h + 8 * mm
        c.setFillColor(ACCENT_DARK)
        c.rect(12 * mm, band_y, pw - 24 * mm, head_h - 8 * mm, stroke=0, fill=1)
        draw_ikat(c, 12 * mm, band_y, pw - 24 * mm, head_h - 8 * mm, colors.white, step=19 * mm, alpha=0.08)
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.4)
        c.rect(12 * mm, 12 * mm, pw - 24 * mm, ph - 24 * mm, stroke=1, fill=0)
        c.setLineWidth(0.5)
        c.rect(14.5 * mm, 14.5 * mm, pw - 29 * mm, ph - 29 * mm, stroke=1, fill=0)
        mark = 22 * mm
        draw_mark(c, 22 * mm, band_y + (head_h - 8 * mm - mark) / 2, mark, GOLD)
        heading = family or title
        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 30)
        c.drawString(22 * mm + mark + 8 * mm, band_y + (head_h - 8 * mm) / 2 + 1 * mm, heading)
        c.setFillColor(GOLD)
        c.setFont(FONT_BOLD, 11)
        c.drawString(22 * mm + mark + 8 * mm, band_y + (head_h - 8 * mm) / 2 - 8 * mm, title.upper())
        # Legend and date at the bottom.
        c.setFont(FONT, 9)
        x = 22 * mm
        for key in ("own", "paternal", "maternal", "other"):
            c.setFillColor(BRANCH[key][0])
            c.circle(x + 1.5 * mm, 20.2 * mm, 1.6 * mm, stroke=0, fill=1)
            c.setFillColor(MUTED)
            text = str(BRANCHES[key])
            c.drawString(x + 5 * mm, 19 * mm, text)
            x += 5 * mm + pdfmetrics.stringWidth(text, FONT, 9) + 8 * mm
        c.drawRightString(pw - 22 * mm, 19 * mm, _footer_text())
    else:
        c.setFont(FONT_BOLD, 16)
        c.setFillColor(INK)
        c.drawString(margin, ph - margin - 7 * mm, title)
        c.setFont(FONT, 9.5)
        c.setFillColor(MUTED)
        c.drawString(margin, ph - margin - 13 * mm, subtitle)
        c.setFont(FONT, 8)
        c.drawString(margin, 8 * mm, _footer_text())

    def tx(x):
        return ox + x * scale

    def ty(y):
        return top - y * scale

    for line in sorted(layout["lines"], key=lambda ln: bool(ln.get("direct"))):
        child = line["kind"] == "child"
        if line.get("direct"):
            c.setStrokeColor(GOLD)
            c.setLineWidth(2.6 * scale)
        else:
            c.setStrokeColor(TREE_LINE if child else ACCENT)
            c.setLineWidth((1.6 if child else 2.3) * scale)
        c.setDash(6 * scale, 4 * scale) if line["kind"] == "partners" else c.setDash()
        path = c.beginPath()
        (x0, y0), *rest = line["points"]
        path.moveTo(tx(x0), ty(y0))
        for x, y in rest:
            path.lineTo(tx(x), ty(y))
        c.drawPath(path, stroke=1, fill=0)
    c.setDash()

    # Card geometry matches static/js/tree.js.
    av_cx, av_cy, av_r, text_x, pad_r = 34, 34, 20, 64, 10
    inner = (CARD_W - text_x - pad_r) * scale
    for n in layout["nodes"]:
        tint, soft = BRANCH.get(n.get("branch"), BRANCH["other"])
        x, y = tx(n["x"]), ty(n["y"] + CARD_H)
        w, h = CARD_W * scale, CARD_H * scale
        c.setFillColor(ACCENT_SOFT if n["focus"] else colors.white)
        c.setStrokeColor(ACCENT if n["focus"] else (GOLD if n.get("direct") else LINE))
        c.setLineWidth((2.4 if n["focus"] else 1.6 if n.get("direct") else 1) * scale)
        if n["dup"]:
            c.setDash(5 * scale, 4 * scale)
        c.roundRect(x, y, w, h, 14 * scale, stroke=1, fill=1)
        c.setDash()
        c.setFillColor(tint)
        c.roundRect(x, y + 12 * scale, 4 * scale, h - 24 * scale, 2 * scale, stroke=0, fill=1)
        cx, cy, r = tx(n["x"] + av_cx), ty(n["y"] + av_cy), av_r * scale
        c.setFillColor(soft)
        c.circle(cx, cy, r, stroke=0, fill=1)
        reader = photos.get(n["id"])
        if reader is not None:
            iw, ih = reader.getSize()
            k = max(2 * r / iw, 2 * r / ih)
            c.saveState()
            clip = c.beginPath()
            clip.circle(cx, cy, r)
            c.clipPath(clip, stroke=0, fill=0)
            c.drawImage(reader, cx - iw * k / 2, cy - ih * k / 2, iw * k, ih * k, mask="auto")
            c.restoreState()
        else:
            c.setFillColor(tint)
            c.setFont(FONT_BOLD, 13 * scale)
            c.drawCentredString(cx, ty(n["y"] + av_cy + 4.5), n.get("initials", ""))

        name_size = 13.5 * scale
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, name_size)
        ly = 25
        for ln in _wrap(n["name"], FONT_BOLD, name_size, inner, 2):
            c.drawString(tx(n["x"] + text_x), ty(n["y"] + ly), ln)
            ly += 16
        if n["years"]:
            c.setFont(FONT, 11.5 * scale)
            c.setFillColor(MUTED)
            c.drawString(tx(n["x"] + text_x), ty(n["y"] + ly + 1), n["years"])
        if n["label"]:
            size = 11 * scale
            label = _wrap(n["label"], FONT_BOLD, size, inner - 12 * scale, 1)[0]
            lw_ = pdfmetrics.stringWidth(label, FONT_BOLD, size) + 12 * scale
            c.setFillColor(colors.white if n["focus"] else ACCENT_SOFT)
            c.roundRect(tx(n["x"] + text_x), ty(n["y"] + CARD_H - 8), lw_, 17 * scale, 8.5 * scale, stroke=0, fill=1)
            c.setFillColor(ACCENT)
            c.setFont(FONT_BOLD, size)
            c.drawString(tx(n["x"] + text_x + 6), ty(n["y"] + CARD_H - 13), label)

        # Closed branches: "+N" where the button is on screen.
        badges = []
        sibs, kids = n.get("sibs"), n.get("kids")
        if sibs and not sibs["open"]:
            badges.append((18 if sibs["side"] == "left" else CARD_W - 18, 0, f"+{sibs['count']}"))
        if kids and not kids["open"]:
            badges.append((CARD_W - 24, CARD_H, f"+{kids['count']}"))
        for bx, by, text in badges:
            bw = max(24, len(text) * 7.5 + 14)
            c.setFillColor(colors.white)
            c.setStrokeColor(ACCENT)
            c.setLineWidth(1.5 * scale)
            c.roundRect(tx(n["x"] + bx - bw / 2), ty(n["y"] + by + 11), bw * scale, 22 * scale, 11 * scale, stroke=1, fill=1)
            c.setFillColor(ACCENT)
            c.setFont(FONT_BOLD, 11.5 * scale)
            c.drawCentredString(tx(n["x"] + bx), ty(n["y"] + by + 4), text)
    c.showPage()
    c.save()
    return buf.getvalue()


def tree_photos(archive, layout):
    """{person id: ImageReader} for the people on a chart who have a photo."""
    out = {}
    for node in layout["nodes"]:
        person = archive.people.get(node["id"])
        if person is not None and person.photo and node["id"] not in out:
            reader = _photo_reader(person)
            if reader is not None:
                out[node["id"]] = reader
    return out
