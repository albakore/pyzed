"""Event handlers for the login form.

Each function receives the running ``form`` (controls are attributes: ``form.button1.text``)
and an ``event`` with ``event.sender``, ``event.name`` and ``event.value``.
"""


def sign_in_click(form, event):
    """Runs when sign_in is clicked."""
    if "@" not in form.email.text:
        form.status.text = "Enter a valid email address."
        form.status.color = "error"
        return form.email.focus()
    form.status.text = ""
    form.sign_in.enabled = False
    form.progress.value = 0
    form.progress.show()
    form.ticker.running = True


def ticker_tick(form, event):
    """Runs every ``interval`` milliseconds while ticker is enabled."""
    form.progress.value += 4
    if form.progress.value >= 100:
        form.ticker.running = False
        form.progress.hide()
        form.status.color = "success"
        form.status.text = f"Signed in as {form.email.text}"
        form.sign_in.enabled = True


def password_submit(form, event):
    """Runs when Enter is pressed in password."""
    return sign_in_click(form, event)


def form_load(form, event):
    """Runs once when login opens."""
    form.status.text = "Tip: any email works in this demo."
    return form.email.focus()
