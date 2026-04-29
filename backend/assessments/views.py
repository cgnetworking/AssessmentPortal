import json
from functools import wraps

from django.contrib.auth import logout
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import AssessmentRun, TenantProfile
from .roles import require_permission, user_permissions, user_roles
from .serializers import log_to_dict, run_to_dict, tenant_to_dict


def parse_json(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def require_auth(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"authenticated": False, "loginUrl": "/auth/login/azuread-tenant-oauth2/"}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapped


def health(_request):
    return JsonResponse({"status": "ok"})


def auth_session(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False, "loginUrl": "/auth/login/azuread-tenant-oauth2/"}, status=401)

    user = request.user
    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.get_username(),
                "email": user.email,
                "name": user.get_full_name() or user.get_username(),
                "roles": user_roles(user),
                "permissions": user_permissions(user),
            },
        }
    )


@csrf_exempt
def auth_logout(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    logout(request)
    return JsonResponse({"authenticated": False})


@require_auth
@require_permission("viewResults")
def dashboard_summary(_request):
    counts = AssessmentRun.objects.aggregate(
        activeRuns=Count("id", filter=Q(status__in=[AssessmentRun.Status.QUEUED, AssessmentRun.Status.RUNNING])),
        reportsStored=Count("artifacts", distinct=True),
    )
    latest_run = AssessmentRun.objects.order_by("-completed_at", "-created_at").first()
    return JsonResponse(
        {
            "savedTenants": TenantProfile.objects.count(),
            "activeRuns": counts["activeRuns"] or 0,
            "reportsStored": counts["reportsStored"] or 0,
            "mostRecentRun": run_to_dict(latest_run) if latest_run else None,
        }
    )


@csrf_exempt
@require_auth
def tenant_collection(request):
    permissions = user_permissions(request.user)
    if request.method == "GET":
        if "viewTenantProfiles" not in permissions and "manageTenantProfiles" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "viewTenantProfiles"}, status=403)
        return JsonResponse({"tenants": [tenant_to_dict(tenant) for tenant in TenantProfile.objects.all()]})

    if request.method == "POST":
        if "manageTenantProfiles" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "manageTenantProfiles"}, status=403)
        data = parse_json(request)
        tenant = TenantProfile.objects.create(
            display_name=data.get("displayName", "").strip(),
            tenant_id=data.get("tenantId", "").strip(),
            client_id=data.get("clientId", "").strip(),
            certificate_thumbprint=data.get("certificateThumbprint", "").strip(),
            key_vault_certificate_uri=data.get("keyVaultCertificateUri", "").strip(),
            exchange_organization=data.get("exchangeOrganization", "").strip(),
            sharepoint_admin_url=data.get("sharePointAdminUrl", "").strip(),
            enabled_connectors=data.get("enabledConnectors", []),
        )
        return JsonResponse({"tenant": tenant_to_dict(tenant)}, status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
@require_auth
def tenant_detail(request, tenant_id):
    tenant = get_object_or_404(TenantProfile, id=tenant_id)
    permissions = user_permissions(request.user)

    if request.method == "GET":
        if "viewTenantProfiles" not in permissions and "manageTenantProfiles" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "viewTenantProfiles"}, status=403)
        return JsonResponse({"tenant": tenant_to_dict(tenant)})

    if request.method in {"PUT", "PATCH"}:
        if "manageTenantProfiles" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "manageTenantProfiles"}, status=403)
        data = parse_json(request)
        field_map = {
            "displayName": "display_name",
            "tenantId": "tenant_id",
            "clientId": "client_id",
            "certificateThumbprint": "certificate_thumbprint",
            "keyVaultCertificateUri": "key_vault_certificate_uri",
            "exchangeOrganization": "exchange_organization",
            "sharePointAdminUrl": "sharepoint_admin_url",
            "enabledConnectors": "enabled_connectors",
        }
        for api_name, model_name in field_map.items():
            if api_name in data:
                setattr(tenant, model_name, data[api_name])
        tenant.save()
        return JsonResponse({"tenant": tenant_to_dict(tenant)})

    if request.method == "DELETE":
        if "deleteTenants" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "deleteTenants"}, status=403)
        tenant.delete()
        return JsonResponse({}, status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "PATCH", "DELETE"])


@csrf_exempt
@require_auth
def run_collection(request):
    permissions = user_permissions(request.user)
    if request.method == "GET":
        if "viewResults" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "viewResults"}, status=403)
        queryset = AssessmentRun.objects.select_related("tenant_profile")
        tenant_id = request.GET.get("tenantProfileId")
        if tenant_id:
            queryset = queryset.filter(tenant_profile_id=tenant_id)
        return JsonResponse({"runs": [run_to_dict(run) for run in queryset[:100]]})

    if request.method == "POST":
        if "runAssessments" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "runAssessments"}, status=403)
        data = parse_json(request)
        tenant = get_object_or_404(TenantProfile, id=data.get("tenantProfileId"))
        run = AssessmentRun.objects.create(tenant_profile=tenant, pillar=data.get("pillar", "All"))
        return JsonResponse({"run": run_to_dict(run)}, status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@require_auth
@require_permission("viewResults")
def run_detail(_request, run_id):
    run = get_object_or_404(AssessmentRun, id=run_id)
    return JsonResponse(
        {
            "run": run_to_dict(run),
            "logs": [log_to_dict(log) for log in run.logs.all()],
            "results": list(run.results.values("test_id", "pillar", "name", "status", "risk", "recommendation", "evidence")),
        }
    )
