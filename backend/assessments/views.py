import json
import logging
import uuid
from functools import wraps

from django.contrib.auth import logout
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from .audit import audit_metadata_diff, record_audit_event, tenant_audit_snapshot
from .models import AssessmentRun, AuditEvent, ReportArtifact, TenantProfile
from .redaction import redact_sensitive_text
from .roles import is_portal_admin, require_permission, user_permissions, user_roles
from .serializers import audit_event_to_dict, log_to_dict, run_to_dict, tenant_to_dict
from .services.certificates import create_certificate_for_tenant, get_public_certificate_der


logger = logging.getLogger(__name__)
RUN_DETAIL_LOG_LIMIT = 500


class BadJsonBody(ValueError):
    pass


def parse_json(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadJsonBody("Request body must be valid JSON.") from exc
    if not isinstance(data, dict):
        raise BadJsonBody("Request body must be a JSON object.")
    return data


def bad_json_response(_exc):
    return JsonResponse({"detail": "Request body must be a valid JSON object."}, status=400)


def validation_error_response(exc):
    if hasattr(exc, "message_dict"):
        errors = exc.message_dict
    else:
        errors = {"nonFieldErrors": exc.messages}
    return JsonResponse({"detail": "Validation failed.", "errors": errors}, status=400)


def safe_error_response(request, exc, *, detail, status, log_message):
    error_id = uuid.uuid4().hex
    logger.warning(
        "%s error_id=%s path=%s exception_type=%s detail=%s",
        log_message,
        error_id,
        getattr(request, "path", ""),
        exc.__class__.__name__,
        redact_sensitive_text(exc),
    )
    return JsonResponse({"detail": detail, "errorId": error_id}, status=status)


def require_auth(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"authenticated": False, "loginUrl": "/auth/login/azuread-tenant-oauth2/"}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapped


def health(_request):
    return JsonResponse({"status": "ok"})


@ensure_csrf_cookie
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


def auth_logout(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if request.user.is_authenticated:
        record_audit_event(request=request, action=AuditEvent.Action.LOGOUT, target=request.user, target_type="User")
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


@require_auth
def tenant_collection(request):
    permissions = user_permissions(request.user)
    if request.method == "GET":
        if "viewTenantProfiles" not in permissions and "manageTenantProfiles" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "viewTenantProfiles"}, status=403)
        return JsonResponse(
            {
                "tenants": [
                    tenant_to_dict(tenant)
                    for tenant in TenantProfile.objects.all()
                ]
            }
        )

    if request.method == "POST":
        if "manageTenantProfiles" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "manageTenantProfiles"}, status=403)
        try:
            data = parse_json(request)
        except BadJsonBody as exc:
            return bad_json_response(exc)
        if "keyVaultCertificateUri" in data:
            return JsonResponse({"detail": "Key Vault certificate URI is managed by the server from ZTA_KEY_VAULT_URL."}, status=400)
        if "certificateThumbprint" in data:
            return JsonResponse({"detail": "Certificate thumbprint is managed by the server from Azure Key Vault."}, status=400)
        try:
            tenant = TenantProfile.objects.create(
                display_name=data.get("displayName", "").strip(),
                tenant_id=data.get("tenantId") or "",
                client_id=data.get("clientId") or "",
                key_vault_certificate_uri="",
            )
        except ValidationError as exc:
            return validation_error_response(exc)
        record_audit_event(
            request=request,
            action=AuditEvent.Action.TENANT_CREATED,
            target=tenant,
            metadata={"tenant": tenant_audit_snapshot(tenant)},
        )
        return JsonResponse(
            {"tenant": tenant_to_dict(tenant)},
            status=201,
        )

    return HttpResponseNotAllowed(["GET", "POST"])


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
        try:
            data = parse_json(request)
        except BadJsonBody as exc:
            return bad_json_response(exc)
        if "keyVaultCertificateUri" in data:
            return JsonResponse({"detail": "Key Vault certificate URI is managed by the server from ZTA_KEY_VAULT_URL."}, status=400)
        if "certificateThumbprint" in data:
            return JsonResponse({"detail": "Certificate thumbprint is managed by the server from Azure Key Vault."}, status=400)
        before = tenant_audit_snapshot(tenant)
        field_map = {
            "displayName": "display_name",
            "tenantId": "tenant_id",
            "clientId": "client_id",
        }
        for api_name, model_name in field_map.items():
            if api_name in data:
                setattr(tenant, model_name, data[api_name])
        try:
            tenant.save()
        except ValidationError as exc:
            return validation_error_response(exc)
        after = tenant_audit_snapshot(tenant)
        record_audit_event(
            request=request,
            action=AuditEvent.Action.TENANT_UPDATED,
            target=tenant,
            metadata={"changes": audit_metadata_diff(before, after)},
        )
        return JsonResponse({"tenant": tenant_to_dict(tenant)})

    if request.method == "DELETE":
        if "deleteTenants" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "deleteTenants"}, status=403)
        record_audit_event(
            request=request,
            action=AuditEvent.Action.TENANT_DELETED,
            target=tenant,
            metadata={"tenant": tenant_audit_snapshot(tenant)},
        )
        tenant.delete()
        return JsonResponse({}, status=204)

    return HttpResponseNotAllowed(["GET", "PUT", "PATCH", "DELETE"])


