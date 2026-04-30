import hashlib
import hmac
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AdminLoginRateLimitBucket


DEFAULT_ADMIN_LOGIN_RATE_LIMITS = {
    "username_ip": {"limit": 5, "window_seconds": 300},
    "username": {"limit": 20, "window_seconds": 3600},
    "ip": {"limit": 30, "window_seconds": 300},
}
ADMIN_LOGIN_PATH = "/admin/login/"
_last_pruned_at = None


@dataclass(frozen=True)
class RateLimitResult:
    limited: bool
    retry_after_seconds: int = 0


def check_admin_login_rate_limit(request):
    now = timezone.now()
    username = _normalize_username(request.POST.get("username", ""))
    ip_address = _client_ip(request)
    limits = _admin_login_rate_limits()
    retry_after_seconds = 0

    _prune_expired_buckets(now)

    for scope, key in _rate_limit_keys(username, ip_address):
        limit_config = limits[scope]
        limited, retry_after = _increment_bucket(
            scope=scope,
            key=key,
            limit=limit_config["limit"],
            window_seconds=limit_config["window_seconds"],
            now=now,
        )
        if limited:
            retry_after_seconds = max(retry_after_seconds, retry_after)

    return RateLimitResult(limited=retry_after_seconds > 0, retry_after_seconds=retry_after_seconds)


def clear_admin_login_rate_limit(request):
    username = _normalize_username(request.POST.get("username", ""))
    ip_address = _client_ip(request)
    keys = [key for _scope, key in _rate_limit_keys(username, ip_address)]
    if keys:
        AdminLoginRateLimitBucket.objects.filter(key__in=keys).delete()


def _admin_login_rate_limits():
    configured_limits = getattr(settings, "ADMIN_LOGIN_RATE_LIMITS", {})
    limits = {}
    for scope, defaults in DEFAULT_ADMIN_LOGIN_RATE_LIMITS.items():
        configured = configured_limits.get(scope, {})
        limits[scope] = {
            "limit": max(int(configured.get("limit", defaults["limit"])), 1),
            "window_seconds": max(int(configured.get("window_seconds", defaults["window_seconds"])), 1),
        }
    return limits


def _rate_limit_keys(username, ip_address):
    ip_hash = _stable_digest(ip_address or "unknown")
    keys = [("ip", f"admin-login:ip:{ip_hash}")]
    if username:
        username_hash = _stable_digest(username)
        keys.extend(
            [
                ("username", f"admin-login:username:{username_hash}"),
                ("username_ip", f"admin-login:username-ip:{username_hash}:{ip_hash}"),
            ]
        )
    return keys


def _increment_bucket(scope, key, limit, window_seconds, now):
    cutoff = now - timedelta(seconds=window_seconds)
    with transaction.atomic():
        bucket, _created = AdminLoginRateLimitBucket.objects.select_for_update().get_or_create(
            key=key,
            defaults={
                "scope": scope,
                "count": 0,
                "window_start": now,
            },
        )
        if bucket.window_start <= cutoff:
            bucket.scope = scope
            bucket.count = 0
            bucket.window_start = now

        bucket.count += 1
        bucket.save(update_fields=["scope", "count", "window_start", "updated_at"])

    if bucket.count <= limit:
        return False, 0

    window_end = bucket.window_start + timedelta(seconds=window_seconds)
    return True, max(1, int((window_end - now).total_seconds()))


def _prune_expired_buckets(now):
    global _last_pruned_at
    if _last_pruned_at and now - _last_pruned_at < timedelta(minutes=5):
        return

    _last_pruned_at = now
    retention_seconds = max(int(getattr(settings, "ADMIN_LOGIN_RATE_LIMIT_RETENTION_SECONDS", 86400)), 1)
    AdminLoginRateLimitBucket.objects.filter(updated_at__lt=now - timedelta(seconds=retention_seconds)).delete()


def _normalize_username(username):
    return str(username or "").strip().casefold()


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _stable_digest(value):
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), str(value).encode("utf-8"), hashlib.sha256).hexdigest()
