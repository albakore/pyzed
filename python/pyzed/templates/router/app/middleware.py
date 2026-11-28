"""Runs before every navigation, like Next.js' middleware.ts."""

from state import favorites

matcher = ["/favorites"]  # only these addresses


def middleware(request):
    if not favorites.ids:  # nothing to show yet: go to the list instead
        return request.redirect("/items")
