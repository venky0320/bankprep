import csv

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from prep.models import Topic, Subtopic, Question

LETTERS = "ABCDE"


class Command(BaseCommand):
    help = "Load questions from data/questions.csv into the database"

    def handle(self, *args, **options):
        path = settings.BASE_DIR / "data" / "questions.csv"
        if not path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {path}"))
            return

        # Topic names -> Topic objects (lowercase, so capital letters don't matter)
        topics = {}
        for t in Topic.objects.all():
            topics.setdefault(t.name.strip().lower(), []).append(t)

        # (topic id, subtopic name in lowercase) -> Subtopic object
        subtopics = {(s.topic_id, s.name.strip().lower()): s for s in Subtopic.objects.all()}

        errors = []
        rows_to_save = []

        # utf-8-sig removes the hidden marker that Excel adds to CSV files
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for number, row in enumerate(reader, start=2):   # row 1 is the header
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                if not any(row.values()):
                    continue                                  # skip empty lines

                topic_name = row.get("topic", "").lower()
                subtopic_name = row.get("subtopic", "")       # optional column
                question_text = row.get("question", "")
                options = [row.get(letter.lower(), "") for letter in LETTERS]
                answer = row.get("answer", "").upper()
                explanation = row.get("explanation", "")
                difficulty = row.get("difficulty", "").capitalize() or "Medium"

                before = len(errors)

                # ---- Check the row ----
                matches = topics.get(topic_name, [])
                if len(matches) == 0:
                    errors.append(f"Row {number}: topic '{row.get('topic', '')}' not found "
                                  f"(run: python manage.py list_topics)")
                elif len(matches) > 1:
                    errors.append(f"Row {number}: topic name '{row.get('topic', '')}' matches more than one topic")

                subtopic = None
                if subtopic_name and len(matches) == 1:
                    subtopic = subtopics.get((matches[0].id, subtopic_name.lower()))
                    if subtopic is None:
                        errors.append(f"Row {number}: subtopic '{subtopic_name}' not found under "
                                      f"topic '{matches[0].name}' (run: python manage.py list_subtopics)")

                if not question_text:
                    errors.append(f"Row {number}: question is empty")
                if sum(1 for o in options[:4] if o) < 4:
                    errors.append(f"Row {number}: options A to D must all be filled")
                if answer not in list(LETTERS):
                    errors.append(f"Row {number}: answer must be A, B, C, D or E (found '{answer}')")
                elif not options[LETTERS.index(answer)]:
                    errors.append(f"Row {number}: answer {answer} points to an empty option")
                if not explanation:
                    errors.append(f"Row {number}: explanation is empty")
                if difficulty not in ("Easy", "Medium", "Hard"):
                    errors.append(f"Row {number}: difficulty must be Easy, Medium or Hard (found '{row.get('difficulty')}')")

                if len(errors) == before:        # this row has no problems
                    rows_to_save.append((matches[0], subtopic, row, options, answer, explanation, difficulty))

        # If anything is wrong, stop and show all the problems
        if errors:
            self.stdout.write(self.style.ERROR("Nothing was imported. Fix these first:"))
            for e in errors:
                self.stdout.write("  " + e)
            return

        # ---- Save everything (all or nothing) ----
        added = updated = 0
        with transaction.atomic():
            for topic, subtopic, row, options, answer, explanation, difficulty in rows_to_save:
                defaults = {
                    "source": row.get("source") or "Original",
                    "difficulty": difficulty,
                    "option_a": options[0],
                    "option_b": options[1],
                    "option_c": options[2],
                    "option_d": options[3],
                    "option_e": options[4],
                    "correct_option": answer,
                    "explanation": explanation,
                }
                # A blank subtopic cell never removes a link that already exists.
                if subtopic is not None:
                    defaults["subtopic"] = subtopic

                _, created = Question.objects.update_or_create(
                    topic=topic,
                    question_text=row["question"],
                    defaults=defaults,
                )
                if created:
                    added += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"Done: {added} added, {updated} updated"))