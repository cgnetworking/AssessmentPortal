from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0003_audit_event"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditevent",
            name="action",
            field=models.CharField(
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
                    ("run_viewed", "Run viewed"),
                    ("audit_log_viewed", "Audit log viewed"),
                ],
                max_length=64,
            ),
        ),
    ]
