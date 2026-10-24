# Designing professional Pyzed interfaces

How to design screens that look and feel like a professional product: the UI and UX fundamentals
(hierarchy, spacing, typography, color, states, feedback, accessibility, writing) and how each one
maps to Pyzed's components, styles and theme tokens. Follow these rules for every screen, then run
`review_design` on the code and look at `screenshot` in both `"Pyzed Dark"` and `"Pyzed Light"`.

## 1. Start from the user's task, not from the widgets

1. **Name the job of the screen in one sentence** ("find an invoice and send it again"). Everything on the
   screen helps that job or goes somewhere else (a menu, a settings page, a second tab).
2. **Pick the primary action.** One per screen or dialog. It gets the strongest button (`variant="solid"`);
   everything else is secondary (`"filled"`), tertiary (`"ghost"`/`"subtle"`) or a menu item.
3. **Choose a known pattern** before inventing one. Users already know them, and `list_examples(kind="blocks")`
   has each as a tested screen:

| The task | Pattern | Start from |
| --- | --- | --- |
| Browse items and work on one | List + detail (sidebar 220–280 px, content fills) | `blocks/file_explorer`, `blocks/chat` |
| Compare many records | Table with toolbar (search, filters, bulk actions) | `blocks/data_table` |
| Watch numbers | Dashboard: a row of `ui.stat`, then charts, then a table | `blocks/dashboard` |
| Change preferences | `ui.settings_group` of `ui.field` rows, saved at once | `blocks/settings` |
| Sign in, sign up, a short form | One centered column 320–420 px wide | `blocks/login` |
| A first run or a long process | Steps with progress and Back / Next | `blocks/onboarding` |
| Tools on a document (editors, IDEs) | `ui.workspace`: title bar, docks, tabs, status bar, command palette | `new_app(layout="workspace")` |
| Work in columns | Board of cards | `blocks/kanban` |

4. **Design every state of the screen** (section 7) before polishing the ideal one.

## 2. Visual hierarchy

The eye should land on the most important thing first, then the next. Hierarchy comes from, in order of
strength: **size, weight, color contrast, position and space**. Use as few levels as you can.

- **One title per screen**: `ui.heading(..., level=1)` (26 px) for a page, `level=2` (20 px) for a section,
  `level=3` (16 px) for a group. Inside dense tools (panels, inspectors) `ui.panel_header` replaces headings.
- **Body text** is `ui.label` at `"md"` (13.5 px, the Zed size). Secondary text uses `color="text_muted"`,
  never a smaller size alone. Captions and metadata use `size="sm"` (12 px) and `"text_muted"`.
- **Emphasis by contrast, not decoration**: a semibold weight or the `text` color against `text_muted` is
  enough. Don't underline, don't put everything in bold, don't use more than two weights on a screen.
- **Top-left is read first** (in left-to-right languages): the title and the main content go there; the
  primary action goes where the flow ends (bottom-right of a dialog or form, top-right of a page toolbar).
- **Group by proximity**: related things are close, unrelated things are far. Space separates better
  than lines; add `ui.divider()` only where space alone is ambiguous.

## 3. Spacing and layout

Use a **4 px grid** and a small scale. Consistency matters more than the exact numbers.

| Token | px | Use it for |
| --- | --- | --- |
| `2xs` | 2 | Icon to its badge, tight key caps |
| `xs` | 4 | Inside compact controls, between an icon and its label |
| `sm` | 8 | Between related controls in a row, list item padding |
| `md` | 12 | Between fields of a form, inside cards on dense screens |
| `lg` | 16 | Panel and card padding, between groups of fields |
| `xl` | 24 | Between sections, padding of a page or dialog |
| `2xl` | 32 | Between major regions, padding of a spacious page |
| `3xl` | 48 | Hero and empty-state breathing room |

Rules:

- **Inner space ≤ outer space**: the padding of a card is smaller than the gap between cards; a label is
  closer to its field than to the previous field.
