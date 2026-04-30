import mimetypes
from pathlib import Path

from django.db import migrations, models


def import_existing_report_artifacts(apps, _schema_editor):
    ReportArtifact = apps.get_model("assessments", "ReportArtifact")
    for artifact in ReportArtifact.objects.exclude(storage_uri=""):
        path = Path(artifact.storage_uri)
        if not path.is_file():
            continue
        content = path.read_bytes()
        filename = ""
        metadata = artifact.metadata if isinstance(artifact.metadata, dict) else {}
        if isinstance(metadata, dict):
            filename = metadata.get("filename", "")
        artifact.filename = filename or path.name
        artifact.content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        artifact.content = content
        if isinstance(metadata, dict):
            metadata["size"] = len(content)
            artifact.metadata = metadata
        artifact.save(update_fields=["filename", "content_type", "content", "metadata"])
        if path.name in {"ZeroTrustAssessmentReport.html", "ZeroTrustAssessmentReport.json"}:
            path.unlink(missing_ok=True)


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0005_limit_tenant_guid_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportartifact",
            name="content",
            field=models.BinaryField(default=b""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reportartifact",
            name="content_type",
            field=models.CharField(default="application/octet-stream", max_length=128),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reportartifact",
            name="filename",
            field=models.CharField(default="report", max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(import_existing_report_artifacts, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="assessmentrun",
            name="output_path",
        ),
        migrations.RemoveField(
            model_name="reportartifact",
            name="storage_uri",
        ),
    ]
