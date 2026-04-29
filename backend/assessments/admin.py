from django.contrib import admin

from .models import AssessmentResult, AssessmentRun, ReportArtifact, RunLog, TenantProfile


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "tenant_id", "client_id", "certificate_thumbprint", "updated_at")
    search_fields = ("display_name", "tenant_id", "client_id")


@admin.register(AssessmentRun)
class AssessmentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant_profile", "status", "pillar", "started_at", "completed_at", "exit_code")
    list_filter = ("status", "pillar")
    search_fields = ("tenant_profile__display_name", "tenant_profile__tenant_id")


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ("run", "stream", "created_at")
    list_filter = ("stream",)


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ("run", "test_id", "pillar", "status", "risk")
    list_filter = ("pillar", "status", "risk")
    search_fields = ("test_id", "name")


@admin.register(ReportArtifact)
class ReportArtifactAdmin(admin.ModelAdmin):
    list_display = ("run", "artifact_type", "created_at")
    list_filter = ("artifact_type",)
