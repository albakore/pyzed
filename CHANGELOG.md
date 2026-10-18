# Changelog

All notable changes to Pyzed are recorded here. Each version is a heading
`## [X.Y.Z] - YYYY-MM-DD` and the project follows
[semantic versioning](https://semver.org/). Versions with a suffix
(`1.0.0-rc.1`, `0.3.0-beta.1`) are pre-releases.

Sections follow FastAPI's release notes: `### Breaking Changes`,
`### Features`, `### Fixes`, `### Refactors`, `### Upgrades`, `### Docs`,
`### Translations` and `### Internal`. They are generated from the gitmoji
commit messages when a version is released (see
[CONTRIBUTING.md](CONTRIBUTING.md#commit-messages-and-pr-titles)); notes
written by hand under `## [Unreleased]` are kept and merged in.
The documentation site reads this file on every build and marks the latest
stable version.

## [Unreleased]

## [0.3.1] - 2026-10-18

### Fixes

- 🐛 Read `pyzed.__version__` from the package metadata. PR [#17](https://github.com/albakore/pyzed/pull/17) by [@albakore](https://github.com/albakore).

## [0.3.0] - 2026-10-18

### Highlights

- **Pyzed Designer**: a Visual Basic / Qt Designer style form editor (`pyzed design app.pzform`) with a toolbox, dot-grid snapping, alignment tools, property grid, events and per-event code editing. **F5** runs the form with all its logic.
- **Hot reload**: `pyzed dev main.py` updates the open window on every save and keeps the app's state.
- **Bilingual docs**: the site is in English by default, with a full Spanish translation under `/es/`.

### Features

- ✨ Add visual form designer with event code editing, grid snapping and alignment. PR [#15](https://github.com/albakore/pyzed/pull/15) by [@albakore](https://github.com/albakore).
- ✨ Add hot reload for running apps (`pyzed dev`, `pz.run(App, reload=True)`, `PYZED_RELOAD=1`). PR [#14](https://github.com/albakore/pyzed/pull/14) by [@albakore](https://github.com/albakore).

### Upgrades

- ⬆️ Bump pyo3 from 0.27.2 to 0.30.1. PR [#11](https://github.com/albakore/pyzed/pull/11) by [@dependabot](https://github.com/apps/dependabot).
- ⬆️ Bump two-face from 0.4.5 to 0.5.2. PR [#10](https://github.com/albakore/pyzed/pull/10) by [@dependabot](https://github.com/apps/dependabot).
- ⬆️ Bump png from 0.17.16 to 0.18.1. PR [#9](https://github.com/albakore/pyzed/pull/9) by [@dependabot](https://github.com/apps/dependabot).
- ⬆️ Bump the GitHub Actions group with 7 updates. PR [#12](https://github.com/albakore/pyzed/pull/12) by [@dependabot](https://github.com/apps/dependabot).

### Docs

- 📝 README images now show up on PyPI.

### Translations

- 🌐 Make the docs bilingual (English by default, Spanish under `/es`), with Mermaid diagrams and new screenshots. PR [#13](https://github.com/albakore/pyzed/pull/13) by [@albakore](https://github.com/albakore).

### Internal

- 👷 Speed up CI, gitmoji release notes, PyPI README images and contribution guidelines. PR [#8](https://github.com/albakore/pyzed/pull/8) by [@albakore](https://github.com/albakore).
- 👷 Deploy the docs site only from `main`, not from release tags. PR [#7](https://github.com/albakore/pyzed/pull/7) by [@albakore](https://github.com/albakore).

## [0.2.0] - 2026-10-18

First version published on PyPI, as `pyzed-ui`.

### Breaking Changes

- 💥 `App.run()` raises an error when it is called a second time in the same process.

### Features

- ✨ Several windows per app: open and close extra windows, window hooks and window commands (`Window`).
- ✨ Async support: coroutines, generators and async generators from `update` or `Command.perform`.
- ✨ Subscriptions: timers with `pz.every` and streams with `pz.listen`.
- ✨ New widgets: `image` (bitmaps), `image_viewer`, `canvas` with `pz.draw`, `rich_text`, `markdown`, `qr_code`, `pick_list`, `radio`, `split`, `pin`, `grid` and `responsive`; gradients and more style options.
- ✨ New `pyzed.ui` components: `select`, `radio_group`, `number_field`, `split_button`, `chip`, `disclosure`, `callout`, `table`, `facepile`, `diff_stat`, charts, `spinner`, `popover`, `markdown`, `split` and `stat`.
- ✨ Theming: import Zed themes, bundled Ayu, Gruvbox and One themes, `Theme.generate()` and automatic light/dark switching.
- ✨ Editor: horizontal scrolling with a sticky line-number gutter, correct line numbers with `wrap`, active line, cursor autoscroll and PageUp/PageDown.

### Fixes

- 🐛 Images are clipped and rounded correctly in every renderer, including off-screen screenshots without a GPU.

### Docs

- 📝 Documentation site with guides, tutorials, API reference and component illustrations.
- 📝 Examples based on Iced's demos (todos, game of life, clock, stopwatch, downloads, websocket, multiple windows, image viewer, markdown, QR code, styling, context menu, panes) and a five-step tutorial.

### Internal

- 👷 CI and release workflows: wheels for Linux, macOS and Windows published on PyPI.

## [0.1.0] - 2026-10-18

First version (not published on PyPI).

### Features

- ✨ Elm-style runtime on top of Iced 0.14 (`App`, `update`, `view`, `on_start`, `on_key`).
- ✨ Messages can be any Python value, or callables that are called directly.
- ✨ `Command`: `exit`, `focus`, `set_editor_text`, `set_editor_cursor`, `scroll_to_end`, `batch`, `message` and `perform` (work on a thread).
- ✨ `pz.post()` to send messages from other threads.
- ✨ Base widgets: `text`, `column`, `row`, `container`, `center`, `button`, `text_input`, `scrollable`, `space`, `rule`, `mouse_area`, `stack`, `opaque`, `hover`, `tooltip`, `checkbox`, `toggler`, `slider`, `progress_bar`, `code_editor`, `svg` and `icon`.
- ✨ About 40 Zed-style components in `pyzed.ui`: buttons, forms, lists, file tree, tabs, workspace with docks, command palette, toasts, code editor and terminal.
- ✨ One Dark, One Light and Gruvbox Dark themes with Zed's color tokens, and `Theme.derive()`.
- ✨ Bundled IBM Plex fonts and Lucide icons.
- ✨ Off-screen screenshots with `app.screenshot()` (no GPU or display needed).
- ✨ CLI: `pyzed new` and `pyzed icons`.
