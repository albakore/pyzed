"""The views from Django's tutorial (parts 3 and 4), plus a small JSON API for the desktop client.

Tutorial: https://docs.djangoproject.com/en/stable/intro/tutorial04/
"""

import json

from django.db.models import F
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Choice, Question


class IndexView(generic.ListView):
    template_name = "polls/index.html"
    context_object_name = "latest_question_list"

    def get_queryset(self):
        """Return the last five published questions (not including those set to be published in the future)."""
        return Question.objects.filter(pub_date__lte=timezone.now()).order_by("-pub_date")[:5]


class DetailView(generic.DetailView):
    model = Question
    template_name = "polls/detail.html"

    def get_queryset(self):
        """Excludes any questions that aren't published yet."""
        return Question.objects.filter(pub_date__lte=timezone.now())


class ResultsView(generic.DetailView):
    model = Question
    template_name = "polls/results.html"


def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    try:
        selected_choice = question.choice_set.get(pk=request.POST["choice"])
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(request, "polls/detail.html", {"question": question, "error_message": "You didn't select a choice."})
    else:
        selected_choice.votes = F("votes") + 1
        selected_choice.save()
        # Always return an HttpResponseRedirect after successfully dealing with POST data.
        return HttpResponseRedirect(reverse("polls:results", args=(question.id,)))


# -- JSON API for desktop clients (client.py) ---------------------------------------------------


def question_json(question):
    return {
        "id": question.id,
        "question_text": question.question_text,
        "pub_date": question.pub_date.isoformat(),
        "choices": [{"id": c.id, "choice_text": c.choice_text, "votes": c.votes} for c in question.choice_set.all()],
    }


@require_GET
def api_questions(request):
    questions = Question.objects.filter(pub_date__lte=timezone.now()).order_by("-pub_date").prefetch_related("choice_set")
    return JsonResponse({"questions": [question_json(q) for q in questions]})


@csrf_exempt  # a desktop app has no CSRF cookie; protect a real API with tokens instead (e.g. Django REST framework)
@require_POST
def api_vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    try:
        choice_id = json.loads(request.body)["choice"]
        selected_choice = question.choice_set.get(pk=choice_id)
    except (KeyError, ValueError, Choice.DoesNotExist):
        return JsonResponse({"detail": "You didn't select a choice."}, status=400)
    selected_choice.votes = F("votes") + 1
    selected_choice.save()
    return JsonResponse(question_json(question))