@require_auth
def tenant_certificate(request, tenant_id):
    tenant = get_object_or_404(TenantProfile, id=tenant_id)
    permissions = user_permissions(request.user)
    if "manageTenantProfiles" not in permissions:
        return JsonResponse({"detail": "Forbidden", "requiredPermission": "manageTenantProfiles"}, status=403)
    if "configureKeyVaultCertificates" not in permissions:
        return JsonResponse({"detail": "Forbidden", "requiredPermission": "configureKeyVaultCertificates"}, status=403)

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        before = tenant_audit_snapshot(tenant)
        created = create_certificate_for_tenant(tenant)
    except ImproperlyConfigured as exc:
        return safe_error_response(
            request,
            exc,
            detail="Certificate service is not configured.",
            status=400,
            log_message="Certificate configuration error",
        )
    except Exception as exc:
        return safe_error_response(
            request,
            exc,
            detail="Certificate creation failed.",
            status=502,
            log_message="Certificate creation failed",
        )

    tenant.certificate_thumbprint = created.certificate_thumbprint
    tenant.key_vault_certificate_uri = created.key_vault_certificate_uri
    tenant.save(update_fields=["certificate_thumbprint", "key_vault_certificate_uri", "updated_at"])
    after = tenant_audit_snapshot(tenant)
    record_audit_event(
        request=request,
        action=AuditEvent.Action.CERTIFICATE_CREATED,
        target=tenant,
        metadata={"changes": audit_metadata_diff(before, after)},
    )
    return JsonResponse({"tenant": tenant_to_dict(tenant)}, status=201)


@require_auth
def tenant_certificate_download(request, tenant_id):
    tenant = get_object_or_404(TenantProfile, id=tenant_id)
    permissions = user_permissions(request.user)
    if "manageTenantProfiles" not in permissions:
        return JsonResponse({"detail": "Forbidden", "requiredPermission": "manageTenantProfiles"}, status=403)
    if "configureKeyVaultCertificates" not in permissions:
        return JsonResponse({"detail": "Forbidden", "requiredPermission": "configureKeyVaultCertificates"}, status=403)

    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    try:
        certificate_der = get_public_certificate_der(tenant)
    except (ImproperlyConfigured, ValidationError) as exc:
        return safe_error_response(
            request,
            exc,
            detail="Certificate download could not be completed.",
            status=400,
            log_message="Certificate download validation error",
        )
    except Exception as exc:
        return safe_error_response(
            request,
            exc,
            detail="Certificate download failed.",
            status=502,
            log_message="Certificate download failed",
        )

    filename = f"{tenant.display_name or tenant.tenant_id}.cer".replace("/", "-").replace("\\", "-")
    response = HttpResponse(certificate_der, content_type="application/x-x509-ca-cert")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_auth
