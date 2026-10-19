"""English descriptions of the public API. Used by gen_api.py.

Each entry: ``"pyzed.name": {"desc": ..., "params": {...}, "example": ..., "extra": ...}``.
Parameters missing from ``params`` are looked up in ``COMMON``.
"""

COMMON = {
    "content": "Content: a `Widget`, a string or a number (converted to text).",
    "children": "List of children. Nested lists are flattened and `None` and `False` are ignored, so you can write `cond and widget`.",
    "width": 'Width: pixels, `"fill"`, `"shrink"` or `"fill:N"` (proportion).',
    "height": 'Height: pixels, `"fill"`, `"shrink"` or `"fill:N"` (proportion).',
    "max_width": "Maximum width in pixels.",
    "max_height": "Maximum height in pixels.",
    "padding": "Inner padding: `8`, `(vertical, horizontal)` or `(top, right, bottom, left)`.",
    "spacing": "Space between children, in pixels.",
    "align": 'Alignment of the children on the cross axis: `"start"`, `"center"` or `"end"`.',
    "align_x": 'Horizontal alignment: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`.',
    "align_y": 'Vertical alignment: `"start"`/`"top"`, `"center"`, `"end"`/`"bottom"`.',
    "clip": "Clips content that overflows the bounds.",
    "bg": 'Background color (`"#rrggbb[aa]"`, `(r, g, b[, a])` or `"transparent"`).',
    "color": "Text or icon color.",
    "border_color": "Border color.",
    "border_width": "Border width in pixels.",
    "radius": "Corner radius: a number or `(top_left, top_right, bottom_right, bottom_left)`.",
    "shadow": "Shadow: `(color, (dx, dy), blur)`.",
    "hover_bg": "Background on hover.",
    "hover_color": "Text color on hover.",
    "hover_border_color": "Border color on hover.",
    "pressed_bg": "Background while pressed.",
    "disabled_color": "Text color when disabled.",
    "on_press": "Message or callable sent on press. `None` disables the control.",
    "theme": "Theme to use instead of the current one (`pyzed.theme.current()`).",
    "id": "Stable identifier used to focus or scroll it with a `Command`.",
    "icon": "Name of a Lucide icon (`pyzed icons` lists them).",
    "icon_color": "Icon color: a theme token or a hex color.",
    "keys": 'Shortcut shown at the end, Zed style: `"ctrl-s"`, `"cmd-k cmd-s"`.',
    "selected": "Marks it as selected.",
    "disabled": "Disables it (ignores clicks).",
    "size": "Size.",
    "label": "Label text.",
    "title": "Title.",
    "on_dismiss": "Message or callable sent on close.",
    "actions": "Extra widgets (usually buttons) shown as actions.",
    "start": "Widgets at the start (left).",
    "end": "Widgets at the end (right).",
    "accent": "Accent color (active part).",
    "knob_color": "Knob color.",
    "check_color": "Check mark color.",
    "text_size": "Label text size.",
    "on_toggle": "Callable that receives the new `bool` (or a message to send).",
    "on_change": "Callable that receives the new value.",
    "on_select": "Callable that receives the chosen item.",
    "on_input": "Callable that receives the new text on every keystroke.",
    "on_submit": "Message or callable sent when Enter is pressed.",
    "placeholder": "Hint text shown when empty.",
    "on_close": "Message or callable sent when the X is pressed.",
    "checked": "Current state.",
    "value": "Current value.",
    "variant": "Visual variant.",
    "tint": 'Semantic color: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` or a token.',
    "app": "An `App` instance (or the class, which is instantiated with no arguments).",
    "path": "File path.",
    "mono": "Uses the monospace font (IBM Plex Mono).",
    "indent": "Left indentation, in pixels.",
    "item_height": "Height of each row.",
    "message": "Any Python value, or a callable.",
}

_SIZES = '`"xs"`, `"sm"`, `"md"` or `"lg"`.'

