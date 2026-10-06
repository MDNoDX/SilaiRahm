from .service import ensure_today, user_today

SESSION_KEY = "reminders_day"


class DailyRemindersMiddleware:
    """Creates the day's reminders on a user's first visit of the day, so the
    bell works even where no background worker runs. The session remembers
    the day, so later page views do not ask the database again."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and request.method == "GET":
            today = user_today(user).isoformat()
            if request.session.get(SESSION_KEY) != today:
                ensure_today(user)
                request.session[SESSION_KEY] = today
        return self.get_response(request)
