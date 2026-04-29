from django.core.management.base import BaseCommand, CommandError

from assessments.models import AssessmentRun
from assessments.services.runner import PowerShellAssessmentRunner


class Command(BaseCommand):
    help = "Runs a queued Zero Trust assessment."

    def add_arguments(self, parser):
        parser.add_argument("run_id")

    def handle(self, *args, **options):
        try:
            run = AssessmentRun.objects.select_related("tenant_profile").get(id=options["run_id"])
        except AssessmentRun.DoesNotExist as exc:
            raise CommandError("Assessment run was not found") from exc

        result = PowerShellAssessmentRunner().run(run)
        self.stdout.write(f"{result.id} {result.status}")
