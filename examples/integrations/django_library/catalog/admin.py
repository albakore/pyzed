from django.contrib import admin

from .models import Author, Book

admin.site.register(Author)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "year", "isbn", "available"]
    list_filter = ["available", "author"]
    search_fields = ["title", "isbn", "author__name"]
