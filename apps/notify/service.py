"""Creating reminders for a day and delivering them to Telegram."""
import datetime
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone, translation
from django.utils.html import escape
from django.utils.translation import gettext as _

from apps.core.dates import format_date
from apps.core.languages import normalize_language
from apps.core.timezones import zone

from . import telegram
from .messages import render_parts, telegram_text
from .models import Notification, NotificationSettings
from .occasions import occasions

log = logging.getLogger(__name__)


def user_today(user):
    """Today in the user's own time zone."""
    return timezone.localdate(timezone=zone(getattr(user, "time_zone", None)))


def generate(user, today=None):
    """Create today's reminders for `user` (safe to call many times a day)."""
    today = today or user_today(user)
    prefs = NotificationSettings.for_user(user)
    created = 0
    if prefs.enabled:
        lead = prefs.days_before
        for o in occasions(user.archive_owner, today, today + datetime.timedelta(days=lead), prefs):
            days_left = (o.date - today).days
            if days_left not in (0, lead):
                continue
            _obj, new = Notification.objects.get_or_create(
                user=user, key=f"{o.key}:{days_left}",
                defaults={"kind": o.kind, "params": {**o.params, "days_left": days_left},
                          "url": o.url, "occasion_date": o.date},
            )
            created += new
    if prefs.last_generated != today:
        prefs.last_generated = today
        prefs.save(update_fields=["last_generated"])
    return created


def ensure_today(user):
    """Called on page views: generate once per day without a background worker."""
    prefs = NotificationSettings.for_user(user)
    if prefs.last_generated != user_today(user):
        generate(user)


def send_pending(prefs, now=None, ignore_hour=False):
    """Send one user's unsent reminders of today and yesterday to Telegram."""
    if not (telegram.configured() and prefs.enabled and prefs.telegram_enabled and prefs.telegram_chat_id):
        return 0
    now = timezone.localtime(now or timezone.now(), zone(prefs.user.time_zone))
    if not ignore_hour and now.hour < prefs.send_hour:
        return 0
    pending = Notification.objects.filter(user=prefs.user, telegram_sent_at=None,
                                          created_at__date__gte=now.date() - datetime.timedelta(days=1))
    lang = normalize_language(prefs.user.preferred_language) or settings.LANGUAGE_CODE
    sent = 0
    for n in pending.order_by("occasion_date", "id"):
        with translation.override(lang):
            text = telegram_text(n)
        try:
            telegram.send_message(prefs.telegram_chat_id, text)
        except telegram.TelegramError as exc:
            log.warning("Telegram send failed for user %s: %s", prefs.user_id, exc)
            if exc.forbidden:  # the user blocked the bot
                prefs.telegram_enabled = False
                prefs.save(update_fields=["telegram_enabled"])
            break
        n.telegram_sent_at = timezone.now()
        n.save(update_fields=["telegram_sent_at"])
        sent += 1
    return sent


def send_pending_telegram(now=None, ignore_hour=False):
    """Send due reminders to everyone who linked Telegram (called every hour)."""
    if not telegram.configured():
        return 0
    return sum(send_pending(prefs, now, ignore_hour) for prefs in NotificationSettings.objects.filter(
        enabled=True, telegram_enabled=True).exclude(telegram_chat_id=None).select_related("user"))


def send_pending_push(now=None, ignore_hour=False):
    """Send due reminders as push notifications to subscribed browsers and phones."""
    from . import push
    from .messages import render
    from .models import PushSubscription

    if not push.configured():
        return 0
    sent = 0
    users = get_user_model().objects.filter(pk__in=PushSubscription.objects.values("user"), is_active=True)
    for user in users:
        prefs = NotificationSettings.for_user(user)
        local = timezone.localtime(now or timezone.now(), zone(user.time_zone))
        if not prefs.enabled or (not ignore_hour and local.hour < prefs.send_hour):
            continue
        pending = Notification.objects.filter(user=user, push_sent_at=None,
                                              created_at__date__gte=local.date() - datetime.timedelta(days=1))
        lang = normalize_language(user.preferred_language) or settings.LANGUAGE_CODE
        for n in pending.order_by("occasion_date", "id"):
            with translation.override(lang):
                parts = render(n)
            push.send_to_user(user, {"title": f"{parts['icon']} {parts['title']}", "body": parts["body"],
                                     "url": n.url or "/", "tag": f"n{n.pk}"})
            n.push_sent_at = timezone.now()
            n.save(update_fields=["push_sent_at"])
            sent += 1
    return sent