PAGES = [
    # ------------------------------------------------------------------ App
    {
        "slug": "app",
        "title": "App and running",
        "description": "The App class, run, screenshot, post and load_font.",
        "order": 1,
        "intro": """
            Everything you need to start an application. See also the
            [architecture](/pyzed/guides/architecture/) guide.
        """,
        "sections": [
            ("Application", {
                "pyzed.App": {
                    "desc": """
Base class for applications (Elm architecture, like Iced). Override `view()` and, if you use
messages, `update(message)`. State lives in instance attributes.

| Class attribute | Default | Description |
| --- | --- | --- |
| `title` | `"Pyzed"` | Window title. Can be a callable (or property) that returns the text. |
| `size` | `(1280, 800)` | Initial window size. |
| `min_size` | `None` | Minimum size. |
| `resizable` | `True` | Whether the window can be resized. |
| `decorations` | `True` | Shows the system frame and buttons. |
| `scale` | `1.0` | Scale factor for the whole interface. |
| `font_size` | `14` | Default text size. |
| `theme` | `themes.ONE_DARK` | Current theme. Change it at any time. |

| Method | Description |
| --- | --- |
| `view()` | Returns the widget tree. Called after every message. |
| `update(message)` | Receives messages. Can return a `Command`, a list of them or another message. |
| `on_start()` | Optional. Runs once at startup; can return a `Command`. |
| `on_key(combo)` | Optional. Receives every key as `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `run()` | Opens the window and blocks until it is closed. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renders the current state to a PNG without a window. |

If `view()` raises an exception, the window shows the traceback instead of closing.
""",
                    "no_signature": True,
                },
                "pyzed.run": {
                    "desc": "Runs an app: opens the window and blocks until it is closed. Accepts the class or an instance.",
                },
                "pyzed.screenshot": {
                    "desc": "Renders `app` offscreen (no window, no GPU) and saves a PNG. Useful for tests and documentation.",
                    "params": {
                        "path": "Path of the output PNG.",
                        "size": "Logical size `(width, height)`. Defaults to `app.size`.",
                        "scale": "PNG scale factor (2.0 = retina).",
                        "wait": "Seconds to wait before capturing (for `on_start` tasks).",
                    },
                    "example": """
                        pz.screenshot(MyApp, "docs/ui.png", size=(800, 600))
                    """,
                },
                "pyzed.post": {
                    "desc": "Sends a message to the running app from **any thread**. Raises `RuntimeError` if no app is running.",
                    "example": """
                        def worker():
                            for i in range(100):
                                time.sleep(0.05)
                                pz.post(("progress", i / 100))

                        threading.Thread(target=worker, daemon=True).start()
                    """,
                },
                "pyzed.load_font": {
                    "desc": 'Loads an extra font (path to a `.ttf`/`.otf` or its bytes) so you can use it by family name: `text("hello", font="JetBrains Mono")`.',
                    "params": {"source": "Path to the font file, or `bytes`."},
                },
            }),
        ],
    },
    # ------------------------------------------------------------- Command
    {
        "slug": "command",
        "title": "Command",
        "description": "Side effects returned by update and callbacks.",
        "order": 2,
        "intro": """
            A `Command` is an effect the runtime performs for you. Return it from `update`,
            `on_start`, `on_key` or any callback. You can also return a list or a tuple of
            commands. See the [commands and tasks](/pyzed/guides/commands/) guide.

            ```python
            from pyzed import Command

            def on_key(self, combo):
                if combo == "ctrl-p":
                    self.finder_open = True
                    return Command.focus("finder")
            ```
        """,
        "sections": [
            ("Static methods", {
                "pyzed.Command": {
                    "desc": "The command class. Don't instantiate it directly: use its static methods.",
                    "no_signature": True,
                },
                "pyzed.Command.exit": {"desc": "Closes the application."},
                "pyzed.Command.focus": {
                    "desc": "Focuses the `text_input` (or editor) with that `id`.",
                    "params": {"id": "The `id` you passed to the widget."},
                },
                "pyzed.Command.set_editor_text": {
                    "desc": "Replaces the content of the `code_editor` with that `id`. Editors are uncontrolled: `text` is only the initial value.",
                    "params": {"id": "The editor's `id`.", "text": "The new text."},
                },
                "pyzed.Command.set_editor_cursor": {
                    "desc": "Moves the editor cursor (line and column start at 1). Works even if the editor hasn't been drawn yet.",
                    "params": {"id": "The editor's `id`.", "line": "Line (from 1).", "column": "Column (from 1)."},
                },
                "pyzed.Command.scroll_to_end": {
                    "desc": "Scrolls the `scrollable` with that `id` to the end.",
                    "params": {"id": "The scrollable's `id`."},
                },
                "pyzed.Command.batch": {
                    "desc": "Runs several commands.",
                    "params": {"commands": "List of `Command`."},
                },
                "pyzed.Command.message": {
                    "desc": "Sends `message` to `update` again on the next cycle.",
                },
                "pyzed.Command.perform": {
                    "desc": "Runs `function()` on a background thread and delivers the result to `then(result)` on the UI thread. Without `then`, the result is sent to `update`. If `function` raises, the error is printed.",
                    "params": {
                        "function": "Function with no arguments that does the slow work.",
                        "then": "Callable that receives the result (or `None` to send it to `update`).",
                    },
                    "example": """
                        def load(self):
                            self.loading = True
                            return Command.perform(lambda: requests.get(URL).json(), self.received)

                        def received(self, data):
                            self.loading, self.data = False, data
                    """,
                },
            }),
        ],
    },
    # ------------------------------------------------------------- Widgets
    {
        "slug": "widgets",
        "title": "Core widgets",
        "description": "Pyzed's native widgets: layout, text, controls, editor, svg and icons.",
        "order": 3,
        "intro": """
            The core widgets are implemented in Rust and imported from `pyzed`. They are the
            building blocks of the [components](/pyzed/components/overview/).
            See the [layout](/pyzed/guides/layout/) guide for sizes, padding and colors.
        """,
        "sections": [
            ("Widget", {
                "pyzed.Widget": {
                    "desc": "An immutable node of the UI tree, implemented in Rust. Returned by every widget and component function. Wherever a child is expected you can also pass a string or a number (converted to `text`) or `None` (ignored).",
                    "no_signature": True,
                },
            }),
            ("Layout", {
                "pyzed.column": {
                    "desc": "Stacks its children vertically.",
                    "example": 'pz.column([pz.text("One"), pz.text("Two")], spacing=8, padding=16)',
                },
                "pyzed.row": {
                    "desc": "Lays out its children horizontally.",
                    "example": 'pz.row([ui.label("Name"), pz.hspace(), ui.button("OK", "ok")], align="center")',
                },
                "pyzed.container": {
                    "desc": "Wraps a child to give it size, alignment, background, border, radius and shadow.",
                    "params": {
                        "content": "The child (or `None` for an empty box, handy as a colored rectangle).",
                        "center": "Centers the content on both axes and fills all the space.",
                    },
                },
                "pyzed.center": {
                    "desc": "Centers `content` in all the available space. Equivalent to `container(content, center=True)`.",
                    "params": {"kwargs": "Any `container` parameter."},
                },
                "pyzed.scrollable": {
                    "desc": "Makes its content scrollable.",
                    "params": {
                        "direction": '`"vertical"`, `"horizontal"` or `"both"`.',
                        "anchor_bottom": "Keeps the scroll pinned to the end (logs, terminals, chats).",
                        "rail": "Scrollbar rail color.",
                        "scroller": "Scroller color.",
                        "scroller_hover": "Scroller color on hover.",
                        "scrollbar_width": "Scrollbar width.",
                        "scroller_width": "Scroller width (defaults to the scrollbar's).",
                        "margin": "Margin between the scrollbar and the content.",
                    },
                },
                "pyzed.stack": {
                    "desc": "Layers its children on top of each other, the last one on top. The basis for layers, modals and notifications.",
                },
                "pyzed.space": {
                    "desc": "Empty space of a given size.",
                },
                "pyzed.hspace": {
                    "desc": 'Flexible horizontal gap: pushes the siblings in a row towards the edges.',
                },
                "pyzed.vspace": {
                    "desc": "Flexible vertical gap: pushes the siblings in a column towards the edges.",
                },
                "pyzed.rule": {
                    "desc": "A horizontal (or vertical) divider line.",
                    "params": {"vertical": "Vertical line instead of horizontal.", "thickness": "Thickness in pixels."},
                    "extra": 'A horizontal rule fills the full width. Inside a column that should shrink, set `width="shrink"` on the column.',
                },
            }),
            ("Text and icons", {
                "pyzed.text": {
                    "desc": "A piece of text.",
                    "params": {
                        "size": "Font size.",
                        "font": '`"sans"` (IBM Plex Sans), `"mono"`, `"icons"`, `"serif"` or the name of a family loaded with `load_font`.',
                        "weight": '`"thin"`, `"light"`, `"normal"`, `"medium"`, `"semibold"`, `"bold"`, `"black"` or a number (100–900).',
                        "italic": "Italic.",
                        "line_height": "Line height relative to the size (1.0, 1.5…).",
                        "wrap": "Line wrapping. With `False` the text doesn't wrap.",
                    },
                },
                "pyzed.icon": {
                    "desc": "A [Lucide](https://lucide.dev) icon. `color` defaults to the surrounding text color.",
                    "params": {"name": "Icon name (`pyzed icons` lists them).", "size": "Size in pixels.", "color": "Color."},
                    "example": 'pz.icon("folder", size=16, color="#74ade8")',
                },
                "pyzed.svg": {
                    "desc": "An SVG image.",
                    "params": {
                        "source": "Path to an `.svg`, the SVG code as a string (starting with `<`) or `bytes`.",
                        "color": "If given, tints the whole SVG with that color (useful for monochrome icons).",
                    },
                },
            }),
            ("Interaction", {
                "pyzed.button": {
                    "desc": "A button with no predefined style. For the Zed button use `ui.button`.",
                    "params": {"content": "Button content."},
                },
                "pyzed.text_input": {
                    "desc": "A controlled text field: it shows `value` and notifies you of changes through `on_input`. For the Zed style use `ui.input`.",
                    "params": {
                        "value": "Current text.",
                        "size": "Font size.",
                        "font": "Font family.",
                        "secure": "Hides the text (passwords).",
                        "icon": "Icon character (use `pyzed.icons.glyph(name)`).",
                        "icon_size": "Icon size.",
                        "focus_border_color": "Border color when focused.",
                        "placeholder_color": "Placeholder color.",
                        "selection_color": "Selection color.",
                        "icon_color": "Icon color.",
                    },
                },
                "pyzed.mouse_area": {
                    "desc": "Detects mouse events over its content.",
                    "params": {
                        "on_press": "Left click (on press).",
                        "on_release": "On releasing the left button.",
                        "on_right_press": "Right click (context menus).",
                        "on_double_click": "Double click.",
                        "on_enter": "The mouse enters.",
                        "on_exit": "The mouse leaves.",
                        "cursor": '`"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"crosshair"`, `"not-allowed"`, `"resize-horizontal"`, `"resize-vertical"`, `"move"` or `"default"`.',
                    },
                },
                "pyzed.hover": {
                    "desc": "Shows `top` over `base` only while the mouse is over it (for example, a tab's close button).",
                    "params": {"base": "Widget underneath.", "top": "Widget that appears on hover."},
                },
                "pyzed.opaque": {
                    "desc": "Makes a widget block the mouse for whatever is below it in a `stack`.",
                },
                "pyzed.tooltip": {
                    "desc": "Shows `tip` next to `content` on hover. `ui.tooltip` adds the Zed style.",
                    "params": {
                        "tip": "Tooltip content.",
                        "position": '`"top"`, `"bottom"`, `"left"`, `"right"` or `"cursor"`.',
                        "gap": "Distance from the content.",
                    },
                },
            }),
            ("Controls", {
                "pyzed.checkbox": {"desc": "A checkbox.", "params": {"size": "Box size."}},
                "pyzed.toggler": {"desc": "An on/off switch.", "params": {"size": "Switch height."}},
                "pyzed.slider": {
                    "desc": "A slider between `min` and `max`.",
                    "params": {"min": "Minimum.", "max": "Maximum.", "step": "Step."},
                },
                "pyzed.progress_bar": {
                    "desc": "A progress bar.",
                    "params": {"min": "Minimum.", "max": "Maximum.", "radius": "Corner radius."},
                },
            }),
            ("Code editor", {
                "pyzed.code_editor": {
                    "desc": """
A code editor with syntax highlighting, line numbers and git markers, based on Iced's
`text_editor`. It is **uncontrolled**: `text` is only the initial value for that `id`; the
text, cursor and history live in Rust. Use `Command.set_editor_text` to replace it.
For the Zed style use [`ui.editor`](/pyzed/components/code/).
""",
                    "params": {
                        "id": "Identifies the buffer. Reuse it to keep state across renders.",
                        "text": "Initial text.",
                        "language": 'Language extension or name (`"py"`, `"rs"`, `"json"`…).',
                        "size": "Font size.",
                        "line_height": "Line height in pixels.",
                        "font": "Family (monospace by default).",
                        "syntax": "Map of TextMate scopes to colors (provided by `Theme.syntax_scopes()`).",
                        "selection_color": "Selection color.",
                        "placeholder_color": "Placeholder color.",
                        "gutter": "Shows line numbers.",
                        "gutter_color": "Line number color.",
                        "gutter_active_color": "Color of the cursor line's number.",
                        "gutter_width": "Gutter width (automatic by default).",
                        "markers": "`{line: color}` for git markers in the gutter (lines from 1).",
                        "wrap": "Line wrapping.",
                        "on_change": "Callable that receives the full text after each edit.",
                        "on_cursor": "Callable that receives `(line, column)`, from 1.",
                    },
                },
            }),
        ],
    },
    # ------------------------------------------------------------------ UI
    {
        "slug": "ui",
        "title": "Components (pyzed.ui)",
        "description": "Reference for every Zed-style component.",
        "order": 4,
        "intro": """
            Signatures and parameters of every component. To see them with images and examples,
            go to the [Components](/pyzed/components/overview/) section.

            They are all functions that return a `Widget` and read their colors from the current theme.
            Color parameters accept a theme **token** (`"accent"`, `"text_muted"`,
            `"error"`…) or a hex color.
        """,
        "sections": [
            ("Basics", {
                "pyzed.ui.label": {
                    "desc": "Text with a theme color.",
                    "params": {
                        "color": 'Theme token or hex color. Defaults to `"text"`.',
                        "size": '`"xs"` (11), `"sm"` (12), `"md"` (13.5), `"lg"` (16), `"xl"` (20), `"2xl"` (26) or a number.',
                        "weight": 'Weight: `"medium"`, `"semibold"`, `"bold"`…',
                        "italic": "Italic.",
                        "wrap": "Line wrapping.",
                        "kwargs": "Passed to `pyzed.text`.",
                    },
                },
                "pyzed.ui.muted": {"desc": 'A `label` with the `"text_muted"` color.', "params": {"kwargs": "Same as `label`."}},
                "pyzed.ui.heading": {
                    "desc": "A semibold heading.",
                    "params": {"level": "1 (26 px), 2 (20 px), 3 (16 px) or 4 (13.5 px).", "kwargs": "Same as `label`."},
                },
                "pyzed.ui.button": {
                    "desc": "The Zed button.",
                    "params": {
                        "content": "Text or widget.",
                        "icon_position": '`"start"` or `"end"`.',
                        "variant": '`"filled"`, `"ghost"`, `"subtle"`, `"outline"`, `"solid"`, `"tinted"`, or a semantic color: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"`.',
                        "tint": "Color for the `solid` and `tinted` variants.",
                        "size": _SIZES,
                        "full_width": "Fills the full width.",
                        "style": "Any `pyzed.button` style parameter (`bg`, `hover_bg`, `color`…).",
                    },
                },
                "pyzed.ui.icon_button": {
                    "desc": "A square button with just an icon (Zed's `IconButton`).",
                    "params": {
                        "name": "Icon name.",
                        "size": _SIZES,
                        "variant": 'As in `ui.button`. Defaults to `"ghost"`.',
                        "color": "Icon color.",
                        "tooltip": "Tooltip text.",
                    },
                },
                "pyzed.ui.badge": {
                    "desc": "A small pill for statuses and counters.",
                    "params": {"variant": '`"soft"`, `"solid"` or `"outline"`.'},
                },
                "pyzed.ui.indicator": {
                    "desc": "A colored dot (status, unsaved changes, presence).",
                    "params": {"color": "Token or color.", "size": "Diameter."},
                },
                "pyzed.ui.kbd": {
                    "desc": 'Draws a shortcut as keys: `"ctrl-shift-p"`, `"cmd-k cmd-s"`. Uses symbols on macOS (⌘⇧P) and words elsewhere.',
                    "params": {"keys": "The shortcut.", "size": '`"xs"` or `"sm"`.'},
                },
                "pyzed.ui.format_keys": {
                    "desc": 'Splits a shortcut into labels per chord: `format_keys("ctrl-shift-p") == [["Ctrl", "Shift", "P"]]`. The style is controlled by `pyzed.ui.base.KEY_STYLE` (`"auto"`, `"symbols"` or `"words"`).',
                    "params": {"keys": "The shortcut."},
                },
                "pyzed.ui.avatar": {
                    "desc": "A round avatar with initials.",
                    "params": {
                        "initials": "Initials (the first two are used).",
                        "color": "Background color.",
                        "size": "Diameter.",
                        "index": "Picks a collaborator color from the theme (`theme.players`).",
                    },
                },
                "pyzed.ui.tooltip": {
                    "desc": "Wraps `content` with a Zed-style tooltip, optionally with its shortcut.",
                    "params": {"text": "Tooltip text.", "position": '`"top"`, `"bottom"`, `"left"`, `"right"` or `"cursor"`.'},
                },
                "pyzed.ui.divider": {
                    "desc": "A divider line in the theme color.",
                    "params": {"vertical": "Vertical instead of horizontal."},
                },
                "pyzed.ui.card": {
                    "desc": "A bordered surface to group content, with an optional title and actions.",
                    "params": {"padding": "Inner padding."},
                },
            }),
            ("Forms", {
                "pyzed.ui.input": {
                    "desc": "A text field.",
                    "params": {
                        "value": "Current text.",
                        "size": '`"sm"`, `"md"` or `"lg"`.',
                        "secure": "Hides the text.",
                        "borderless": "No border or background (as in the command palette).",
                    },
                },
                "pyzed.ui.search_input": {
                    "desc": "An `input` with a magnifying glass icon.",
                    "params": {"value": "Current text.", "kwargs": "Same as `input`."},
                },
                "pyzed.ui.switch": {"desc": "An on/off switch."},
                "pyzed.ui.checkbox": {"desc": "A checkbox."},
                "pyzed.ui.slider": {
                    "desc": "A slider.",
                    "params": {"min": "Minimum.", "max": "Maximum.", "step": "Step."},
                },
                "pyzed.ui.progress": {
                    "desc": "A thin progress bar.",
                    "params": {"max": "Maximum value.", "height": "Thickness."},
                },
                "pyzed.ui.segmented": {
                    "desc": "A group of mutually exclusive buttons (Zed's `ToggleButtonGroup`).",
                    "params": {"options": "List of options (strings).", "selected": "The active option."},
                },
                "pyzed.ui.field": {
                    "desc": "A form row: title and description on the left, control on the right (like Zed's settings).",
                    "params": {"control": "The control (switch, input…).", "description": "Help text."},
                },
            }),
            ("Lists, tree and menus", {
                "pyzed.ui.list_item": {
                    "desc": "A list row (Zed's `ListItem`): icon, text and a slot at the end.",
                    "params": {
                        "content": "Text or widget.",
                        "focused": "Draws a focus border.",
                        "height": "Row height.",
                        "color": "Text color.",
                        "inset": "With margin and rounded corners (menus, palettes).",
                        "on_right_press": "Right click.",
                    },
                },
                "pyzed.ui.list_header": {"desc": "A section header for lists."},
                "pyzed.ui.TreeNode": {
                    "desc": 'A file or folder for `ui.tree`. Folders have `children` (a list). `status` is `"modified"`, `"created"`, `"deleted"`, `"conflict"` or `"ignored"`. `TreeNode.from_paths(paths, status=None)` builds the tree from paths like `"src/main.rs"`, with folders first and the git status propagated to folders.',
                    "params": {
                        "name": "Display name.",
                        "children": "Children (`None` for a file).",
                        "status": "Git status.",
                    },
                },
                "pyzed.ui.tree": {
                    "desc": "A collapsible file tree (Zed's project panel).",
                    "params": {
                        "nodes": "List of `TreeNode`.",
                        "expanded": "Set of open folder ids.",
                        "selected": "Id of the selected node.",
                        "on_toggle": "Called with the id of the clicked folder.",
                        "on_select": "Called with the id of the clicked file.",
                    },
                },
                "pyzed.ui.MenuItem": {
                    "desc": "An entry of `ui.menu`.",
                    "params": {"danger": "In red (destructive actions).", "checked": "Shows a check mark (`True`/`False`) or nothing (`None`)."},
                },
                "pyzed.ui.menu": {
                    "desc": "A floating context menu. Use `ui.SEPARATOR` between groups; a plain string is a header.",
                    "params": {"items": "List of `MenuItem`, `ui.SEPARATOR` or strings."},
                },
                "pyzed.ui.SEPARATOR": {"desc": "Separator for `ui.menu`.", "no_signature": True},
            }),
            ("Navigation", {
                "pyzed.ui.Tab": {
                    "desc": "A tab. `Tab.for_file(path, **kwargs)` creates it with the file's name and icon.",
                    "params": {
                        "dirty": "Unsaved changes (shows a dot).",
                        "preview": "Preview tab (in italics).",
                        "status": "Git status (tints the name).",
                    },
                },
                "pyzed.ui.tab": {
                    "desc": "A single tab. You normally use `tab_bar`.",
                    "params": {"item": "The `Tab`.", "active": "Whether it is the active one.", "height": "Height."},
                },
                "pyzed.ui.tab_bar": {
                    "desc": "A row of tabs with optional controls at the start and end (navigation, split, +). The close button appears on the active tab and on hover.",
                    "params": {"tabs": "List of `Tab`.", "active": "Id of the active tab.", "height": "Height."},
                },
                "pyzed.ui.breadcrumbs": {
                    "desc": "`src › main.rs › fn main`. Parts can be strings or `(icon, text)` tuples.",
                    "params": {"parts": "The parts.", "separator": "Separator.", "on_press": "Called with the index of the clicked part."},
                },
                "pyzed.ui.toolbar": {
                    "desc": "The bar below the tabs: breadcrumbs on the left and buffer actions on the right.",
                    "params": {"height": "Height."},
                },
            }),
            ("Workspace", {
                "pyzed.ui.workspace": {
                    "desc": "The layout of a Zed window: title bar, left, right and bottom docks, center and status bar. Pass `None` to hide a dock.",
                    "params": {
                        "center": "Central content (usually tabs + editor).",
                        "title_bar": "Title bar (`ui.title_bar`).",
                        "left": "Left dock.",
                        "right": "Right dock.",
                        "bottom": "Bottom dock.",
                        "status_bar": "Status bar (`ui.status_bar`).",
                        "left_width": "Width of the left dock.",
                        "right_width": "Width of the right dock.",
                        "bottom_height": "Height of the bottom dock.",
                        "on_resize": "Called with `(side, size)` when the user finishes resizing a dock by dragging its inner border.",
                    },
                },
                "pyzed.ui.title_bar": {
                    "desc": "The top bar: project and branch pickers on the left, account and actions on the right.",
                    "params": {"center": "Centered widget.", "height": "Height."},
                },
                "pyzed.ui.title_button": {
                    "desc": "A compact button for the title bar (`pyzed ▾`, `main`…).",
                    "params": {"content": "Text.", "muted": "Muted text.", "chevron": "Adds a ▾."},
                },
                "pyzed.ui.status_bar": {"desc": "The bottom status bar.", "params": {"height": "Height."}},
                "pyzed.ui.status_item": {
                    "desc": "An icon and/or text in the status bar (diagnostics, cursor position, language…).",
                    "params": {"content": "Text.", "tooltip": "Tooltip text."},
                },
                "pyzed.ui.panel": {
                    "desc": "A dockable panel. `side` decides which edge gets the border line; with a numeric `width` (`height` for the bottom) that border can be dragged to resize it.",
                    "params": {
                        "header": "Header (`ui.panel_header`).", "side": '`"left"`, `"right"` or `"bottom"`.',
                        "resizable": "`False` keeps the size fixed.", "on_resize": "Called with the new size when a drag ends.",
                        "min_size": "Smallest size when resizing.",
                    },
                },
                "pyzed.ui.panel_header": {"desc": "A panel header: icon, title and actions.", "params": {"height": "Height."}},
            }),
            ("Overlays", {
                "pyzed.ui.layer": {
                    "desc": "Stacks `overlay` on top of `base`. Clicking outside sends `on_dismiss`. With `overlay=None` it returns `base` unchanged.",
                    "params": {
                        "base": "The UI underneath.",
                        "overlay": "What floats on top (modal, palette, menu).",
                        "backdrop": "Color of the backdrop that dims the UI.",
                        "offset": "Distance from the top when `align_y` is `\"start\"`.",
                    },
                },
                "pyzed.ui.modal": {
                    "desc": "A dialog. Use it as the `overlay` of `ui.layer`.",
                    "params": {"footer": "Footer buttons, aligned to the right."},
                },
                "pyzed.ui.PaletteItem": {
                    "desc": "An entry of `command_palette` or `picker`.",
                    "params": {"detail": "Secondary text (for example, a file path)."},
                },
                "pyzed.ui.command_palette": {
                    "desc": "Zed's command palette: fuzzy-filters `commands` by `query` and shows their shortcuts.",
                    "params": {
                        "query": "Search text.",
                        "on_query": "Callable that receives the new text.",
                        "commands": "List of `PaletteItem`.",
                        "selected": "Highlighted index (for arrow-key navigation).",
                        "input_id": "Field id (for `Command.focus`).",
                        "kwargs": "Same as `picker`.",
                    },
                },
                "pyzed.ui.picker": {
                    "desc": "A searchable list on a floating surface. The basis of the palette and the file finder.",
                    "params": {
                        "query": "Search text.",
                        "on_query": "Callable that receives the new text.",
                        "items": "`(PaletteItem, positions)` pairs, for example from `fuzzy_filter`.",
                        "selected": "Highlighted index.",
                        "input_id": "Field id.",
                        "empty_text": "Text shown when there are no results.",
                    },
                },
                "pyzed.ui.fuzzy_match": {
                    "desc": "Returns `(score, positions)` if every letter of `query` appears in order in `candidate`; otherwise `None`. Rewards word starts and consecutive letters.",
                    "params": {"query": "Search text.", "candidate": "Candidate text."},
                },
                "pyzed.ui.fuzzy_filter": {
                    "desc": "Filters and sorts `items` by fuzzy score. Returns `[(item, positions), ...]`.",
                    "params": {"query": "Search text.", "items": "Items.", "key": "Function that returns the text of each item."},
                },
                "pyzed.ui.highlighted": {
                    "desc": "Text with the characters at `positions` highlighted (fuzzy search matches).",
                    "params": {"text": "Text.", "positions": "Indices to highlight.", "match_color": "Color of the matches.", "weight": "Text weight."},
                },
                "pyzed.ui.toast": {
                    "desc": "A notification.",
                    "params": {"message": "Secondary text.", "kind": '`"info"`, `"success"`, `"warning"` or `"error"`.'},
                },
                "pyzed.ui.toasts": {
                    "desc": "Shows `items` (usually `toast(...)`) stacked in the bottom-right corner over `base`.",
                    "params": {"base": "The UI underneath.", "items": "List of toasts."},
                },
            }),
            ("Code", {
                "pyzed.ui.editor": {
                    "desc": "Zed's code editor: highlighting with the theme colors, line numbers and git markers.",
                    "params": {
                        "id": "Identifies the buffer (use the file path).",
                        "text": "Initial text.",
                        "language": "Language. If missing, it is inferred from `path`.",
                        "markers": '`{line: "created" | "modified" | "deleted"}`.',
                        "on_cursor": "Callable that receives `(line, column)`.",
                        "font_size": "Font size (defaults to the theme's).",
                        "line_height": "Line height.",
                        "gutter": "Shows line numbers.",
                        "wrap": "Line wrapping.",
                    },
                },
                "pyzed.ui.language_token": {
                    "desc": 'Returns the highlighter language token for a path (`"main.rs"` → `"rs"`).',
                },
                "pyzed.ui.terminal": {
                    "desc": "A read-only terminal view with ANSI colors. It stays scrolled to the end.",
                    "params": {"lines": "Text with ANSI escapes, or a list of lines of `(text, color)` segments.", "font_size": "Font size."},
                },
                "pyzed.ui.ansi": {
                    "desc": "Converts text with ANSI colors into lines of `(text, color_name)` segments.",
                    "params": {"text": "Text with ANSI escapes."},
                },
            }),
        ],
    },
    # --------------------------------------------------------------- Theme
    {
        "slug": "theme",
        "title": "Themes",
        "description": "Theme, the built-in themes and the color utilities.",
        "order": 5,
        "intro": """
            See the [theming](/pyzed/guides/theming/) guide for the list of tokens and how to create your own.
        """,
        "sections": [
            ("Theme", {
                "pyzed.Theme": {
                    "desc": "A theme: an immutable dataclass with Zed's color tokens (surfaces, borders, elements, text, status, editor, syntax, collaborator and ANSI colors) and metrics (`radius`, `radius_sm`, `ui_font_size`, `buffer_font_size`). The `is_dark` property tells whether it is dark.",
                    "no_signature": True,
                },
                "pyzed.Theme.derive": {
                    "desc": "Returns a copy with some tokens changed. The `syntax` and `ansi` dicts are merged instead of replaced.",
                    "params": {"changes": "Tokens to change."},
                    "example": 'ocean = pz.themes.ONE_DARK.derive(name="Ocean", accent="#4fb3ff", syntax={"keyword": "#ff79c6"})',
                },
                "pyzed.Theme.color": {
                    "desc": 'Resolves a token (`"accent"`, `"text_muted"`…) to its color. Hex colors and `"transparent"` pass through unchanged.',
                    "params": {"name": "Token or color."},
                },
                "pyzed.Theme.tokens": {"desc": "All tokens as a dict."},
                "pyzed.Theme.syntax_scopes": {"desc": "Maps Zed's syntax tokens to TextMate scopes for the highlighter."},
                "pyzed.Theme.palette": {"desc": "The base palette passed to Iced for its internal styles. Internal use."},
            }),
            ("Built-in themes", {
                "pyzed.themes": {
                    "desc": "Namespace with the built-in themes: `themes.ONE_DARK`, `themes.ONE_LIGHT` and `themes.GRUVBOX_DARK`.",
                    "no_signature": True,
                },
                "pyzed.themes.all": {"desc": "List of all built-in themes."},
            }),
            ("Utilities (pyzed.theme)", {
                "pyzed.theme.current": {"desc": "The theme components use when no `theme=` is passed."},
                "pyzed.theme.use": {"desc": "Changes the current theme. `App` does this before every `view()`, so you normally don't need it.", "params": {"theme": "The theme."}},
                "pyzed.theme.alpha": {
                    "desc": "Returns `color` with its opacity multiplied by `value`.",
                    "params": {"color": "Hex color.", "value": "Factor from 0 to 1."},
                    "example": 'pz.theme.alpha("#74ade8", 0.2)  # "#74ade833"',
                },
                "pyzed.theme.mix": {
                    "desc": "Mixes two colors: `amount=0` is `a` and `amount=1` is `b`.",
                    "params": {"a": "First color.", "b": "Second color.", "amount": "Proportion of `b`."},
                },
            }),
        ],
    },
    # --------------------------------------------------------------- Icons
    {
        "slug": "icons",
        "title": "Icons",
        "description": "Bundled Lucide icons and file-type utilities.",
        "order": 6,
        "intro": """
            Pyzed bundles the [Lucide](https://lucide.dev) font (ISC license) with about 2000 icons.
            Search names with `pyzed icons <filter>` or on the Lucide website.
        """,
        "sections": [
            ("pyzed.icons", {
                "pyzed.icons.icon": {
                    "desc": "An icon widget. Also available as `pyzed.icon`.",
                    "params": {"name": "Icon name.", "size": "Size.", "color": "Color (defaults to the text color)."},
                },
                "pyzed.icons.glyph": {
                    "desc": 'Returns an icon\'s character, to use in any text with `font="icons"`. Raises `ValueError` if it doesn\'t exist.',
                    "params": {"name": "Icon name."},
                },
                "pyzed.icons.names": {"desc": "Sorted list of all icon names."},
                "pyzed.icons.for_file": {
                    "desc": 'Returns `(icon, color_or_None)` for a file name, as in Zed\'s project panel.',
                    "params": {"name": "File name."},
                },
                "pyzed.icons.language_for": {
                    "desc": 'Human-readable language name of a file (`"main.py"` → `"Python"`), handy for the status bar.',
                    "params": {"name": "File name."},
                },
            }),
        ],
    },
]


