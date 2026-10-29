import random
import time

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import render, redirect

from .models import Topic, Subtopic, Question, PracticeLog

SESSION_SIZE = 10      # questions in one practice session


def start_session(request, ids, title):
    """Begin a practice session with these question ids."""
    request.session["practice"] = {
        "ids": list(ids),
        "answers": {},            # {"question id": "chosen letter"}
        "current": 0,             # which question is on screen (0 = first)
        "started": time.time(),
        "title": title,
    }
    request.session.pop("practice_done", None)


def upgrade_session(data):
    """Sessions started by older pages have a different shape. Make them fit the new one."""
    if "answers" not in data:
        data = {
            "ids": data.get("ids", []),
            "answers": {},
            "current": 0,
            "started": time.time(),
            "title": "Practice session",
        }
    return data


@login_required
def practice_home(request):
    message = ""
    last = request.session.get("practice_last", {})       # what the user practised last time

    # ---- The user pressed "Practice" next to a topic ----
    if request.method == "POST":
        topic_id = request.POST.get("topic", "")
        topic = Topic.objects.filter(id=topic_id).first() if topic_id.isdigit() else None

        if topic is None:
            message = "Choose a topic to practise."
        else:
            questions = Question.objects.filter(topic=topic)

            # Optional: practise only one subtopic of this topic (each topic has its own dropdown)
            subtopic = None
            subtopic_id = request.POST.get(f"subtopic_{topic.id}", "")
            if subtopic_id.isdigit():
                subtopic = Subtopic.objects.filter(id=subtopic_id, topic=topic).first()
                if subtopic is not None:
                    questions = questions.filter(subtopic=subtopic)
            ids = list(questions.values_list("id", flat=True))

            # Remember which subject was open, so this page looks the same when the user comes back
            request.session["practice_last"] = {"open": topic.subject_id}
            if ids:
                random.shuffle(ids)
                title = f"{topic.name}: {subtopic.name}" if subtopic else topic.name
                start_session(request, ids[:SESSION_SIZE], title)
                return redirect("practice_question")

            where = f"{subtopic.name} ({topic.name})" if subtopic else topic.name
            message = f"There are no questions in {where} yet."
            last = request.session["practice_last"]

    # ---- Which subject to show open ----
    open_id = str(request.GET.get("open") or last.get("open", ""))

    # ---- All topics with their question counts ----
    topics = (
        Topic.objects.select_related("subject")
        .prefetch_related(
            # each subtopic with the number of questions it has (used by the subtopic dropdown)
            Prefetch("subtopics", queryset=Subtopic.objects.annotate(n=Count("questions")), to_attr="sub_list")
        )
        .annotate(
            n=Count("question", distinct=True),
        )
        .order_by("id")
    )

    # ---- How this user has done in each topic ----
    stats = {
        row["question__topic_id"]: row
        for row in PracticeLog.objects.filter(user=request.user)
        .values("question__topic_id")
        .annotate(total=Count("id"), right=Count("id", filter=Q(is_correct=True)))
    }

    groups = {}
    for t in topics:
        s = stats.get(t.id)
        t.attempts = s["total"] if s else 0
        t.accuracy = round(s["right"] * 100 / s["total"]) if s else None
        g = groups.setdefault(
            t.subject_id,
            {"id": t.subject_id, "name": t.subject.name, "topics": [], "questions": 0, "with_q": 0},
        )
        g["topics"].append(t)
        g["questions"] += t.n
        if t.n:
            g["with_q"] += 1

    group_list = list(groups.values())
    for g in group_list:
        g["total"] = len(g["topics"])
        g["topics"].sort(key=lambda t: t.n == 0)       # topics that have questions come first
        g["open"] = (str(g["id"]) == open_id)

    return render(request, "prep/practice_home.html", {
        "groups": group_list,
        "message": message,
    })


