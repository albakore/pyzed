# Pyzed best practices

Rules that keep Pyzed apps fast, correct and easy to change. They are written for AI agents but
hold for people too.

## Before writing code

- **Look names up, don't guess them.** Use `list_components` / `describe_component` for the exact
  signature of a widget or component, `search_icons` for icon names and `list_themes` for theme
  names and color tokens. Run `validate_code` on what you wrote.
- Prefer a ready-made `pz.ui` component over rebuilding it from `pz.*` primitives: they already
  follow the theme, sizes and hover states of Zed.
- For a whole screen (login, dashboard, settings, data table, chat, IDE layout, onboarding, media
  player, kanban), start from a block: `read_example("blocks/dashboard")`. Blocks are tested, use
  theme tokens and show how the components fit together.
- Don't name `App` attributes after window options (`title`, `size`, `position`, `theme`, `style`,
  `scale`...) unless you mean them: the runtime reads them.

## Design (the essentials of `get_guide("design")`)

- **Job first**: name each screen's job in one sentence and its **one primary action** (`variant="solid"`); the
  rest is `"filled"`, `"ghost"` or a menu. Start from the matching block (list + detail, table, dashboard,
  settings, form, wizard, workspace).
- **Hierarchy**: one `ui.heading` per screen (`level=1` page, `2` section, `3` group), body `ui.label` at `"md"`,
  secondary text `color="text_muted"`. Sizes only from the scale `xs` 11 · `sm` 12 · `md` 13.5 · `lg` 16 ·
  `xl` 20 · `2xl` 26; at most two weights.
- **Spacing on a 4 px grid**: 4 · 8 · 12 · 16 · 24 · 32 · 48. Inner space ≤ outer space; group by proximity
  before adding lines; forms and text 320–720 px wide.
- **Color**: theme tokens only. Layers `background` → `panel` → `surface` → `elevated`; `accent` for the primary
  action, selection and focus (≤ 10 % of the screen); `error`/`warning`/`success`/`info` only for status, always
  with an icon or text; `text_placeholder` never for real content. Check Pyzed Dark and Pyzed Light.
- **States**: every control has hover, pressed, focus, disabled, loading and invalid; every data region has
  loading (`ui.spinner`, `ui.progress`), empty (`ui.empty_state` with an action), error (`ui.callout(tint="error")`
  with Retry) and ideal states.
- **Feedback**: < 100 ms just update; up to 1 s `loading=True`; up to 10 s a spinner; longer a progress with
  Cancel. Prefer undo to confirmation; `ui.confirm(danger=True)` names the object and the action.
- **Forms**: one column, a visible label per input (`ui.field`), errors under the field after submit that say
  how to fix it, focus on the first field, primary button at the bottom right.
- **Writing**: sentence case, verb + object on buttons ("Create project"), errors = what happened + how to fix.
- **Accessibility**: Tab order = reading order, visible focus, shortcuts with `keys=`, tooltips on icon buttons,
  targets ≥ 24 px, room for 30 % longer translations.
- Run `review_design` and look at `screenshot(..., theme="Pyzed Light")` and `theme="Pyzed Dark"` before
  delivering.

## Architecture (the essentials of `get_guide("app-architecture")`)

- `pyzed new my_app` for anything beyond one screen: models, rules and stores in `src/<package>/` (no `pyzed`
  imports there), adapters (database, HTTP, files) behind `typing.Protocol` ports, views, components, forms and
  the stylesheet in `ui/`, tests in `tests/`, one composition root (`main.py`) that wires them.
- One owner per piece of state; derive instead of duplicating; change state through store methods; typed
  messages (frozen dataclasses + `match` in `update`) once the app grows.
- Background work returns results as messages; only the UI thread changes state. Track each request as
  idle/loading/ready/error and drop stale results.
- Services start in `on_start` and stop in `on_close`; settings in `pz.Settings`; secrets in the keychain or the
  environment; every user-facing string through `pz.t`; `logging`, not `print`.
- Feature folders when the app grows; `ui.error_boundary` around independent regions; test domain → stores →
  app → screenshots.

## `view()`

- `view()` is called after **every** message. Keep it cheap and **side-effect free**: no I/O, no
  network, no state changes, no `time.sleep`. Compute what to show; do the work in `update`, in
  callbacks or in background tasks.
- Build the tree from state only. Never cache widgets across renders or mutate them: widgets are
  immutable values, so build new ones.
- Split large views into methods (`self.sidebar()`, `self.toolbar()`) or functions that take data
  and callbacks and return widgets, like `pz.ui` does.

## Keyboard

- Show shortcuts with `keys=` (`ui.icon_button("save", self.save, tooltip="Save", keys="ctrl-s")`,
  `ui.button(..., keys=...)`, `ui.MenuItem(..., keys=...)`), never inside the text: they are drawn as
  key caps in the platform's style. `ui.keys_text(keys)` gives plain text for a label.