# ---------------------------------------------------------------------------
# 0.2: multi-window, async, new widgets and components
# ---------------------------------------------------------------------------

COMMON.update({
    "font": "Font of the span or text (family name, e.g. `\"IBM Plex Mono\"`).",
    "weight": "Font weight: `\"normal\"`, `\"medium\"`, `\"semibold\"` or `\"bold\"`.",
    "italic": "If `True`, the span is drawn in italics.",
    "wrap": "Line wrapping / moves children to a new row when they don't fit.",
    "line_spacing": "Space between rows when `wrap=True`.",
    "gradient": "Linear background gradient: `(angle, [colors])` or `(angle, [(position, color), ...])`.",
    "on_scroll": "Called on scroll.",
    "on_move": "Called with `(x, y)` when the mouse moves.",
    "on_middle_press": "Middle-button click.",
    "on_release": "Called on release.",
    "vertical": "Vertical orientation.",
    "content_fit": '`"contain"`, `"cover"`, `"fill"`, `"none"` or `"scale-down"`.',
    "opacity": "Opacity from 0 to 1.",
    "rotation": "Rotation in degrees.",
    "active_line": "Background color of the cursor line.",
    "scrollbar_color": "Scrollbar color.",
    "key": "Key that identifies the subscription (defaults to the message or the function).",
    "filter": '`"linear"` (smooth) or `"nearest"` (crisp pixels, for pixel art).',
    "source": "File path, `bytes` of the encoded file, or raw RGBA pixels with `size=(width, height)`.",
    "description": "Secondary text.",
    "options": "List of options.",
    "on_menu": "Message or callable for the menu button.",
    "handle": "Width of the draggable area.",
    "text_size": "Text size.",
})


