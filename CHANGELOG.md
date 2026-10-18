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
