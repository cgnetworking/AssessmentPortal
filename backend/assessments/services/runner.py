import json
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from assessment_portal.azure_postgres import get_postgres_access_token
from assessments.models import AssessmentRun, ReportArtifact, RunLog


class PowerShellAssessmentRunner:
    def run(self, run: AssessmentRun) -> AssessmentRun:
        tenant = run.tenant_profile
        output_dir = Path(settings.ZTA_OUTPUT_ROOT) / str(run.id)
        output_dir.mkdir(parents=True, exist_ok=True)

        run.status = AssessmentRun.Status.RUNNING
        run.started_at = timezone.now()
        run.output_path = str(output_dir)
        run.save(update_fields=["status", "started_at", "output_path", "updated_at"])

        try:
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
        env.pop("POSTGRES_PASSWORD", None)
        env.pop("ZT_POSTGRES_CONNECTION_STRING", None)
        env.update(
            {
                "PGHOST": settings.POSTGRES_HOST,
                "PGDATABASE": settings.POSTGRES_DB,
                "PGUSER": settings.POSTGRES_USER,
                "PGPASSWORD": get_postgres_access_token(),
                "PGPORT": settings.POSTGRES_PORT,
                "PGSSLMODE": settings.POSTGRES_SSLMODE,
                "ZTA_RUN_ID": str(run.id),
                "ZTA_TENANT_ID": tenant.tenant_id,
                "ZTA_CLIENT_ID": tenant.client_id,
                "ZTA_KEY_VAULT_CERTIFICATE_URI": tenant.key_vault_certificate_uri,
                "ZTA_CERTIFICATE_THUMBPRINT": tenant.certificate_thumbprint,
                "ZTA_EXCHANGE_ORGANIZATION": tenant.exchange_organization,
                "ZTA_SHAREPOINT_ADMIN_URL": tenant.sharepoint_admin_url,
                "ZTA_ENABLED_CONNECTORS": json.dumps(tenant.enabled_connectors),
                "ZTA_MODULE_PATH": str(settings.ZTA_MODULE_PATH),
                "ZTA_OUTPUT_PATH": str(output_dir),
                "ZTA_PILLAR": run.pillar,
                "ZT_POSTGRES_SCHEMA": f"assessment_{str(run.id).replace('-', '_')}",
            }
        )
        return env

    def _record_artifacts(self, run, output_dir):
        for path in output_dir.glob("**/*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".html", ".json"}:
                ReportArtifact.objects.get_or_create(
                    run=run,
                    artifact_type=path.suffix.lower().lstrip("."),
                    storage_uri=str(path),
                    defaults={"metadata": {"filename": path.name}},
                )