def _page(slug):
    return next(p for p in PAGES if p["slug"] == slug)


def _section(slug, title, items, before=None):
    page = _page(slug)
    sections = page["sections"]
    for i, (name, existing) in enumerate(sections):
        if name == title:
            existing.update(items)
            return
    index = next((i for i, (n, _) in enumerate(sections) if n == before), len(sections))
    sections.insert(index, (title, items))


# -- App, windows and async ------------------------------------------------
_page("app")["intro"] += """

See also [multiple windows](/pyzed/guides/windows/) and [async and subscriptions](/pyzed/guides/async/).
"""
_page("app")["sections"][0][1]["pyzed.App"]["desc"] = """
Base class for applications (Elm architecture, like Iced). It is also the **main
window**, so it inherits everything from [`Window`](#window). Override `view()` and, if you use
messages, `update(message)`. State lives in instance attributes.

| Class attribute | Default | Description |
| --- | --- | --- |
| `title` | `"Pyzed"` | Window title. Can be a callable (or property) that returns the text. |
| `size` | `(1280, 800)` | Initial window size. |
| `font_size` | `14` | Default text size. |
| `theme` | `themes.ONE_DARK` | A `Theme`, the name of a registered theme or `themes.auto(light, dark)`. Change it at any time. |
| `system_dark` | `True` | Whether the system is in dark mode (updated by the runtime). |

The remaining window options (`min_size`, `resizable`, `decorations`, `scale`…) are on `Window`.

| Method | Description |
| --- | --- |
| `view()` | Returns the widget tree. Called after every message. |
| `update(message)` | Receives messages. Can return a `Command`, a list of them, a coroutine, a generator (regular or async) or another message. |
| `on_start()` | Optional. Runs once at startup; can return a `Command` or a coroutine. |
| `on_key(combo)` | Optional. Receives every key as `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `subscriptions()` | Optional. Returns the active subscriptions (`pz.every`, `pz.listen`). Re-evaluated after every `update`. |
| `resolved_theme()` | The concrete `Theme` in use (resolves names and `themes.auto`). |
| `run()` | Opens the window and blocks until the app exits. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renders the current state to a PNG without a window. |

If `view()` raises an exception, the window shows the traceback instead of closing.
"""
_section("app", "Windows", {
    "pyzed.Window": {
        "desc": """
An extra window with its own `view()`, title, size and theme. Open it by returning
`window.open()` (or `Command.open_window(window)`). Inside it, `self.app` is the app, so
windows share state; the messages it produces go to its `update()`, which by default
forwards them to `app.update()`.

| Attribute | Default | Description |
| --- | --- | --- |
| `title` | `"Pyzed"` | Text or callable. |
| `size` | `(800, 600)` | Initial size. |
| `min_size`, `max_size` | `None` | Size limits. |
| `position` | `None` | `"center"` or `(x, y)`. |
| `resizable` | `True` | Whether it can be resized. |
| `decorations` | `True` | `False` removes the system frame (custom title bar with `drag()`). |
| `transparent`, `maximized`, `fullscreen` | `False` | Initial state. |
| `scale` | `1.0` | UI scale. |
| `theme` | `None` | Its own theme; `None` uses the app's. |
| `app` | — | The app that owns the window (assigned when it opens). |
| `window_size` | — | Current size in logical pixels (updated by the runtime). |

| Method | Description |
| --- | --- |
| `view()` | Required. Returns the window's widget tree. |
| `update(message)` | Receives the window's messages (by default forwards them to the app). |
| `open()` / `close()` / `drag()` | Commands to open it, close it or start moving it. |
| `is_open` | Whether it is open. |
| `resolved_theme()` | The concrete `Theme` it uses. |
| `on_open()` | When it opens. |
| `on_close()` | When the user asks to close it; return `False` to prevent it. |
| `on_resize(width, height)` | When it is resized. |
| `on_key(combo)`, `subscriptions()` | As in `App`. |
""",
        "no_signature": True,
    },
})
_section("app", "Async and subscriptions", {
    "pyzed.every": {
        "desc": "A subscription that sends `message` to `update` every `seconds` seconds (like Iced's `time::every`). If `message` is a callable, it is called. Return it from `subscriptions()`.",
        "params": {"seconds": "Interval in seconds (greater than 0)."},
        "example": """
            def subscriptions(self):
                return [pz.every(1, "tick")] if self.running else []
        """,
    },
    "pyzed.listen": {
        "desc": "A subscription that runs `function()` (a generator or async generator) while it is active and sends every value it yields to `update`. Ideal for websockets and streams.",
        "params": {"function": "Generator function (regular or `async def`)."},
        "example": """
            async def feed():
                async for message in websocket:
                    yield message

            def subscriptions(self):
                return [pz.listen(feed)]
        """,
    },
    "pyzed.Subscription": {"desc": "What `every` and `listen` return. It is identified by its `key`: as long as `subscriptions()` keeps returning one with the same key, it keeps running; when it disappears, it stops.", "no_signature": True},
    "pyzed.spawn": {
        "desc": "Schedules a coroutine on Pyzed's asyncio loop without waiting for its result and returns a `concurrent.futures.Future`. To receive the result in the UI, return the coroutine from `update` or use `Command.perform`.",
        "params": {"awaitable": "The coroutine."},
    },
    "pyzed.asyncio_loop": {"desc": "The asyncio loop (on a background thread) where Pyzed runs every coroutine. It starts the first time it is used."},
})