- **Align to a few edges.** Every block of a column shares the same left edge; inputs of a form share the same
  width. Mixed alignments look accidental.
- **Reading width**: text blocks and forms are 320–720 px wide (`max_width`). Don't stretch a paragraph or a
  form across a 1600 px window: center it or give the extra space to a list or a canvas.
- **Density**: tools (editors, inspectors, dashboards for experts) are compact like Zed: controls `"sm"`/`"md"`,
  12–16 px padding. Consumer screens (onboarding, sign in, settings for everyone) are comfortable: `"md"`/`"lg"`
  controls, 24–32 px padding. Pick one density per screen.
- **Fixed chrome, flexible content**: sidebars and inspectors have a fixed width (`width=240`, resizable with
  `pz.split`), the content `"fill"`s. Set `App.min_size` so the layout never breaks.
- **Responsive windows**: use `@media (max_width: ...)` rules or `pz.media()` to collapse a sidebar into a
  menu, stack columns and hide secondary panels below ~720 px.
- **Layout with boxes**: `pz.box(display="flex"|"grid", gap=...)` and stylesheet classes, never spacer
  widgets with magic numbers. A flex row (a toolbar, a list row) inside a column takes `height="shrink"`;
  otherwise the rows share the column's height and spread out.

## 4. Typography

Pyzed ships IBM Plex Sans (UI) and IBM Plex Mono (code). The type scale of `ui.label(size=...)`:

| Size | px | Use |
| --- | --- | --- |
| `xs` | 11 | Badges, key caps, dense table metadata |
| `sm` | 12 | Captions, helper text, status bar, table headers |
| `md` | 13.5 | Body text, controls, list items (the default) |
| `lg` | 16 | `heading(level=3)`, lead paragraphs, comfortable screens |
| `xl` | 20 | `heading(level=2)`, section titles, dialog titles on big dialogs |
| `2xl` | 26 | `heading(level=1)`, page titles, the number of a `ui.stat` |

- Use the named sizes, not arbitrary pixels: a screen with 13, 14, 15 and 17 px text looks unplanned.
- **Sentence case** everywhere ("Save changes", not "Save Changes" or "SAVE CHANGES"). Uppercase only for
  tiny overlines, with letter spacing, and rarely.
- Line length 45–90 characters; long text wraps (`wrap=True`) inside a width-limited box.
- **Numbers**: right-align numeric columns, use the same decimals in a column, put the unit in the header
  (`"Size (MB)"`), and use `mono=True` for ids, hashes, paths and code.
- Never use text smaller than 11 px, nor `text_placeholder`/`text_disabled` for information (they are too
  faint to read on purpose).

## 5. Color with theme tokens

Colors come from the theme, so the app follows Pyzed Dark, Pyzed Light and any theme the user picks.
**Never hard-code a hex color** in a view or a stylesheet: pass a token name (`background="panel"`,
`color="text_muted"`) or read `pz.theme.current().<token>` for drawing code.

| Role | Token | Pyzed Dark | Pyzed Light | Use |
| --- | --- | --- | --- | --- |
| App background | `background` | `#0d0e11` | `#f6f7f9` | Behind everything, gaps between panels |
| Chrome | `panel` | `#191c22` | `#f1f3f6` | Sidebars, title bar, status bar, docks |
| Content | `surface` / `editor` | `#14161b` | `#ffffff` | The main working area, inputs, documents |
| Raised | `elevated` | `#222630` | `#ffffff` | Cards, popovers, menus, dialogs (with `shadow`) |
| Hover | `element_hover` / `ghost_hover` | `#222630` | `#e7eaf0` | Hovered rows and ghost buttons |
| Lines | `border` / `border_variant` | `#2a2f39` | `#dce0e7` | Separators, card and input outlines |
| Focus | `border_focused` | `#8b83ff` | `#4f46e5` | Focus rings, active inputs |
| Text | `text` | `#e7e9ee` | `#14161b` | Main text and icons |
| Secondary text | `text_muted` | `#9aa1ae` | `#576070` | Descriptions, metadata, inactive tabs |
| Placeholder / disabled | `text_placeholder` / `text_disabled` | `#5c6370` | `#9aa1ae` | Only placeholders and disabled controls |
| Brand / primary | `accent` (+ `on_accent` text) | `#5b50f0` | `#4f46e5` | The primary button, selection, links, progress |
| Accent as text | `text_accent` | `#8b83ff` | `#4f46e5` | Links and accent text on dark surfaces |
| Status | `error`, `warning`, `success`, `info` | `#f26d85` `#f5a524` `#3fcf8e` `#6fc3ff` | `#d0344f` `#b45f00` `#12805c` `#0b6bcb` | Only for status: validation, alerts, deltas |
| Instruments | `led`, `display`, `display_text` | amber | amber | LEDs and LCD read-outs (`ui.led`, `ui.lcd`), never for brand |