def deliver_now(notification):
    """Send one notification to Telegram and to phones straight away (a
    request from a relative should not wait for the morning reminders)."""
    from . import push
    from .messages import render

    user = notification.user
    prefs = NotificationSettings.for_user(user)
    lang = normalize_language(user.preferred_language) or settings.LANGUAGE_CODE
    now = timezone.now()
    if telegram.configured() and prefs.telegram_enabled and prefs.telegram_chat_id:
        with translation.override(lang):
            text = telegram_text(notification)
        try:
            telegram.send_message(prefs.telegram_chat_id, text)
            notification.telegram_sent_at = now
        except telegram.TelegramError as exc:
            log.warning("Telegram send failed for user %s: %s", user.pk, exc)
    if push.configured():
        with translation.override(lang):
            parts = render(notification)
        push.send_to_user(user, {"title": f"{parts['icon']} {parts['title']}", "body": parts["body"],
                                 "url": notification.url or "/", "tag": f"n{notification.pk}"})
    notification.push_sent_at = now  # nothing is left for the hourly job either way
    notification.telegram_sent_at = notification.telegram_sent_at or now
    notification.save(update_fields=["telegram_sent_at", "push_sent_at"])


BACKUP_LIMIT = 45 * 1024 * 1024  # Telegram bots may upload 50 MB


def send_backup(prefs):
    """Send the whole database (gzip) to an administrator's Telegram."""
    from apps.core import backup

    data = backup.dump_gzip()
    with translation.override(normalize_language(prefs.user.preferred_language) or settings.LANGUAGE_CODE):
        if len(data) > BACKUP_LIMIT:
            telegram.send_message(prefs.telegram_chat_id, escape(_(
                "The weekly backup is too large for Telegram. Download it from the Control panel.")))
            return False
        caption = _("Weekly backup of Silai Rahm. Keep this file: it restores the whole site.")
    telegram.send_document(prefs.telegram_chat_id, backup.filename("json.gz"), data, caption)
    return True


def weekly_backup(now=None):
    """Once a week (on the first run of the week) send the backup to the
    administrators who asked for it. Returns how many were sent."""
    from .models import BotState

    if not telegram.configured():
        return 0
    now = timezone.localtime(now or timezone.now())
    week = "{}-W{:02d}".format(*now.isocalendar()[:2])
    if BotState.get("backup_week") == week:
        return 0
    recipients = NotificationSettings.objects.filter(
        backup_telegram=True, user__is_superuser=True).exclude(telegram_chat_id=None).select_related("user")
    sent = 0
    for prefs in recipients:
        try:
            sent += bool(send_backup(prefs))
        except telegram.TelegramError as exc:
            log.warning("Backup to Telegram failed for user %s: %s", prefs.user_id, exc)
    if recipients:
        BotState.put("backup_week", week)
    return sent


def upcoming_text(user, days=30, limit=12):
    """Telegram message with the next dates (for /next and after connecting)."""
    today = user_today(user)
    items = occasions(user.archive_owner, today, today + datetime.timedelta(days=days))[:limit]
    if not items:
        return escape(_("No dates in the next %(days)d days.") % {"days": days})
    lines = [f"<b>{escape(_('Upcoming dates'))}</b>"]
    for o in items:
        parts = render_parts(o.kind, o.params, (o.date - today).days)
        lines.append(f"{parts['icon']} {escape(format_date(o.date))} — {escape(parts['title'])}")
    return "\n".join(lines)


def test_message(prefs):
    with translation.override(normalize_language(prefs.user.preferred_language) or settings.LANGUAGE_CODE):
        text = "✅ " + escape(_("Test message: Telegram reminders work.")) + "\n\n" + upcoming_text(prefs.user)
    telegram.send_message(prefs.telegram_chat_id, text)


def run_daily(today=None):
    total = 0
    for user in get_user_model().objects.filter(is_active=True):
        total += generate(user, today)
    return total
