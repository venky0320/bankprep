import json
from django.conf import settings
from django.core.management.base import BaseCommand

from prep.models import Exam, Subject, Topic, Question, Note


class Command(BaseCommand):
    help = "Load syllabus, questions and notes from the data folder into the database"

    def handle(self, *args, **options):
        data_dir = settings.BASE_DIR / "data"

        # Read the three JSON files
        syllabus = json.loads((data_dir / "syllabus.json").read_text(encoding="utf-8"))
        questions = json.loads((data_dir / "questions.json").read_text(encoding="utf-8"))
        notes = json.loads((data_dir / "notes.json").read_text(encoding="utf-8"))

        # ---- 1. Topics (plus their subjects and exams) ----
        topic_by_json_id = {}   # remembers which JSON id belongs to which Topic

        for item in syllabus:
            subject, _ = Subject.objects.get_or_create(name=item["subject"])

            topic, _ = Topic.objects.update_or_create(
                subject=subject,
                name=item["name"],
                defaults={
                    "priority": item["priority"],
                    "in_prelims": "Prelims" in item["stages"],
                    "in_mains": "Mains" in item["stages"],
                },
            )

            # Connect the topic to its exams
            exam_objects = []
            for exam_name in item["exams"]:
                exam, _ = Exam.objects.get_or_create(name=exam_name)
                exam_objects.append(exam)
            topic.exams.set(exam_objects)

            topic_by_json_id[item["id"]] = topic

        self.stdout.write(f"Topics: {len(topic_by_json_id)}")

        # ---- 2. Questions ----
        letters = "ABCDE"
        added = 0
        for q in questions:
            topic = topic_by_json_id.get(q["topicId"])
            if topic is None:
                self.stdout.write(self.style.WARNING(f"Skipped {q['id']}: unknown topic {q['topicId']}"))
                continue

            options = q["options"] + [""] * (5 - len(q["options"]))   # pad to 5 options

            _, created = Question.objects.get_or_create(
                topic=topic,
                question_text=q["questionText"],
                defaults={
                    "source": q.get("source", "Original"),
                    "option_a": options[0],
                    "option_b": options[1],
                    "option_c": options[2],
                    "option_d": options[3],
                    "option_e": options[4],
                    "correct_option": letters[q["correctOptionIndex"]],
                    "explanation": q["explanation"],
                },
            )
            if created:
                added += 1

        self.stdout.write(f"Questions added: {added} (of {len(questions)} in file)")

        # ---- 3. Notes ----
        notes_added = 0
        for n in notes:
            _, created = Note.objects.get_or_create(
                title=n["title"],
                defaults={
                    "topic": topic_by_json_id.get(n.get("topicId")),
                    "content": n["content"],
                },
            )
            if created:
                notes_added += 1

        self.stdout.write(f"Notes added: {notes_added} (of {len(notes)} in file)")
        self.stdout.write(self.style.SUCCESS("Import finished"))