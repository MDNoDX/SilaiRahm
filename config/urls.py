from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.accounts import app_bridge
from apps.core import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("til/", core_views.set_language, name="set_language"),
    # Translations for static/js, from locale/*/LC_MESSAGES/djangojs.po.
    path("", include("apps.accounts.urls")),
    path("", include("apps.genealogy.urls")),
    path("dostlar/", include("apps.friends.urls")),
    path("boglanishlar/", include("apps.network.urls")),
    path("", include("apps.notify.urls")),
    path("salomatlik/", core_views.health, name="health"),
    path("media/<path:name>", core_views.media, name="media"),
    # Google sign-in (allauth). Its own login/signup pages point to the site's.
    path("accounts/login/", RedirectView.as_view(pattern_name="accounts:login", query_string=True)),
    path("accounts/signup/", RedirectView.as_view(pattern_name="accounts:register", query_string=True)),
    path("accounts/logout/", RedirectView.as_view(pattern_name="accounts:logout")),
    path("accounts/", include("allauth.urls")),
    path("ilova/kirish/boshlash/", app_bridge.start, name="app_login_start"),
    path("ilova/kirish/tugatish/", app_bridge.finish, name="app_login_finish"),
    path("ilova/kirish/", app_bridge.consume, name="app_login"),
    path("boshqaruv/", core_views.control_panel, name="control_panel"),
    path("boshqaruv/zaxira.json", core_views.full_backup, name="full_backup"),
    path("boshqaruv/telegram/", core_views.set_telegram_webhook, name="set_telegram_webhook"),
    path("boshqaruv/zaxira/telegram/", core_views.backup_telegram, name="backup_telegram"),
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("oflayn/", core_views.offline, name="offline"),
    path("admin/", admin.site.urls),
]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"