Rules:

- **Layers**: `background` → `panel` → `surface` → `elevated`. Each step up is one layer closer to the user.
  Don't put a card of the same color as its background without a border.
- **60-30-10**: about 60 % neutral surfaces, 30 % text and lines, at most 10 % accent. If more than one thing
  per screen is accent colored, nothing stands out.
- **Status colors mean status.** Red is for errors and destructive actions only, green for success, amber for
  warnings. Don't use them for decoration or categories (use `players` or neutral badges for categories).
- **Never rely on color alone**: pair it with an icon, a label or a shape (`ui.callout` and `ui.badge` do).
- **Contrast**: body text needs 4.5:1 against its background, large text (≥ 18 px, or 14 px bold) and icons
  3:1. `text` and `text_muted` pass on every Pyzed surface; `text_placeholder` does not (2.3–3:1), so it is
  never used for real content. In Pyzed Light the status colors are ~4.4:1 on `panel`: put status text on
  `surface` or pair it with an icon.
- **Both themes**: check every screen with `screenshot(code, theme="Pyzed Light")` and
  `theme="Pyzed Dark"`, and offer `pz.themes.auto()` (follows the system) as the app's theme.
- Shadows only on raised layers (`elevated`): `shadow="shadow"` token, never black on light themes.
- Corner radius: `theme.radius` (8 in the Pyzed themes) for cards and dialogs, `theme.radius_sm` (5) for
  controls; nested corners are smaller than their parent's.

## 6. Components and actions

- **Button hierarchy**: one `variant="solid"` (primary) per view; `"filled"` for secondary actions,
  `"ghost"`/`"subtle"` for tertiary ones and toolbars, `variant="error"` (or `ui.confirm(danger=True)`) for
  destructive ones. Disabled buttons should be rare: prefer enabled buttons that explain what is missing.
- **Order of buttons**: in dialogs and forms, secondary on the left and primary on the right, at the bottom
  right (`Cancel` · `Save`). Keep the same order on every screen.
- **Labels are verbs + objects**: "Create project", "Send invoice", "Delete 3 files". Never "OK", "Submit",
  "Yes" or "Click here": a dialog's buttons must make sense without reading the question.
- **Icon-only buttons** (`ui.icon_button`) always have a `tooltip=` and, when there is a shortcut, `keys=`.
  Use them in toolbars for frequent actions with well-known icons; anything else gets a text label.
- **Size**: interactive targets are at least 24 px tall (`ui.button` `"md"` is 28 px); keep 8 px between
  neighbouring targets.
- **The right control**: 2–5 exclusive options → `ui.segmented` or `ui.radio_group`; more → `ui.select`;
  on/off applied at once → `ui.switch`; on/off applied on Save → `ui.checkbox`; a number in a range →
  `ui.slider` with a `ui.number_field`; dates → `ui.DatePicker`; many items → `ui.search_input` + a list.
- **Reuse `pz.ui`**: its components already have hover, pressed, focus, disabled and loading states in both
  themes. Rebuild one from `pz.*` primitives only when nothing fits, and then give it every state (section 7).

