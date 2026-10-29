from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class Exam(models.Model):
    """An exam such as IBPS PO or SBI PO."""
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    """A subject such as Quantitative Aptitude or Reasoning."""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Topic(models.Model):
    """A syllabus topic such as Number Series."""
    PRIORITY_CHOICES = [
        ("High", "High"),
        ("Medium", "Medium"),
        ("Low", "Low"),
    ]

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="Medium")
    exams = models.ManyToManyField(Exam, blank=True)   # which exams include this topic
    in_prelims = models.BooleanField(default=True)
    in_mains = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.subject.name}: {self.name}"


class Subtopic(models.Model):
    """A detailed part of a topic, such as 'Missing term' under Number Series."""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="subtopics")
    name = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)   # lower numbers are shown first

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("topic", "name")   # no duplicate subtopic inside one topic

    def __str__(self):
        return f"{self.topic.name}: {self.name}"


class Question(models.Model):
    """One multiple-choice question."""
    ANSWER_CHOICES = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E")]
    DIFFICULTY_CHOICES = [("Easy", "Easy"), ("Medium", "Medium"), ("Hard", "Hard")]

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    # Optional: which part of the topic this question practises (must belong to the same topic)
    subtopic = models.ForeignKey(
        Subtopic, on_delete=models.SET_NULL, null=True, blank=True, related_name="questions"
    )
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="Medium")
    source = models.CharField(max_length=100, default="Original")  # e.g. IBPS PO 2023 Prelims
    question_text = models.TextField()
    option_a = models.CharField(max_length=300)
    option_b = models.CharField(max_length=300)
    option_c = models.CharField(max_length=300)
    option_d = models.CharField(max_length=300)
    option_e = models.CharField(max_length=300, blank=True)   # optional 5th option
    correct_option = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    explanation = models.TextField()

    def clean(self):
        if self.subtopic_id and self.subtopic.topic_id != self.topic_id:
            raise ValidationError({"subtopic": "This subtopic belongs to a different topic."})

    def options(self):
        """The filled-in options as [("A", "text"), ("B", "text"), ...]."""
        texts = [self.option_a, self.option_b, self.option_c, self.option_d, self.option_e]
        return [(letter, text) for letter, text in zip("ABCDE", texts) if text]

    def __str__(self):
        return self.question_text[:60]


class Note(models.Model):
    """A study note for a topic. Write text (Markdown), upload a PDF, or both."""
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)                        # text is optional
    pdf = models.FileField(
        upload_to="notes_pdfs/",
        blank=True,
        validators=[FileExtensionValidator(["pdf"])],   # only .pdf files are allowed
    )

    def __str__(self):
        return self.title


class TopicProgress(models.Model):
    """Remembers one user's status for one topic."""
    STATUS_CHOICES = [
        ("Not Started", "Not Started"),
        ("Covered", "Covered"),
        ("Revised", "Revised"),
        ("Mastered", "Mastered"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Not Started")

    class Meta:
        unique_together = ("user", "topic")   # one row per user per topic

    def __str__(self):
        return f"{self.user.username} - {self.topic.name}: {self.status}"


class PracticeLog(models.Model):
    """Remembers every answer a user gives (practice and mock tests)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    chosen = models.CharField(max_length=1)           # the letter the user picked
    is_correct = models.BooleanField()
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Q{self.question_id} - {'right' if self.is_correct else 'wrong'}"


class UserSettings(models.Model):
    """Small personal settings for each user (just the exam date for now)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    exam_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Settings of {self.user.username}"


class MockTest(models.Model):
    """One mock test taken by one user, from start to finish."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    preset = models.CharField(max_length=100)                  # e.g. "IBPS PO Prelims"
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    is_finished = models.BooleanField(default=False)

    # [{"name": "English Language", "minutes": 20, "ids": [4, 9, 12]}, ...]
    sections = models.JSONField(default=list)
    # {"4": "B", "9": "C"}  (question id -> letter chosen)
    answers = models.JSONField(default=dict)

    current_section = models.PositiveIntegerField(default=0)
    section_started_at = models.DateTimeField(default=timezone.now)

    negative_mark = models.FloatField(default=0.25)
    score = models.FloatField(null=True, blank=True)
    max_score = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.preset} ({self.created_at:%d %b %Y})"