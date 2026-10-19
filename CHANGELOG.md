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

## [1.0.0] - 2026-10-19

First stable version. From 1.0.0 on, the public API follows semantic versioning: breaking changes only land in a new major version.

### Highlights

- **Animations and effects**: animate any widget property, with ready-made animations, transitions between windows and visual effects such as glow, bloom, glass and transparency, in the library and in Pyzed Design.
- **AI agents**: an Agent panel in Pyzed Design and `pyzed.agents` in the library, to write code and generate components and forms, with browser login or personal tokens kept in the system keychain. `pyzed mcp` also exposes Pyzed to external agents.
- **Built-in reference**: a searchable, Godot-style reference of every component and function, inside Pyzed Design and from the library.
- **A Zed-grade code editor**: Zed's actions and keys, multiple cursors, find and replace.
- **Updates**: Pyzed Design updates itself like Zed, with a What's new tab.
- **New docs site**: a component library, the Pyzed Design manual and a download page.

### Features

- ✨ Add Zed-style updates to Pyzed Design with a What's new tab. PR [#40](https://github.com/albakore/pyzed/pull/40) by [@albakore](https://github.com/albakore).
- ✨ Add an MCP server for AI agents (`pyzed mcp`). PR [#41](https://github.com/albakore/pyzed/pull/41) by [@albakore](https://github.com/albakore).
- ✨ Add Zed's editor actions, keys, multiple cursors, find and replace, and opt-in telemetry. PR [#44](https://github.com/albakore/pyzed/pull/44) by [@albakore](https://github.com/albakore).
- ✨ Add AI agents to Pyzed Design and the library (`pyzed.agents`). PR [#47](https://github.com/albakore/pyzed/pull/47) by [@albakore](https://github.com/albakore).
- ✨ Add a built-in, searchable reference to the library and the designer, like Godot's. PR [#46](https://github.com/albakore/pyzed/pull/46) by [@albakore](https://github.com/albakore).
- ✨ Add animations, transitions and visual effects (glow, bloom, glass) to widgets, windows and Pyzed Design. PR [#48](https://github.com/albakore/pyzed/pull/48) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Fix the MCP docs index after the docs redesign and document self-updates. PR [#45](https://github.com/albakore/pyzed/pull/45) by [@albakore](https://github.com/albakore).

### Docs

- 📝 Redesign the docs site with a component library, the Pyzed Design manual and a download page. PR [#42](https://github.com/albakore/pyzed/pull/42) by [@albakore](https://github.com/albakore).
- 📝 Add the reference browser to the component library. PR [#49](https://github.com/albakore/pyzed/pull/49) by [@albakore](https://github.com/albakore).

### Translations

- 🌐 Translate the designer's context menu, code panel, color picker and status bar, and rename it to Pyzed Design. PR [#43](https://github.com/albakore/pyzed/pull/43) by [@albakore](https://github.com/albakore).

## [0.4.0] - 2026-10-19

### Highlights

- **Component Designer**: draw reusable components with typed properties, state, methods and events, inherit from them and use them like any widget, with a Component view, tabs and a New component button.
- **A much richer designer**: containers, dockable panels, menus, templates, a debug console, a Style section with a floating color picker, list and table editors, drag and drop from the outline, and a code editor with completion, diagnostics, folding and a minimap.
- **Styles and layout**: CSS-like styles for every widget with global styles, gradients and masks, plus track grids, flex, resizable panels and a Zed-style dock.
- **Apps and projects**: common events for every widget, translations, ready-made dialogs, uv projects and `pyzed build` to package an app.
- **Full API docs**: every function, method, class and component is documented.

### Features

- ✨ Add uv projects, a Project tab in the designer and `pyzed build`. PR [#18](https://github.com/albakore/pyzed/pull/18) by [@albakore](https://github.com/albakore).
- ✨ Add common events for every widget, custom components and quiet Linux/WSL startup. PR [#19](https://github.com/albakore/pyzed/pull/19) by [@albakore](https://github.com/albakore).
- ✨ Add completion, diagnostics, code lens and settings to the designer's code editor. PR [#20](https://github.com/albakore/pyzed/pull/20) by [@albakore](https://github.com/albakore).
- ✨ Add track grids, flex, resizable panels and a Zed-style dock. PR [#25](https://github.com/albakore/pyzed/pull/25) by [@albakore](https://github.com/albakore).
- ✨ Add a component designer mode: draw reusable components with properties, state, methods and events. PR [#24](https://github.com/albakore/pyzed/pull/24) by [@albakore](https://github.com/albakore).
- ✨ Add translations, ready-made dialogs and opening forms from code. PR [#26](https://github.com/albakore/pyzed/pull/26) by [@albakore](https://github.com/albakore).
- ✨ Add auto-closing pairs, code folding, a minimap, font zoom and cursor shapes to the code editor. PR [#27](https://github.com/albakore/pyzed/pull/27) by [@albakore](https://github.com/albakore).
- ✨ Add containers, dockable panels, menus, templates, a debug console and translations to the designer. PR [#28](https://github.com/albakore/pyzed/pull/28) by [@albakore](https://github.com/albakore).
- ✨ Drag components and outline rows onto the form, and open context menus where the pointer is. PR [#30](https://github.com/albakore/pyzed/pull/30) by [@albakore](https://github.com/albakore).
- ✨ Make designed components responsive, add a New component button and component inheritance. PR [#31](https://github.com/albakore/pyzed/pull/31) by [@albakore](https://github.com/albakore).
- ✨ Add a grip tab to select and drag containers in the designer. PR [#32](https://github.com/albakore/pyzed/pull/32) by [@albakore](https://github.com/albakore).
- ✨ Add CSS-like styles for every widget, global styles, gradients, masks and a color picker. PR [#33](https://github.com/albakore/pyzed/pull/33) by [@albakore](https://github.com/albakore).
- ✨ Add a Style section and the form's global style to the designer, with the color picker. PR [#35](https://github.com/albakore/pyzed/pull/35) by [@albakore](https://github.com/albakore).
- ✨ Add a Component view with tabs, typed properties, reusable methods and child access. PR [#37](https://github.com/albakore/pyzed/pull/37) by [@albakore](https://github.com/albakore).
- ✨ Float the color picker, add list and table editors, and line up the Properties and Events docks. PR [#36](https://github.com/albakore/pyzed/pull/36) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Silence "MESA: error: ZINK" with `MESA_LOG=null` (`silent` is not a Mesa option). PR [#22](https://github.com/albakore/pyzed/pull/22) by [@albakore](https://github.com/albakore).
- 🐛 Make a fixed grid height the height of each row with `columns=<int>`. PR [#29](https://github.com/albakore/pyzed/pull/29) by [@albakore](https://github.com/albakore).

### Upgrades

- ➕ Add ty to the development dependencies. PR [#23](https://github.com/albakore/pyzed/pull/23) by [@albakore](https://github.com/albakore).

### Docs

- 📝 Document setting up Pyzed with uv. PR [#21](https://github.com/albakore/pyzed/pull/21) by [@albakore](https://github.com/albakore).
- 📝 Document every function, method, class and component. PR [#38](https://github.com/albakore/pyzed/pull/38) by [@albakore](https://github.com/albakore).

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
