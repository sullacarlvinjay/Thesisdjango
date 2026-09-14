import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


DEBUG = _env_bool('DEBUG', False)

SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-development-only-do-not-deploy'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY must be set when DEBUG is off. Generate one with:\n'
            '  python -c "from django.core.management.utils import get_random_secret_key;'
            ' print(get_random_secret_key())"'
        )

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
_render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)

CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')
if _render_host:
    _render_origin = f'https://{_render_host}'
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)

CSRF_FAILURE_VIEW = 'api.error_views.csrf_failure'


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
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'api.middleware.ReleaseVerifiedAccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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


DATABASE_URL = os.environ.get('DATABASE_URL', '')
PGHOST = os.environ.get('PGHOST', '')


def _database_from_url(url):
    try:
        import dj_database_url
    except ModuleNotFoundError:
        raise ImproperlyConfigured(
            'DATABASE_URL is set, but dj-database-url is not installed.\n'
            '  Install the requirements into the interpreter you are running:\n'
            '    venv\\Scripts\\python.exe -m pip install -r requirements.txt\n'
            '  Or unset DATABASE_URL to run on the local SQLite file.'
        ) from None

    try:
        return dj_database_url.parse(
            url, conn_max_age=600, conn_health_checks=True, ssl_require=not DEBUG,
        )
    except Exception as exc:
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


AUTH_USER_MODEL = 'api.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'


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
        'BACKEND': 'api.storage.ProtectedS3Storage',
        'OPTIONS': {
            'endpoint_url': os.environ['SUPABASE_S3_ENDPOINT'],
            'region_name': os.environ['SUPABASE_S3_REGION'],
            'access_key': os.environ['SUPABASE_S3_ACCESS_KEY_ID'],
            'secret_key': os.environ['SUPABASE_S3_SECRET_ACCESS_KEY'],
            'bucket_name': os.environ['SUPABASE_STORAGE_BUCKET'],
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

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', '10'))


SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = _env_bool('SECURE_SSL_REDIRECT', True)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
    SECURE_HSTS_PRELOAD = _env_bool('SECURE_HSTS_PRELOAD', False)


BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '').strip()
EMAIL_HOST = os.environ.get('EMAIL_HOST', '').strip()

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')

EMAIL_ENABLED = bool(BREVO_API_KEY or EMAIL_HOST)

if BREVO_API_KEY:
    EMAIL_BACKEND = 'api.email_backends.BrevoEmailBackend'
elif EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', True)
    EMAIL_USE_SSL = _env_bool('EMAIL_USE_SSL', False)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_HOST_USER = ''

EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 10))

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', '').strip() or (
    f'BiPSU SRMS <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER
    else 'BiPSU SRMS <no-reply@bipsu.edu.ph>'
)

SITE_URL = os.environ.get('SITE_URL', '').strip().rstrip('/')


CORS_ALLOWED_ORIGINS = _env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080',
)


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


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