# -- Command ---------------------------------------------------------------------
_win = "The window (`pz.Window`). Without it, the one that produced the message."
_page("command")["sections"][0][1].update({
    "pyzed.Command.scroll_to": {
        "desc": "Scrolls the `scrollable` with that `id` to an absolute position in pixels.",
        "params": {"id": "The scrollable's `id`.", "x": "Horizontal offset.", "y": "Vertical offset."},
    },
    "pyzed.Command.copy": {"desc": "Copies `text` to the system clipboard.", "params": {"text": "The text."}},
    "pyzed.Command.paste": {"desc": "Reads the clipboard and calls `then(text)` (empty string if it is empty).", "params": {"then": "Callable that receives the text."}},
})
_page("command")["sections"][0][1]["pyzed.Command.perform"]["desc"] = (
    "Runs `function()` in the background and delivers the result to `then(result)` on the UI "
    "thread. `function` can be regular (runs on a thread) or `async def` (runs on Pyzed's asyncio "
    "loop). If it returns a generator (regular or async), `then` is called with each value. It also accepts "
    "an already created coroutine or generator (`fetch(url)` instead of `fetch`). Without `then`, results go to "
    "`update`. If `function` raises, the error is printed."
)
_section("command", "Windows and clipboard", {
    "pyzed.Command.open_window": {"desc": "Opens a new window for that `pz.Window` instance.", "params": {"window": "The window."}},
    "pyzed.Command.close_window": {"desc": "Closes the window.", "params": {"window": _win}},
    "pyzed.Command.drag_window": {"desc": "Starts moving the window with the mouse (use it when a custom title bar is pressed).", "params": {"window": _win}},
    "pyzed.Command.minimize_window": {"desc": "Minimizes the window.", "params": {"window": _win}},
    "pyzed.Command.toggle_maximize_window": {"desc": "Maximizes the window, or restores it if it already is.", "params": {"window": _win}},
    "pyzed.Command.set_fullscreen": {"desc": "Enters or leaves fullscreen.", "params": {"fullscreen": "`True` for fullscreen.", "window": _win}},
    "pyzed.Command.resize_window": {"desc": "Resizes the window (logical pixels).", "params": {"width": "Width.", "height": "Height.", "window": _win}},
    "pyzed.Command.move_window": {"desc": "Moves the window to a position on the screen.", "params": {"x": "Horizontal position.", "y": "Vertical position.", "window": _win}},
    "pyzed.Command.focus_window": {"desc": "Brings the window to the front and focuses it.", "params": {"window": _win}},
})

# -- Widgets ----------------------------------------------------------------------
_w = _page("widgets")["sections"]
dict(_w)["Layout"].update({
    "pyzed.grid": {
        "desc": "Lays out its children in a grid. With `columns=3` the columns are equal (or `max_width` fits as many as possible). With track lists (`columns=[200, \"1fr\", \"auto\"]`, `rows=...`) it works like a CSS grid: numbers are pixels, `\"auto\"` fits the content and `\"<n>fr\"` shares the space left. Wrap children in `pz.cell` to place them and make them span; the rest fill the free cells row by row. See [Layout](/pyzed/guides/layout/#grids).",
        "params": {
            "columns": "Number of equal columns, or tracks: a list (`[200, \"1fr\", \"auto\"]`) or a string (`\"200 1fr auto\"`).",
            "rows": "Row tracks, like `columns`. Rows beyond the list are `\"auto\"`.",
            "spacing": "Space between cells.", "row_spacing": "Space between rows, if different.",
            "height": "With `columns=<int>`: height of each row. With tracks: the grid's height.",
            "width": "With `columns=<int>`: pixels. With tracks: the grid's width (default `\"fill\"`).",
            "aspect_ratio": "Keeps cells at this width/height ratio (`columns=<int>` only).",
            "max_width": "Fits as many columns of at most this width as possible (`columns=<int>` only).",
            "padding": "Space around the cells.",
            "align_x": "Horizontal alignment of items in their cells: `\"start\"`, `\"center\"`, `\"end\"`.",
            "align_y": "Vertical alignment of items in their cells.",
        },
        "example": """
            pz.grid([pz.cell(header, column=0, row=0, column_span=2), sidebar, content],
                    columns=[200, "1fr"], rows=[48, "1fr"], spacing=8, height="fill")
        """,
    },
    "pyzed.cell": {
        "desc": "Places a child in a track grid: its column and row (from 0) and how many it spans. Children without a cell fill the free cells row by row. Outside a grid it is just the child.",
        "params": {
            "content": "The widget.", "column": "Column index (from 0).", "row": "Row index (from 0).",
            "column_span": "Columns it covers.", "row_span": "Rows it covers.",
            "align_x": "Horizontal alignment in the cell.", "align_y": "Vertical alignment in the cell.",
        },
        "example": 'pz.cell(ui.button("Save"), column=2, row=3, align_x="end")',
    },
    "pyzed.flex": {
        "desc": "Lays children out along one axis, like CSS flexbox, with `justify` on the main axis and `align` on the cross axis. Use `pz.flex_item` to make a child grow or give it a fixed size.",
        "params": {
            "children": "The widgets, or `pz.flex_item(...)` for children with their own sizing.",
            "direction": "`\"row\"` or `\"column\"`.",
            "justify": "`\"start\"`, `\"center\"`, `\"end\"`, `\"between\"`, `\"around\"` or `\"evenly\"`. No effect when a child grows.",
            "align": "Cross-axis alignment: `\"start\"`, `\"center\"` or `\"end\"`.",
            "gap": "Space between children.", "wrap": "Wraps onto new lines (rows with `justify=\"start\"` only).",
            "padding": "Space around the children.", "width": "Width.", "height": "Height.",
        },
        "example": 'pz.flex([logo, title, pz.flex_item(search, grow=1), avatar], justify="between", align="center", gap=8)',
    },
    "pyzed.flex_item": {
        "desc": "Sizes a child of `pz.flex`.",
        "params": {
            "content": "The widget.", "grow": "Share of the free space on the main axis (`0` keeps its natural size).",
            "basis": "A fixed main size in pixels, instead of growing.", "align": "Cross-axis alignment for this child.",
        },
    },
    "pyzed.resizable": {
        "desc": "A panel whose `edge` can be dragged to resize it. It keeps the size the user drags it to; `on_resize(size)` is called when a drag ends so you can save it. Changing `size` later resets it.",
        "params": {
            "content": "The panel's content.",
            "edge": "The edge with the handle: `\"right\"` (a left sidebar), `\"left\"`, `\"top\"` (a bottom panel) or `\"bottom\"`.",
            "size": "Starting width (height for top/bottom edges).",
            "min_size": "Smallest size.", "max_size": "Largest size.",
            "on_resize": "Called with the new size when a drag ends.",
            "color": "Line color.", "hover_color": "Line color while hovered or dragged.",
            "thickness": "Line thickness.", "handle": "Width of the area that can be grabbed.",
            "width": "Width for top/bottom edges.", "height": "Height for left/right edges.",
        },
        "example": 'pz.row([pz.resizable(sidebar, edge="right", size=240, on_resize=self.save_width), editor])',
    },
    "pyzed.split": {
        "desc": "Two panes with a draggable divider. For the theme style use `ui.split`.",
        "params": {
            "first": "First pane.", "second": "Second pane.",
            "ratio": "Proportion of the first pane (0–1). The split keeps the ratio the user drags to until this changes.",
            "on_resize": "Callable that receives the new ratio while dragging.",
            "vertical": "Stacks the panes top/bottom.",
            "min_size": "Minimum size of the first pane.", "min_size_second": "Minimum size of the second pane.",
            "color": "Divider color.", "hover_color": "Divider color on hover or while dragging.",
            "thickness": "Line thickness.",
        },
    },
    "pyzed.pin": {
        "desc": "Places `content` at `(x, y)` inside a box. Use it in a `stack` to position popovers and context menus.",
        "params": {"x": "Horizontal position.", "y": "Vertical position."},
    },
    "pyzed.responsive": {
        "desc": "Builds its content with `function(width, height)` using the space actually available, so the layout can adapt (for example, hiding a sidebar when the window is narrow).",
        "params": {"function": "Function that receives `(width, height)` and returns a widget."},
    },
})
_section("widgets", "Images and content", {
    "pyzed.image": {
        "desc": "A bitmap image (PNG, JPEG, GIF, BMP, WebP…) from a path or `bytes`, or raw RGBA pixels.",
        "params": {"radius": "Corner radius.", "scale": "Scale.", "size": "`(width, height)` when `source` is raw RGBA pixels."},
        "example": 'pz.image("photo.jpg", width=320, content_fit="cover", radius=8)',
    },
    "pyzed.image_viewer": {
        "desc": "An image you can pan (by dragging) and zoom (mouse wheel), like Iced's viewer.",
        "params": {"min_scale": "Minimum zoom.", "max_scale": "Maximum zoom.", "scale_step": "How much the zoom changes per wheel step.", "size": "`(width, height)` for raw RGBA pixels."},
    },
    "pyzed.markdown": {
        "desc": "Renders Markdown (headings, lists, code blocks, quotes, tables, links…). For the theme colors use `ui.markdown`.",
        "params": {"source": "The Markdown text.", "link_color": "Link color.", "code_color": "Code color.", "code_bg": "Code background.", "on_link": "Callable that receives the URL when a link is clicked."},
    },
    "pyzed.rich_text": {
        "desc": "Text made of spans with different styles. Plain strings are unstyled spans.",
        "params": {"spans": "List of `span(...)` or strings.", "line_height": "Line height."},
        "example": 'pz.rich_text(["Click ", pz.span("here", color="#74ade8", underline=True, link=self.open), " to open."])',
    },
    "pyzed.span": {
        "desc": "A styled span for `rich_text`. With `link`, clicking it sends (or calls) that value.",
        "params": {"text": "The text.", "radius": "Background radius.", "underline": "Underline.", "strikethrough": "Strikethrough.", "link": "Message or callable on click."},
    },
    "pyzed.Span": {"desc": "The type of the spans created by `pz.span`.", "no_signature": True},
    "pyzed.qr_code": {
        "desc": "A QR code that encodes `data`.",
        "params": {"data": "The text or URL to encode.", "cell_size": "Size of each module in pixels."},
    },
    "pyzed.canvas": {
        "desc": "A 2D drawing surface. `shapes` is a list created with [`pyzed.draw`](/pyzed/reference/draw/). Mouse callbacks receive coordinates relative to the canvas. With an `id`, the geometry is cached between frames and only recomputed when the shapes change. See the [drawing with canvas](/pyzed/guides/canvas/) guide.",
        "params": {
            "shapes": "List of `pyzed.draw` shapes (nested lists are accepted).",
            "id": "Enables the geometry cache.",
            "on_press": "Callable that receives `(x, y)` on press.",
            "on_release": "Callable that receives `(x, y)` on release.",
            "on_right_press": "Callable that receives `(x, y)` on right click.",
            "on_scroll": "Callable that receives `(dx, dy)` in lines when the wheel is used.",
            "cursor": "Mouse cursor (`\"crosshair\"`, `\"pointer\"`…).",
        },
    },
}, before="Interaction")
dict(_w)["Controls"].update({
    "pyzed.vertical_slider": {"desc": "A vertical slider (`slider(..., vertical=True)`).", "params": {"min": "Minimum.", "max": "Maximum.", "kwargs": "Same as `slider`."}},
    "pyzed.pick_list": {
        "desc": "A dropdown to choose one of `options`. `on_select(option)` receives the chosen one. For the Zed style use `ui.select`.",
        "params": {
            "selected": "Current option.", "handle": "Arrow icon character.", "handle_size": "Arrow size.",
            "menu_height": "Maximum menu height.", "font": "Font family.",
            "placeholder_color": "Placeholder color.", "handle_color": "Arrow color.",
            "menu_bg": "Menu background.", "menu_color": "Menu text.", "menu_border_color": "Menu border.",
            "selected_bg": "Background of the highlighted option.", "selected_color": "Text of the highlighted option.",
        },
    },
    "pyzed.radio": {
        "desc": "A radio button. Group several yourself (or use `ui.radio_group`); `on_select` is sent when it is clicked.",
        "params": {"selected": "Whether it is checked.", "on_select": "Message or callable on click.", "spacing": "Space between the circle and the text."},
    },
})
dict(_w)["Interaction"]["pyzed.mouse_area"]["params"]["on_scroll"] = "Callable that receives `(dx, dy)` in lines when the wheel is used."
dict(_w)["Layout"]["pyzed.scrollable"]["params"]["on_scroll"] = "Callable that receives a dict with `x`, `y`, `relative_x`, `relative_y`, `width`, `height`, `content_width` and `content_height`."
dict(_w)["Controls"]["pyzed.slider"]["params"]["on_release"] = "Sent when the knob is released."

