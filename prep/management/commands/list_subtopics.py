from django.core.management.base import BaseCommand

from prep.models import Topic


class Command(BaseCommand):
    help = "Print every topic with its subtopics (use these names in the 'subtopic' column of the CSV)"

    def handle(self, *args, **options):
        topics = Topic.objects.select_related("subject").prefetch_related("subtopics")
        for t in topics.order_by("subject__name", "name"):
            self.stdout.write(f"{t.subject.name}  |  {t.name}")
            for s in t.subtopics.all():
                self.stdout.write(f"      - {s.name}")