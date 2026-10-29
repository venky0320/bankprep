from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Topic, TopicProgress, PracticeLog, UserSettings


@login_required
def dashboard(request):
    settings_obj, _ = UserSettings.objects.get_or_create(user=request.user)

    # The user pressed "Save" on the exam date box
    if request.method == "POST":
        try:
            settings_obj.exam_date = date.fromisoformat(request.POST.get("exam_date", ""))
        except ValueError:
            settings_obj.exam_date = None     # empty or invalid date clears it
        settings_obj.save()
        return redirect("home")

    # ---- Practice numbers ----
    logs = PracticeLog.objects.filter(user=request.user)
    attempted = logs.count()
    correct = logs.filter(is_correct=True).count()
    accuracy = round(correct * 100 / attempted) if attempted else None

    # ---- Syllabus numbers ----
    total_topics = Topic.objects.count()
    started = (
        TopicProgress.objects.filter(user=request.user)
        .exclude(status="Not Started")
        .count()
    )
    syllabus_pct = round(started * 100 / total_topics) if total_topics else 0

    # ---- Weak topics: lowest accuracy, with at least 3 attempts ----
    per_topic = (
        logs.values("question__topic__name")
        .annotate(total=Count("id"), right=Count("id", filter=Q(is_correct=True)))
        .filter(total__gte=3)
    )
    weak = sorted(
        [
            {"name": row["question__topic__name"],
             "accuracy": round(row["right"] * 100 / row["total"]),
             "total": row["total"]}
            for row in per_topic
        ],
        key=lambda x: x["accuracy"],
    )[:3]

    # ---- Days left to the exam ----
    days_left = None
    if settings_obj.exam_date:
        days_left = max(0, (settings_obj.exam_date - timezone.localdate()).days)

    return render(request, "prep/dashboard.html", {
        "attempted": attempted,
        "accuracy": accuracy,
        "syllabus_pct": syllabus_pct,
        "started": started,
        "total_topics": total_topics,
        "weak": weak,
        "days_left": days_left,
        "exam_date": settings_obj.exam_date,
    })


@login_required
def wrong_answers(request):
    # Go through the attempts from newest to oldest. For every question,
    # only the LATEST attempt matters, so a question you later got right disappears.
    latest = {}
    for log in (
        PracticeLog.objects.filter(user=request.user)
        .select_related("question", "question__topic")
        .order_by("-attempted_at")
    ):
        if log.question_id not in latest:
            latest[log.question_id] = log

    wrong = []
    for log in latest.values():
        if not log.is_correct:
            q = log.question
            options = {"A": q.option_a, "B": q.option_b, "C": q.option_c,
                       "D": q.option_d, "E": q.option_e}
            wrong.append({
                "question": q,
                "your_letter": log.chosen,
                "your_text": options.get(log.chosen, ""),
                "right_letter": q.correct_option,
                "right_text": options.get(q.correct_option, ""),
            })

    return render(request, "prep/wrong_answers.html", {"wrong": wrong})