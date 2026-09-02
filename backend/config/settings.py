"""
Django settings for the SRMS scholarship system.

Everything that differs between a laptop and the deployed site is read from the
environment, so this file is safe to commit and the same code runs in both
places. Copy .env.example to .env for local work; on Render the same keys are
set as environment variables in the dashboard.

The defaults are the *production* ones. A missing variable degrades toward the
safe choice (DEBUG off, HTTPS enforced) rather than the convenient one, so a
forgotten setting can never quietly ship an insecure site.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Local development reads .env; on Render the variables are already in the
# environment and this call finds nothing, which is fine.
load_dotenv(BASE_DIR / '.env')


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# ── Core ──────────────────────────────────────────────────────────────────────

DEBUG = _env_bool('DEBUG', False)

SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        # Development only. Sessions reset whenever this process restarts, which
        # is the correct trade for never having a real key sitting in the repo.
        SECRET_KEY = 'django-insecure-local-development-only-do-not-deploy'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY must be set when DEBUG is off. Generate one with:\n'
            '  python -c "from django.core.management.utils import get_random_secret_key;'
            ' print(get_random_secret_key())"'
        )

# Render injects RENDER_EXTERNAL_HOSTNAME with the service's own domain, so the
# site works on first deploy before a custom domain is pointed at it.
ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
# Appended rather than assumed: naming the host in ALLOWED_HOSTS too is the
# normal thing to do once a custom domain exists, and that should not produce
# a duplicate entry.
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

# Django 4+ requires the scheme here, unlike ALLOWED_HOSTS.
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')
if _render_host:
    _render_origin = f'https://{_render_host}'
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)

# What a failed CSRF check shows. Django's own answer is "Forbidden (403). CSRF
# verification failed. Request aborted. More information is available with
# DEBUG=True" — an accusation, plus advice only a developer can act on. In
# practice the cause is a form left open past the session's life or a browser
# refusing cookies, so api/error_views.py says that instead.
CSRF_FAILURE_VIEW = 'api.error_views.csrf_failure'


# ── Applications ──────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'storages',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Serves the collectstatic output in production. Must sit directly after
    # SecurityMiddleware and before everything else.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # After AuthenticationMiddleware: it reads request.user to decide whether a
    # just-registered visitor still needs letting in.
    'api.middleware.ReleaseVerifiedAccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# The document viewer frames uploaded files (proofs, certificates, appointment
# papers) from our own /media/. Django's default of DENY blocks that even for
# same-origin frames; SAMEORIGIN still keeps other sites from framing us.
X_FRAME_OPTIONS = 'SAMEORIGIN'

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'api.context_processors.system_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ── Database ──────────────────────────────────────────────────────────────────
# Supabase offers two hosts, and only one of them works from Render.
#
#   db.<ref>.supabase.co          the "direct connection". Resolves to an AAAA
#                                 record only — no IPv4. Render's free tier has
#                                 no IPv6 egress, so this host cannot be reached
#                                 at all; it fails at connect time, which reads
#                                 like a credentials problem but is not one.
#
#   aws-0-<region>.pooler.supabase.com    the pooler (Supavisor). IPv4. Use this.
#
# The pooler answers on two ports and the choice matters for Django:
#
#   5432  session mode — a connection behaves like a normal Postgres session.
#         Prepared statements and conn_max_age below both work. Use this.
#   6543  transaction mode — a connection is handed back after every statement.
#         More efficient, but psycopg3's prepared statements collide on it
#         ("prepared statement already exists") and holding connections open
#         via conn_max_age just occupies pooler slots. Only worth it with
#         conn_max_age=0 and prepared statements disabled.
#
# Falls back to SQLite so a fresh clone runs without any database set up.

# Two ways to say the same thing. DATABASE_URL is what Render and Supabase both
# hand you, so it is tried first — but a URL has to carry the password through
# its userinfo field, and a password containing @ # ? / : % (Supabase generates
# some of these) has to be percent-encoded or the string stops being a valid URL
# at all. That failure is opaque, so PGHOST/PGUSER/... is offered as a way to
# supply the same details with no quoting rules to get wrong.

DATABASE_URL = os.environ.get('DATABASE_URL', '')
PGHOST = os.environ.get('PGHOST', '')


def _database_from_url(url):
    try:
        return dj_database_url.parse(
            url, conn_max_age=600, conn_health_checks=True, ssl_require=not DEBUG,
        )
    except Exception as exc:
        # dj_database_url raises ParseError without saying which part offended,
        # which turns a five-second fix into a whole deploy cycle. Only these
        # characters actually break the parse; '@', ':' and '%' in a password
        # are fine, so naming them would send people chasing the wrong thing.
        hint = ''
        if '[' in url or ']' in url:
            hint = ("\n  It still contains '[' or ']'. Those are the dashboard's "
                    "placeholder brackets: replace the whole of [YOUR-PASSWORD], "
                    "brackets included, with the password itself.")
        else:
            offenders = [c for c in '#/?' if c in url.rpartition('@')[0]]
            if offenders:
                enc = {'#': '%23', '/': '%2F', '?': '%3F'}
                shown = ', '.join(f"{c} -> {enc[c]}" for c in offenders)
                hint = (f"\n  The password contains {shown}. Percent-encode it, "
                        "or use the PG* variables below and skip encoding.")
        raise ImproperlyConfigured(
            f'DATABASE_URL could not be parsed ({exc.__class__.__name__}).{hint}\n'
            '  Expected: postgresql://USER:PASSWORD@HOST:5432/postgres\n'
            '  Alternatively set PGHOST, PGUSER, PGPASSWORD, PGDATABASE and '
            'PGPORT, which have no quoting rules at all.'
        ) from None


if DATABASE_URL:
    DATABASES = {'default': _database_from_url(DATABASE_URL)}
elif PGHOST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': PGHOST,
            'PORT': os.environ.get('PGPORT', '5432'),
            'NAME': os.environ.get('PGDATABASE', 'postgres'),
            'USER': os.environ.get('PGUSER', 'postgres'),
            'PASSWORD': os.environ.get('PGPASSWORD', ''),
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {} if DEBUG else {'sslmode': 'require'},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ── Authentication ────────────────────────────────────────────────────────────

AUTH_USER_MODEL = 'api.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── Internationalization ──────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True


# ── Static files ──────────────────────────────────────────────────────────────

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# collectstatic writes here at build time; WhiteNoise serves it at runtime.
STATIC_ROOT = BASE_DIR / 'staticfiles'


# ── Uploaded files ────────────────────────────────────────────────────────────
# Every upload is a student document, so none of it is served by a plain file
# handler — see api.media_views, wired at /media/ in config.urls.
#
# Render's free tier has no persistent disk: anything written to the container
# is gone on the next deploy. Setting USE_SUPABASE_STORAGE moves uploads to
# Supabase Storage, which speaks the S3 API, so they outlive the container.

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_SUPABASE_STORAGE = _env_bool('USE_SUPABASE_STORAGE', False)

if USE_SUPABASE_STORAGE:
    _required = ['SUPABASE_S3_ENDPOINT', 'SUPABASE_S3_REGION',
                 'SUPABASE_S3_ACCESS_KEY_ID', 'SUPABASE_S3_SECRET_ACCESS_KEY',
                 'SUPABASE_STORAGE_BUCKET']
    _missing = [name for name in _required if not os.environ.get(name)]
    if _missing:
        raise ImproperlyConfigured(
            'USE_SUPABASE_STORAGE is on but these are unset: ' + ', '.join(_missing)
        )
    _media_backend = {
        # Not storages.backends.s3.S3Storage directly: that one hands templates
        # the bucket's own URL, which never passes through api.media_views and
        # so answers nobody's question about who is asking. See api/storage.py.
        'BACKEND': 'api.storage.ProtectedS3Storage',
        'OPTIONS': {
            'endpoint_url': os.environ['SUPABASE_S3_ENDPOINT'],
            'region_name': os.environ['SUPABASE_S3_REGION'],
            'access_key': os.environ['SUPABASE_S3_ACCESS_KEY_ID'],
            'secret_key': os.environ['SUPABASE_S3_SECRET_ACCESS_KEY'],
            'bucket_name': os.environ['SUPABASE_STORAGE_BUCKET'],
            # The bucket stays private. Files reach the browser only through
            # api.media_views, which checks who is asking first.
            'default_acl': None,
            'querystring_auth': False,
            'file_overwrite': False,
            'signature_version': 's3v4',
            'addressing_style': 'path',
        },
    }
else:
    _media_backend = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}

STORAGES = {
    'default': _media_backend,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Uploads above this size stream to a temp file instead of being held in memory.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024      # 5 MB
# Ceiling on a whole non-file POST body, so a form cannot exhaust memory.
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024     # 15 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000               # masterlist forms are wide

# Largest single upload accepted, enforced in api.validators.
MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', '10'))


# ── Security ──────────────────────────────────────────────────────────────────
# Only applied off DEBUG, so local http://127.0.0.1 keeps working.

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', True)
    # Render terminates TLS at its proxy; without this Django believes every
    # request arrived over plain http and the SSL redirect loops forever.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    # Offices open student documents from links inside the app only.
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

    # Start at one hour. Raise to 31536000 with preload only once you are sure
    # the domain will never need to serve plain http again — it is not easily
    # undone, because browsers cache the instruction.
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
    SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', False)


# ── Email ─────────────────────────────────────────────────────────────────────
# The office's review screens tell applicants what was decided, by email as well
# as in the portal (see api/notify.py). Nothing here is required to run the
# site: with no host configured the messages are printed to the console instead
# of sent, so development and the test suite never touch a mail server.

EMAIL_HOST = os.environ.get('EMAIL_HOST', '').strip()

# Whether mail actually leaves this machine. The console backend below is a
# development convenience that looks exactly like success to every caller, so
# the office had no way to tell 'the applicant was emailed' from 'the message
# was printed to a log nobody reads'. The screens that send mail show a warning
# when this is False rather than letting it fail silently.
EMAIL_ENABLED = bool(EMAIL_HOST)

if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', True)
    EMAIL_USE_SSL = _env_bool('EMAIL_USE_SSL', False)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_HOST_USER = ''

# Seconds to wait on the mail server. A review must not hang because SMTP is
# slow; api.notify gives up and logs rather than blocking the office.
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 10))

DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'BiPSU SRMS <no-reply@bipsu.edu.ph>')

# Used in the links inside those emails. Without it they carry no link at all
# rather than pointing at a hostname that only resolves on the office's laptop.
SITE_URL = os.environ.get('SITE_URL', '').strip().rstrip('/')


# ── CORS ──────────────────────────────────────────────────────────────────────
# The UI is served by Django templates; these origins only matter if the
# separate Vite frontend is revived.

CORS_ALLOWED_ORIGINS = _env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080',
)


# ── REST framework ────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# ── Logging ───────────────────────────────────────────────────────────────────
# With DEBUG off Django sends 500s to the 'django' logger and nowhere else, so
# without this block production errors vanish silently. Render captures stdout.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'api': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
