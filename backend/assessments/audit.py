from django.contrib.auth import get_user_model

from .models import AssessmentRun, AuditEvent, TenantProfile


def client_ip_from_request(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def request_user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:2048]


def audit_metadata_diff(before, after):
    changed = {}
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changed[key] = {"before": before.get(key), "after": after.get(key)}
    return changed


def tenant_audit_snapshot(tenant):
    return {
        "displayName": tenant.display_name,
        "tenantId": tenant.tenant_id,
        "clientId": tenant.client_id,
        "certificateThumbprint": tenant.certificate_thumbprint,
        "keyVaultCertificateUri": tenant.key_vault_certificate_uri,
        "exchangeOrganization": tenant.exchange_organization,
        "sharePointAdminUrl": tenant.sharepoint_admin_url,
        "enabledConnectors": tenant.enabled_connectors,
    }


def record_audit_event(
    *,
    request=None,
    actor=None,
    action,
    target=None,
    target_type="",
    target_id="",
    target_label="",
    tenant_profile=None,
    assessment_run=None,
    metadata=None,
):
    if request is not None:
        actor = actor or getattr(request, "user", None)
        source_ip = client_ip_from_request(request)
        user_agent = request_user_agent(request)
    else:
        source_ip = None
        user_agent = ""

    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None

    if target is not None:
        target_type = target_type or target.__class__.__name__
        target_id = target_id or str(getattr(target, "pk", ""))
        target_label = target_label or str(target)

    if isinstance(target, TenantProfile):
        tenant_profile = tenant_profile or target
    if isinstance(target, AssessmentRun):
        assessment_run = assessment_run or target
        tenant_profile = tenant_profile or target.tenant_profile

    AuditEvent.objects.create(
        actor=actor,
        actor_username=actor.get_username() if actor else "",
        actor_email=getattr(actor, "email", "") if actor else "",
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        tenant_profile=tenant_profile,
        assessment_run=assessment_run,
        source_ip=source_ip,
        user_agent=user_agent,
        metadata=metadata or {},
    )


def actor_label_from_user_id(user_id):
    if not user_id:
        return ""
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    return user.get_username() if user else str(user_id)
