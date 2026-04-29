from functools import wraps

from django.http import JsonResponse


PORTAL_ADMIN = "Portal Admin"
ASSESSMENT_OPERATOR = "Assessment Operator"
READER = "Reader"

ROLE_DEFINITIONS = {
    PORTAL_ADMIN: {
        "manageTenantProfiles",
        "configureKeyVaultCertificates",
        "deleteTenants",
        "runAssessments",
        "viewAuditLog",
        "viewResults",
    },
    ASSESSMENT_OPERATOR: {
        "viewTenantProfiles",
        "runAssessments",
        "viewResults",
    },
    READER: {
        "viewTenantProfiles",
        "viewResults",
    },
}


def user_roles(user):
    if not user.is_authenticated:
        return []
    roles = list(user.groups.filter(name__in=ROLE_DEFINITIONS.keys()).values_list("name", flat=True))
    if user.is_superuser and PORTAL_ADMIN not in roles:
        roles.append(PORTAL_ADMIN)
    return roles


def user_permissions(user):
    permissions = set()
    for role in user_roles(user):
        permissions.update(ROLE_DEFINITIONS[role])
    return sorted(permissions)


def has_permission(user, permission):
    return permission in user_permissions(user)


def require_permission(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"authenticated": False, "loginUrl": "/auth/login/azuread-tenant-oauth2/"}, status=401)
            if not has_permission(request.user, permission):
                return JsonResponse({"detail": "Forbidden", "requiredPermission": permission}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
