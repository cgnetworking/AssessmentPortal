import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("assessments", "0002_seed_role_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "actor_username",
                    models.CharField(blank=True, max_length=255),
                ),
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
                            ("assessment_queued", "Assessment queued"),
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
    ]
