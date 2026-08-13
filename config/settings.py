"""Django settings for HireHorizon.

Everything environment-specific is read from the environment (optionally via a
.env file) so the same code runs on a phone under Termux and on a real host.
The app is deliberately text-only: there is no media/upload configuration and
no SMTP backend anywhere.
"""

from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Read a boolean from the environment. Accepts 1/true/yes/on."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    """Read a comma-separated list, dropping blanks."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# SECURITY
# A generated fallback keeps the app runnable with no .env at all; sessions
# reset on restart until SECRET_KEY is set. Refuse to do that with DEBUG off,
# because in production it silently logs everybody out on every deploy.
SECRET_KEY = os.getenv("SECRET_KEY", "")
DEBUG = env_bool("DEBUG", True)

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-dev-only-" + os.urandom(16).hex()
    else:
        raise RuntimeError(
            "SECRET_KEY must be set when DEBUG=False. "
            "Generate one with: python manage.py generate_secret_key"
        )

# Termux serves on the LAN, so the phone's IP has to be allowed. Defaults are
# permissive for local use only; set ALLOWED_HOSTS explicitly in production.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"] if DEBUG else []

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "apps.accounts",
    "apps.blog",
    "apps.messaging",
    "apps.notifications",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.notifications.context_processors.notification_badge",
                "apps.core.context_processors.rail_content",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASE
# DATABASE_URL wins when set (postgres://... on a host); otherwise SQLite in
# the project directory, which is what Termux uses.
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# STATIC FILES
# WhiteNoise serves them with DEBUG=False, so the app works on Termux without
# a separate web server in front.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# No MEDIA_ROOT / MEDIA_URL on purpose: HireHorizon is text-only and accepts no
# uploads, so there is no upload directory to serve or secure.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# EMAIL
# SMTP has been removed. The contact form writes to the database instead. This
# backend discards anything Django itself might try to send so that no code
# path can block on a mail server.
EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

# SECURITY HEADERS
# Only the ones that are safe over plain HTTP are unconditional; the HTTPS-only
# ones are opt-in so they cannot break local Termux testing over http://.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Set HTTPS_ENABLED=True only when the site is actually served over TLS.
# Turning these on over plain HTTP makes the site unreachable.
HTTPS_ENABLED = env_bool("HTTPS_ENABLED", False)
if HTTPS_ENABLED:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Pagination size used across feeds, profiles and search.
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "20"))

# File-based rather than Django's default LocMemCache: LocMemCache is
# per-process, so under gunicorn's multiple workers (tunnel.sh runs two)
# each worker would hand out its own separate rate-limit quota instead of
# sharing one. A shared file on disk fixes that without adding a dependency
# like Redis. Used by apps/core/ratelimit.py for login/register/contact.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / ".django_cache",
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
