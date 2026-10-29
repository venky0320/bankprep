
from django.core.management.base import BaseCommand
from django.db.models import Count

from prep.models import Subject, Topic


EXPECTED_SYLLABUS = {
    "Quantitative Aptitude": [
        "Number Series",
        "Data Interpretation (Bar, Line, Pie, Table, Caselet)",
        "Simplification & Approximation",
        "Quadratic Equations",
        "Percentage",
        "Ratio & Proportion",
        "Profit & Loss",
        "Simple & Compound Interest",
        "Time & Work",
        "Speed, Distance & Time (Boats, Trains)",
        "Mixtures & Alligation",
        "Ages",
        "Partnership",
        "Mensuration",
        "Probability, Permutation & Combination",
        "Word Problems (Averages, Numbers)",
    ],
    "Reasoning Ability": [
        "Puzzles (Floor, Box, Scheduling)",
        "Seating Arrangement (Linear, Circular)",
        "Syllogism",
        "Inequality",
        "Coding-Decoding",
        "Blood Relations",
        "Direction Sense",
        "Order & Ranking",
        "Input-Output",
        "Data Sufficiency",
        "Alphanumeric Series",
        "Logical Reasoning (Assumption, Course of Action)",
        "Computer Aptitude",
    ],
    "English Language": [
        "Reading Comprehension",
        "Cloze Test",
        "Error Detection",
        "Para Jumbles",
        "Fill in the Blanks",
        "Sentence Improvement",
        "Vocabulary (Synonyms, Antonyms, Word Usage)",
        "Descriptive Writing (Essay, Letter, Precis)",
    ],
    "Banking & Economy Awareness": [
        "RBI Functions & Monetary Policy",
        "Banking Terminology",
        "Indian Banking System & Types of Banks",
        "Types of Accounts & Negotiable Instruments",
        "Basel Norms & NPA",
        "Digital Payments (UPI, NEFT, RTGS)",
        "Government Schemes",
        "Economy Basics (GDP, Inflation, Budget)",
        "Financial Institutions (SEBI, IRDAI, NABARD, IMF, World Bank)",
        "Static GK (Currencies, Capitals, Important Days)",
        "Current Affairs (Last 6 Months)",
    ],
}


class Command(BaseCommand):
    help = "Audit BankPrep subjects and topics without changing database records."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            "\nBANKPREP SYLLABUS AUDIT\n"
        ))

        subject_names = set(
            Subject.objects.values_list("name", flat=True)
        )

        missing_subjects = (
            set(EXPECTED_SYLLABUS.keys()) - subject_names
        )

        if missing_subjects:
            self.stdout.write(self.style.ERROR("\nMissing subjects:"))
            for name in sorted(missing_subjects):
                self.stdout.write(f"  - {name}")
        else:
            self.stdout.write(self.style.SUCCESS(
                "All expected subjects exist."
            ))

        total_expected = 0
        total_found = 0

        for subject_name, expected_topics in EXPECTED_SYLLABUS.items():
            self.stdout.write(f"\n{subject_name}")
            self.stdout.write("-" * len(subject_name))

            subject = Subject.objects.filter(
                name=subject_name
            ).first()

            if subject is None:
                self.stdout.write(self.style.ERROR(
                    "Subject not found; topic check skipped."
                ))
                total_expected += len(expected_topics)
                continue

            actual_topics = list(
                Topic.objects.filter(subject=subject)
                .values_list("name", flat=True)
            )

            actual_names = set(actual_topics)
            expected_names = set(expected_topics)

            missing_topics = expected_names - actual_names
            unexpected_topics = actual_names - expected_names

            total_expected += len(expected_topics)
            total_found += len(expected_names & actual_names)

            self.stdout.write(
                f"Expected topics: {len(expected_topics)}"
            )
            self.stdout.write(
                f"Found matching topics: "
                f"{len(expected_names & actual_names)}"
            )

            if missing_topics:
                self.stdout.write(self.style.ERROR(
                    "\nMissing topics:"
                ))
                for name in sorted(missing_topics):
                    self.stdout.write(f"  - {name}")

            if unexpected_topics:
                self.stdout.write(self.style.WARNING(
                    "\nAdditional topics in database:"
                ))
                for name in sorted(unexpected_topics):
                    self.stdout.write(f"  - {name}")

            if not missing_topics and not unexpected_topics:
                self.stdout.write(self.style.SUCCESS(
                    "Topic list matches the expected syllabus."
                ))

        duplicate_topics = (
            Topic.objects.values("subject_id", "name")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )

        self.stdout.write("\nSUMMARY")
        self.stdout.write("-------")
        self.stdout.write(
            f"Expected topics across subjects: {total_expected}"
        )
        self.stdout.write(
            f"Matching expected topics: {total_found}"
        )

        if duplicate_topics.exists():
            self.stdout.write(self.style.ERROR(
                "\nDuplicate topic names within a subject:"
            ))
            for item in duplicate_topics:
                self.stdout.write(
                    f"  Subject ID {item['subject_id']}: "
                    f"{item['name']} "
                    f"({item['total']} records)"
                )
        else:
            self.stdout.write(self.style.SUCCESS(
                "No duplicate topic names within a subject."
            ))

        self.stdout.write(self.style.SUCCESS(
            "\nAudit completed. No database records were changed."
        ))