## 7. States: design all of them

**Every control** has: default, hover, pressed, focus (visible ring for the keyboard), disabled, loading,
selected and invalid. `pz.ui` draws them; for your own styled boxes use
`.style(hover={...}, pressed={...}, focus={...}, transition=120)` or `":hover"` rules in the stylesheet.

**Every region that shows data** has five states. Write each one:

| State | What the user sees | In Pyzed |
| --- | --- | --- |
| Loading | Where the content will be, and that it is coming | `ui.spinner()` (≤ 2 s), `ui.progress(None)`, or `ui.progress(value)` with a label for long work |
| Empty | Why it is empty and the action that fills it | `ui.empty_state(title, description, icon=, actions=[ui.button(..., variant="solid")])` |
| Error | What failed, why if known, and how to recover (Retry) | `ui.callout(title, description, tint="error", actions=[...])`; `ui.error_boundary` around risky parts |
| Partial | Some results, and that there are more or some failed | A footer row, a `ui.badge` count, a warning `ui.callout` |
| Ideal | The content | Lists, tables, cards |

Also design: the first run (no data, no settings yet), a search with no results ("No results for "x"", with a
Clear button), offline / permission denied, and very long or missing values (truncate, show "—").

## 8. Feedback and response times

| Delay | Rule |
| --- | --- |
| < 100 ms | Feels instant: just update the view. |
| 100 ms – 1 s | Show that something happens: the button's `loading=True`, a pressed state. |
| 1 – 10 s | A spinner or an indeterminate `ui.progress` next to what is loading, and keep the UI usable. |
| > 10 s | A determinate progress with what is happening ("Uploading 3 of 12"), and a Cancel button. |

- Slow work never runs in `view()` or blocks a callback: return a coroutine, use `Command.perform` or a
  `pz.Worker` (see `get_guide("app-architecture")`).
- **Confirm results where they happened**: the row updates, the field shows a check. Use a `ui.toast` (with
  `kind="success"`, auto-dismissed) for actions whose result is not visible, and an error toast or callout
  that stays until dismissed for failures.
- **Prefer undo to confirmation**: delete at once and offer "Undo" in a toast. Ask with `ui.confirm` only for
  destructive actions that can't be undone, and name the object ("Delete "Q3 report"? This can't be undone.")
  with a danger button labelled with the action ("Delete report").
- **Don't lose work**: warn before closing with unsaved changes (`ui.unsaved_changes`, `App.on_close`),
  keep drafts, and keep the user's input when a request fails.
- Keyboard: `Enter` submits the focused form, `Esc` closes the top dialog or popover, shortcuts are shown with
  `keys=` on buttons, menu items and tooltips.

## 9. Forms

- **One column**, labels above or beside the fields (`ui.field(title, control)`), in the order people think
  (name before email before password). Group long forms with `ui.settings_group` or headings.
- Every input has a **visible label**: a placeholder is an example (`"you@example.com"`), not the label.
- Mark the exception: if most fields are required, mark the optional ones ("Optional"), and vice versa
  (`required=True` adds `*`).
- **Validate on submit, then live**: show errors after the first submit or when a field loses focus, never
  while the user is still typing the first time. The error goes under its field (`ui.field(error=...)` plus
  `invalid=True` on the control) and says how to fix it ("Enter an email like name@example.com").
- Put the focus on the first field when the form opens (`Command.focus(id)`) and on the first invalid field
  after a failed submit.
- Sensible defaults, input masks only when they help (dates, numbers), and never clear the form after an error.
- While submitting: the primary button shows `loading=True`; the form stays readable.

## 10. Navigation and information architecture

- **Where am I?** The selected item in the sidebar, the active tab and the window title say it.
  `ui.breadcrumbs` for deep hierarchies.
- **Shallow and predictable**: at most three levels; the same thing is always in the same place.
- **Power users**: every command is reachable from the keyboard, the command palette (`ui.command_palette`)
  and menus (`frame_menus`), not only from buttons. Show shortcuts with `keys=`.
