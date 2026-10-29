import random

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Exam, Topic, TopicProgress, Question, PracticeLog

STATUSES = ["Not Started", "Covered", "Revised", "Mastered"]


def home(request):
    return redirect("syllabus")


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("syllabus")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


# ---------------------------------------------------------------
# SYLLABUS TRACKER
# ---------------------------------------------------------------
@login_required
def syllabus(request):
    selected_exam = request.GET.get("exam", "")
    only_pending = request.GET.get("pending") == "1"

    topics = Topic.objects.select_related("subject").order_by("subject__name", "id")
    if selected_exam:
        topics = topics.filter(exams__name=selected_exam)

    saved = {p.topic_id: p.status for p in TopicProgress.objects.filter(user=request.user)}

    groups = {}
    for t in topics:
        t.status = saved.get(t.id, "Not Started")
        g = groups.setdefault(
            t.subject.name,
            {"subject": t.subject.name, "topics": [], "done": 0, "total": 0},
        )
        g["total"] += 1
        if t.status != "Not Started":
            g["done"] += 1
        if not only_pending or t.status == "Not Started":
            g["topics"].append(t)

    group_list = []
    for g in groups.values():
        g["pct"] = round(g["done"] * 100 / g["total"])
        if g["topics"]:
            group_list.append(g)

    return render(request, "prep/syllabus.html", {
        "groups": group_list,
        "exams": Exam.objects.all(),
        "selected_exam": selected_exam,
        "only_pending": only_pending,
        "statuses": STATUSES,
    })


@login_required
@require_POST
def set_status(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    status = request.POST.get("status")
    if status in STATUSES:
        TopicProgress.objects.update_or_create(
            user=request.user, topic=topic, defaults={"status": status}
        )

    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("syllabus")


# ---------------------------------------------------------------
# PRACTICE
# The current practice session is kept in request.session, like:
#   {"ids": [question ids], "index": 0, "score": 0, "answered": None}
# ---------------------------------------------------------------
@login_required
def practice_home(request):
    message = ""

    # The user pressed "Start" for a topic
    if request.method == "POST":
        topic_id = request.POST.get("topic")
        ids = list(Question.objects.filter(topic_id=topic_id).values_list("id", flat=True))
        if ids:
            random.shuffle(ids)
            request.session["practice"] = {
                "ids": ids[:10],       # up to 10 questions per session
                "index": 0,
                "score": 0,
                "answered": None,      # the letter chosen for the current question
            }
            return redirect("practice_question")
        message = "No questions for that topic yet."

    # Only list topics that have at least one question
    topics = (
        Topic.objects.annotate(n=Count("question"))
        .filter(n__gt=0)
        .select_related("subject")
        .order_by("subject__name", "name")
    )
    return render(request, "prep/practice_home.html", {"topics": topics, "message": message})


@login_required
def practice_question(request):
    data = request.session.get("practice")
    if not data:
        return redirect("practice_home")

    # All questions done? Show the result.
    if data["index"] >= len(data["ids"]):
        return redirect("practice_result")

    question = get_object_or_404(Question, id=data["ids"][data["index"]])

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "answer" and data["answered"] is None:
            choice = request.POST.get("choice")
            # Validate against the options actually displayed for this question.
            # A letter such as E must not be accepted when option E is empty.
            available_choices = {letter for letter, _ in question.options()}
            if choice in available_choices:
                correct = (choice == question.correct_option)
                PracticeLog.objects.create(
                    user=request.user, question=question, chosen=choice, is_correct=correct
                )
                if correct:
                    data["score"] += 1
                data["answered"] = choice

        elif action == "next" and data["answered"] is not None:
            data["index"] += 1
            data["answered"] = None

        request.session["practice"] = data   # save the changes back to the session
        return redirect("practice_question")

    # Build the list of options (skip the empty 5th option)
    texts = [question.option_a, question.option_b, question.option_c, question.option_d, question.option_e]
    options = [(letter, text) for letter, text in zip("ABCDE", texts) if text]

    return render(request, "prep/practice_question.html", {
        "question": question,
        "options": options,
        "answered": data["answered"],
        "number": data["index"] + 1,
        "total": len(data["ids"]),
        "is_last": data["index"] + 1 == len(data["ids"]),
    })


@login_required
def practice_result(request):
    data = request.session.pop("practice", None)   # end the session
    if not data:
        return redirect("practice_home")
    return render(request, "prep/practice_result.html", {
        "score": data["score"],
        "total": len(data["ids"]),
    })