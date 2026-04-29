from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0003_audit_event"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tenantprofile",
            name="enabled_connectors",
        ),
    ]
