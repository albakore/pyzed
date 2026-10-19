from django.urls import path

from . import views

app_name = "polls"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    path("<int:pk>/results/", views.ResultsView.as_view(), name="results"),
    path("<int:question_id>/vote/", views.vote, name="vote"),
    # JSON for the desktop client
    path("api/questions/", views.api_questions, name="api-questions"),
    path("api/questions/<int:question_id>/vote/", views.api_vote, name="api-vote"),
]
