import datetime

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.utils.http import content_disposition_header, url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.muchal import current_cycle_year, muchal
from apps.genealogy.kinship import Archive
from apps.notify.messages import render_parts
from apps.notify.occasions import occasions

from .dates import format_date
from .languages import normalize_language


def home(request):
    if not request.user.is_authenticated:
        return render(request, "core/landing.html")
    from urllib.parse import quote

    from apps.genealogy.access import viewer_person
    from apps.genealogy.models import Change
    from apps.network.models import Connection

    user, owner = request.user, request.archive
    archive = Archive(owner)
    focus = viewer_person(request, archive)
    today = timezone.localdate()
    upcoming = [(o, render_parts(o.kind, o.params, (o.date - today).days), (o.date - today).days)
                for o in occasions(owner, today, today + datetime.timedelta(days=30), archive=archive)]
    todays = []
    for o, text, days in upcoming:
        if days:
            continue
        person = archive.people.get(o.person) if o.person else None
        greeting = ""
        if o.kind in ("birthday", "friend_birthday"):
            greeting = _("Happy birthday, {name}! Wishing you health, happiness and every success.").format(
                name=(person.first_name if person else o.params.get("name", "")))
        elif o.kind == "anniversary":
            greeting = _("Congratulations on your wedding anniversary! Wishing you many happy years together.")
        todays.append({"occasion": o, "text": text, "person": person, "greeting": greeting,
                       "share": "tg://msg?text=" + quote(greeting) if greeting else ""})
    generations = len(set(archive.generations(focus).values())) if focus else 0
    return render(request, "core/dashboard.html", {
        "people_count": len(archive.people),
        "friends_count": owner.contacts.count(),
        "events_count": owner.events.count(),
        "stories_count": owner.stories.count(),
        "generations": generations,
        "me": archive.people.get(focus),
        "today_items": todays,
        "today_label": format_date(today),
        "soon": [row for row in upcoming if row[2]][:6],
        "changes": Change.objects.filter(owner=owner).select_related("actor", "person")[:6],
        "cycle_animal": muchal(current_cycle_year(), 6, 1),
        "connection_requests": list(Connection.objects.filter(recipient=user, status=Connection.Status.PENDING)
                                    .select_related("sender")[:5]),
    })


@require_POST
def set_language(request):
    """Switch the interface language; saved on the account when signed in."""
    code = normalize_language(request.POST.get("language"))
    next_url = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        next_url = "/"
    response = redirect(next_url)
    if not code:
        return response
    if request.user.is_authenticated and request.user.preferred_language != code:
        request.user.preferred_language = code
        request.user.save(update_fields=["preferred_language"])
    translation.activate(code)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, code, max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax",
        secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
    )
    return response


def media(request, name):
    """Serve a photo or album file from the database storage — only to the
    owner of the archive it belongs to and to the members of that archive."""
    from django.http import Http404, HttpResponse
    from django.utils.http import http_date

    from apps.genealogy.access import can_view
    from apps.genealogy.models import Media, Person

    from .models import StoredFile

    if not request.user.is_authenticated:
        raise Http404
    holder = (Person.objects.filter(photo=name).select_related("owner").first()
              or Media.objects.filter(file=name).select_related("owner").first())
    if holder is None or not can_view(request.user, holder.owner):
        raise Http404
    obj = None
    if request.GET.get("s") == "t":  # the small copy for avatars and cards, made once
        from .images import thumbnail
        from .storage import thumb_name

        obj = StoredFile.objects.filter(name=thumb_name(name)).first()
        if obj is None:
            original = StoredFile.objects.filter(name=name).first()
            small = thumbnail(bytes(original.content)) if original and original.content_type.startswith("image/") else None
            if small is not None:
                obj, _created = StoredFile.objects.update_or_create(
                    name=thumb_name(name), defaults={"content": small, "size": len(small), "content_type": "image/jpeg"})
    obj = obj or StoredFile.objects.filter(name=name).first()
    if obj is None:
        raise Http404
    response = HttpResponse(bytes(obj.content), content_type=obj.content_type)
    response["Cache-Control"] = "private, max-age=31536000, immutable"  # names are unique (uuid)
    response["Last-Modified"] = http_date(obj.created_at.timestamp())
    response["X-Content-Type-Options"] = "nosniff"
    return response


