import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from prep.models import Subject, Topic, Subtopic


class Command(BaseCommand):
    help = (
        "Load subtopics from data/subtopics.json into the database. "
        "Safe to run again and again: it never deletes anything and never creates duplicates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Check the file and show what would change, without saving anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        path = settings.BASE_DIR / "data" / "subtopics.json"

        if not path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {path}"))
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            self.stdout.write(self.style.ERROR(f"subtopics.json is not valid JSON: {error}"))
            return

        # ---- 1. Check the whole file first. Nothing is saved if anything is wrong. ----
        errors = []
        plan = []   # (Topic object, [subtopic names])

        for subject_name, topics in data.items():
            subject = Subject.objects.filter(name=subject_name).first()
            if subject is None:
                errors.append(f"Subject not found in the database: '{subject_name}'")
                continue

            for topic_name, names in topics.items():
                matches = list(Topic.objects.filter(subject=subject, name=topic_name))
                if len(matches) == 0:
                    errors.append(f"Topic not found: '{topic_name}' under '{subject_name}'")
                    continue
                if len(matches) > 1:
                    errors.append(f"Topic name matches more than one record: '{topic_name}'")
                    continue

                seen = set()
                for name in names:
                    clean = (name or "").strip()
                    if not clean:
                        errors.append(f"Empty subtopic name under '{topic_name}'")
                    elif len(clean) > 200:
                        errors.append(f"Subtopic name longer than 200 characters under '{topic_name}'")
                    elif clean.lower() in seen:
                        errors.append(f"Duplicate subtopic '{clean}' under '{topic_name}'")
                    seen.add(clean.lower())

                plan.append((matches[0], [n.strip() for n in names]))

        if errors:
            self.stdout.write(self.style.ERROR("Nothing was saved. Fix these first:"))
            for e in errors:
                self.stdout.write("  " + e)
            return

        # ---- 2. Save (all or nothing) ----
        added = updated = unchanged = 0
        not_in_file = []

        with transaction.atomic():
            for topic, names in plan:
                existing = {s.name.lower(): s for s in Subtopic.objects.filter(topic=topic)}

                for position, name in enumerate(names, start=1):
                    found = existing.get(name.lower())
                    if found is None:
                        added += 1
                        if not dry_run:
                            Subtopic.objects.create(topic=topic, name=name, order=position)
                    elif found.order != position:
                        updated += 1
                        if not dry_run:
                            found.order = position
                            found.save(update_fields=["order"])
                    else:
                        unchanged += 1

                # Subtopics you added by hand in the admin are never deleted. Just report them.
                file_names = {n.lower() for n in names}
                for key, s in existing.items():
                    if key not in file_names:
                        not_in_file.append(f"{topic.name}: {s.name}")

            if dry_run:
                transaction.set_rollback(True)

        label = "DRY RUN (nothing saved). " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{label}Topics: {len(plan)} | Subtopics added: {added} | "
            f"order updated: {updated} | already up to date: {unchanged}"
        ))
        if not_in_file:
            self.stdout.write(self.style.WARNING(
                f"{len(not_in_file)} subtopic(s) exist in the database but not in the file (left untouched):"
            ))
            for item in not_in_file:
                self.stdout.write("  " + item)