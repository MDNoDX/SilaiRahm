from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Getting in (views/auth.py)
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("kirish/kod/", views.two_factor, name="two_factor"),
    path("chiqish/", auth_views.LogoutView.as_view(), name="logout"),
    path("royxatdan-otish/", views.register, name="register"),
    path("royxatdan-otish/tasdiqlash/", views.verify_email, name="verify_email"),
    path("profilni-toldirish/", views.complete_profile, name="complete_profile"),
    path("oilangiz/", views.family_start, name="family_start"),
    path("parol/tiklash/", views.password_reset, name="password_reset"),
    path("parol/tiklash/yuborildi/", views.password_reset_done, name="password_reset_done"),
    path("parol/tiklash/<uidb64>/<token>/", views.password_reset_confirm, name="password_reset_confirm"),
    path("parol/tiklash/tayyor/", views.password_reset_complete, name="password_reset_complete"),

    # Settings → General and Your data (views/profile.py)
    path("sozlamalar/", views.settings_view, name="settings"),
    path("sozlamalar/malumotlar/", views.data_view, name="data"),
    path("sozlamalar/hisobni-ochirish/", views.delete_account, name="delete_account"),

    # Settings → Security (views/security.py)
    path("sozlamalar/xavfsizlik/", views.security_view, name="security"),
    path("sozlamalar/xavfsizlik/ikki-bosqich/", views.two_factor_setup, name="two_factor_setup"),
    path("sozlamalar/xavfsizlik/ikki-bosqich/ochirish/", views.two_factor_off, name="two_factor_off"),
    path("sozlamalar/xavfsizlik/ikki-bosqich/kodlar/", views.two_factor_codes, name="two_factor_codes"),
    path("sozlamalar/xavfsizlik/boshqa-qurilmalar/", views.sign_out_others, name="sign_out_others"),
    path("sozlamalar/xavfsizlik/google/uzish/", views.google_disconnect, name="google_disconnect"),

    # Settings → Family members, invitations (views/family.py)
    path("sozlamalar/oila/", views.family_view, name="family"),
    path("sozlamalar/oila/taklif/<int:pk>/bekor/", views.invite_revoke, name="invite_revoke"),
    path("sozlamalar/oila/azo/<int:pk>/", views.member_update, name="member_update"),
    path("sozlamalar/oila/almashish/<int:user_id>/", views.archive_switch, name="archive_switch"),
    path("sozlamalar/oila/chiqish/<int:user_id>/", views.archive_leave, name="archive_leave"),
    path("taklif/men/", views.who_am_i, name="who_am_i"),
    path("taklif/<str:token>/", views.invite_view, name="invite"),
]
