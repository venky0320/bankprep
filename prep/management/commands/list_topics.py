from django.core.management.base import BaseCommand

from prep.models import Topic


class Command(BaseCommand):
    help = "Print all topic names (use these in the 'topic' column of the CSV)"

    def handle(self, *args, **options):
        for t in Topic.objects.select_related("subject").order_by("subject__name", "name"):
            self.stdout.write(f"{t.subject.name}  |  {t.name}")