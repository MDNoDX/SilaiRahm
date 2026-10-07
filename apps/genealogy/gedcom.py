"""GEDCOM 5.5.1 export and import — the standard exchange format of genealogy
programs (MyHeritage, Ancestry, FamilySearch, Gramps …). Names and places are
written exactly as stored, in UTF-8; files from other programs are read in
UTF-8, UTF-16 or Windows-1251."""
import datetime
import re

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def gedcom_date(year, month=None, day=None):
    if not year:
        return ""
    parts = []
    if month and day:
        parts.append(str(day))
    if month:
        parts.append(MONTHS[month - 1])
    parts.append(str(year))
    return " ".join(parts)


def _text(level, tag, value):
    """A line, with long or multi-line text split into CONT/CONC lines."""
    lines = []
    for i, chunk in enumerate(str(value).splitlines() or [""]):
        pieces = [chunk[j:j + 200] for j in range(0, len(chunk), 200)] or [""]
        first_tag = tag if i == 0 else "CONT"
        first_level = level if i == 0 else level + 1
        lines.append(f"{first_level} {first_tag} {pieces[0]}".rstrip())
        lines += [f"{level + 1} CONC {p}" for p in pieces[1:]]
    return lines


def export(archive, owner_name=""):
    people = archive.people
    fams = {}  # (husband, wife) -> family record
    for m in archive.marriages:
        fams[(m.husband_id, m.wife_id)] = {"husb": m.husband_id, "wife": m.wife_id, "marriage": m, "kids": []}
    for p in people.values():
        if p.father_id or p.mother_id:
            key = (p.father_id if p.father_id in people else None, p.mother_id if p.mother_id in people else None)
            fams.setdefault(key, {"husb": key[0], "wife": key[1], "marriage": None, "kids": []})["kids"].append(p.pk)
    fam_ids = {key: f"@F{i}@" for i, key in enumerate(fams, start=1)}

    out = ["0 HEAD", "1 SOUR SILAIRAHM", "2 NAME Silai Rahm", "1 GEDC", "2 VERS 5.5.1", "2 FORM LINEAGE-LINKED",
           "1 CHAR UTF-8", f"1 DATE {gedcom_date(*_today())}"]
    if owner_name:
        out += ["1 SUBM @U1@", "0 @U1@ SUBM", f"1 NAME {owner_name}"]
    for p in sorted(people.values(), key=lambda x: x.pk):
        out.append(f"0 @I{p.pk}@ INDI")
        out.append(f"1 NAME {p.first_name} /{p.last_name}/".rstrip())
        out.append(f"2 GIVN {p.first_name}")
        if p.last_name:
            out.append(f"2 SURN {p.last_name}")
        out.append(f"1 SEX {'M' if p.gender == 'male' else 'F'}")
        if p.birth_year or p.birth_place:
            out.append("1 BIRT")
            if p.birth_year:
                out.append(f"2 DATE {gedcom_date(p.birth_year, p.birth_month, p.birth_day)}")
            if p.birth_place:
                out.append(f"2 PLAC {p.birth_place}")
        if p.is_deceased:
            out.append("1 DEAT Y" if not (p.death_year or p.death_place) else "1 DEAT")
            if p.death_year:
                out.append(f"2 DATE {gedcom_date(p.death_year, p.death_month, p.death_day)}")
            if p.death_place:
                out.append(f"2 PLAC {p.death_place}")
        if p.burial_place:
            out += ["1 BURI", f"2 PLAC {p.burial_place}"]
        if p.occupation:
            out.append(f"1 OCCU {p.occupation}")
        if p.education:
            out.append(f"1 EDUC {p.education}")
        for note in (p.biography, p.life_story):
            if note:
                out += _text(1, "NOTE", note)
        for key, fid in fam_ids.items():
            if p.pk in fams[key]["kids"]:
                out.append(f"1 FAMC {fid}")
            if p.pk in (fams[key]["husb"], fams[key]["wife"]):
                out.append(f"1 FAMS {fid}")
    for key, fid in fam_ids.items():
        fam = fams[key]
        out.append(f"0 {fid} FAM")
        if fam["husb"]:
            out.append(f"1 HUSB @I{fam['husb']}@")
        if fam["wife"]:
            out.append(f"1 WIFE @I{fam['wife']}@")
        m = fam["marriage"]
        if m:
            out.append("1 MARR" + ("" if m.year else " Y"))
            if m.year:
                out.append(f"2 DATE {gedcom_date(m.year, m.month, m.day)}")
            if m.is_divorced:
                out.append("1 DIV Y")
        for kid in sorted(fam["kids"], key=lambda k: (people[k].birth_key or (9999,), k)):
            out.append(f"1 CHIL @I{kid}@")
    out.append("0 TRLR")
    return "\r\n".join(out) + "\r\n"


def _today():
    d = datetime.date.today()
    return d.year, d.month, d.day


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
class GedcomError(ValueError):
    pass


LINE = re.compile(r"^\s*(\d+)\s+(?:(@[^@]+@)\s+)?([A-Za-z0-9_]+)(?: (.*))?$")
DATE = re.compile(r"(?:(\d{1,2})\s+)?(?:([A-Z]{3})[A-Z]*\.?\s+)?(\d{3,4})\b")
MAX_PEOPLE = 5000


def _decode(raw):
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("latin-1")


