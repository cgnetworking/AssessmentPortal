import uuid

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion


HEX_GUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
HEX_GUID_ERROR = "Must use the 8-4-4-4-12 hexadecimal GUID pattern, such as 12345678-abcd-1234-abcd-1234567890ab."
ALPHANUMERIC_DISPLAY_NAME_PATTERN = r"^[0-9A-Za-z]{1,50}$"
ALPHANUMERIC_DISPLAY_NAME_ERROR = "Display name must be 1 to 50 alphanumeric characters."
ROLE_GROUPS = ["Portal Admin", "Assessment Operator", "Reader"]


def seed_role_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_role_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "display_name",
                    models.CharField(
                        max_length=50,
                        validators=[RegexValidator(message=ALPHANUMERIC_DISPLAY_NAME_ERROR, regex=ALPHANUMERIC_DISPLAY_NAME_PATTERN)],
                    ),
                ),
                (
                    "tenant_id",
                    models.CharField(
                        max_length=36,
                        unique=True,
                        validators=[RegexValidator(message=HEX_GUID_ERROR, regex=HEX_GUID_PATTERN)],
                    ),
                ),
                (
                    "client_id",
                    models.CharField(max_length=36, validators=[RegexValidator(message=HEX_GUID_ERROR, regex=HEX_GUID_PATTERN)]),
                ),
                ("certificate_thumbprint", models.CharField(blank=True, max_length=128)),
                ("key_vault_certificate_uri", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["display_name"],
            },
        ),
        migrations.CreateModel(
            name="AssessmentRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("pillar", models.CharField(default="All", max_length=32)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="assessments.tenantprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("actor_username", models.CharField(blank=True, max_length=255)),
                ("actor_email", models.EmailField(blank=True, max_length=254)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("login", "Login"),
                            ("logout", "Logout"),
                            ("role_assigned", "Role assigned"),
                            ("role_removed", "Role removed"),
                            ("tenant_created", "Tenant created"),
                            ("tenant_updated", "Tenant updated"),
                            ("tenant_deleted", "Tenant deleted"),
                            ("certificate_created", "Certificate created"),
                            ("assessment_queued", "Assessment queued"),
                            ("assessment_cancelled", "Assessment cancelled"),
                            ("run_viewed", "Run viewed"),
                            ("audit_log_viewed", "Audit log viewed"),
                        ],
                        max_length=64,
                    ),
                ),
                ("target_type", models.CharField(blank=True, max_length=64)),
                ("target_id", models.CharField(blank=True, max_length=128)),
                ("target_label", models.CharField(blank=True, max_length=255)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assessment_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="assessments.assessmentrun",
                    ),
                ),
                (
                    "tenant_profile",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="assessments.tenantprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
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
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="assessments.assessmentrun",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ReportArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("artifact_type", models.CharField(max_length=64)),
                ("filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=128)),
                ("content", models.BinaryField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="assessments.assessmentrun",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RunLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stream", models.CharField(max_length=16)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="assessments.assessmentrun",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="AdminLoginRateLimitBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=200, unique=True)),
                ("scope", models.CharField(max_length=64)),
                ("count", models.PositiveIntegerField(default=0)),
                ("window_start", models.DateTimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="assessmentresult",
            index=models.Index(fields=["run", "test_id"], name="assessment_run_id_16f5ee_idx"),
        ),
        migrations.AddIndex(
            model_name="assessmentresult",
            index=models.Index(fields=["run", "status"], name="assessment_run_id_8dc710_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["-created_at"], name="assessment_created_a87bf5_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["action", "-created_at"], name="assessment_action_d10c7c_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["actor_username", "-created_at"], name="assessment_actor_u_8cef62_idx"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["target_type", "target_id"], name="assessment_target__926d37_idx"),
        ),
        migrations.AddIndex(
            model_name="adminloginratelimitbucket",
            index=models.Index(fields=["scope", "updated_at"], name="assessment_scope_9885f4_idx"),
        ),
        migrations.AddIndex(
            model_name="adminloginratelimitbucket",
            index=models.Index(fields=["updated_at"], name="assessment_updated_6efe2c_idx"),
        ),
        migrations.AddConstraint(
            model_name="tenantprofile",
            constraint=models.CheckConstraint(condition=models.Q(client_id__regex=HEX_GUID_PATTERN), name="tenant_profile_client_id_hex_guid"),
        ),
        migrations.AddConstraint(
            model_name="tenantprofile",
            constraint=models.CheckConstraint(condition=models.Q(tenant_id__regex=HEX_GUID_PATTERN), name="tenant_profile_tenant_id_hex_guid"),
        ),
        migrations.RunPython(seed_role_groups, remove_role_groups),
    ]