# -- UI -----------------------------------------------------------------------------
_section("ui", "Controls", {
    "pyzed.ui.select": {
        "desc": "A dropdown with the theme style (Zed's `DropdownMenu`). Options are displayed with `str()`, so strings, enums or dataclasses all work.",
        "params": {"selected": "Current option.", "size": '`"sm"`, `"md"` or `"lg"`.'},
    },
    "pyzed.ui.radio_group": {
        "desc": "Mutually exclusive options as radio buttons.",
        "params": {"options": "Strings or `(value, label)` pairs.", "selected": "Current value.", "on_select": "Callable that receives the chosen value.", "horizontal": "In a row instead of a column."},
    },
    "pyzed.ui.number_field": {
        "desc": "A numeric field with −/+ buttons (Zed's `NumericStepper`). `on_change(value)` receives the number already clamped to `min`/`max`; anything that can't be parsed as a number is ignored.",
        "params": {"min": "Minimum.", "max": "Maximum.", "step": "Button step.", "suffix": "Unit shown at the end (`\"px\"`, `\"%\"`…).", "align": 'Where the number sits between the buttons: `"center"` (default), `"start"` or `"end"`.'},
    },
    "pyzed.ui.split_button": {
        "desc": "A button with a separate arrow for more options (Zed's `SplitButton`). `on_press` runs the main action and `on_menu` usually opens a `ui.menu` in a `ui.popover`.",
        "params": {"content": "Button text.", "variant": "As in `ui.button`.", "size": _SIZES},
    },
    "pyzed.ui.toggle_group": {
        "desc": "An icon-only segmented control.",
        "params": {"options": "`(value, icon_name)` pairs.", "selected": "Current value."},
    },
    "pyzed.ui.chip": {
        "desc": "A compact tag, optionally clickable (filters) and with a button to remove it.",
        "params": {"content": "Text.", "on_remove": "Shows a ✕ that sends this when clicked."},
    },
    "pyzed.ui.disclosure": {
        "desc": "A collapsible section: a header with an arrow that shows or hides `content`. You own the open state: change it in `on_toggle`.",
        "params": {"title": "Title (text or widget).", "content": "Content.", "open": "Whether it is open.", "on_toggle": "Message or callable when the header is clicked."},
    },
    "pyzed.ui.AccordionSection": {
        "desc": "One section of `ui.accordion`: `key`, `title`, `content` and optional `icon` and header `end` widget.",
    },
    "pyzed.ui.accordion": {
        "desc": "Stacked collapsible sections separated by dividers, like the panels of Zed's settings. Each header spans the whole width, so the content lines up with the rest of the panel. You own the open state: change it in `on_toggle`.",
        "params": {"sections": "`ui.AccordionSection(key, title, content, icon=None, end=None)` items (or `(key, title, content)` tuples).", "open": "The set of open ids, a `{id: bool}` dict, or `True` for all.", "on_toggle": "Called with the key of the clicked header.", "icons": "`{id: icon}`: a Lucide icon for each header.", "spacing": "Space around the dividers between sections.", "padding": "Padding around the content of an open section."},
        "example": """
            ui.accordion([
                ui.AccordionSection("layout", "Layout", layout_rows, icon="ruler"),
                ui.AccordionSection("events", "Events", event_rows, icon="zap"),
            ], open=self.open_sections, on_toggle=lambda key: self.open_sections.symmetric_difference_update({key}))
        """,
    },
}, before="Lists, tree and menus")
_section("ui", "Data and feedback", {
    "pyzed.ui.callout": {
        "desc": "An inline notice (Zed's `Callout`/`Banner`).",
        "params": {"title": "Title (text or widget).", "tint": '`"info"`, `"success"`, `"warning"`, `"error"` or `"hint"`: picks the color and icon.', "on_dismiss": "Adds a close button."},
    },
    "pyzed.ui.empty_state": {
        "desc": "A centered placeholder for empty lists, searches with no results, etc.",
        "params": {"title": "Title."},
    },
    "pyzed.ui.settings_group": {
        "desc": "A titled block of `ui.field` rows separated by lines (Zed's settings UI).",
        "params": {"title": "Group title.", "rows": "The rows (usually `ui.field`)."},
    },
    "pyzed.ui.Column": {
        "desc": 'A column of `ui.table`. `key` is a dict key, an attribute name or a function of the row; `render` (optional) turns the value into a widget. `width` is `"fill"`, a number or `("fill", 2)`.',
        "params": {"title": "Header (and name used for sorting).", "key": "How to get the value from each row.", "align": '`"start"`, `"center"` or `"end"`.', "render": "Function value → widget.", "sortable": "Whether the header can be clicked to sort."},
    },
    "pyzed.ui.table": {
        "desc": "A data table with a fixed header, optional sorting and row selection. Sorting happens here when `sort_by` names a column: clicking a header calls `on_sort(title)` and you update `sort_by`/`descending` in your state.",
        "params": {
            "columns": "`ui.Column` or plain keys.", "rows": "Dicts or objects.", "sort_by": "Title of the column to sort by.",
            "descending": "Descending order.", "on_sort": "Callable that receives the clicked title.", "on_row_press": "Callable that receives the clicked row.",
            "selected": "The highlighted row.", "striped": "Shaded alternating rows.", "row_height": "Height of each row.",
        },
    },
    "pyzed.ui.stat": {
        "desc": "A dashboard number: title, large value, optional change (`+4.2%`) and sparkline.",
        "params": {"title": "Title.", "delta": "Change in %; green if positive, red otherwise.", "trend": "Values for the sparkline."},
    },
    "pyzed.ui.sparkline": {
        "desc": "A tiny line chart for trends.",
        "params": {"values": "Values.", "fill": "Fills the area under the line."},
    },
    "pyzed.ui.bar_chart": {
        "desc": "A vertical bar chart with optional labels.",
        "params": {"values": "Values.", "labels": "Labels under each bar."},
    },
    "pyzed.ui.donut": {
        "desc": "A donut chart; `label` is drawn in the center.",
        "params": {"values": "Values.", "colors": "Colors (defaults to the theme's).", "thickness": "Ring thickness.", "label": "Center text."},
    },
    "pyzed.ui.spinner": {
        "desc": "A spinning arc for loading states. Its angle comes from the clock, so keep a `pz.every(1/30, ...)` subscription active while it is shown.",
        "params": {"speed": "Turns per second."},
    },
    "pyzed.ui.count_badge": {
        "desc": "A round counter (notifications, problems…). Shows `99+` above `max`.",
        "params": {"count": "The number.", "max": "Maximum before showing `N+`."},
    },
    "pyzed.ui.facepile": {
        "desc": "Overlapping collaborator avatars, as in Zed's title bar. Those beyond `max_shown` are grouped into `+N`.",
        "params": {"people": "Initials or names.", "overlap": "Overlap in pixels.", "max_shown": "How many to show."},
    },
    "pyzed.ui.diff_stat": {
        "desc": "`+12 −3` with GitHub-style colored blocks.",
        "params": {"added": "Lines added.", "removed": "Lines removed.", "blocks": "Number of blocks."},
    },
    "pyzed.ui.keybinding_hint": {
        "desc": "A muted hint like “Open file Ctrl P” for footers and empty states.",
        "params": {"text": "Text."},
    },
    "pyzed.ui.markdown": {
        "desc": "`pz.markdown` with the theme's text, link and code colors.",
        "params": {"source": "The Markdown text.", "on_link": "Callable that receives the URL when a link is clicked."},
    },
    "pyzed.ui.split": {
        "desc": "`pz.split` with the divider in the theme's border color (accent while dragging).",
        "params": {"first": "First pane.", "second": "Second pane.", "ratio": "Proportion of the first pane (0–1).", "on_resize": "Callable that receives the new ratio.", "min_size": "Minimum size of each pane.", "kwargs": "Same as `pz.split`."},
    },
}, before="Lists, tree and menus")
dict(_page("ui")["sections"])["Overlays"]["pyzed.ui.popover"] = {
    "desc": "Shows `content` (a `ui.menu`, a card…) over `base` at `(x, y)`. Clicking anywhere else calls `on_dismiss`. For a right-click menu, store the mouse position with `mouse_area(on_move=...)` and open the popover from `on_right_press` (see `examples/context_menu.py`).",
    "params": {"base": "The UI underneath.", "content": "What floats (or `None`).", "x": "Horizontal position.", "y": "Vertical position."},
}

