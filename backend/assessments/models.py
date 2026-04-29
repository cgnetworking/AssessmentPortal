import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TenantProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=255)
    tenant_id = models.CharField(max_length=64, unique=True)
    client_id = models.CharField(max_length=64)
    certificate_thumbprint = models.CharField(max_length=128, blank=True)
    key_vault_certificate_uri = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name


class AssessmentRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_profile = models.ForeignKey(TenantProfile, related_name="runs", on_delete=models.CASCADE)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    pillar = models.CharField(max_length=32, default="All")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    output_path = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class RunLog(models.Model):
    run = models.ForeignKey(AssessmentRun, related_name="logs", on_delete=models.CASCADE)
    stream = models.CharField(max_length=16)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class AssessmentResult(models.Model):
    run = models.ForeignKey(AssessmentRun, related_name="results", on_delete=models.CASCADE)
    test_id = models.CharField(max_length=64)
    pillar = models.CharField(max_length=64, blank=True)
    name = models.TextField(blank=True)
    status = models.CharField(max_length=64, blank=True)
    risk = models.CharField(max_length=64, blank=True)
    recommendation = models.TextField(blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["run", "test_id"]),
            models.Index(fields=["run", "status"]),
        ]


class ReportArtifact(models.Model):
    run = models.ForeignKey(AssessmentRun, related_name="artifacts", on_delete=models.CASCADE)
    artifact_type = models.CharField(max_length=64)
    storage_uri = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        ROLE_ASSIGNED = "role_assigned", "Role assigned"
        ROLE_REMOVED = "role_removed", "Role removed"
        TENANT_CREATED = "tenant_created", "Tenant created"
        TENANT_UPDATED = "tenant_updated", "Tenant updated"
        TENANT_DELETED = "tenant_deleted", "Tenant deleted"
        ASSESSMENT_QUEUED = "assessment_queued", "Assessment queued"
        RUN_VIEWED = "run_viewed", "Run viewed"
        AUDIT_LOG_VIEWED = "audit_log_viewed", "Audit log viewed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor_username = models.CharField(max_length=255, blank=True)
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=64, choices=Action.choices)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=128, blank=True)
    target_label = models.CharField(max_length=255, blank=True)
    tenant_profile = models.ForeignKey(TenantProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    assessment_run = models.ForeignKey(AssessmentRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["actor_username", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding and AuditEvent.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are immutable.")
