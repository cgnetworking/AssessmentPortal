from django.core.validators import RegexValidator
from django.db import migrations, models


HEX_GUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
HEX_GUID_ERROR = "Must use the 8-4-4-4-12 hexadecimal GUID pattern, such as 12345678-abcd-1234-abcd-1234567890ab."


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0004_add_certificate_created_audit_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenantprofile",
            name="client_id",
            field=models.CharField(max_length=36, validators=[RegexValidator(message=HEX_GUID_ERROR, regex=HEX_GUID_PATTERN)]),
        ),
        migrations.AlterField(
            model_name="tenantprofile",
            name="tenant_id",
            field=models.CharField(max_length=36, unique=True, validators=[RegexValidator(message=HEX_GUID_ERROR, regex=HEX_GUID_PATTERN)]),
        ),
        migrations.AddConstraint(
            model_name="tenantprofile",
            constraint=models.CheckConstraint(condition=models.Q(client_id__regex=HEX_GUID_PATTERN), name="tenant_profile_client_id_hex_guid"),
        ),
        migrations.AddConstraint(
            model_name="tenantprofile",
            constraint=models.CheckConstraint(condition=models.Q(tenant_id__regex=HEX_GUID_PATTERN), name="tenant_profile_tenant_id_hex_guid"),
        ),
    ]