# -- Theme ------------------------------------------------------------------------------
_t = _page("theme")
_t["sections"][0][1].update({
    "pyzed.Theme.with_accent": {"desc": "A copy with a different accent color and everything that depends on it (focus, selection, links, primary buttons, text on accent).", "params": {"accent": "The color."}},
    "pyzed.Theme.generate": {
        "desc": "Creates a complete theme from a few colors. Surfaces, borders, hover states and muted text are mixed from `background` and `text`; the appearance is inferred from the background brightness if not given.",
        "params": {"name": "Name.", "background": "Editor/background color.", "text": "Text color.", "accent": "Accent color.", "appearance": '`"dark"` or `"light"`.', "error": "Error color.", "warning": "Warning color.", "success": "Success color.", "syntax": "Extra syntax colors.", "radius": "Corner radius."},
        "example": 'pz.Theme.generate("Custom", background="#1b1d23", text="#e6e6e6", accent="#ff8a65")',
    },
    "pyzed.Theme.from_zed": {
        "desc": "Reads a theme from a Zed theme family file (`.json`) or a dict. A family usually has several (Ayu Dark/Light/Mirage); `name` picks one (the first by default).",
        "params": {"source": "Path, JSON text or dict.", "name": "Name of the theme within the family."},
    },
    "pyzed.Theme.to_dict": {"desc": "A JSON-ready dict; `Theme.from_dict` reads it back."},
    "pyzed.Theme.from_dict": {"desc": "Creates a theme from `to_dict`. Missing tokens come from `base` (One Dark or One Light depending on `appearance`).", "params": {"data": "The tokens.", "base": "Base theme."}},
    "pyzed.Theme.save": {"desc": "Saves the theme as JSON (Pyzed's own format).", "params": {"path": "File path."}},
    "pyzed.Theme.load": {"desc": "Reads a theme written with `save` (for Zed themes use `from_zed`).", "params": {"path": "File path."}},
})
dict(_t["sections"])["Built-in themes"].update({
    "pyzed.themes.names": {"desc": "Names of all registered themes."},
    "pyzed.themes.get": {"desc": "Looks up a theme by name (case-insensitive). Raises `KeyError` if it doesn't exist.", "params": {"name": "Name."}},
    "pyzed.themes.register": {"desc": "Adds (or replaces) a theme so it can be used by name.", "params": {"theme": "The theme."}},
    "pyzed.themes.load_zed": {"desc": "Loads and registers every theme in a Zed family file.", "params": {"source": "Path, JSON text or dict."}},
    "pyzed.themes.auto": {"desc": "A theme that follows the system's light/dark mode.", "params": {"light": "Theme (or name) for light mode.", "dark": "Theme (or name) for dark mode."}},
    "pyzed.AutoTheme": {"desc": "What `themes.auto` returns: a `(light, dark)` pair. `pick(dark)` returns the right one.", "no_signature": True},
})
_t["sections"][1][1]["pyzed.themes"]["desc"] = (
    "Namespace with the built-in themes (Zed's One, Ayu and Gruvbox families) and the theme "
    "registry. Built-in themes are also available as attributes: `themes.ONE_DARK`, `themes.ONE_LIGHT`, "
    "`themes.AYU_DARK`, `themes.AYU_LIGHT`, `themes.AYU_MIRAGE`, `themes.GRUVBOX_DARK`, `themes.GRUVBOX_LIGHT`…"
)
dict(_t["sections"])["Utilities (pyzed.theme)"].update({
    "pyzed.theme.resolve": {"desc": "Turns an `App.theme` value (theme, name, `AutoTheme` or `None`) into a `Theme`.", "params": {"value": "The value.", "dark": "Whether the system is in dark mode."}},
    "pyzed.theme.lighten": {"desc": "Lightens a color.", "params": {"color": "Hex color.", "amount": "Amount from 0 to 1."}},
    "pyzed.theme.darken": {"desc": "Darkens a color.", "params": {"color": "Hex color.", "amount": "Amount from 0 to 1."}},
    "pyzed.theme.luminance": {"desc": "Relative luminance (WCAG) of a color, from 0 to 1.", "params": {"color": "Hex color."}},
    "pyzed.theme.contrast": {"desc": "WCAG contrast ratio between two colors (1 to 21).", "params": {"a": "First color.", "b": "Second color."}},
    "pyzed.theme.readable_on": {"desc": "Returns `light` or `dark`, whichever has more contrast on `background`.", "params": {"background": "Background color.", "light": "Light text.", "dark": "Dark text."}},
})

# -- Draw ---------------------------------------------------------------------------------
_paint = {"fill": "Fill color.", "stroke": "Stroke color.", "width": "Stroke width.", "dash": "Dash pattern, e.g. `[6, 4]`.", "cap": '`"round"`, `"square"` or `"butt"`: shape of the line ends.'}
PAGES.append({
    "slug": "draw",
    "title": "Drawing (pyzed.draw)",
    "description": "Shapes, text and transforms for pz.canvas.",
    "order": 7,
    "intro": """
        `pyzed.draw` shapes are plain dicts you pass to [`pz.canvas`](/pyzed/reference/widgets/#canvas).
        Angles are in degrees and `y` grows downwards. See the [drawing with canvas](/pyzed/guides/canvas/) guide.

        ```python
        from pyzed import draw

        pz.canvas([
            draw.background("#1e2127"),
            draw.circle(100, 100, 40, fill="#74ade8"),
            draw.text(100, 180, "Hello", color="#dce0e5", align_x="center"),
        ], width=200, height=200)
        ```
    """,
    "sections": [
        ("Shapes", {
            "pyzed.draw.background": {"desc": "Fills the whole canvas.", "params": {"color": "Color."}},
            "pyzed.draw.rect": {"desc": "A rectangle, filled and/or stroked.", "params": {**_paint, "x": "Left.", "y": "Top.", "w": "Width.", "h": "Height.", "radius": "Corner radius."}},
            "pyzed.draw.rects": {"desc": "Many rectangles filled with one color in a single shape (fast for grids and bars).", "params": {"items": "`(x, y, w, h)` tuples.", "fill": "Color."}},
            "pyzed.draw.circle": {"desc": "A circle centered at `(x, y)`.", "params": {**_paint, "x": "Center x.", "y": "Center y.", "r": "Radius."}},
            "pyzed.draw.line": {"desc": "A straight line.", "params": {**_paint, "x1": "Start x.", "y1": "Start y.", "x2": "End x.", "y2": "End y."}},
            "pyzed.draw.polyline": {"desc": "Joins `points` with straight lines (`closed=True` closes the shape).", "params": {**_paint, "points": "List of `(x, y)`.", "closed": "Closes the shape."}},
            "pyzed.draw.polygon": {"desc": "A closed shape through `points`.", "params": {**_paint, "points": "List of `(x, y)`."}},
            "pyzed.draw.arc": {"desc": "A circular arc from `start` to `end` degrees (0 = 3 o'clock, clockwise). `pie=True` closes it through the center (pie slice).", "params": {**_paint, "x": "Center x.", "y": "Center y.", "r": "Radius.", "start": "Start angle.", "end": "End angle.", "pie": "Closes through the center."}},
            "pyzed.draw.path": {
                "desc": "A free-form path with SVG-like operations: `(\"M\", x, y)` move, `(\"L\", x, y)` line, `(\"Q\", cx, cy, x, y)` quadratic curve, `(\"C\", c1x, c1y, c2x, c2y, x, y)` cubic curve, `(\"A\", cx, cy, r, start, end)` arc, `(\"Z\",)` close.",
                "params": {**_paint, "ops": "List of operations."},
            },
            "pyzed.draw.text": {"desc": "Text anchored at `(x, y)`; `align_x`/`align_y` choose which side of the text sits on that point.", "params": {"x": "X position.", "y": "Y position.", "content": "The text.", "color": "Color.", "size": "Size.", "font": "Family.", "weight": "Weight.", "align_x": '`"start"`, `"center"` or `"end"`.', "align_y": '`"top"`, `"center"` or `"bottom"`.'}},
        }),
        ("Transforms", {
            "pyzed.draw.translate": {"desc": "Offsets the shapes that come after it.", "params": {"x": "Horizontal.", "y": "Vertical."}},
            "pyzed.draw.rotate": {"desc": "Rotates the shapes that come after it around the current origin.", "params": {"degrees": "Degrees."}},
            "pyzed.draw.scale": {"desc": "Scales the shapes that come after it.", "params": {"x": "Horizontal factor.", "y": "Vertical factor (defaults to `x`)."}},
            "pyzed.draw.save": {"desc": "Saves the current transform (use it with `restore`)."},
            "pyzed.draw.restore": {"desc": "Goes back to the transform saved by the last `save`."},
            "pyzed.draw.group": {"desc": "Draws `shapes` translated, rotated and scaled without affecting the following shapes. Returns a list: expand it with `*`.", "params": {"shapes": "The shapes.", "x": "X offset.", "y": "Y offset.", "rotation": "Degrees.", "scale_by": "Scale."}},
        }),
    ],
})
for p in PAGES:
    if p["slug"] == "icons":
        p["order"] = 8


