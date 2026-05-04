import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from assessments.models import AssessmentRun, ReportArtifact, RunLog
from assessments.redaction import redact_sensitive_text


MAX_RUN_SECONDS = 24 * 60 * 60
POWERSHELL_INHERITED_ENV_VARS = {
    "AZURE_CLIENT_ID",
    "AZURE_MANAGED_IDENTITY_CLIENT_ID",
    "HOME",
    "IDENTITY_ENDPOINT",
    "IDENTITY_HEADER",
    "LANG",
    "LC_ALL",
    "PATH",
    "PSModulePath",
    "TEMP",
    "TMP",
    "TMPDIR",
    "ZTA_REQUIRED_MODULES_PATH",
}


class PowerShellAssessmentRunner:
    def run(self, run: AssessmentRun) -> AssessmentRun:
        run.refresh_from_db(fields=["status"])
        if run.status == AssessmentRun.Status.CANCELLED:
            if run.completed_at is None:
                run.completed_at = timezone.now()
                run.save(update_fields=["completed_at", "updated_at"])
            return run

        work_root = Path(settings.ZTA_WORK_ROOT)
        work_root.mkdir(parents=True, exist_ok=True)

        run.status = AssessmentRun.Status.RUNNING
        run.started_at = timezone.now()
        if not self._mark_running_if_not_cancelled(run):
            return run

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
                exit_code, cancellation_requested, timed_out = self._monitor_process(run, process)

                run.exit_code = exit_code
                run.completed_at = timezone.now()
                if cancellation_requested or self._is_cancelled(run):
                    run.status = AssessmentRun.Status.CANCELLED
                    run.error_message = "Assessment run was cancelled."
                elif timed_out:
                    run.status = AssessmentRun.Status.FAILED
                    run.error_message = "Assessment run exceeded the 24 hour maximum runtime."
                elif exit_code == 0:
                    run.status = AssessmentRun.Status.COMPLETED
                    self._record_artifacts(run, output_dir)
                else:
                    run.status = AssessmentRun.Status.FAILED
                    run.error_message = f"PowerShell assessment exited with code {exit_code}"
            self._save_completion_if_not_cancelled(run)
            return run
        except Exception as exc:
            run.completed_at = timezone.now()
            if self._is_cancelled(run):
                run.status = AssessmentRun.Status.CANCELLED
                run.error_message = "Assessment run was cancelled."
            else:
                run.status = AssessmentRun.Status.FAILED
                run.error_message = redact_sensitive_text(exc)
            self._save_completion_if_not_cancelled(run)
            self._record_log(run, "stderr", exc)
            return run

    def _monitor_process(self, run, process):
        output_queue = queue.Queue()

        def read_stdout():
            try:
                for line in process.stdout:
                    output_queue.put(line)
            finally:
                output_queue.put(None)

        threading.Thread(target=read_stdout, daemon=True).start()
        stdout_closed = False
        cancellation_requested = False
        timed_out = False
        deadline = time.monotonic() + MAX_RUN_SECONDS

        while True:
            try:
                line = output_queue.get(timeout=1)
            except queue.Empty:
                line = None
            else:
                if line is None:
                    stdout_closed = True
                else:
                    self._record_log(run, "stdout", line.rstrip())

            if not cancellation_requested and self._is_cancelled(run):
                cancellation_requested = True
                self._record_log(run, "stderr", "Cancellation requested. Stopping assessment process.")
                self._terminate_process(process)

            if not timed_out and time.monotonic() >= deadline:
                timed_out = True
                self._record_log(run, "stderr", "Assessment exceeded the 24 hour maximum runtime. Stopping assessment process.")
                self._terminate_process(process)

            if stdout_closed and process.poll() is not None:
                break

        return process.wait(), cancellation_requested, timed_out

    def _record_log(self, run, stream, message):
        RunLog.objects.create(run=run, stream=stream, message=redact_sensitive_text(message))

    def _terminate_process(self, process):
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _is_cancelled(self, run):
        return AssessmentRun.objects.filter(pk=run.pk, status=AssessmentRun.Status.CANCELLED).exists()

    def _mark_running_if_not_cancelled(self, run):
        updated_at = timezone.now()
        updated = (
            AssessmentRun.objects.filter(pk=run.pk)
            .exclude(status=AssessmentRun.Status.CANCELLED)
            .update(
                status=AssessmentRun.Status.RUNNING,
                started_at=run.started_at,
                updated_at=updated_at,
            )
        )
        if updated:
            run.updated_at = updated_at
            return True

        run.refresh_from_db(fields=["status", "started_at", "completed_at", "error_message", "updated_at"])
        return False

    def _save_completion_if_not_cancelled(self, run):
        updated_at = timezone.now()
        updated = (
            AssessmentRun.objects.filter(pk=run.pk)
            .exclude(status=AssessmentRun.Status.CANCELLED)
            .update(
                status=run.status,
                completed_at=run.completed_at,
                exit_code=run.exit_code,
                error_message=run.error_message,
                updated_at=updated_at,
            )
        )
        if updated:
            run.updated_at = updated_at
            return True

        run.refresh_from_db(fields=["status", "completed_at", "exit_code", "error_message", "updated_at"])
        return False

    def _build_environment(self, run, output_dir):
        tenant = run.tenant_profile
        env = {
            name: value
            for name in POWERSHELL_INHERITED_ENV_VARS
            if (value := os.environ.get(name))
        }
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