@login_required
def practice_question(request):
    data = request.session.get("practice")
    if not data:
        return redirect("practice_home")
    data = upgrade_session(data)

    # Load the session's questions (skip any that were deleted in the meantime)
    found = {q.id: q for q in Question.objects.filter(id__in=data["ids"])}
    ids = [i for i in data["ids"] if i in found]
    if not ids:
        request.session.pop("practice", None)
        return redirect("practice_home")
    data["ids"] = ids
    total = len(ids)

    def position(value, default):
        """Turn '3' into the position 2 (0-based). Falls back to default if it is not valid."""
        if str(value).isdigit() and 1 <= int(value) <= total:
            return int(value) - 1
        return default

    # ---- The user did something ----
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "answer":
            idx = position(request.POST.get("q"), data["current"])
            question = found[ids[idx]]
            choice = request.POST.get("choice")
            # Only letters that are really shown for this question are accepted
            valid = {letter for letter, _ in question.options()}
            if choice in valid and str(question.id) not in data["answers"]:
                PracticeLog.objects.create(
                    user=request.user, question=question,
                    chosen=choice, is_correct=(choice == question.correct_option),
                )
                data["answers"][str(question.id)] = choice
            data["current"] = idx
            request.session["practice"] = data
            return redirect(f"{request.path}?q={idx + 1}")

        if action == "finish":
            data["finished"] = time.time()
            request.session["practice_done"] = data
            request.session.pop("practice", None)
            return redirect("practice_result")

        request.session["practice"] = data
        return redirect("practice_question")

    # ---- Show one question ----
    idx = position(request.GET.get("q"), min(data["current"], total - 1))
    data["current"] = idx
    request.session["practice"] = data

    question = found[ids[idx]]
    chosen = data["answers"].get(str(question.id))

    tiles = []
    correct = wrong = 0
    for n, qid in enumerate(ids, start=1):
        pick = data["answers"].get(str(qid))
        if pick is None:
            state, label = "open", "not answered"
        elif pick == found[qid].correct_option:
            state, label = "correct", "correct"
            correct += 1
        else:
            state, label = "wrong", "wrong"
            wrong += 1
        tiles.append({"number": n, "state": state, "label": label, "current": n - 1 == idx})

    answered_count = correct + wrong
    return render(request, "prep/practice_question.html", {
        "title": data["title"],
        "question": question,
        "options": question.options(),
        "chosen": chosen,
        "number": idx + 1,
        "total": total,
        "tiles": tiles,
        "correct": correct,
        "wrong": wrong,
        "left": total - answered_count,
        "answered_count": answered_count,
        "progress_pct": round(answered_count * 100 / total),
        "prev_number": idx if idx > 0 else None,
        "next_number": idx + 2 if idx + 1 < total else None,
        "elapsed": int(time.time() - data["started"]),
    })


@login_required
def practice_result(request):
    data = request.session.get("practice_done")
    if not data:
        return redirect("practice_home")

    found = {q.id: q for q in Question.objects.filter(id__in=data["ids"])}
    rows = []
    correct = wrong = skipped = 0
    retry_ids = []

    for n, qid in enumerate(data["ids"], start=1):
        question = found.get(qid)
        if question is None:
            continue
        pick = data["answers"].get(str(qid))
        if pick is None:
            status = "skipped"
            skipped += 1
        elif pick == question.correct_option:
            status = "correct"
            correct += 1
        else:
            status = "wrong"
            wrong += 1
        if status != "correct":
            retry_ids.append(qid)

        rows.append({
            "number": n,
            "question": question,
            "status": status,
            "chosen": pick,
            "options": [
                {"letter": letter, "text": text,
                 "is_correct": letter == question.correct_option, "is_chosen": letter == pick}
                for letter, text in question.options()
            ],
        })

    # "Retry the ones I missed" starts a new session with the wrong and skipped questions
    if request.method == "POST" and request.POST.get("action") == "retry" and retry_ids:
        random.shuffle(retry_ids)
        start_session(request, retry_ids, "Retry: " + data.get("title", "Practice"))
        return redirect("practice_question")

    total = len(rows)
    seconds = max(0, int(data.get("finished", time.time()) - data["started"]))
    return render(request, "prep/practice_result.html", {
        "title": data.get("title", "Practice session"),
        "rows": rows,
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "skipped": skipped,
        "accuracy": round(correct * 100 / total) if total else 0,
        "time_text": f"{seconds // 60}:{seconds % 60:02d}",
        "can_retry": bool(retry_ids),
    })