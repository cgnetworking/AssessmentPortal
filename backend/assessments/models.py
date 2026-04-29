import uuid

from django.db import models


class TenantProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=255)
    tenant_id = models.CharField(max_length=64, unique=True)
    client_id = models.CharField(max_length=64)
    certificate_thumbprint = models.CharField(max_length=128, blank=True)
    key_vault_certificate_uri = models.TextField()
    exchange_organization = models.CharField(max_length=255, blank=True)
    sharepoint_admin_url = models.URLField(blank=True)
    enabled_connectors = models.JSONField(default=list, blank=True)
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
