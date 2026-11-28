"""Runs before every navigation to /account: without a session, the login page instead."""

from state import session

matcher = ["/account/:path*"]


def middleware(request):
    if not session.signed_in:
        return request.redirect(f"/login?next={request.pathname}")
    request.locals["user"] = session.user  # account pages take it as `locals`