def parse_date(text):
    """"ABT 12 MAR 1950", "MAR 1950", "BET 1950 AND 1955" → (year, month, day); unknown parts are None."""
    m = DATE.search((text or "").upper())
    if not m:
        return None, None, None
    day, month, year = m.groups()
    month = MONTHS.index(month) + 1 if month in MONTHS else None
    day = int(day) if day and month else None
    year = int(year)
    if not 1000 <= year <= datetime.date.today().year + 1:
        return None, None, None
    if day and not 1 <= day <= 31:
        day = None
    return year, month, day


def parse(text):
    """{"INDI": {xref: record}, "FAM": {…}, "NOTE": {…}}; a record is a
    nested list of (tag, value, children)."""
    records = {"INDI": {}, "FAM": {}, "NOTE": {}}
    stack = []
    seen = False
    for raw in text.splitlines():
        m = LINE.match(raw.rstrip("\r\n"))
        if not m:
            continue
        level, xref, tag, value = int(m.group(1)), m.group(2), m.group(3).upper(), m.group(4) or ""
        node = (tag, value, [])
        if level == 0:
            seen = True
            stack = [node]
            if xref and tag in records:
                records[tag][xref] = node
            continue
        if not stack:
            continue
        del stack[level:]
        if len(stack) < level:
            continue
        stack[-1][2].append(node)
        stack.append(node)
    if not seen or not records["INDI"]:
        raise GedcomError("no people")
    return records


def _child(node, tag):
    return next((c for c in node[2] if c[0] == tag), None)


def _value(node, *path):
    for tag in path:
        node = _child(node, tag) if node else None
    return node[1].strip() if node else ""


def _long_text(node):
    """A NOTE with its CONT (new line) and CONC (same line) continuations."""
    text = node[1]
    for tag, value, _kids in node[2]:
        if tag == "CONT":
            text += "\n" + value
        elif tag == "CONC":
            text += value
    return text.strip()


def import_file(owner, raw):
    """Add the people and families of a GEDCOM file to `owner`'s archive.
    Returns {"people": n, "families": n}."""
    from django.db import transaction

    from apps.core.text import normalize_apostrophes

    from .models import Marriage, Person

    records = parse(_decode(raw))
    if len(records["INDI"]) > MAX_PEOPLE:
        raise GedcomError("too large")

    # Sex is sometimes missing: the role in a family tells it.
    role = {}
    for fam in records["FAM"].values():
        if _value(fam, "HUSB"):
            role[_value(fam, "HUSB")] = "male"
        if _value(fam, "WIFE"):
            role[_value(fam, "WIFE")] = "female"

    def clean(value, limit):
        return normalize_apostrophes(" ".join(value.split()))[:limit]

    with transaction.atomic():
        people = {}
        for xref, rec in records["INDI"].items():
            name = _child(rec, "NAME")
            given = surname = ""
            if name:
                given, surname = _value(name, "GIVN"), _value(name, "SURN")
                if not given and not surname:
                    parts = name[1].split("/")
                    given = parts[0]
                    surname = parts[1] if len(parts) > 1 else ""
            sex = _value(rec, "SEX").upper()[:1]
            birth, death = _child(rec, "BIRT"), _child(rec, "DEAT")
            by, bm, bd = parse_date(_value(birth, "DATE")) if birth else (None, None, None)
            dy, dm, dd = parse_date(_value(death, "DATE")) if death else (None, None, None)
            notes = []
            for note in (c for c in rec[2] if c[0] == "NOTE"):
                linked = records["NOTE"].get(note[1].strip())
                notes.append(_long_text(linked) if linked else _long_text(note))
            person = Person(
                owner=owner,
                first_name=clean(given, 100) or "?",
                last_name=clean(surname, 100),
                gender={"M": "male", "F": "female"}.get(sex) or role.get(xref, "male"),
                birth_year=by, birth_month=bm, birth_day=bd,
                birth_place=clean(_value(birth, "PLAC"), 200) if birth else "",
                is_deceased=death is not None,
                death_year=dy, death_month=dm, death_day=dd,
                death_place=clean(_value(death, "PLAC"), 200) if death else "",
                burial_place=clean(_value(rec, "BURI", "PLAC"), 250),
                occupation=clean(_value(rec, "OCCU"), 200),
                education=clean(_value(rec, "EDUC"), 200),
                biography="\n\n".join(n for n in notes if n),
            )
            person.save()
            people[xref] = person

        families = 0
        for fam in records["FAM"].values():
            husband, wife = people.get(_value(fam, "HUSB")), people.get(_value(fam, "WIFE"))
            if husband and wife and husband.gender == "female" and wife.gender == "male":
                husband, wife = wife, husband
            for tag, value, _kids in fam[2]:
                child = people.get(value.strip()) if tag == "CHIL" else None
                if child is None:
                    continue
                if husband and child.pk != husband.pk and not child.father_id:
                    child.father = husband
                if wife and child.pk != wife.pk and not child.mother_id:
                    child.mother = wife
                child.save()
            if husband and wife and husband.pk != wife.pk and husband.gender != wife.gender:
                my, mm, md = parse_date(_value(fam, "MARR", "DATE"))
                Marriage.objects.get_or_create(owner=owner, husband=husband, wife=wife,
                                               defaults={"year": my, "month": mm, "day": md,
                                                         "is_divorced": _child(fam, "DIV") is not None})
            families += 1
    return {"people": len(people), "families": families}
