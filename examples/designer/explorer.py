"""Event handlers for the project explorer: the tree, breadcrumbs, tabs, table and the other newer controls.

files (Tree view) picks a file and fills the breadcrumbs, path (Breadcrumbs) goes back up, pages
(Tab bar) switches between the listing, a preview and a log and can close its tabs, listing (Table)
sorts by any column, share (Split button) shows a QR code from its menu, the filter chips can be
removed, and unread (Counter badge) counts what has not been looked at yet.
"""

import pyzed as pz

PAGES = {"Details": "listing", "Preview": "preview", "Output": "log"}


def say(form, text):
    """Shows ``text`` in the status line and adds it to the log."""
    form.status.text = text
    form.log.text += text + "\n"


def show_page(form, tab):
    """Shows the control of the tab called ``tab`` and hides the others."""
    for name, control in PAGES.items():
        form[control].visible = name == tab


def crumbs(form):
    """The parts of the breadcrumbs as a list (the designer stores them one per line)."""
    parts = form.path.parts
    return parts.splitlines() if isinstance(parts, str) else list(parts)


def form_load(form, event):
    """Runs once when explorer opens."""
    say(form, "Pick a file in the tree, or double-click a row of the table.")


def files_change(form, event):
    """Runs when an item of files is selected (``event.value`` is its path, such as ``"Docs/README.md"``)."""
    form.path.parts = ["Project", *event.value.split("/")]
    rows = form.listing.data.splitlines()[1:]
    names = [row.split(",")[0].strip() for row in rows]
    name = event.value.rsplit("/", 1)[-1]
    form.listing.selected = names.index(name) if name in names else None
    say(form, f"Selected {event.value}")


def files_toggle(form, event):
    """Runs when an item of files is folded or unfolded (``event.value`` is its path)."""
    state = "Opened" if event.value in form.files.expanded.splitlines() else "Folded"
    say(form, f"{state} {event.value}")


def files_open(form, event):
    """Runs when an item without children of files is double-clicked (``event.value`` is its path)."""
    path = form.files.selected
    form.preview.title = path.rsplit("/", 1)[-1]
    form.preview.text = f"A preview of {path} would go here."
    form.preview.icon = "file-text"
    form.pages.selected = "Preview"
    show_page(form, "Preview")


def path_click(form, event):
    """Runs when a part of path is clicked (``event.value`` is its index, 0 for the first)."""
    parts = crumbs(form)[1:event.value + 1]
    form.path.parts = ["Project", *parts]
    form.files.selected = "/".join(parts)
    say(form, "Back to " + ("/".join(parts) or "the project"))


def pages_change(form, event):
    """Runs when the value of pages changes (``event.value`` is the tab's name)."""
    show_page(form, event.value)


def pages_close(form, event):
    """Runs after a tab of pages is closed with its x (``event.value`` is its name)."""
    show_page(form, form.pages.selected)
    say(form, f"Closed the {event.value} tab")


def listing_change(form, event):
    """Runs when a row of listing is clicked (``event.value`` is its index)."""
    row = form.listing.data.splitlines()[event.value + 1].split(",")
    say(form, f"{row[0].strip()}: {row[3].strip()}, {row[2].strip()}")


def listing_open(form, event):
    """Runs when a row of listing is double-clicked (``event.value`` is its index)."""
    row = form.listing.data.splitlines()[event.value + 1].split(",")
    folder, name = row[1].strip(), row[0].strip()
    path = f"{folder}/{name}" if folder else name
    form.files.selected = path
    form.path.parts = ["Project", *path.split("/")]
    files_open(form, event)


def listing_sort(form, event):
    """Runs when a column header of listing is clicked to sort it (``event.value`` is its title)."""
    order = "descending" if form.listing.descending else "ascending"
    say(form, f"Sorted by {event.value}, {order}")


def share_click(form, event):
    """Runs when the main part of share is clicked."""
    form.link_qr.visible = not form.link_qr.visible


def share_choose(form, event):
    """Runs when an item of the menu of share is chosen (``event.value`` is its text)."""
    if event.value == "Copy link":
        say(form, "Link copied: " + form.link_qr.data)
        return pz.Command.copy(form.link_qr.data)
    form.link_qr.visible = event.value == "Show QR code"
    return None


def view_change(form, event):
    """Runs when a button of view is pressed (``event.value`` is its value)."""
    form.listing.striped = event.value == "details"
    say(form, f"{event.value.capitalize()} view")


def markdown_chip_click(form, event):
    """Runs when markdown_chip is clicked."""
    form.markdown_chip.selected = not form.markdown_chip.selected


def markdown_chip_remove(form, event):
    """Runs when the x of markdown_chip is clicked."""
    form.markdown_chip.hide()
    say(form, "Removed the Markdown filter")


def image_chip_click(form, event):
    """Runs when image_chip is clicked."""
    form.image_chip.selected = not form.image_chip.selected


def image_chip_remove(form, event):
    """Runs when the x of image_chip is clicked."""
    form.image_chip.hide()
    say(form, "Removed the Images filter")


def unread_click(form, event):
    """Runs when unread is clicked."""
    form.unread.count = 0
    say(form, "All caught up")


def team_click(form, event):
    """Runs when team is clicked."""
    say(form, "Shared with " + ", ".join(form.team.people.splitlines()))


def sync_click(form, event):
    """Runs when sync is clicked."""
    online = form.sync.color == "success"
    form.sync.color, form.sync.text = ("warning", "Offline") if online else ("success", "Synced")


def zoom_change(form, event):
    """Runs when the value of zoom changes (``event.value``)."""
    form.status.text = f"Zoom {event.value:.0f}%"


def zoom_release(form, event):
    """Runs when the user lets go of zoom."""
    say(form, f"Zoom set to {form.zoom.value:.0f}%")
