import json

import markdown
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from .models import Note


@login_required
def notes(request):
    # Search text from the address (?q=rbi)
    query = request.GET.get("q", "").strip()

    note_list = Note.objects.select_related("topic").order_by("title")
    if query:
        note_list = note_list.filter(Q(title__icontains=query) | Q(content__icontains=query))

    # Which note to show on the right (?id=3). Default: the first one.
    active = None
    note_id = request.GET.get("id", "")
    if note_id.isdigit():
        active = note_list.filter(id=note_id).first()
    if active is None:
        active = note_list.first()

    # Turn the Markdown text into HTML.
    # Only the admin can write notes, so it is safe to show this HTML.
    body_html = ""
    if active:
        body_html = markdown.markdown(active.content, extensions=["tables", "fenced_code"])

    return render(request, "prep/notes.html", {
        "notes": note_list,
        "active": active,
        "body_html": body_html,
        "query": query,
    })


@login_required
def exam_info(request):
    # Read the exam patterns from the data folder
    path = settings.BASE_DIR / "data" / "exams.json"
    exams = json.loads(path.read_text(encoding="utf-8"))

    # Which exam to show (?exam=sbi-po). Default: the first one.
    selected_id = request.GET.get("exam", exams[0]["id"])
    exam = next((e for e in exams if e["id"] == selected_id), exams[0])

    return render(request, "prep/exam_info.html", {"exams": exams, "exam": exam})