import random
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .mock_config import PRESETS, NEGATIVE_MARK, DIFFICULTY_MIX
from .models import Question, Topic, PracticeLog, MockTest

GRACE_SECONDS = 20     # a section submitted this late is still accepted (slow internet)


# ---------------------------------------------------------------
# PRACTICE HOME (now with a difficulty choice)
# ---------------------------------------------------------------
@login_required
def practice_home(request):
    message = ""

    if request.method == "POST":
        topic_id = request.POST.get("topic", "")
        difficulty = request.POST.get("difficulty", "")

        questions = Question.objects.none()
        if topic_id.isdigit():
            questions = Question.objects.filter(topic_id=topic_id)
            if difficulty in ("Easy", "Medium", "Hard"):    # empty means "any difficulty"
                questions = questions.filter(difficulty=difficulty)

        ids = list(questions.values_list("id", flat=True))
        if ids:
            random.shuffle(ids)
            request.session["practice"] = {
                "ids": ids[:10],       # up to 10 questions per session
                "index": 0,
                "score": 0,
                "answered": None,
            }
            return redirect("practice_question")
        message = "No questions for that topic and difficulty yet."

    topics = (
        Topic.objects.annotate(n=Count("question"))
        .filter(n__gt=0)
        .select_related("subject")
        .order_by("subject__name", "name")
    )
    return render(request, "prep/practice_home.html", {"topics": topics, "message": message})


# ---------------------------------------------------------------
# MOCK TESTS
# ---------------------------------------------------------------
def pick_questions(subject_name, count):
    """Pick `count` random questions of a subject, mixing Easy/Medium/Hard."""
    pool = list(
        Question.objects.filter(topic__subject__name=subject_name).values_list("id", "difficulty")
    )
    random.shuffle(pool)
    if len(pool) <= count:                      # not enough questions: use them all
        return [qid for qid, _ in pool]

    chosen = []
    for level, share in DIFFICULTY_MIX.items():
        wanted = round(count * share)
        chosen += [qid for qid, d in pool if d == level][:wanted]
    chosen = chosen[:count]

    if len(chosen) < count:                     # a level ran short: fill from the rest
        taken = set(chosen)
        chosen += [qid for qid, _ in pool if qid not in taken][: count - len(chosen)]

    random.shuffle(chosen)
    return chosen


def evaluate(test):
    """Work out the score of a test. Returns (sections, total, maximum)."""
    all_ids = [qid for sec in test.sections for qid in sec["ids"]]
    questions = {q.id: q for q in Question.objects.filter(id__in=all_ids)}

    result = []
    total = 0.0
    maximum = 0
    for sec in test.sections:
        stats = {"name": sec["name"], "correct": 0, "wrong": 0, "skipped": 0, "rows": []}
        for qid in sec["ids"]:
            q = questions.get(qid)
            if q is None:                       # question was deleted after the test
                continue
            chosen = test.answers.get(str(qid), "")
            options = dict(q.options())
            if not chosen:
                status = "skipped"
            elif chosen == q.correct_option:
                status = "correct"
            else:
                status = "wrong"
            stats[status] += 1
            stats["rows"].append({
                "question": q,
                "status": status,
                "chosen": chosen,
                "chosen_text": options.get(chosen, ""),
                "right": q.correct_option,
                "right_text": options.get(q.correct_option, ""),
            })
        stats["count"] = len(stats["rows"])
        stats["marks"] = stats["correct"] - test.negative_mark * stats["wrong"]
        total += stats["marks"]
        maximum += stats["count"]
        result.append(stats)
    return result, total, maximum


def finish_test(test, when):
    """Mark a test as finished, save the score, and log the answers once."""
    if test.is_finished:
        return
    sections, total, maximum = evaluate(test)
    logs = []
    for sec in sections:
        for row in sec["rows"]:
            if row["chosen"]:
                logs.append(PracticeLog(
                    user=test.user, question=row["question"],
                    chosen=row["chosen"], is_correct=(row["status"] == "correct"),
                ))
    PracticeLog.objects.bulk_create(logs)       # so Dashboard and Wrong Answers see them

    test.is_finished = True
    test.finished_at = when
    test.score = round(total, 2)
    test.max_score = maximum
    test.save()


