"""
Silai Rahm (oilaviy shajara) — Django settings.

The product language is Uzbek. Two interface languages are supported:
  uz       — Oʻzbekcha (Latin script), the default
  uz-cyrl  — Кириллча (Uzbek Cyrillic), locale directory "uz_Cyrl"
All interface text goes through gettext; see locale/ and apps/core/languages.py.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 (and VERCEL_URL, VERCEL_PROJECT_PRODUCTION_URL) in its functions.
ON_VERCEL = bool(os.environ.get("VERCEL"))

DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_VERCEL else "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me" if DEBUG else "")
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY (see .env.example).")


def _env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
# The site's Vercel addresses: the current one and the one from before the rename (still in use).
PRODUCTION_HOSTS = ["silairahm.vercel.app", "shajara-liard.vercel.app"]
_hosts = [os.environ.get(v, "") for v in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL", "VERCEL_BRANCH_URL")]
for _host in filter(None, _hosts + (PRODUCTION_HOSTS if ON_VERCEL else [])):
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")
# The name of the project (a brand: the same in every language).
SITE_NAME = "Silai Rahm"

# The public address of the site (used in links sent by Telegram and e-mail).
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/") or (
    f"https://{PRODUCTION_HOSTS[0]}" if ON_VERCEL
    else "http://localhost:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.genealogy",
    "apps.friends",
    "apps.network",
    "apps.notify",
    "apps.assistant",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Language from cookie → Accept-Language (Uzbek only) → LANGUAGE_CODE.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # Which family archive the user works in (their own or a shared one).
    "apps.accounts.middleware.ArchiveMiddleware",
    # Accounts created through Google finish their profile (gender) first.
    "apps.accounts.middleware.ProfileCompletionMiddleware",
    # For signed-in users the saved account preference wins (language, time zone).
    "apps.core.middleware.UserLanguageMiddleware",
    "apps.notify.middleware.DailyRemindersMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.notify.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite for local development; set DATABASE_URL=postgres://… for PostgreSQL.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60, conn_health_checks=True
    )
}

# The cache holds single-use sign-in tokens for the macOS app. A database
# cache works across serverless instances; create it with `createcachetable`.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "cache"}}

# Neon's pooled connection (PgBouncer, transaction mode) does not support
# server-side cursors.
if "pooler" in DATABASES["default"].get("HOST", ""):
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# ---------------------------------------------------------------------------
# Sign in with Google (django-allauth). Only the Google login is used from
# allauth; username/password sign-in and registration are the site's own.
# Create an OAuth client at console.cloud.google.com → APIs & Services →
# Credentials, with the redirect URI  https://<domain>/accounts/google/login/callback/
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}]
        if GOOGLE_CLIENT_ID else [],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "uz"
# Plain strings (not gettext_lazy): hosting tools read settings before Django
# is ready. Users see the self-names from apps/core/languages.py instead.
LANGUAGES = [
    ("uz", "Oʻzbekcha (lotin)"),
    ("uz-cyrl", "Ўзбекча (кирилл)"),
    ("ru", "Русский"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
FORMAT_MODULE_PATH = ["config.formats"]
USE_I18N = True
USE_TZ = True
TIME_ZONE = "Asia/Tashkent"
LANGUAGE_COOKIE_NAME = "til"
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365

# ---------------------------------------------------------------------------
# Static and uploaded files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    # Photos are kept in the database: one backup holds everything, and it
    # works on serverless hosting without a disk. See apps/core/storage.py.
    "default": {"BACKEND": "apps.core.storage.DatabaseStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
PHOTO_MAX_BYTES = 12 * 1024 * 1024  # before shrinking; the browser also scales photos down
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Unicode font embedded into every PDF (covers Oʻ Gʻ and Ў Қ Ғ Ҳ).
PDF_FONT_DIR = BASE_DIR / "fonts"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# Telegram reminders (optional): create a bot with @BotFather.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
# Secret in the webhook URL header so only Telegram can call it.
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
# AI assistant (optional): a Google AI Studio key; the free tier is enough.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "") or "gemini-2.5-flash"
# Vercel Cron sends "Authorization: Bearer $CRON_SECRET" to /cron/kunlik/.
CRON_SECRET = os.environ.get("CRON_SECRET", "")
# Web Push (reminders on phones and in browsers): a VAPID key pair.
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
# Who the push services may contact about this sender: the site itself.
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "") or (
    SITE_URL if SITE_URL.startswith("https://") else "mailto:admin@example.com")

SESSION_COOKIE_AGE = 60 * 60 * 24 * 60  # stay signed in for two months

EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "silairahm@localhost")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

if not DEBUG:
    # Behind a reverse proxy (Caddy / nginx) that terminates HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    LANGUAGE_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"
