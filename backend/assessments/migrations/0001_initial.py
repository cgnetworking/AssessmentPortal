import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TenantProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("display_name", models.CharField(max_length=255)),
                ("tenant_id", models.CharField(max_length=64, unique=True)),
                ("client_id", models.CharField(max_length=64)),
                ("certificate_thumbprint", models.CharField(blank=True, max_length=128)),
                ("key_vault_certificate_uri", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["display_name"]},
        ),
        migrations.CreateModel(
            name="AssessmentRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="queued", max_length=32)),
                ("pillar", models.CharField(default="All", max_length=32)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("output_path", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant_profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="runs", to="assessments.tenantprofile")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReportArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("artifact_type", models.CharField(max_length=64)),
                ("storage_uri", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="assessments.assessmentrun")),
            ],
        ),
        migrations.CreateModel(
            name="RunLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stream", models.CharField(max_length=16)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="logs", to="assessments.assessmentrun")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="AssessmentResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("test_id", models.CharField(max_length=64)),
                ("pillar", models.CharField(blank=True, max_length=64)),
                ("name", models.TextField(blank=True)),
                ("status", models.CharField(blank=True, max_length=64)),
                ("risk", models.CharField(blank=True, max_length=64)),
                ("recommendation", models.TextField(blank=True)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="assessments.assessmentrun")),
            ],
        ),
        migrations.AddIndex(model_name="assessmentresult", index=models.Index(fields=["run", "test_id"], name="assessment_run_id_16f5ee_idx")),
        migrations.AddIndex(model_name="assessmentresult", index=models.Index(fields=["run", "status"], name="assessment_run_id_8dc710_idx")),
    ]
