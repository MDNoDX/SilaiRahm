import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.http import HttpResponse, JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import service, telegram
from .forms import NotificationSettingsForm
from .middleware import SESSION_KEY
from .models import Notification, NotificationSettings


@login_required
def notification_list(request):
    items = list(request.user.notifications.all()[:100])
    return render(request, "notify/list.html", {"items": items})


@login_required
def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    if not note.read_at:
        note.read_at = timezone.now()
        note.save(update_fields=["read_at"])
    target = note.url if url_has_allowed_host_and_scheme(note.url, {request.get_host()}) else ""
    return redirect(target or "notify:list")


@login_required
def status(request):
    """Unread reminders for the desktop app (dock badge, system notifications)."""
    from django.db.models import Count, Q

    unread = request.user.notifications.filter(read_at=None)
    counts = unread.aggregate(total=Count("id"), connections=Count("id", filter=Q(kind__in=PEOPLE_KINDS)))
    response = JsonResponse({
        "unread": counts["total"], "connections": counts["connections"],
        "items": [{"id": n.pk, "kind": n.kind, "url": request.build_absolute_uri(reverse("notify:open", args=[n.pk])),
                   **{k: n.text[k] for k in ("title", "body", "icon")}} for n in unread[:20]],
    })
    response["Cache-Control"] = "no-store"
    return response


# Requests and answers between people: they change the Friends page, so it refreshes itself.
PEOPLE_KINDS = ["connection_request", "connection_accepted", "follow_request", "new_follower", "follow_accepted"]


@require_POST
@login_required
def mark_all_read(request):
    request.user.notifications.filter(read_at=None).update(read_at=timezone.now())
    return redirect(request.POST.get("next") or "notify:list")


@login_required
def notification_settings(request):
    prefs = NotificationSettings.for_user(request.user)
    form = NotificationSettingsForm(request.POST or None, instance=prefs)
    if request.method == "POST" and form.is_valid():
        form.save()
        prefs.last_generated = None  # re-check today's reminders with the new choices
        prefs.save(update_fields=["last_generated"])
        request.session.pop(SESSION_KEY, None)
        messages.success(request, _("The information has been saved."))
        return redirect("notify:settings")
    link = {}
    connected = bool(prefs.telegram_enabled and prefs.telegram_chat_id)
    if telegram.configured() and not prefs.telegram_chat_id:
        link = telegram.link_urls(prefs)
        if link:
            link["qr"] = telegram.qr_svg(link["web"])
    return render(request, "notify/settings.html", {
        "form": form, "prefs": prefs, "telegram_available": telegram.configured(), "link": link,
        "connected": connected, "bot": telegram.bot_username() if telegram.configured() else "",
        "vapid_key": settings.VAPID_PUBLIC_KEY if settings.VAPID_PRIVATE_KEY else "",
        "push_devices": request.user.push_subscriptions.count(),
        "settings_tab": "reminders",
    })


@login_required
def telegram_status(request):
    prefs = NotificationSettings.for_user(request.user)
    return JsonResponse({"connected": bool(prefs.telegram_chat_id), "name": prefs.telegram_name})


@require_POST
@login_required
def telegram_connect(request):
    """A fresh code (the old one expired or the user asked for a new one)."""
    prefs = NotificationSettings.for_user(request.user)
    if not telegram.configured() or not telegram.link_urls(prefs, renew=True):
        messages.error(request, _("Telegram reminders are not available at the moment."))
    return redirect(reverse("notify:settings") + "#telegram")


@require_POST
@login_required
def telegram_toggle(request):
    """Pause or resume Telegram messages without unlinking."""
    prefs = NotificationSettings.for_user(request.user)
    if prefs.telegram_chat_id:
        prefs.telegram_enabled = not prefs.telegram_enabled
        prefs.save(update_fields=["telegram_enabled"])
    return redirect(reverse("notify:settings") + "#telegram")


