import time

from django.core.management.base import BaseCommand
from django.db import transaction

from assessments.models import AssessmentRun
from assessments.services.runner import PowerShellAssessmentRunner


class Command(BaseCommand):
    help = "Processes queued Zero Trust assessment runs."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process at most one queued run and exit.")
        parser.add_argument("--sleep", type=int, default=10, help="Seconds to sleep between polling attempts.")

    def handle(self, *args, **options):
        runner = PowerShellAssessmentRunner()

        while True:
            run = self._claim_next_run()
            if run:
                self.stdout.write(f"Running assessment {run.id}")
                result = runner.run(run)
                self.stdout.write(f"Completed assessment {result.id} with status {result.status}")
            elif options["once"]:
                self.stdout.write("No queued assessment runs found.")
                return

            if options["once"]:
                return

            time.sleep(options["sleep"])

    def _claim_next_run(self):
        with transaction.atomic():
            run = (
                AssessmentRun.objects.select_for_update(skip_locked=True)
                .select_related("tenant_profile")
                .filter(status=AssessmentRun.Status.QUEUED)
                .order_by("created_at")
                .first()
            )
            if run:
                run.status = AssessmentRun.Status.RUNNING
                run.save(update_fields=["status", "updated_at"])
            return run