def service_worker(request):
    """The service worker must be served from the site root to control every page."""
    response = render(request, "pwa/sw.js", content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def offline(request):
    """What the service worker shows when there is no connection. The page is
    kept on the device, so it carries nothing about who is signed in."""
    request.user = AnonymousUser()
    return render(request, "pwa/offline.html")


def health(request):
    """For the load balancer / container health check."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


def csrf_failure(request, reason=""):
    return render(request, "errors/403_csrf.html", status=403)


def bad_request(request, exception=None):
    return render(request, "errors/400.html", status=400)


def permission_denied(request, exception=None):
    message = str(exception) if exception and str(exception) else ""
    return render(request, "errors/403.html", {"message": message}, status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)


# ---------------------------------------------------------------------------
# Site administration (superusers only)
# ---------------------------------------------------------------------------
def _superuser(user):
    return user.is_active and user.is_superuser


def _count_memberships():
    from apps.accounts.models import Membership

    return Membership.objects.count()


@user_passes_test(_superuser)
def control_panel(request):
    from django.contrib.auth import get_user_model
    from django.db.models import Sum

    from apps.friends.models import Contact
    from apps.genealogy.models import Event, Person, Story
    from apps.notify import telegram
    from apps.notify.models import Notification, NotificationSettings

    from .models import StoredFile

    webhook, bot = None, {}
    if telegram.configured():
        bot = telegram.bot_info()
        try:
            webhook = telegram.webhook_info()
            webhook["ok"] = webhook.get("url") == telegram.webhook_url()
        except telegram.TelegramError as exc:
            webhook = {"error": str(exc)}
    users = get_user_model().objects
    return render(request, "core/control_panel.html", {
        "stats": [
            (_("Users"), users.count()),
            (_("People in all trees"), Person.objects.count()),
            (_("Events"), Event.objects.count()),
            (_("Stories"), Story.objects.count()),
            (_("Friends"), Contact.objects.count()),
            (_("Photos"), StoredFile.objects.count()),
            (_("Notifications"), Notification.objects.count()),
            (_("Telegram connected"), NotificationSettings.objects.filter(telegram_enabled=True).count()),
        ],
        "photo_mb": round((StoredFile.objects.aggregate(s=Sum("size"))["s"] or 0) / 1024 / 1024, 1),
        "recent_users": users.order_by("-date_joined")[:10],
        "telegram": telegram.configured(), "webhook": webhook, "bot": bot, "cron": bool(settings.CRON_SECRET),
        "google": bool(settings.GOOGLE_CLIENT_ID), "site_url": settings.SITE_URL,
        "push": bool(settings.VAPID_PRIVATE_KEY),
        "my_prefs": NotificationSettings.for_user(request.user),
        "members_count": _count_memberships(),
    })


@user_passes_test(_superuser)
def full_backup(request):
    """The whole database as JSON (for `manage.py loaddata` on any server)."""
    from . import backup

    response = HttpResponse(backup.dump_json(), content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(True, backup.filename())
    return response


@require_POST
@user_passes_test(_superuser)
def backup_telegram(request):
    """Turn the weekly backup to my Telegram on or off, or send one now."""
    from django.contrib import messages

    from apps.notify import service, telegram
    from apps.notify.models import NotificationSettings

    prefs = NotificationSettings.for_user(request.user)
    if not prefs.telegram_chat_id:
        messages.error(request, _("Connect Telegram first: Settings → Reminders."))
    elif "now" in request.POST:
        try:
            if service.send_backup(prefs):
                messages.success(request, _("The backup has been sent to your Telegram."))
            else:
                messages.error(request, _("The backup is too large for Telegram. Download it here instead."))
        except telegram.TelegramError as exc:
            messages.error(request, str(exc))
    else:
        prefs.backup_telegram = not prefs.backup_telegram
        prefs.save(update_fields=["backup_telegram"])
        messages.success(request, _("The information has been saved."))
    return redirect("control_panel")


@require_POST
@user_passes_test(_superuser)
def set_telegram_webhook(request):
    from django.contrib import messages

    from apps.notify import telegram

    try:
        telegram.bot_info(refresh=True)
        telegram.set_webhook()
        telegram.set_commands()
        messages.success(request, _("The Telegram bot is connected to the site."))
    except telegram.TelegramError as exc:
        messages.error(request, str(exc))
    return redirect("control_panel")
