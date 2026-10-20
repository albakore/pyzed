"""Event handlers for the sign-up form (tutorial: Data binding and validation).

    pyzed run examples/tutorial/designer/signup.pzform

The controls are bound to fields of ``form.data`` (Properties → Data → Bind to) and carry their
validation rules, so the handler only has to call ``form.validate()`` and read ``form.data``.
"""


def create_click(form, event):
    """Runs when create is clicked."""
    if not form.validate():  # checks every rule and shows the messages under the controls
        form.status.color = "error"
        form.status.text = f"{len(form.errors)} field(s) need your attention."
        return
    data = form.data  # {"name": ..., "email": ..., "password": ..., "age": ..., "terms": True}
    print("New account:", {k: v for k, v in data.items() if k != "password"})
    form.status.color = "success"
    form.status.text = f"Welcome aboard, {data['name']}!"