- Dialogs are for short, focused tasks that block the rest; anything longer is a page or a panel.
  Never stack dialogs. Popovers and menus close on `Esc` and on a click outside.
- Remember the user's place: the selected tab, sizes of split panels, filters and window size (`pz.Settings`).

## 11. Accessibility

- **Keyboard first**: `Tab` order follows `view()` order, so build the tree in reading order. Custom controls use
  `pz.focusable(...)`; give the important actions shortcuts (plain buttons don't take the focus yet).
- **Visible focus**: keep the focus rings `pz.ui` draws; custom focusables pass
  `ring_color=theme.border_focused`.
- **Contrast** as in section 5, and never color alone.
- **Text, not only icons**: Pyzed has no screen reader support yet, so meaning must be in visible text
  (labels, tooltips, empty states).
- **Motion**: animations respect the system's reduced motion setting automatically
  (`pz.system_reduced_motion()`); don't convey information only through motion.
- **Room for languages**: Spanish and German text is ~30 % longer than English. Don't fix widths of buttons and
  labels to the English text; use `pz.t()` for every string (`get_guide("i18n")`).
- Targets ≥ 24 px, `App.min_size` set, and the UI scales with `App.scale` and the system DPI.

## 12. Motion

- Motion explains change: something appears (fade + small move), moves (to its new place), or reacts (press).
  Never decorate with motion that repeats forever.
- Durations: 100–150 ms for hover and press (`transition=120`), 150–250 ms for popovers, toasts and panels,
  250–400 ms for page transitions. Enter with ease-out, leave with ease-in.
- Animate `opacity` and position, not layout-heavy properties, and only what changed (`pz.presence` for items
  entering and leaving a list, `pz.stagger` for a list appearing).

## 13. Writing (UX copy)

- Short, specific, in the user's words. Front-load the important word: "Invoices: 3 overdue".
- **Errors**: what happened + why (if known) + what to do. "Couldn't save the file. The disk is full. Free some
  space and try again." Never blame the user, never show raw exceptions as the only message (put the details
  behind a Details button, like `ui.error_card`).
- **Empty states** invite action: "No projects yet" + "Create a project to start." + [Create project].
- Consistent vocabulary: if it is a "project" on one screen, it is not a "workspace" on another.
- Dates and numbers in the user's locale; relative times ("2 min ago") with the exact time in a tooltip.

## 14. A screen with every state

A list screen done right: one primary action, hierarchy by size and color, the 4 px grid, tokens only, and the
loading, error, empty and ideal states.

```python
import pyzed as pz
from pyzed import ui

pz.stylesheet({
    ".page": {"padding": 24, "width": "fill", "height": "fill", "background": "surface"},
    ".row": {"padding": (8, 12), "radius": 6, "transition": 120},
    ".row:hover": {"background": "element_hover"},
})


class Invoices(pz.App):
    title = "Invoices"
    size = (640, 360)
    min_size = (420, 280)

    def __init__(self):
        self.state = "ready"            # "loading" | "error" | "ready"
        self.query = ""
        self.invoices = [("INV-1042", "Acme Corp", 1250.0, "Overdue"), ("INV-1043", "Globex", 380.5, "Paid")]

    def visible(self):
        q = self.query.lower()
        return [i for i in self.invoices if q in i[0].lower() or q in i[1].lower()]

    def toolbar(self):
        return pz.box(
            ui.heading("Invoices", level=2),
            pz.hspace(),
            ui.search_input(self.query, lambda v: setattr(self, "query", v), width=220),
            ui.button("New invoice", lambda: None, icon="plus", variant="solid", keys="ctrl-n"),
            display="flex", gap=8, align="center", height="shrink",
        )

    def row(self, number, client, amount, status):
        tint = {"Overdue": "error", "Paid": "success"}.get(status, "info")
        return pz.box(
            ui.label(number, mono=True, color="text_muted", size="sm"),
            ui.label(client, width="fill"),
            ui.badge(status, tint=tint),
            ui.label(f"{amount:,.2f} €", width=96, align_x="end"),
            display="flex", gap=12, align="center", height="shrink", class_="row",
        )

    def body(self):
        if self.state == "loading":
            return pz.center(ui.spinner(size=20))
        if self.state == "error":
            return ui.callout("Couldn't load the invoices", "Check your connection and try again.", tint="error",
                              actions=[ui.button("Retry", lambda: None, variant="filled")])
        rows = self.visible()
        if not rows and self.query:
            return ui.empty_state(f"No results for “{self.query}”", "Try another client or invoice number.",
                                  icon="search", actions=[ui.button("Clear search",
                                                                    lambda: setattr(self, "query", ""))])
        if not rows:
            return ui.empty_state("No invoices yet", "Create your first invoice to start getting paid.",
                                  icon="file-text", actions=[ui.button("New invoice", lambda: None,
                                                                       variant="solid")])
        return pz.scrollable(pz.box(*[self.row(*i) for i in rows], gap=2))

    def view(self):
        return pz.box(self.toolbar(), self.body(), gap=16, class_="page")


pz.run(Invoices)
```