def go_to_next_section(test, start_time):
    test.current_section += 1
    if test.current_section >= len(test.sections):
        test.current_section = len(test.sections) - 1
        finish_test(test, start_time)
    else:
        test.section_started_at = start_time
        test.save()


def deadline_of(test):
    section = test.sections[test.current_section]
    return test.section_started_at + timedelta(minutes=section["minutes"])


def skip_expired_sections(test):
    """If the user was away while a section's time ran out, move on."""
    now = timezone.now()
    while not test.is_finished and now > deadline_of(test):
        go_to_next_section(test, deadline_of(test))   # next section's clock starts at the old deadline


@login_required
def mock_home(request):
    message = ""

    if request.method == "POST":
        preset = PRESETS.get(request.POST.get("preset", ""))
        if preset:
            sections = []
            for subject, count, minutes in preset["sections"]:
                ids = pick_questions(subject, count)
                if ids:                                  # skip subjects with no questions
                    sections.append({"name": subject, "minutes": minutes, "ids": ids})
            if sections:
                test = MockTest.objects.create(
                    user=request.user, preset=preset["name"], sections=sections,
                    answers={}, section_started_at=timezone.now(), negative_mark=NEGATIVE_MARK,
                )
                return redirect("mock_test", test_id=test.id)
            message = "There are no questions for this test yet. Add some in the admin panel."

    # How many questions exist per subject
    available = {
        row["topic__subject__name"]: row["n"]
        for row in Question.objects.values("topic__subject__name").annotate(n=Count("id"))
    }
    presets = []
    for key, p in PRESETS.items():
        rows = [(s, wanted, min(wanted, available.get(s, 0))) for s, wanted, _ in p["sections"]]
        presets.append({
            "key": key, "name": p["name"], "description": p["description"],
            "rows": rows,
            "total_have": sum(r[2] for r in rows),
            "total_want": sum(r[1] for r in rows),
        })

    history = MockTest.objects.filter(user=request.user).order_by("-created_at")[:10]
    return render(request, "prep/mock_home.html", {
        "presets": presets, "history": history, "message": message,
    })


@login_required
def mock_test(request, test_id):
    test = get_object_or_404(MockTest, id=test_id, user=request.user)
    if test.is_finished:
        return redirect("mock_result", test_id=test.id)

    if request.method == "POST":
        # Only accept answers for the section that is currently on screen
        if request.POST.get("section") == str(test.current_section):
            now = timezone.now()
            section_deadline = deadline_of(test)
            section = test.sections[test.current_section]

            # Only accept a submission during the section or within the small
            # grace window. If it is too late, advance from the actual deadline
            # so time spent away cannot extend later sections.
            within_grace = now <= section_deadline + timedelta(seconds=GRACE_SECONDS)
            if within_grace:
                section_questions = {
                    q.id: q for q in Question.objects.filter(id__in=section["ids"])
                }
                for qid in section["ids"]:
                    choice = request.POST.get(f"q{qid}")
                    question = section_questions.get(qid)
                    if question and choice in dict(question.options()):
                        test.answers[str(qid)] = choice

            next_section_start = now if within_grace else section_deadline
            go_to_next_section(test, next_section_start)
        return redirect("mock_test", test_id=test.id)

    skip_expired_sections(test)
    if test.is_finished:
        return redirect("mock_result", test_id=test.id)

    section = test.sections[test.current_section]
    questions = {q.id: q for q in Question.objects.filter(id__in=section["ids"])}
    ordered = [questions[qid] for qid in section["ids"] if qid in questions]
    remaining = max(0, int((deadline_of(test) - timezone.now()).total_seconds()))

    return render(request, "prep/mock_test.html", {
        "test": test,
        "section": section,
        "section_number": test.current_section + 1,
        "section_total": len(test.sections),
        "is_last": test.current_section + 1 == len(test.sections),
        "questions": ordered,
        "remaining_seconds": remaining,
    })


@login_required
def mock_result(request, test_id):
    test = get_object_or_404(MockTest, id=test_id, user=request.user)
    if not test.is_finished:
        return redirect("mock_test", test_id=test.id)
    sections, total, maximum = evaluate(test)
    return render(request, "prep/mock_result.html", {
        "test": test, "sections": sections, "total": round(total, 2), "maximum": maximum,
    })