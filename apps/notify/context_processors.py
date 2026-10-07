from django.db.models import Count, Q


def notifications(request):
    """Unread notifications for the menu, and how many of them are connection requests (one query)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    counts = user.notifications.filter(read_at=None).aggregate(
        total=Count("id"), connections=Count("id", filter=Q(kind__in=["connection_request", "follow_request"])))
    return {"unread_count": counts["total"], "unread_connections": counts["connections"]}
