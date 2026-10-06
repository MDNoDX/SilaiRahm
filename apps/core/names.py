"""What a name tells: whether it is usually a man's or a woman's.

Used only to pre-select a choice the person can change (signing up with
Google, a new relative): Uzbek and Russian surnames and patronymics say it
clearly (-ova / -ov, qizi / oʻgʻli), first names often do.
"""
from .text import search_key

# Endings of surnames and patronymics, folded to Latin by `search_key`.
FEMALE_ENDINGS = ("ova", "eva", "yeva", "ovna", "evna", "yevna", "ina", "skaya", "kaya", "qizi", "kizi")
MALE_ENDINGS = ("ov", "ev", "yev", "ovich", "evich", "yevich", "in", "skiy", "skii", "ugli", "ogli", "oʻgʻli")
# First names: whole names and endings that are (almost) always one or the other.
FEMALE_NAMES = {"gulnora", "malika", "dilnoza", "nilufar", "zarina", "madina", "shahnoza", "feruza", "nigora",
                "kamola", "umida", "dilorom", "dilfuza", "dilsevar", "mukarram", "nafisa", "aziza", "laylo",
                "sevara", "mohira", "maftuna", "zuhra", "robiya", "mubina", "oysuluv", "anzirat", "gulnafis",
                "gulnoza", "shoira", "mamura", "muqaddam", "enaxon", "bibi", "maryam", "fotima", "oisha", "xadicha"}
FEMALE_STARTS = ("gul", "dil", "oy", "nil", "mehri", "zeb", "shahr")
FEMALE_TAILS = ("xon", "oy", "niso", "bonu", "bibi", "gul", "nisa", "noza", "nora", "ra", "na", "da", "ma", "ya",
                "la", "sa", "za", "ta", "fa")
MALE_NAMES = {"muhammad", "ali", "umar", "usmon", "rustam", "timur", "jasur", "sherzod", "samir", "anvar", "karim",
              "nodirbek", "alisher", "xolmatjon", "madaminjon", "sharobiddin", "jaloliddin", "abdulhamid", "erkinjon",
              "orifjon", "tavakiljon", "muxtorjon", "abduqahhor", "vohobjon"}
MALE_TAILS = ("bek", "jon", "boy", "ali", "ullo", "ulloh", "iddin", "uddin", "mirzo", "qul", "xoja", "murod", "shod",
              "dor", "zod", "ur", "yor")
MALE_STARTS = ("muhammad", "mukhammad", "mohammad", "abdu", "abdul", "nur", "mirza")


def _fold(words):
    """The lists above, written the way `search_key` folds names (q→k, x→h, …)."""
    return tuple(dict.fromkeys(search_key(w).replace(" ", "") for w in words))


FEMALE_ENDINGS, MALE_ENDINGS = _fold(FEMALE_ENDINGS), _fold(MALE_ENDINGS)
FEMALE_NAMES, MALE_NAMES = set(_fold(FEMALE_NAMES)), set(_fold(MALE_NAMES))
FEMALE_STARTS, FEMALE_TAILS = _fold(FEMALE_STARTS), _fold(FEMALE_TAILS)
MALE_STARTS, MALE_TAILS = _fold(MALE_STARTS), _fold(MALE_TAILS)


def _word(value):
    return search_key(value).split(" ")[0] if value and search_key(value) else ""


def guess_gender(first_name="", last_name="", patronymic=""):
    """ "male", "female" or "" when the name does not tell."""
    for value in (patronymic, last_name):
        word = search_key(value).replace(" ", "") if value else ""
        if not word:
            continue
        if word.endswith(FEMALE_ENDINGS):
            return "female"
        if word.endswith(MALE_ENDINGS):
            return "male"
    first = _word(first_name)
    if not first:
        return ""
    if first in FEMALE_NAMES:
        return "female"
    if first in MALE_NAMES or first.startswith(MALE_STARTS) or first.endswith(MALE_TAILS):
        return "male"
    if first.startswith(FEMALE_STARTS) or first.endswith(FEMALE_TAILS):
        return "female"
    return ""


def gender_of(user):
    """An account's gender: from the person's own record in their tree, then
    from the account, then from the name."""
    from apps.genealogy.models import Person

    record = Person.objects.filter(pk=user.home_person_id).only("gender").first() if user.home_person_id else None
    return (record.gender if record else "") or user.gender or guess_gender(user.first_name, user.last_name)
