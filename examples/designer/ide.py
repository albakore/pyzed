"""Event handlers for the mini IDE: a Dock with panels on its sides, like Zed.

workspace (Dock) holds the panels: Explorer and Outline on the left, Terminal and Problems at the
bottom, Settings on the right and the Editor in the center. Drag a tab to another side, or drag a
side's inner edge, and the workspace_layout handler logs the new layout in the terminal.
"""

FILES = {
    "src/main.py": 'from app import greet\n\n\ndef main():\n    print(greet("Pyzed"))\n',
    "src/app.py": 'def greet(name):\n    return f"Hello, {name}!"\n',
    "src/forms.py": "# forms made in Pyzed Design\n",
    "README.md": "# Mini IDE\n\nA Dock made in Pyzed Design.\n",
    "pyproject.toml": '[project]\nname = "mini-ide"\nversion = "0.1.0"\n',
}


def log(form, text):
    """Adds a line to the terminal."""
    form.log.text += text + "\n"


def form_load(form, event):
    """Runs once when ide opens."""
    log(form, "Double-click a file in the Explorer to open it.")


def files_change(form, event):
    """Runs when an item of files is selected (``event.value`` is its path)."""
    if event.value in FILES:
        files_open(form, event)


def files_open(form, event):
    """Runs when an item without children of files is double-clicked (``event.value`` is its path)."""
    form.code.text = FILES.get(event.value, "")
    form.code.language = "md" if event.value.endswith(".md") else "toml" if event.value.endswith(".toml") else "py"
    form.editor.title = event.value.rsplit("/", 1)[-1]
    log(form, f"Opened {event.value}")


def workspace_layout(form, event):
    """Runs when a panel of workspace is moved, resized or switched (``event.value`` is the layout)."""
    sizes = ", ".join(f"{side} {size:.0f}" for side, size in event.value.get("sizes", {}).items())
    moved = ", ".join(f"{panel} → {side}" for panel, side in event.value.get("positions", {}).items())
    log(form, f"Layout: {moved or 'panels where they started'}; sizes {sizes}")


def wrap_change(form, event):
    """Runs when the value of wrap changes (``event.value``)."""
    form.code.wrap = event.value


def numbers_change(form, event):
    """Runs when the value of numbers changes (``event.value``)."""
    form.code.line_numbers = event.value