@require_POST
@login_required
def telegram_test(request):
    prefs = NotificationSettings.for_user(request.user)
    if not prefs.telegram_chat_id:
        return redirect("notify:settings")
    try:
        service.test_message(prefs)
        messages.success(request, _("A test message has been sent. Check Telegram."))
    except telegram.TelegramError as exc:
        if exc.forbidden:
            prefs.telegram_enabled = False
            prefs.telegram_chat_id = None
            prefs.save(update_fields=["telegram_enabled", "telegram_chat_id"])
            messages.error(request, _("The bot is blocked in Telegram. Connect it again."))
        else:
            messages.error(request, _("Telegram did not accept the message. Try again later."))
    return redirect(reverse("notify:settings") + "#telegram")


@require_POST
@login_required
def telegram_disconnect(request):
    prefs = NotificationSettings.for_user(request.user)
    prefs.telegram_enabled = False
    prefs.telegram_chat_id = None
    prefs.telegram_name = ""
    prefs.save(update_fields=["telegram_enabled", "telegram_chat_id", "telegram_name"])
    messages.info(request, _("Telegram has been disconnected."))
    return redirect(reverse("notify:settings") + "#telegram")


# ---------------------------------------------------------------------------
# Push notifications in this browser / on this phone
# ---------------------------------------------------------------------------
@require_POST
@login_required
def push_subscribe(request):
    from .models import PushSubscription

    try:
        data = json.loads(request.body.decode())
        endpoint, keys = data["endpoint"], data["keys"]
        p256dh, auth = keys["p256dh"], keys["auth"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({"ok": False}, status=400)
    if not str(endpoint).startswith("https://") or len(endpoint) > 2000:
        return JsonResponse({"ok": False}, status=400)
    PushSubscription.objects.update_or_create(endpoint=endpoint, defaults={
        "user": request.user, "p256dh": p256dh[:200], "auth": auth[:100],
        "device": request.headers.get("User-Agent", "")[:200]})
    return JsonResponse({"ok": True})


@require_POST
@login_required
def push_unsubscribe(request):
    from .models import PushSubscription

    try:
        endpoint = json.loads(request.body.decode()).get("endpoint", "")
    except (ValueError, UnicodeDecodeError, AttributeError):
        endpoint = ""
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required
def push_test(request):
    from . import push

    delivered = push.send_to_user(request.user, {
        "title": settings.SITE_NAME, "body": _("Notifications work on this device."), "url": reverse("notify:settings"),
        "tag": "test"}) if push.configured() else 0
    return JsonResponse({"ok": bool(delivered)})


# ---------------------------------------------------------------------------
# Serverless entry points: Vercel Cron and the Telegram webhook
# ---------------------------------------------------------------------------
@csrf_exempt
def cron_daily(request):
    """Daily job (Vercel Cron sends "Authorization: Bearer <CRON_SECRET>")."""
    secret = settings.CRON_SECRET
    if not secret or not constant_time_compare(request.headers.get("Authorization", ""), f"Bearer {secret}"):
        return HttpResponse(status=401)
    # Runs every hour (Vercel Hobby: 24 daily cron entries, one per hour).
    webhook_fixed = telegram.ensure_webhook()
    created = service.run_daily()
    everyone = request.GET.get("all") == "1"
    sent = service.send_pending_telegram(ignore_hour=everyone)
    pushed = service.send_pending_push(ignore_hour=everyone)
    backups = service.weekly_backup()
    return JsonResponse({"created": created, "telegram_sent": sent, "push_sent": pushed, "backups": backups,
                         "webhook_fixed": webhook_fixed})


@csrf_exempt
@require_POST
def telegram_webhook(request):
    if not telegram.configured():
        return HttpResponse(status=404)
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not constant_time_compare(token, telegram.webhook_secret()):
        return HttpResponse(status=403)
    try:
        update = json.loads(request.body.decode())
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)
    telegram.handle_update(update)
    return JsonResponse({"ok": True})
