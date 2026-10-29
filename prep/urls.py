from django.urls import path
from . import views, dashboard_views, content_views, mock_views, syllabus_views, practice_views

urlpatterns = [
    path("", dashboard_views.dashboard, name="home"),
    path("wrong-answers/", dashboard_views.wrong_answers, name="wrong_answers"),
    path("notes/", content_views.notes, name="notes"),
    path("exam-info/", content_views.exam_info, name="exam_info"),
    path("signup/", views.signup, name="signup"),
    path("syllabus/", syllabus_views.syllabus, name="syllabus"),
    path("syllabus/set/<int:topic_id>/", views.set_status, name="set_status"),
    path("practice/", practice_views.practice_home, name="practice_home"),
    path("practice/question/", practice_views.practice_question, name="practice_question"),
    path("practice/result/", practice_views.practice_result, name="practice_result"),
    path("mock/", mock_views.mock_home, name="mock_home"),
    path("mock/<int:test_id>/", mock_views.mock_test, name="mock_test"),
    path("mock/<int:test_id>/result/", mock_views.mock_result, name="mock_result"),
]