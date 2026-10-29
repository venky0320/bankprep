from django.contrib import admin

from .models import Exam, Subject, Topic, Subtopic, Question, Note, MockTest

# Show these models in the admin page
admin.site.register(Exam)
admin.site.register(Subject)


class SubtopicInline(admin.TabularInline):
    model = Subtopic
    extra = 1


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "priority")
    list_filter = ("subject", "priority", "exams")
    search_fields = ("name",)
    filter_horizontal = ("exams",)
    inlines = [SubtopicInline]


# Bulk actions: tick several questions, then choose one from the "Action" menu
@admin.action(description="Set difficulty to Easy")
def mark_easy(modeladmin, request, queryset):
    queryset.update(difficulty="Easy")


@admin.action(description="Set difficulty to Medium")
def mark_medium(modeladmin, request, queryset):
    queryset.update(difficulty="Medium")


@admin.action(description="Set difficulty to Hard")
def mark_hard(modeladmin, request, queryset):
    queryset.update(difficulty="Hard")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("question_text", "topic", "subtopic", "difficulty", "correct_option", "source")
    list_filter = ("difficulty", "topic__subject", "topic", "subtopic", "source")
    search_fields = ("question_text",)
    actions = [mark_easy, mark_medium, mark_hard]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "topic")
    search_fields = ("title", "content")


@admin.register(MockTest)
class MockTestAdmin(admin.ModelAdmin):
    list_display = ("user", "preset", "created_at", "is_finished", "score", "max_score")
    list_filter = ("preset", "is_finished")