## 15. A form done right

Labels on every field, one primary action at the bottom right, errors under their fields after submit, and a
loading state while it saves.

```python
import pyzed as pz
from pyzed import ui


class NewProject(pz.App):
    title = "New project"
    size = (460, 340)

    def __init__(self):
        self.name, self.template, self.private = "", "Empty", True
        self.errors, self.saving = {}, False

    def validate(self):
        errors = {}
        if not self.name.strip():
            errors["name"] = "Give the project a name."
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors["name"] = "Use letters, numbers, - and _ only."
        return errors

    def create(self):
        self.errors = self.validate()
        if self.errors:
            return pz.Command.focus("name")
        self.saving = True          # the real work goes in a coroutine or Command.perform

    def view(self):
        return pz.box(
            ui.heading("Create a project", level=3),
            ui.label("You can change these later in Settings.", color="text_muted", size="sm"),
            ui.field("Name", ui.input(self.name, lambda v: setattr(self, "name", v), placeholder="my-app", id="name",
                                      invalid="name" in self.errors, on_submit=self.create),
                     error=self.errors.get("name"), required=True, vertical=True),
            ui.field("Template", ui.select(["Empty", "Dashboard", "Editor"], self.template,
                                           lambda v: setattr(self, "template", v), width="fill"), vertical=True),
            ui.field("Private", ui.switch(self.private, lambda v: setattr(self, "private", v)),
                     description="Only you can open it."),
            pz.vspace(),
            pz.box(pz.hspace(), ui.button("Cancel", lambda: None, variant="ghost"),
                   ui.button("Create project", self.create, variant="solid", loading=self.saving),
                   display="flex", gap=8),
            gap=12, padding=24, height="fill",
        ).style(background="surface")


pz.run(NewProject)
```

## 16. Before you deliver: the design review

Run `review_design(code)` and fix what it reports, then check by eye with `screenshot` (or
`screenshot_project`) in both themes and at a narrow and a wide size:

1. Is there exactly one primary action per view, and is it where the flow ends?
2. Can you tell the title, the content and the secondary text apart at a glance (squint test)?
3. Is all spacing on the 4 px scale, and is inner space smaller than outer space?
4. Are all colors tokens, and does the screen work in Pyzed Light and Pyzed Dark?
5. Are the loading, empty, error and ideal states designed?
6. Does every icon-only button have a tooltip, and every input a visible label?
7. Can the whole task be done with the keyboard, with the focus visible?
8. Are the texts in sentence case, specific verbs on buttons, errors that say how to fix them?
9. Does it still work at `min_size`, and with 30 % longer text?
10. Does anything slow block the UI, and does every action give feedback within 100 ms?
