# Pyzed best practices

Rules that keep Pyzed apps fast, correct and easy to change. They are written for AI agents but
hold for people too.

## Before writing code

- **Look names up, don't guess them.** Use `list_components` / `describe_component` for the exact
  signature of a widget or component, `search_icons` for icon names and `list_themes` for theme
  names and color tokens. Run `validate_code` on what you wrote.
- Prefer a ready-made `pz.ui` component over rebuilding it from `pz.*` primitives: they already
  follow the theme, sizes and hover states of Zed.

## `view()`

- `view()` is called after **every** message. Keep it cheap and **side-effect free**: no I/O, no
  network, no state changes, no `time.sleep`. Compute what to show; do the work in `update`, in
  callbacks or in background tasks.
- Build the tree from state only. Never cache widgets across renders or mutate them: widgets are
  immutable values, so build new ones.
- Split large views into methods (`self.sidebar()`, `self.toolbar()`) or functions that take data
  and callbacks and return widgets, like `pz.ui` does.

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
- A component's docstring, `label`, `icon` and `category` are how it appears in the designer's
  toolbox. Set `designer = False` to keep internal components out of it.

## Styling and themes

- Use theme tokens (`"accent"`, `"panel"`, `"elevated"`, `"border"`, `"text_muted"`...) instead
  of hard-coded hex colors, so light and dark themes both work.
- Reuse looks with `pz.Style(...)` / `pz.define_style(...)` instead of repeating keyword styles.
- Use `pz.icon(name)` / `icon=` with Lucide names from `search_icons`.

## Layout

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
- Test logic without a window: create the app, call `update(...)` or the callbacks, and assert on
  the state. Smoke-test views with `app.screenshot(path)` (off-screen, no GPU), or with the
  `screenshot` tool of this server.
- Package with `pyzed build` (PyInstaller); `pyzed build --workflow` writes a CI workflow that
  builds for Linux, Windows and macOS.
