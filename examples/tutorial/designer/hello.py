"""Event handlers for the hello form (tutorial: Your first window in Pyzed Design).

    pyzed run examples/tutorial/designer/hello.pzform      # run it
    pyzed design examples/tutorial/designer/hello.pzform   # open it in the designer

Each function receives the running ``form`` (controls are attributes: ``form.your_name.text``)
and an ``event`` with ``event.sender``, ``event.name`` and ``event.value``.
"""


def greet_click(form, event):
    """Runs when greet is clicked."""
    name = form.your_name.text.strip() or "stranger"
    form.headline.text = f"Hello, {name}!"
    form.subtitle.text = "Change the name and press the button again."


def your_name_submit(form, event):
    """Runs when Enter is pressed in your_name: the same as clicking the button."""
    return greet_click(form, event)
