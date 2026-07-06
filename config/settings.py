"""
Django settings for the ClassProject group-formation app.

Configuration comes from environment variables (or the git-ignored `.env` file
locally), so the same code runs on a dev PC and on Azure App Service.
See SPEC.md §7 and `.env.example`.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

# The default below is for local development only — Azure must set SECRET_KEY
# as an App Service application setting (Milestone 6).
SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key-not-for-production")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Production hardening (SPEC §7) — active whenever DEBUG is off.
if not DEBUG:
    # App Service's front end terminates HTTPS and forwards plain HTTP to
    # gunicorn with this header — Django's equivalent of ASP.NET Core's
    # ForwardedHeaders middleware. Without it, is_secure() is always False
    # and the redirect below would loop forever.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True          # http:// → https://
    SESSION_COOKIE_SECURE = True        # cookies only over HTTPS
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days; raise once stable
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "anymail",  # SendGrid email backend (SPEC §6)
    # Project apps
    "accounts",
    "projects",
    "reports",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "reports.context_processors.current_project",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database — local dev uses SQLite; Azure sets DATABASE_URL=postgres://...
# as an app setting (SPEC §1, §7).

if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"]["CONN_MAX_AGE"] = 60
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Authentication — custom email-login user (SPEC §3.1)

AUTH_USER_MODEL = "accounts.User"

# The default ModelBackend makes unverified (inactive) accounts fail exactly
# like a wrong password. This variant lets the login form see the user and
# show "account not verified yet" instead (SPEC §3.1); the form still blocks
# the actual sign-in.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.AllowAllUsersModelBackend"]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Shanghai"  # class runs on UTC+8 (SPEC §8)

USE_I18N = True

USE_TZ = True


# Static files — served by WhiteNoise in production (SPEC §1)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)  # WhiteNoise warns if the directory is absent

if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }


# Bonus-score curve for the stats card (SPEC §3.4) — tunable without code
# changes: set BONUS_MAX etc. as environment variables / app settings.

BONUS_SCORE = {
    "max": env.int("BONUS_MAX", default=20),
    "min": env.int("BONUS_MIN", default=3),
    "midpoint": env.int("BONUS_MIDPOINT", default=12),
    "steepness": env.float("BONUS_STEEPNESS", default=2.5),
}


# Email (SPEC §6) — SendGrid via Anymail when SENDGRID_API_KEY is set
# (production); otherwise emails print to the runserver console (local dev).

SENDGRID_API_KEY = env("SENDGRID_API_KEY", default="")
if SENDGRID_API_KEY:
    EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
    ANYMAIL = {"SENDGRID_API_KEY": SENDGRID_API_KEY}
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="ClassProject <no-reply@example.com>")

# Notifications (SPEC §6). ADMINS feeds Django's mail_admins() — the instructor
# address that hears about new users, new projects and fulfilled projects.
# Leave ADMIN_EMAIL unset to turn admin notifications off (mail_admins is a
# no-op with an empty ADMINS list).
ADMIN_EMAIL = env("ADMIN_EMAIL", default="")
ADMINS = [("Site admin", ADMIN_EMAIL)] if ADMIN_EMAIL else []
SERVER_EMAIL = DEFAULT_FROM_EMAIL  # mail_admins' From: — must be a verified SendGrid sender
EMAIL_SUBJECT_PREFIX = "[ClassProject] "

# Absolute base URL for links inside notification emails, which are sent from
# the service layer where no HttpRequest is available to build one from.
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
