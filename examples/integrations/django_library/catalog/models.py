"""The catalog: ordinary Django models, shared by the admin and the Pyzed window."""

from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    year = models.PositiveIntegerField()
    isbn = models.CharField("ISBN", max_length=13, unique=True,
                            validators=[RegexValidator(r"^\d{13}$", "An ISBN has 13 digits.")])
    available = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        # Runs after the field checks even when they failed, so year may still be the typed text.
        if isinstance(self.year, int) and self.year > date.today().year:
            raise ValidationError({"year": "That year hasn't happened yet."})
