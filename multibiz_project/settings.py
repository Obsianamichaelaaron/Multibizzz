"""
Django settings for multibiz_project.
"""

from pathlib import Path
import os

import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Helper functions for safe environment variable parsing
def get_int_env(key, default):
    val = os.environ.get(key)
    if val is not None and str(val).strip():
        try:
            return int(str(val).strip())
        except ValueError:
            return default
    return default

def get_bool_env(key, default=False):
    val = os.environ.get(key)
    if val is None or not str(val).strip():
        return default
    return str(val).strip().lower() in ('true', '1', 'yes', 't')

# Auto-load .env file if it exists
_env_path = BASE_DIR / '.env'
if _env_path.exists():
    with open(_env_path, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                _val = _v.strip().strip("'").strip('"')
                if _val:
                    os.environ[_k.strip()] = _val

# Keep production secrets and host names outside source control.
SECRET_KEY = os.environ.get('SECRET_KEY') or 'django-insecure-multibiz-dev-only'
DEBUG = get_bool_env('DEBUG', True)
raw_hosts = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,.vercel.app,.onrender.com')
ALLOWED_HOSTS = [
    host.strip()
    for host in raw_hosts.split(',')
    if host.strip()
]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.vercel.app', '.onrender.com', '*']

# Google Drive destination folder for candidate exports.
GOOGLE_DRIVE_FOLDER_ID = os.environ.get(
    'GOOGLE_DRIVE_FOLDER_ID'
) or '142yr98iPnLBJqg8WE6c-XKoScO_AFgix'
GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE = os.environ.get(
    'GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE',
    ''
)
GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE = os.environ.get(
    'GOOGLE_DRIVE_OAUTH_CREDENTIALS_FILE'
) or str(BASE_DIR / 'client_secret_244236718785-cncc88lcudaqn13hao2d8phe0il7563r.apps.googleusercontent.com.json')
GOOGLE_DRIVE_OAUTH_TOKEN_FILE = os.environ.get(
    'GOOGLE_DRIVE_OAUTH_TOKEN_FILE'
) or str(BASE_DIR / 'google-drive-token.json')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Custom Multibiz Apps
    'accounts.apps.AccountsConfig',
    'core.apps.CoreConfig',
    'jobs.apps.JobsConfig',
    'applications.apps.ApplicationsConfig',
    'chatbot.apps.ChatbotConfig',
    'messaging.apps.MessagingConfig',
    'audit.apps.AuditConfig',
    'ml_engine.apps.MlEngineConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'multibiz_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'messaging.context_processors.unread_messages_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'multibiz_project.wsgi.application'

# Database Configuration
# Use PostgreSQL/MySQL when DATABASE_URL is present; otherwise use SQLite (with /tmp support for serverless).
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.strip():
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL.strip(),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Serverless runtime (e.g., Vercel / AWS Lambda) has a read-only root (/var/task).
    # Redirect SQLite storage to the writable /tmp partition and copy bundled DB if present.
    sqlite_db_path = BASE_DIR / 'db.sqlite3'
    if os.environ.get('VERCEL') or not os.access(str(BASE_DIR), os.W_OK):
        import shutil
        tmp_db_path = Path('/tmp') / 'db.sqlite3'
        if sqlite_db_path.exists() and not tmp_db_path.exists():
            try:
                shutil.copy2(str(sqlite_db_path), str(tmp_db_path))
            except Exception:
                pass
        sqlite_db_path = tmp_db_path

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(sqlite_db_path),
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6}
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (User uploads, Resumes, Photos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload limits (up to 20MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# Authentication Redirection
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard_router'
LOGOUT_REDIRECT_URL = 'home'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email & Notification Dispatch Configuration
EMAIL_HOST = os.environ.get('EMAIL_HOST') or 'smtp.gmail.com'
EMAIL_PORT = get_int_env('EMAIL_PORT', 587)
EMAIL_USE_TLS = get_bool_env('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = get_int_env('EMAIL_TIMEOUT', 15)

# If user provided real SMTP credentials, use SMTP backend; otherwise use console
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL') or (f"Multibiz Intelligence <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else 'no-reply@multibiz.com')
SITE_URL = os.environ.get('SITE_URL') or 'http://127.0.0.1:8000/'

# PythonAnywhere / Vercel / Reverse proxy HTTPS termination
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in (os.environ.get('CSRF_TRUSTED_ORIGINS') or '').split(',')
    if origin.strip()
]
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = get_int_env('SECURE_HSTS_SECONDS', 31536000 if not DEBUG else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True