# -- Hot reload, events and components ---------------------------------------
_page("app")["sections"][0][1]["pyzed.run"].setdefault("params", {}).update({
    "reload": "Hot reload: saving a project file updates the running window and keeps its state. `None` follows `PYZED_RELOAD` (set by `pyzed dev`).",
    "watch": "Extra folders or files to watch for hot reload.",
})
_section("app", "Events and components", {
    "pyzed.on": {
        "desc": "Attaches common event handlers to a widget; same as `widget.on(...)`. Events: `click`, `double_click`, `right_click`, `middle_click`, `mouse_down`, `mouse_up`, `mouse_enter`, `mouse_leave`, `mouse_move`, `scroll`, `drag_start`, `drag`, `drag_end`, `focus`, `blur`, `key_down`, `key_up`, `resize`. See [Events](/pyzed/guides/events/).",
        "params": {
            "widget": "The widget (a string is wrapped in a container).",
            "cursor": 'Mouse cursor over the widget, such as `"pointer"` or `"grab"`.',
            "handlers": "`event=handler` pairs. A handler that takes an argument gets a `pz.Event`; a non-callable value is a message for `update`; `None` removes it.",
        },
        "example": """
            pz.container(card, padding=12).on(click=self.select, drag=lambda e: self.move(e.dx, e.dy))
        """,
    },
    "pyzed.Event": {
        "desc": "What happened, passed to event handlers: `type`, `x`, `y` (relative to the widget), `dx`, `dy` (scroll or drag movement), `width`, `height`, `button`, `key`, `shift`, `ctrl`, `alt`, `logo`, and `value`/`source` for custom events.",
    },
    "pyzed.Dock": {
        "desc": "A Zed-style workspace: a `center` with `pz.DockPanel`s docked left, right, bottom or top. Users resize a side by dragging its inner edge and move a panel by dragging its tab onto a drop zone (or from the tab's right-click menu). `on_layout` receives the layout as a dict to save; pass it back as `layout=`. See [Layout](/pyzed/guides/layout/#docks-and-resizable-panels).",
        "params": {
            "args": "Props by position: `center`, `panels`, `layout`.", "kwargs": "Props and handlers by name, plus `key=`.",
            "center": "The main area.", "panels": "A list of `pz.DockPanel`.",
            "layout": "A saved layout (from `on_layout`) to restore.",
            "on_layout": "Called with `event.value` = `{positions, sizes, active, hidden}` when panels move, resize or switch.",
        },
        "example": """
            pz.Dock(center=editor, panels=[
                pz.DockPanel("project", "Project", tree, icon="folder", side="left"),
                pz.DockPanel("terminal", "Terminal", terminal, icon="terminal", side="bottom"),
            ], layout=self.layout, on_layout=lambda e: setattr(self, "layout", e.value))
        """,
    },
    "pyzed.DockPanel": {
        "desc": "A panel for `pz.Dock`.",
        "params": {
            "id": "Stable id (used in the saved layout).", "title": "Tab title.", "content": "The panel's widget.",
            "icon": "Lucide icon for the tab.", "side": 'Starting side: `"left"`, `"right"`, `"bottom"` or `"top"`.',
        },
    },
    "pyzed.Component": {
        "desc": "Base class for custom components, like React components: annotated class attributes are props, other attributes are state kept between renders, `render()` returns widgets and `events` declares custom events raised with `self.emit(name, value)`. Calling the class returns a widget. Components appear in the designer's toolbox. See [Custom components](/pyzed/guides/components/).",
        "example": """
            class Rating(pz.Component):
                value: int = 0
                events = {"change": "A star was picked."}

                def render(self):
                    return pz.row([pz.text("★").on(click=lambda i=i: self.emit("change", i)) for i in range(1, 6)])

            Rating(value=3, on_change=lambda e: print(e.value))
        """,
    },
    "pyzed.state": {
        "desc": 'Declares a private state variable on a component class: the parent cannot pass it, and every instance starts with its own copy of the default (lists and dicts are safe). The designer lists it next to the props. See [Custom components](/pyzed/guides/components/).',
        "params": {'default': 'Initial value, copied for each instance.', 'doc': 'Description shown in the designer.'},
        "example": """
            class Counter(pz.Component):
                step: int = 1
                count: int = pz.state(0)
        """,
    },
})
_page("app")["sections"][-1][1]["pyzed.Event"]["params"] = {
    "type": "Event name.", "x": "Pointer x, relative to the widget.", "y": "Pointer y, relative to the widget.",
    "dx": "Horizontal scroll (lines) or drag movement.", "dy": "Vertical scroll (lines) or drag movement.",
    "width": "Widget width.", "height": "Widget height.", "button": '`"left"`, `"right"`, `"middle"`...',
    "key": 'Key combo, such as `"ctrl-s"`.', "shift": "Shift held.", "ctrl": "Control held.", "alt": "Alt held.",
    "logo": "Cmd/Windows key held.", "value": "Value of a custom event.", "source": "Component that emitted it.",
}
_page("app")["sections"][-1][1]["pyzed.Component"]["params"] = {
    "args": "Props, in declaration order.",
    "kwargs": "Props by name, `on_<event>=` handlers (custom, lifecycle or common events) and `key=` to keep state when items move.",
}

# -- Dialogs and translations -------------------------------------------------
_section("ui", "Dialogs", {
    "pyzed.ui.dialog_layer": {
        "desc": "Shows a dialog centered over `base` with a dimmed backdrop. With `dialog=None` it returns `base` unchanged, so it can always wrap the view. See [Dialogs](/pyzed/guides/i18n/#dialogs).",
        "params": {"base": "The UI underneath.", "dialog": "A dialog from the functions below, or `ui.modal`.",
                   "on_dismiss": "Sent when the backdrop is clicked."},
        "example": """
            ui.dialog_layer(self.main_view(), ui.confirm("Delete 3 files?", self.delete, self.cancel, danger=True)
                            if self.asking else None, on_dismiss=self.cancel)
        """,
    },
    "pyzed.ui.alert": {
        "desc": "A message with one button.",
        "params": {"message": "Text or widget.", "on_close": "The button and the close icon.",
                   "kind": '`"info"`, `"success"`, `"warning"` or `"error"` adds an icon.', "ok_label": "Button text (default: OK, translated)."},
    },
    "pyzed.ui.confirm": {
        "desc": "Asks a yes/no question.",
        "params": {"message": "Text or widget.", "on_confirm": "The confirm button.", "on_cancel": "Cancel, the close icon.",
                   "danger": "Paints the confirm button red and labels it Delete.", "kind": "Adds an icon, as in `alert`.",
                   "confirm_label": "Confirm button text.", "cancel_label": "Cancel button text."},
    },
    "pyzed.ui.prompt": {
        "desc": "Asks for a line of text.",
        "params": {"value": "Current text.", "on_input": "Receives each edit.", "on_submit": "Enter or the submit button.",
                   "on_cancel": "Cancel, the close icon.", "message": "Text above the field.", "id": "Field id (for `Command.focus`).",
                   "submit_label": "Submit button text.", "cancel_label": "Cancel button text."},
    },
    "pyzed.ui.choice": {
        "desc": "A message with your own buttons.",
        "params": {"options": "`(label, on_press)` pairs; the last one is the main button.", "on_cancel": "The close icon."},
    },
    "pyzed.ui.unsaved_changes": {
        "desc": "\"Save your changes to *name* before closing?\" with Don't save, Cancel and Save.",
        "params": {"name": "File or document name.", "on_save": "Save.", "on_discard": "Don't save.", "on_cancel": "Cancel."},
    },
}, before="Controls")

_section("app", "Languages", {
    "pyzed.t": {
        "desc": "The text for `key` in the current language, formatted with `values`. Falls back from `\"es_AR\"` to `\"es\"`, then to the fallback language, then to the key. See [Languages](/pyzed/guides/i18n/).",
        "params": {"key": "Dotted key, like `\"menu.open\"`.", "language": "Look it up in another language.",
                   "default": "Returned when the key is missing (default: the key).",
                   "values": "Values for `{name}` placeholders; `count=` also picks the plural form."},
        "example": """
            i18n.add("es", {"greeting": "¡Hola, {name}!", "files": {"one": "{count} archivo", "other": "{count} archivos"}})
            i18n.set_language("es")
            pz.t("greeting", name="Kev"), pz.t("files", count=3)
        """,
    },
    "pyzed.i18n.add": {"desc": "Adds or overrides texts for a language. Nested tables become dotted keys; `{\"one\": ..., \"other\": ...}` tables are plural forms.",
                       "params": {"language": "Language code, like `\"es\"` or `\"pt_BR\"`.", "catalog": "Dict of texts."}},
    "pyzed.i18n.load": {"desc": "Loads every `<language>.json` and `<language>.toml` in `folder`; returns the languages found.", "params": {"folder": "Folder with the catalog files."}},
    "pyzed.i18n.set_language": {"desc": "Switches the language. The app shows it on its next render, so call it from a handler.", "params": {"language": "Language code, like `\"es\"`."}},
    "pyzed.i18n.language": {"desc": "The current language, normalized (`\"es_ar\"`)."},
    "pyzed.i18n.languages": {"desc": "The languages with a catalog."},
    "pyzed.i18n.set_fallback": {"desc": "The language used when a text is missing (default `\"en\"`).", "params": {"language": "Language code."}},
    "pyzed.i18n.on_change": {"desc": "Calls `listener(language)` after every switch; returns a function that removes it.", "params": {"listener": "Callable that receives the new language."}},
    "pyzed.i18n.system_language": {"desc": "The operating system's language (`LANG`, `LC_ALL` or the locale).", "params": {"default": "Returned when the system reports none."}},
    "pyzed.i18n.has": {"desc": "Whether `key` has a text in the language or its fallbacks.", "params": {"key": "Dotted key.", "language": "Language to check (default: the current one)."}},
})
