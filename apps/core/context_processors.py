from django.conf import settings
from django.utils.translation import get_language

from .languages import CYRILLIC_SCRIPT, HTML_LANG, LANGUAGE_LABELS, LANGUAGE_SHORT, language_options, normalize_language


# Which menu item a page belongs to: exact page names, never parts of them
# ("friends:create" must not light up "person_create").
NAV_SECTIONS = {
    "home": {"home"},
    "tree": {"genealogy:tree", "genealogy:tree_for", "genealogy:book"},
    "people": {"genealogy:people", "genealogy:person", "genealogy:person_edit", "genealogy:person_create",
               "genealogy:relative_add", "genealogy:marriage_edit", "genealogy:search", "genealogy:duplicates",
               "genealogy:person_delete"},
    "events": {"genealogy:upcoming", "genealogy:event", "genealogy:event_create", "genealogy:event_edit",
               "genealogy:event_delete"},
    "timeline": {"genealogy:timeline"},
    "friends": {"friends:list", "friends:create", "friends:edit", "friends:delete", "network:index",
                "network:request", "network:answer", "network:connection", "network:profile", "network:merge"},
    "calculator": {"genealogy:calculator"},
    "assistant": {"assistant:chat"},
    "notifications": {"notify:list"},
    "history": {"genealogy:history"},
}
PAGE_SECTION = {page: section for section, pages in NAV_SECTIONS.items() for page in pages}


def site(request):
    current = normalize_language(get_language()) or settings.LANGUAGE_CODE
    context = {
        "current_language": current,
        "current_language_label": LANGUAGE_LABELS[current],
        "current_language_short": LANGUAGE_SHORT[current],
        "html_lang": HTML_LANG.get(current, "uz"),
        "is_cyrillic": current in CYRILLIC_SCRIPT,
        "language_options": language_options(current),
        "google_login": bool(settings.GOOGLE_CLIENT_ID),
        "ai_ready": bool(settings.GEMINI_API_KEY),
        "brand_name": settings.SITE_NAME,
        "nav": PAGE_SECTION.get(getattr(getattr(request, "resolver_match", None), "view_name", None), ""),
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from apps.accounts.sharing import archives_of

        context["archive"] = getattr(request, "archive", user)
        context["can_edit"] = getattr(request, "can_edit", True)
        context["shared_archives"] = archives_of(user)
    return context
