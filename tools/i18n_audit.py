"""Language audit: finds interface text that would bypass translation.

    python tools/i18n_audit.py          # prints problems, exit code 1 if any

Checks
  1. Catalogues (locale/*/LC_MESSAGES/*.po): every entry translated (English
     may fall back to the source text), nothing fuzzy, placeholders kept,
     Russian plurals in three forms; Uzbek Latin free of Cyrillic and of
     non-canonical apostrophes (o' o‘ o’ g' …); Uzbek Cyrillic and Russian
     free of Latin letters except a few intentional tokens (PDF, PNG, the
     "Alisher" search example); Russian free of Uzbek letters (ў қ ғ ҳ);
     English free of Cyrillic.
  2. Templates: visible text outside {% translate %} / {% blocktranslate %}.
  3. JavaScript: quoted sentences that are not wrapped in gettext().
  4. Python: user-facing calls (messages.*, ValidationError, add_error,
     Http404, PermissionDenied) given a bare string instead of gettext.
The same checks run in the test suite (tests/test_i18n.py).
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = {"uz": "latin", "uz_Cyrl": "cyrillic", "ru": "russian", "en": "english"}
PLURAL_FORMS = {"uz": 1, "uz_Cyrl": 1, "ru": 3, "en": 2}
UZBEK_ONLY_CYRILLIC = re.compile(r"[ЎўҚқҒғҲҳ]")
# "# Translators: placeholders {a} {b}" lists extra values a sentence may use.
DECLARED = re.compile(r"placeholders?((?:\s*\{\w+\})+)")

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN = re.compile(r"[A-Za-z]")
# o/g followed by any apostrophe other than the canonical ʻ (U+02BB).
BAD_OG = re.compile(r"[oOgG]['‘’`ʼ]")
# Letter + ASCII/typographic apostrophe + letter (should be ʼ U+02BC).
BAD_TUTUQ = re.compile(r"(?<=[^\W\d_])['’`](?=[^\W\d_])")
PLACEHOLDER = re.compile(r"%\(\w+\)[sd]|%[sd]|\{\w+\}")
# Format names, key names and bot commands stay in Latin in both scripts.
ALLOWED_LATIN_IN_CYRILLIC = {"PDF", "PNG", "Alisher", "MB", "GEDCOM", "Ctrl", "Mac", "Start", "stop", "JSON", "Google",
                             "Telegram", "Web", "MyHeritage", "Ancestry", "Gramps", "UTC", "Shajara", "Silai", "Rahm", "Gemini", "GEMINI", "API", "KEY", "AI", "Studio", "Get", "key", "next", "help", "start", "URL", "cookie",
                             "Authenticator", "Microsoft", "Push", "iPhone", "iPad"}
# Brand and format names that appear as they are in every language.
BRANDS = {"Google", "Telegram", "GEDCOM", "JSON", "PDF", "PNG"}


def _po_entries():
    import polib

    for loc, script in LOCALES.items():
        for path in sorted((ROOT / "locale" / loc / "LC_MESSAGES").glob("*.po")):
            for entry in polib.pofile(str(path)):
                yield loc, script, path, entry


def _strings(entry):
    if entry.msgid_plural:
        return list(entry.msgstr_plural.values())
    return [entry.msgstr]


def _allowed_placeholders(entry):
    m = DECLARED.search(entry.comment or "")
    return set(PLACEHOLDER.findall(m.group(1))) if m else None


def check_catalogues():
    problems = []
    for loc, script, path, entry in _po_entries():
        where = f"{path.relative_to(ROOT)}: {entry.msgid!r}"
        if entry.obsolete:
            continue
        if "fuzzy" in entry.flags:
            problems.append(f"{where} is marked fuzzy")
        if entry.msgid_plural and script != "english" and len(entry.msgstr_plural) != PLURAL_FORMS[loc]:
            problems.append(f"{where} needs {PLURAL_FORMS[loc]} plural form(s)")
        declared = _allowed_placeholders(entry)
        for text in _strings(entry):
            if not text.strip():
                if script != "english":  # English falls back to the source text
                    problems.append(f"{where} is not translated")
                continue
            bare = re.sub(r"<[^>]+>", "", PLACEHOLDER.sub("", text))  # HTML tags are markup
            if script == "latin":
                if CYRILLIC.search(bare) and "Алишер" not in bare:
                    problems.append(f"{where} contains Cyrillic in the Latin catalogue: {text!r}")
                if BAD_OG.search(bare) or BAD_TUTUQ.search(bare):
                    problems.append(f"{where} uses a non-canonical apostrophe (use ʻ / ʼ): {text!r}")
            elif script == "english":
                if CYRILLIC.search(bare) and "Алишер" not in bare:
                    problems.append(f"{where} contains Cyrillic in the English catalogue: {text!r}")
            else:
                for word in re.findall(r"[A-Za-z]+", bare):
                    if word not in ALLOWED_LATIN_IN_CYRILLIC:
                        problems.append(f"{where} contains Latin text {word!r} in the {loc} catalogue")
                        break
                if script == "russian" and UZBEK_ONLY_CYRILLIC.search(bare):
                    problems.append(f"{where} contains Uzbek letters in the Russian catalogue: {text!r}")
            used = set(PLACEHOLDER.findall(text))
            if declared is not None:
                if not used <= declared:
                    problems.append(f"{where} uses undeclared placeholders: {text!r}")
            elif not entry.msgid_plural and used != set(PLACEHOLDER.findall(entry.msgid)):
                problems.append(f"{where} placeholders differ: {text!r}")
            elif entry.msgid_plural and not used <= set(PLACEHOLDER.findall(entry.msgid_plural)):
                problems.append(f"{where} placeholders differ: {text!r}")
    return problems


class _TextCollector(HTMLParser):
    SKIP = {"script", "style", "svg", "code", "kbd"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        for name, value in attrs:
            if name in ("placeholder", "title", "aria-label", "alt") and value and LATIN.search(value):
                self.found.append(value)

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth and LATIN.search(data):
            self.found.append(data.strip())


TEMPLATE_TAGS = re.compile(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", re.S)
# Blocks that hold CSS class names, not text.
NON_TEXT_BLOCK = re.compile(r"\{%\s*block main_class\s*%\}.*?\{%\s*endblock\s*%\}", re.S)
TRANSLATE_BLOCK = re.compile(r"\{%\s*blocktranslate.*?%\}.*?\{%\s*endblocktranslate\s*%\}", re.S)


def check_templates():
    problems = []
    for path in sorted((ROOT / "templates").rglob("*")):
        if path.suffix not in (".html", ".txt") or path.name == "logo.svg":
            continue
        source = path.read_text(encoding="utf-8")
        source = NON_TEXT_BLOCK.sub("", source)
        source = TRANSLATE_BLOCK.sub("", source)
        source = TEMPLATE_TAGS.sub("", source)
        if path.suffix == ".txt":
            leftovers = [line.strip() for line in source.splitlines() if re.search(r"[A-Za-z]{2,}", line)
                         and not re.search(r"://", line)]
        else:
            parser = _TextCollector()
            parser.feed(source)
            leftovers = [t for t in parser.found if re.search(r"[A-Za-z]{2,}", t) and t not in BRANDS]
        for text in leftovers:
            problems.append(f"{path.relative_to(ROOT)}: untranslated text {text!r}")
    return problems


JS_STRING = re.compile(r"""(["'])((?:(?!\1).)*[A-Za-z]{2,}\s+[A-Za-z]{2,}(?:(?!\1).)*)\1""")
JS_WRAPPED = re.compile(r"""(?:gettext|pgettext|ngettext|interpolate)\s*\(\s*(?:["'][^"']*["']\s*,\s*)?$""")


def check_javascript():
    problems = []
    for path in sorted((ROOT / "static" / "js").glob("*.js")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//")[0] if not line.strip().startswith("/*") else ""
            for m in JS_STRING.finditer(code):
                text = m.group(2)
                # CSS selectors and SVG attribute values are code, not text.
                if re.match(r"^[.#\[]", text) or text.startswith("xMid") or re.fullmatch(r"[a-z-]+( [a-z-]+){0,2}", text):
                    continue
                # Markup and the code between two neighbouring literals are not sentences.
                if "<" in text or re.search(r"&&|===|\);|\) ", text):
                    continue
                if text == "use strict" or any(k in text for k in ("Noto Sans", "system-ui", "image/", "same-origin", "application/json")):
                    continue
                if JS_WRAPPED.search(code[: m.start()]):
                    continue
                problems.append(f"{path.relative_to(ROOT)}:{lineno}: string not passed through gettext: {text!r}")
    return problems


PY_CALL = re.compile(
    r"""(messages\.(?:success|error|info|warning)\(\s*request\s*,|ValidationError\(|add_error\([^,]+,|Http404\(|PermissionDenied\()\s*["']"""
)


def check_python():
    problems = []
    for path in sorted((ROOT / "apps").rglob("*.py")):
        if "migrations" in path.parts or path.name == "seed_demo.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PY_CALL.search(line):
                problems.append(f"{path.relative_to(ROOT)}:{lineno}: user-facing message without gettext")
    return problems


def run_all():
    return check_catalogues() + check_templates() + check_javascript() + check_python()


if __name__ == "__main__":
    found = run_all()
    for problem in found:
        print(problem)
    print(f"\n{len(found)} problem(s) found." if found else "Language audit passed.")
    sys.exit(1 if found else 0)