def run_collection(request):
    permissions = user_permissions(request.user)
    if request.method == "GET":
        if "viewResults" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "viewResults"}, status=403)
        queryset = AssessmentRun.objects.select_related("tenant_profile").annotate(report_artifact_count=Count("artifacts", distinct=True))
        tenant_id = request.GET.get("tenantProfileId")
        if tenant_id:
            queryset = queryset.filter(tenant_profile_id=tenant_id)
        return JsonResponse({"runs": [run_to_dict(run) for run in queryset[:100]]})

    if request.method == "POST":
        if "runAssessments" not in permissions:
            return JsonResponse({"detail": "Forbidden", "requiredPermission": "runAssessments"}, status=403)
        try:
            data = parse_json(request)
        except BadJsonBody as exc:
            return bad_json_response(exc)
        if "pillar" in data:
            return JsonResponse({"detail": "Assessment pillar is managed by the server and always runs all pillars."}, status=400)
        tenant = get_object_or_404(TenantProfile, id=data.get("tenantProfileId"))
        run = AssessmentRun.objects.create(tenant_profile=tenant, pillar="All")
        record_audit_event(
            request=request,
            action=AuditEvent.Action.ASSESSMENT_QUEUED,
            target=run,
            metadata={"pillar": run.pillar, "tenantProfileId": str(tenant.id), "tenantDisplayName": tenant.display_name},
        )
        return JsonResponse({"run": run_to_dict(run)}, status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


@require_auth
@require_permission("viewResults")
def run_detail(request, run_id):
    run = get_object_or_404(AssessmentRun, id=run_id)
    record_audit_event(
        request=request,
        action=AuditEvent.Action.RUN_VIEWED,
        target=run,
        metadata={"tenantProfileId": str(run.tenant_profile_id), "status": run.status},
    )
    payload = {
        "run": run_to_dict(run),
        "results": list(run.results.values("test_id", "pillar", "name", "status", "risk", "recommendation", "evidence")),
    }
    if is_portal_admin(request.user):
        logs = list(run.logs.order_by("-created_at", "-id")[:RUN_DETAIL_LOG_LIMIT])
        logs.reverse()
        payload["logs"] = [log_to_dict(log) for log in logs]
        payload["logsTruncated"] = run.logs.count() > RUN_DETAIL_LOG_LIMIT
    return JsonResponse(payload)


@require_auth
@require_permission("runAssessments")
def run_cancel(request, run_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    with transaction.atomic():
        run = get_object_or_404(AssessmentRun.objects.select_for_update().select_related("tenant_profile"), id=run_id)
        if run.status not in {AssessmentRun.Status.QUEUED, AssessmentRun.Status.RUNNING}:
            return JsonResponse({"detail": "Only queued or running assessments can be cancelled.", "run": run_to_dict(run)}, status=409)

        previous_status = run.status
        run.status = AssessmentRun.Status.CANCELLED
        run.completed_at = timezone.now()
        run.error_message = "Cancellation requested." if previous_status == AssessmentRun.Status.RUNNING else "Assessment run was cancelled."
        run.save(update_fields=["status", "completed_at", "error_message", "updated_at"])

    record_audit_event(
        request=request,
        action=AuditEvent.Action.ASSESSMENT_CANCELLED,
        target=run,
        metadata={"previousStatus": previous_status, "tenantProfileId": str(run.tenant_profile_id)},
    )
    return JsonResponse({"run": run_to_dict(run)})


@require_auth
@require_permission("viewResults")
def run_report_download(request, run_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    run = get_object_or_404(AssessmentRun, id=run_id)
    artifact = (
        ReportArtifact.objects.filter(run=run, artifact_type="html").order_by("created_at", "id").first()
        or ReportArtifact.objects.filter(run=run, artifact_type="json").order_by("created_at", "id").first()
    )
    if artifact is None:
        return JsonResponse({"detail": "No report artifact is stored for this run."}, status=404)

    response = HttpResponse(artifact.content, content_type=artifact.content_type or "application/octet-stream")
    filename = artifact.filename or f"assessment-report.{artifact.artifact_type}"
    safe_filename = filename.replace("/", "-").replace("\\", "-")
    response["Content-Disposition"] = f'attachment; filename="{safe_filename}"'
    return response


@require_auth
@require_permission("viewAuditLog")
def audit_log(request):
    try:
        limit = min(max(int(request.GET.get("limit", "250")), 1), 500)
    except ValueError:
        return JsonResponse({"detail": "limit must be an integer"}, status=400)
    events = list(AuditEvent.objects.select_related("actor", "tenant_profile", "assessment_run")[:limit])
    record_audit_event(request=request, action=AuditEvent.Action.AUDIT_LOG_VIEWED, target_type="AuditEvent", metadata={"limit": limit})
    return JsonResponse({"events": [audit_event_to_dict(event) for event in events]})
