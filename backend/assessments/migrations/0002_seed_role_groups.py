from django.db import migrations


ROLE_GROUPS = ["Portal Admin", "Assessment Operator", "Reader"]


def seed_role_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLE_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_role_groups(apps, _schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_GROUPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("assessments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_role_groups, remove_role_groups),
    ]