- `ui.select`, `ui.switch`, `ui.checkbox`, `ui.slider`, `ui.segmented` and `ui.radio_group` take the
  keyboard focus (click or Tab) and keep it: a select then picks the next option with ↓ without
  opening. The keys they use do not reach `on_key`. Pass `id=` to focus one with `Command.focus(id)`.
- Make a custom control keyboard-friendly with `pz.focusable(content, on_key, keys=[...])`.

## State and messages

- Keep all state on the app (or on a component). Initialize it in `__init__` (or `setup()` for
  components); never use mutable class attributes as state on an `App`.
- Small apps: pass callables (`ui.button("Save", self.save)`). Larger apps: plain-value messages
  handled in `update` keep the logic in one place and are easy to test.
- **Lambdas in loops** must capture the loop variable: `lambda item=item: self.open(item)`.
- `pz.run(...)` starts the event loop once per process and blocks. Call it only at the bottom of
  the main script, under `if __name__ == "__main__":` when the module is also imported.

## Effects and async

- Return a `pz.Command` from `update`, callbacks or `on_start` for effects (focus, scroll, close,
  windows...). Don't call window APIs from `view()`.
- Slow or blocking work goes in a coroutine (`async def`), a generator or `pz.spawn(...)`: the UI
  keeps responding and each yielded value goes to `update`. Timers and streams belong in
  `subscriptions()` (`pz.every`, `pz.listen`).

## Components

- Reach for `pz.Component` when a piece has its own state or events, or is reused. Otherwise a
  plain function returning widgets is simpler.
- Props are annotated class attributes with defaults; private state uses `pz.state(default)`;
  custom events are declared in `events = {"name": "doc"}` and raised with `self.emit(name, value)`.
  Document each prop and event: the designer and these tools show the docs.
- Give components created in loops a stable `key=` so their state follows the item.
- Containers take their content as `children` (positional arguments), like HTML. Share values many
  levels deep with `pz.provide(...)` / `pz.use_context(...)` instead of passing props down each level.
- A component's docstring, `label`, `icon` and `category` are how it appears in the designer's
  toolbox. Set `designer = False` to keep internal components out of it.

## Styling and themes

- Use theme tokens (`"accent"`, `"panel"`, `"elevated"`, `"border"`, `"text_muted"`...) instead
  of hard-coded hex colors, so light and dark themes both work.
- Reuse looks with `pz.stylesheet` classes (or `pz.Style(...)` / `pz.define_style(...)`) instead of
  repeating keyword styles. Call `pz.stylesheet` at module level, not in `view()`.
- Hover, pressed and focus looks go in the style (`hover=`, `":hover"` rules) with a `transition`,
  not in state the app keeps by hand.
- Use `pz.icon(name)` / `icon=` with Lucide names from `search_icons`.

## Layout

- Build screens like a web page: `pz.box` containers (`display="flex"`/`"grid"`, `gap`), a
  `pz.stylesheet` of classes for the look, and `@media` rules or `pz.media()` for narrow windows.
  Give boxes classes instead of repeating keyword styles on each one.
- A `"fill"` child makes its parent fill too; give columns that should hug their content an
  explicit `width="shrink"`.
- Don't put a `pz.responsive` inside a vertical `pz.scrollable`; give scrollable content a fixed
  or shrink height instead.
- Long or unbounded lists go inside `pz.scrollable`.

## Forms made with the designer

- Keep layout in the `.pzform` and logic in the handlers module next to it. Handlers are
  `def <control>_<event>(form, event):` and change controls through `form.<control>.<prop>`.
- Control names must be valid identifiers and must not be reserved (`name`, `title`, `size`,
  `window`, `close`, Python keywords).
- Generate forms with `new_form` (or `pyzed.designer.Document` from Python) and check them with
  `validate_form` instead of hand-writing JSON.

## Projects, testing and shipping

- Start with `pyzed new my_app` (uv, ruff, ty and git ready) and run with `pyzed dev main.py` for
  hot reload. Check with `pyzed check` before committing.
- Add libraries with `pyzed add <name>` (uv), never `pip install` into the project. Pyzed Design runs the uv
  chosen in Settings → Package managers (included, this computer's or a custom path); if uv fails there, point
  the user to that page instead of working around it.
- Test logic without a window: create the app, call `update(...)` or the callbacks, and assert on
  the state. Smoke-test views with `app.screenshot(path)` (off-screen, no GPU), or with the
  `screenshot` tool of this server. `pyzed record shot` / `pyzed record clip` record any app, form or
  component from the command line, in several themes and sizes at once.
- Package with `pyzed build` (PyInstaller); `pyzed build --workflow` writes a CI workflow that
  builds for Linux, Windows and macOS.
