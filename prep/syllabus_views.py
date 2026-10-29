from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Topic, TopicProgress

STATUSES = ["Not Started", "Covered", "Revised", "Mastered"]


def stage_label(topic):
    """Short text such as 'Prelims and Mains' for one topic."""
    if topic.in_prelims and topic.in_mains:
        return "Prelims and Mains"
    if topic.in_prelims:
        return "Prelims only"
    return "Mains only"


@login_required
def syllabus(request):
    # Which subject is open after saving a status (?open=3)
    open_id = request.GET.get("open", "")

    # This user's saved statuses, like {topic_id: "Covered"}
    saved = {p.topic_id: p.status for p in TopicProgress.objects.filter(user=request.user)}

    # All topics, in the order they were added (so subjects keep a sensible order)
    topics = (
        Topic.objects.select_related("subject")
        .prefetch_related("subtopics")      # loads all subtopics in one extra query
        .order_by("id")
    )

    groups = {}
    for t in topics:
        t.status = saved.get(t.id, "Not Started")
        t.stage_text = stage_label(t)
        g = groups.setdefault(
            t.subject_id,
            {"id": t.subject_id, "name": t.subject.name, "topics": [], "started": 0},
        )
        g["topics"].append(t)
        if t.status != "Not Started":
            g["started"] += 1

    group_list = list(groups.values())
    for g in group_list:
        g["total"] = len(g["topics"])
        g["pct"] = round(g["started"] * 100 / g["total"])
        g["open"] = (str(g["id"]) == open_id)

    total_topics = sum(g["total"] for g in group_list)
    total_started = sum(g["started"] for g in group_list)

    return render(request, "prep/syllabus.html", {
        "groups": group_list,
        "statuses": STATUSES,
        "total_topics": total_topics,
        "total_started": total_started,
        "total_pct": round(total_started * 100 / total_topics) if total_topics else 0,
    })