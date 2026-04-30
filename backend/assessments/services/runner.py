import os
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from assessments.models import AssessmentRun, ReportArtifact, RunLog


class PowerShellAssessmentRunner:
    def run(self, run: AssessmentRun) -> AssessmentRun:
        tenant = run.tenant_profile
        work_root = Path(settings.ZTA_WORK_ROOT)
        work_root.mkdir(parents=True, exist_ok=True)

        run.status = AssessmentRun.Status.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at", "updated_at"])

        try:
            with tempfile.TemporaryDirectory(prefix=f"assessment-{run.id}-", dir=work_root) as output_dir_name:
                output_dir = Path(output_dir_name)
                env = self._build_environment(run, output_dir)
                process = subprocess.Popen(
                    [
                        "pwsh",
                        "-NoLogo",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(settings.ZTA_RUNNER_SCRIPT),
                    ],
                    cwd=str(settings.BASE_DIR),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                assert process.stdout is not None
                for line in process.stdout:
                    RunLog.objects.create(run=run, stream="stdout", message=line.rstrip())

                exit_code = process.wait()
                run.exit_code = exit_code
                run.completed_at = timezone.now()
                if exit_code == 0:
                    run.status = AssessmentRun.Status.COMPLETED
                    self._record_artifacts(run, output_dir)
                else:
                    run.status = AssessmentRun.Status.FAILED
                    run.error_message = f"PowerShell assessment exited with code {exit_code}"
            run.save()
            return run
        except Exception as exc:
            run.status = AssessmentRun.Status.FAILED
            run.completed_at = timezone.now()
            run.error_message = str(exc)
            run.save()
            RunLog.objects.create(run=run, stream="stderr", message=str(exc))
            return run

    def _build_environment(self, run, output_dir):
        tenant = run.tenant_profile
        env = os.environ.copy()
        env.pop("DATABASE_URL", None)
        env.pop("PGPASSWORD", None)
        env.pop("POSTGRES_PASSWORD", None)
        env.pop("ZT_POSTGRES_CONNECTION_STRING", None)
        env.update(
            {
                "PGHOST": settings.POSTGRES_HOST,
                "PGDATABASE": settings.POSTGRES_DB,
                "PGUSER": settings.POSTGRES_USER,
                "PGPORT": settings.POSTGRES_PORT,
                "PGSSLMODE": settings.POSTGRES_SSLMODE,
                "ZT_POSTGRES_TOKEN_RESOURCE": os.environ.get(
                    "AZURE_POSTGRES_TOKEN_RESOURCE",
                    "https://ossrdbms-aad.database.windows.net",
                ),
                "ZTA_RUN_ID": str(run.id),
                "ZTA_TENANT_ID": tenant.tenant_id,
                "ZTA_CLIENT_ID": tenant.client_id,
                "ZTA_KEY_VAULT_CERTIFICATE_URI": tenant.key_vault_certificate_uri,
                "ZTA_CERTIFICATE_THUMBPRINT": tenant.certificate_thumbprint,
                "ZTA_MODULE_PATH": str(settings.ZTA_MODULE_PATH),
                "ZTA_OUTPUT_PATH": str(output_dir),
                "ZTA_PILLAR": run.pillar,
                "ZT_POSTGRES_SCHEMA": f"assessment_{str(run.id).replace('-', '_')}",
            }
        )
        return env

    def _record_artifacts(self, run, output_dir):
        artifacts = [
            (output_dir / "ZeroTrustAssessmentReport.html", "html", "text/html; charset=utf-8"),
            (output_dir / "zt-export" / "ZeroTrustAssessmentReport.json", "json", "application/json"),
        ]
        for path, artifact_type, content_type in artifacts:
            if not path.is_file():
                continue
            content = path.read_bytes()
            ReportArtifact.objects.filter(run=run, artifact_type=artifact_type).delete()
            ReportArtifact.objects.create(
                run=run,
                artifact_type=artifact_type,
                filename=path.name,
                content_type=content_type,
                content=content,
                metadata={"filename": path.name, "size": len(content)},
            )
