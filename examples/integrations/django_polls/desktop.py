"""Desktop app on Django's ORM: the models, validation and database of the site, with no web server.

    uv run manage.py migrate          # once, as in Django's tutorial
    uv run desktop.py

The window imports the polls app and queries it directly (architecture "same process").
`uv run manage.py runserver` can run at the same time on the same database: votes cast in
the window show up on /polls/ and in /admin/, and the other way round.
"""

import functools
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()  # what manage.py does before anything touches the models

from django.core.exceptions import ValidationError  # noqa: E402
from django.db import connections, transaction  # noqa: E402
from django.db.models import F  # noqa: E402
from django.utils import timezone  # noqa: E402

import pyzed as pz  # noqa: E402

from polls.models import Question  # noqa: E402
from polls.views import question_json  # noqa: E402
from polls_window import PollsWindow  # noqa: E402


def in_thread(function):
    """Pyzed runs these in a worker thread; Django opens one connection per thread, so close it."""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        finally:
            connections.close_all()

    return wrapper


@in_thread
def load():
    questions = Question.objects.filter(pub_date__lte=timezone.now()).order_by("-pub_date").prefetch_related("choice_set")
    return [question_json(q) for q in questions]


@in_thread
def vote(question_id, choice_id):
    choice = Question.objects.get(pk=question_id).choice_set.get(pk=choice_id)
    choice.votes = F("votes") + 1  # the database adds one, so two voters never overwrite each other
    choice.save()


@in_thread
def create(draft):
    question = Question(question_text=draft["question_text"], pub_date=timezone.now())
    try:
        question.full_clean()  # the model's own rules: required, max_length=200
        if len(draft["choices"]) < 2:
            raise ValidationError("A poll needs at least two choices.")
    except ValidationError as error:
        return pz.validation_errors(error)
    with transaction.atomic():
        question.save()
        for text in draft["choices"]:
            question.choice_set.create(choice_text=text, votes=0)
    return question_json(question)


if __name__ == "__main__":
    pz.run(PollsWindow(load, vote, create, mode="Django ORM, same process"))
