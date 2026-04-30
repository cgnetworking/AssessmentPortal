import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from assessment_portal.azure_postgres import validate_remote_postgres_host

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} is required.")
    return value


def require_min_length_env(name, minimum_length):
    value = require_env(name)
    if len(value) < minimum_length:
        raise ImproperlyConfigured(f"{name} must be at least {minimum_length} characters long.")
    return value


SECRET_KEY = require_min_length_env("DJANGO_SECRET_KEY", 50)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "social_django",
    "assessments.apps.AssessmentsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "assessment_portal.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
            ],
        },
    },
]

WSGI_APPLICATION = "assessment_portal.wsgi.application"

POSTGRES_HOST = require_env("POSTGRES_HOST")
POSTGRES_DB = require_env("POSTGRES_DB")
POSTGRES_USER = require_env("POSTGRES_USER")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_SSLMODE = os.environ.get("POSTGRES_SSLMODE", "require")

validate_remote_postgres_host(POSTGRES_HOST)

DATABASES = {
    "default": {
        "ENGINE": "assessment_portal.db.backends.azure_postgresql",
        "NAME": POSTGRES_DB,
        "USER": POSTGRES_USER,
        "HOST": POSTGRES_HOST,
        "PORT": POSTGRES_PORT,
        "OPTIONS": {
            "sslmode": POSTGRES_SSLMODE,
        },
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "social_core.backends.azuread_tenant.AzureADTenantOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173")
LOGIN_URL = "/auth/login/azuread-tenant-oauth2/"
LOGIN_REDIRECT_URL = FRONTEND_URL
LOGOUT_REDIRECT_URL = FRONTEND_URL
LOGIN_ERROR_URL = f"{FRONTEND_URL}/login?error=1"
SOCIAL_AUTH_LOGIN_ERROR_URL = LOGIN_ERROR_URL

SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_URL_NAMESPACE = "social"
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_KEY = os.environ.get("AZUREAD_AUTH_CLIENT_ID", "")
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_SECRET = os.environ.get("AZUREAD_AUTH_CLIENT_SECRET", "")
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_TENANT_ID = os.environ.get("AZUREAD_AUTH_TENANT_ID", "")
SOCIAL_AUTH_AZUREAD_TENANT_OAUTH2_RESOURCE = "https://graph.microsoft.com/"

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
    if origin.strip()
]
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "1") == "1"
CSRF_COOKIE_SECURE = os.environ.get("DJANGO_CSRF_COOKIE_SECURE", "1") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "1") == "1"
SECURE_HSTS_PRELOAD = os.environ.get("DJANGO_SECURE_HSTS_PRELOAD", "0") == "1"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

ZTA_MODULE_PATH = Path(os.environ.get("ZTA_MODULE_PATH", REPO_ROOT / "modules" / "ZeroTrustAssessment"))
ZTA_RUNNER_SCRIPT = Path(os.environ.get("ZTA_RUNNER_SCRIPT", BASE_DIR / "assessments" / "powershell" / "run_assessment.ps1"))
ZTA_WORK_ROOT = Path(os.environ.get("ZTA_WORK_ROOT") or os.environ.get("ZTA_OUTPUT_ROOT") or BASE_DIR / "var" / "assessment-work")
ZTA_KEY_VAULT_URL = os.environ.get("ZTA_KEY_VAULT_URL", "").strip().rstrip("/")
