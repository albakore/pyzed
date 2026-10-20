"""Event handlers for the contact form (tutorial: A form with inputs and a button).

    pyzed run examples/tutorial/designer/contact.pzform

Each function receives the running ``form`` and an ``event`` (``event.value`` holds the new
value of a ``change`` event).
"""

LIMIT = 500


def form_load(form, event):
    """Runs once when contact opens: put the cursor in the first box."""
    return form.your_name.focus()


def message_change(form, event):
    """Runs on every keystroke in message: update the character counter."""
    count = len(event.value)
    form.counter.text = f"{count} / {LIMIT}"
    form.counter.color = "error" if count > LIMIT else "text_muted"


def send_click(form, event):
    """Runs when send is clicked: check the fields, then 'send' the message."""
    if not form.your_name.text.strip():
        form.status.color = "error"
        form.status.text = "Please tell us your name."
        return form.your_name.focus()
    if "@" not in form.email.text:
        form.status.color = "error"
        form.status.text = "That email does not look right."
        return form.email.focus()
    if len(form.message.text) > LIMIT:
        form.status.color = "error"
        form.status.text = f"Keep the message under {LIMIT} characters."
        return None
    # print() shows up in the designer's console (and in the terminal)
    print(f"New {form.topic.selected.lower()} from {form.email.text}: {form.message.text!r}")
    form.status.color = "success"
    form.status.text = f"Thanks, {form.your_name.text.split()[0]}! We got your message."
    form.message.text = ""
    form.counter.text = f"0 / {LIMIT}"
    return None
