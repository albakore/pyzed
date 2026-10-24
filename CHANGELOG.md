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

## [1.12.0] - 2026-10-24

### Highlights

- **A faster code editor that colors like Zed**: typing sends only the changed range to the language servers, highlighting is incremental and shared with the sticky lines and the minimap, Python names get Zed's colors, and indent guides follow the scopes.
- **`pyzed record`**: screenshots and clips from the command line, from job files that record every theme and size in parallel, or from its own window, with recordings several times faster.
- **Design and architecture rules for AI agents**: two new guides, a `review_design` tool and an `AGENTS.md` in new projects, so agents build apps that look and are built like a professional product.

### Features

- ✨ Code editor: Python colors as in Zed (constants, types, properties, variables), sticky lines with their colors, indent guides by scope with the current block highlighted (*Indent guide colors*: One color or Rainbow; `ui.editor(indent_guides=...)`) and Ctrl over a name underlines it when Ctrl+click can follow it. PR [#218](https://github.com/albakore/pyzed/pull/218) by [@albakore](https://github.com/albakore).
- ⚡️ Typing in big files is fast: edits go to ty and ruff as the changed range, highlighting only parses again until it catches up, the problems list is virtual and the minimap no longer highlights the whole file on each key. PR [#218](https://github.com/albakore/pyzed/pull/218) by [@albakore](https://github.com/albakore).
- ✨ `pyzed record shot|clip|batch|gui|info`: screenshots and clips in WebP, PNG, GIF, APNG, MP4 or WebM, job files whose lists multiply (themes, sizes, scales), one process per core, a cache that skips what didn't change, and a window to edit, preview and run the jobs. `pyzed.recording` for scripts. PR [#217](https://github.com/albakore/pyzed/pull/217) by [@albakore](https://github.com/albakore).
- ⚡️ Faster screenshots and recordings: each thread keeps its off-screen renderer (92 to 20 ms per screenshot), recorded frames build the view fewer times and WebP encodes about 8x faster. PR [#217](https://github.com/albakore/pyzed/pull/217) by [@albakore](https://github.com/albakore).
- ✨ Design and architecture guides for agents (`get_guide("design")`, `get_guide("app-architecture")`, docs pages in en/es), the MCP `review_design` tool and `polish_design` prompt, `theme=` in `screenshot` and `screenshot_project`, and `pyzed new` writes an `AGENTS.md`. PR [#214](https://github.com/albakore/pyzed/pull/214) by [@albakore](https://github.com/albakore).
- ✨ Settings → Package managers: which uv to use (included, this computer's or a custom path), Install and Update for this computer's, and uv's defaults (Python of new projects, package indexes, pre-releases, offline, link mode). `pyzed.package_managers` is a registry ready for other managers. PR [#213](https://github.com/albakore/pyzed/pull/213) by [@albakore](https://github.com/albakore).
- ✨ Settings → Rendering chooses Pyzed Design's own renderer, graphics API and GPU; if the choice can't open the windows it goes back to Auto and restarts once. PR [#215](https://github.com/albakore/pyzed/pull/215) by [@albakore](https://github.com/albakore).
- ✨ Ctrl+V in the Agent panel's message box attaches the image on the clipboard when it holds no text. Editors gain `on_paste`. PR [#216](https://github.com/albakore/pyzed/pull/216) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 uv no longer fails on Windows with "os error 448" (untrusted mount point) when creating a project, preparing its environment or updating `pyzed-ui`. PR [#213](https://github.com/albakore/pyzed/pull/213) by [@albakore](https://github.com/albakore).
- 🐛 The agent's form screenshots work in the installed Pyzed Design (they opened another editor), run in the project's environment and fall back to capturing a real window when the off-screen renderer fails. `Theme.color` takes short names such as `"muted"`. PR [#216](https://github.com/albakore/pyzed/pull/216) by [@albakore](https://github.com/albakore).
- 🐛 Settings → Rendering is always shown: the project's page (Project → App rendering) no longer vanishes without a project, and apps started from the designer don't inherit its renderer. PR [#215](https://github.com/albakore/pyzed/pull/215) by [@albakore](https://github.com/albakore).
- 🐛 Duplicate line (Shift+Alt+Down) and delete line (Ctrl+Shift+K) ran twice. PR [#218](https://github.com/albakore/pyzed/pull/218) by [@albakore](https://github.com/albakore).
- 🐛 Designed components (`.pzcomp`) take the theme of the form or app they are placed in, so their panels follow Pyzed Light. PR [#214](https://github.com/albakore/pyzed/pull/214) by [@albakore](https://github.com/albakore).

### Docs

- 🍱 Every illustration of the docs, about 4,400 screenshots and clips, is recorded again in Pyzed Dark and Pyzed Light. PR [#212](https://github.com/albakore/pyzed/pull/212) by [@albakore](https://github.com/albakore).
- 📝 New guides: "Recording screenshots and clips", "Design" and "App architecture" (en/es). PR [#217](https://github.com/albakore/pyzed/pull/217) by [@albakore](https://github.com/albakore). PR [#214](https://github.com/albakore/pyzed/pull/214) by [@albakore](https://github.com/albakore).

## [1.11.0] - 2026-10-23

### Highlights

- **A brand of its own**: Pyzed Dark and Pyzed Light are the new default themes, with the Pyzed logo, app icons and an instrument-panel look (LEDs, LCD displays, a theme rack) in Pyzed Design and as components, and a redesigned docs site.
- **Faster and lighter**: idle windows skip their work (8 open windows go from 15.3 ms to 2.6 ms of CPU per tick), frame rate limits and GPU tuning, a native library 30% smaller, big images decoded off the UI thread and `@pz.background` for your own work.
- **Any screen, any device**: screens and fullscreen on a chosen monitor, always-on-top and kiosk windows, device profiles, a design resolution, touch media queries and arrow-key focus.

### Features

- ✨ Rendering settings gain isolated windows (`Window.isolated`, `Window.refresh()`), antialiasing, present mode, frame latency, memory, GPU choice, `max_fps` and `background_fps`, also in the designer and the MCP server; `pz.renderer_info()` tells the GPU and API in use. PR [#203](https://github.com/albakore/pyzed/pull/203) by [@albakore](https://github.com/albakore).
- ✨ Screens, fullscreen on a monitor (exclusive or borderless), always-on-top and kiosk windows, device profiles, a design resolution, touch media queries and focus with the arrow keys. PR [#203](https://github.com/albakore/pyzed/pull/203) by [@albakore](https://github.com/albakore).
- ⚡️ The native library is 30% smaller (39.1 MB to 27.5 MB), big images decode on worker threads (`pz.image(background=...)`) and `@pz.background` runs a function off the UI thread. PR [#203](https://github.com/albakore/pyzed/pull/203) by [@albakore](https://github.com/albakore).
- 🎨 Pyzed Dark and Pyzed Light brand themes, Pyzed Dark by default, with instrument tokens (`led`, `led_off`, `display`, `display_text`, `canvas`, `canvas_grid`, `guide`) that follow the other colors when a theme leaves them empty. PR [#207](https://github.com/albakore/pyzed/pull/207) by [@albakore](https://github.com/albakore).
- ✨ `ui.led`, `ui.led_toggle`, `ui.lcd`, `ui.theme_rack` and `pz.brand` logo widgets, with IBM Plex Sans Bold bundled. PR [#207](https://github.com/albakore/pyzed/pull/207) by [@albakore](https://github.com/albakore).
- 💄 Pyzed Design wears the brand: logo, indigo Run button, an LCD in the title bar that shows the graphics API, LED switches, a size tag, a new Properties header, a theme rack and the brand app icon. PR [#207](https://github.com/albakore/pyzed/pull/207) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Pyzed Design updates on Windows even while a process works in its folder ("Access is denied"): the updater swaps what is inside the folder when the folder itself cannot move, and writes in its log which programs run from it. PR [#205](https://github.com/albakore/pyzed/pull/205) by [@albakore](https://github.com/albakore).

> Updating from an older version still uses its own updater: if it fails, install this version with the setup program from the Download page.

### Docs

- 💄 The docs site has the Pyzed brand: Graphite and Paper palettes, IBM Plex, a new home with the install command on an amber display, LED stats, brand code themes, new favicon, icons and social cards, and a Brand page in Contributing (en/es). PR [#206](https://github.com/albakore/pyzed/pull/206) by [@albakore](https://github.com/albakore).
- 📝 The Library sidebar groups the components by category (Layout, Forms, Dates and times, System...). PR [#209](https://github.com/albakore/pyzed/pull/209) by [@albakore](https://github.com/albakore).
- 🐛 Code blocks keep their colors on every page of the docs: the site build no longer reuses pages rendered with the previous code theme. PR [#209](https://github.com/albakore/pyzed/pull/209) by [@albakore](https://github.com/albakore).
- 📝 Privacy policy page (what Pyzed Design sends over the network, what it keeps on your computer and how to turn each part off). PR [#210](https://github.com/albakore/pyzed/pull/210) by [@albakore](https://github.com/albakore).

## [1.10.1] - 2026-10-23

### Fixes

- 🐛 Fix the Windows update failing with "Access is denied" while a program runs from the app folder: the updater now stops the helpers left there (such as the bundled uv kept by an agent's MCP server), names another open Pyzed Design window instead of failing silently, and agents use a copy of uv outside the app folder. PR [#204](https://github.com/albakore/pyzed/pull/204) by [@albakore](https://github.com/albakore).

> Updating from 1.9.0 or 1.10.0 still uses the old updater: if it fails, install this version with the setup program from the Download page.

## [1.10.0] - 2026-10-23

### Highlights

- **Apps for Android**: `pyzed build --target android-arm64` (or `android-x64`) packs a project as an APK or an AAB signed with a release key, also from the Export dialog. Apps keep clear of the system bars, the camera cutout and the keyboard, and handle the back button.
- **An Agent panel like Zed's**: one thread for every agent with reasoning, tool calls as lines or cards, editable messages with Restore Checkpoint and messages queued while the agent works.
- **A sturdier Pyzed Design**: it asks about unsaved changes on close, explains failed exports, writes crashes to `crash.log`, runs untrusted projects in restricted mode and fixes uv's os error 448 on Windows.
- **Iced with the community's work**: Pyzed now builds on its own fork of Iced 0.14 with 81 community pull requests.

### Features

- ✨ System tray icons with a tooltip and a menu, without GTK: `pz.TrayIcon` and a Tray icon component in the designer's System category. PR [#194](https://github.com/albakore/pyzed/pull/194) by [@albakore](https://github.com/albakore).
- ✨ The Agent panel looks and works like Zed's: one thread model for every agent, reasoning as thinking blocks, tool calls as lines or cards, editable title, Restore Checkpoint, turn stats and queued messages. PR [#198](https://github.com/albakore/pyzed/pull/198) by [@albakore](https://github.com/albakore).
- ✨ Pyzed Design writes its crashes to `crash.log` and tells you on the next start. PR [#199](https://github.com/albakore/pyzed/pull/199) by [@albakore](https://github.com/albakore).
- ✨ Android: windows wait for the activity, keep clear of the system bars, cutout and keyboard (`safe_area`, `pz.safe_area()`), `on_back()` handles the back button, and `pyzed build --target android-arm64`/`android-x64` makes signed APKs and AABs, also from the Export dialog. PR [#201](https://github.com/albakore/pyzed/pull/201) by [@albakore](https://github.com/albakore).
- ✨ Edit the tab order on the canvas, step the z-order (Ctrl+] / Ctrl+[), find and replace in the whole project (Ctrl+Shift+F / Ctrl+Shift+H), and restricted mode for projects you have not trusted yet. PR [#200](https://github.com/albakore/pyzed/pull/200) by [@albakore](https://github.com/albakore).
- ⚡️ Pyzed Design opens faster and tells how long it took in the Logs panel, and downloaded updates are read once before the restart so the new version opens sooner. PR [#197](https://github.com/albakore/pyzed/pull/197) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 uv no longer fails with os error 448 on recent Windows 11 builds: Pyzed moves uv's Pythons to a readable folder and remakes the project's `.venv`; the app bundle is lighter too. PR [#195](https://github.com/albakore/pyzed/pull/195) by [@albakore](https://github.com/albakore).
- 🐛 A form run from the designer no longer fails with a flush error when it closes in the installed app. PR [#196](https://github.com/albakore/pyzed/pull/196) by [@albakore](https://github.com/albakore).
- 🐛 Pyzed Design asks about unsaved changes when it closes, shows why an export failed and translates the texts that still showed in English. PR [#199](https://github.com/albakore/pyzed/pull/199) by [@albakore](https://github.com/albakore).
- 🐛 Tab moves the focus in forms run from the designer. PR [#200](https://github.com/albakore/pyzed/pull/200) by [@albakore](https://github.com/albakore).

### Upgrades

- ⬆️ Iced comes from Pyzed's fork (0.14 with Pyzed's changes and 81 community pull requests, pinned by commit); `vendor/` is gone. PR [#193](https://github.com/albakore/pyzed/pull/193) by [@albakore](https://github.com/albakore).

### Docs

- 📝 Building for Android (en, es) and updated known limitations. PR [#199](https://github.com/albakore/pyzed/pull/199) by [@albakore](https://github.com/albakore).

### Internal

- 👷 CI lints the Python code with ruff. PR [#199](https://github.com/albakore/pyzed/pull/199) by [@albakore](https://github.com/albakore).

## [1.9.0] - 2026-10-22

### Highlights

- **A code editor that knows your code**: hover cards with types and docs, go to definition, find references, rename across the project, quick fixes (ruff, ty, auto-imports, `uv add`) and sticky scroll.
- **A Figma-style Properties panel**: numbers you drag, position and size first, auto layout for flex and grid containers, a margin/padding box model, file and folder pickers and animations on events.
- **Dates, files and the system**: date, range and time pickers, a calendar, a file picker, a drop zone, popups and `pyzed.system` (system info, launcher, network and power monitors).
- **Settings that follow you**: one Settings dialog with search, user profiles, per-project settings, Reset to default and the project's renderer (GPU or CPU) in `pyproject.toml`.

### Features

- ✨ IDE features in the code editor: hover, go to definition (F12, Ctrl+click), type definition, back/forward, find references, rename symbol (F2), quick fixes (Ctrl+.) and sticky scroll; the language servers fall back to the designer's Python when the project has no `.venv`. PR [#183](https://github.com/albakore/pyzed/pull/183) by [@albakore](https://github.com/albakore).
- ✨ Component icons take the color of their role (layout, input, action, navigation, display, media, system, custom) in the toolbox, the outline, the tray and the Properties/Events headers, and the Design tab is now called Toolbox. PR [#184](https://github.com/albakore/pyzed/pull/184) by [@albakore](https://github.com/albakore).
- ✨ One Settings dialog with search, user profiles, per-project settings and Reset to default; a project picks its renderer (GPU or CPU, graphics API, GPU and vsync) in `pyproject.toml`, and the MCP server reads and changes it. PR [#185](https://github.com/albakore/pyzed/pull/185) by [@albakore](https://github.com/albakore).
- ✨ Keyboard focus for selects, switches, check boxes, sliders, segmented controls and radio groups, `pz.focusable` for any control, and tooltip shortcuts shown as key caps from the keymap. PR [#186](https://github.com/albakore/pyzed/pull/186) by [@albakore](https://github.com/albakore).
- ✨ A Figma-style Properties panel: draggable numbers, Position first with align buttons, Text/Fill/Border/Spacing sections, auto layout, group and ungroup (Ctrl+G, Ctrl+Shift+G), path pickers for every file or folder property and animations on events. PR [#188](https://github.com/albakore/pyzed/pull/188) by [@albakore](https://github.com/albakore).
- ✨ `ui.Calendar`, `ui.DatePicker`, `ui.DateRangePicker`, `ui.TimePicker`, `ui.file_input`, `ui.DropZone`, `pz.popup` and `pyzed.system` (`SystemInfo`, `Launcher`, `NetworkMonitor`, `PowerMonitor`), with the toolbox split into Forms, Date & time and System. PR [#189](https://github.com/albakore/pyzed/pull/189) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 A WSL project opened from Windows still lists its tools when Windows can't reach the distro. PR [#180](https://github.com/albakore/pyzed/pull/180) by [@albakore](https://github.com/albakore).
- 🐛 A project's components load whenever it opens, and a missing one is drawn as a warning instead of breaking the form. PR [#182](https://github.com/albakore/pyzed/pull/182) by [@albakore](https://github.com/albakore).
- 🐛 Windows updates no longer keep the old version: the installer clears the old files before copying, and Restart to update stops child processes, retries the folder swap and says so if it fails. PR [#192](https://github.com/albakore/pyzed/pull/192) by [@albakore](https://github.com/albakore).
- 🐛 Component descriptions show without raw reST marks: inline code in the Properties header and clean tooltips. PR [#187](https://github.com/albakore/pyzed/pull/187) by [@albakore](https://github.com/albakore).

### Refactors

- ♻️ Custom events have their own place in the Events tab, apart from the built-in ones. PR [#181](https://github.com/albakore/pyzed/pull/181) by [@albakore](https://github.com/albakore).

## [1.8.1] - 2026-10-22

### Highlights

- **Updates that get out of the way**: the update button moves to the top right of the title bar with a subtle blink, new versions download in the background, and Pyzed Design restarts cleanly on Windows after updating.

### Features

- ✨ The update button sits in the title bar next to View, Help and Settings and blinks softly while it waits; the version found by the automatic check downloads in the background, the check runs again every 4 hours while the designer is open, a finished download is reused and old downloads are cleaned up. PR [#178](https://github.com/albakore/pyzed/pull/178) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Restarting after an update on Windows no longer fails with `'NoneType' object has no attribute 'flush'` or opens several console windows. PR [#178](https://github.com/albakore/pyzed/pull/178) by [@albakore](https://github.com/albakore).

### Docs

- 📝 The README is in English (Spanish in `README.es.md`), the repository has a `CITATION.cff`, and the docs sitemap carries real dates, unique titles and image descriptions. PR [#177](https://github.com/albakore/pyzed/pull/177) by [@albakore](https://github.com/albakore).

## [1.8.0] - 2026-10-22

### Highlights

- **A faster designer**: Pyzed draws only what changed (cached components, form controls and panels), skips rebuilds for pointer moves that change nothing and redraws big forms for less.
- **Projects that stay in sync**: Pyzed Design warns when a project needs a newer `pyzed-ui` or a sync, and the Dependencies tab keeps itself up to date.

### Features

- ✨ Pyzed Design warns when a project needs a newer `pyzed-ui` or a sync, and keeps the Dependencies tab up to date. PR [#172](https://github.com/albakore/pyzed/pull/172) by [@albakore](https://github.com/albakore).
- ✨ Hidden dialogs and drawers stay off the designer canvas until one is selected. PR [#171](https://github.com/albakore/pyzed/pull/171) by [@albakore](https://github.com/albakore).
- ✨ Select and copy text in the Agent, Logs and Console panels, and close any tab. PR [#173](https://github.com/albakore/pyzed/pull/173) by [@albakore](https://github.com/albakore).
- ⚡️ Pointer moves that change nothing no longer rebuild the view, and big forms are cheaper to redraw. PR [#174](https://github.com/albakore/pyzed/pull/174) by [@albakore](https://github.com/albakore).
- ⚡️ Only what changed is drawn again: cached components, form controls and designer panels. PR [#175](https://github.com/albakore/pyzed/pull/175) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 New projects are no longer created in the installed app's folder (where they failed, or were deleted by the next update): Pyzed Design offers the last project's folder or `~/Pyzed Projects`, and refuses folders it cannot write to with a clear message. PR [#170](https://github.com/albakore/pyzed/pull/170) by [@albakore](https://github.com/albakore).

### Docs

- 📝 The docs reach search engines and AI answer engines sooner: new and changed pages are sent to IndexNow on every deploy, Google, Bing and Yandex ownership checks come from repository variables, the PyPI page links the docs, and the FAQ tells Pyzed apart from the ZED camera SDK's `pyzed` module. PR [#176](https://github.com/albakore/pyzed/pull/176) by [@albakore](https://github.com/albakore).

## [1.7.0] - 2026-10-22

1.6.0 was tagged but never published (its wheels failed to build), so this release carries all of it.

### Highlights

- **Sound in your apps**: `pyzed.audio`, an audio engine in Rust with 23 modules joined by cables (oscillators, filters, effects, sampler, drums, sequencer, MIDI) and low-latency output on every system, plus waveform, spectrum, knobs, faders, a webcam view and a VCV-style rack with animated cables.
- **Export your app**: Pyzed Design builds apps for Windows, macOS and Linux on x64 and ARM with PyInstaller or Nuitka, with an icon and a splash screen. An Android prototype builds APKs too.
- **Components that do work**: timers, shortcuts, file watchers, processes, workers and web requests as non-visual components in Pyzed Design, and `pyzed.services` in code.
- **Hot reload that keeps your app running**: the state stays and new attributes, initial values and methods are picked up without restarting.
- **A fuller designer**: every library component in the toolbox (Dock included) with its properties and events, the startup form, any Pyzed file open in the editor, and animations you start from code with an easier timeline.
- **Tabs anywhere and WSL as Windows**: any tab goes to any dock or window of its own, and under WSL Pyzed opens its windows as native Windows programs.

### Features

- ✨ Put any tab anywhere: panels next to the forms, forms in docks, and a clearer tab drag. PR [#136](https://github.com/albakore/pyzed/pull/136) by [@albakore](https://github.com/albakore).
- ✨ Interface and code fonts and sizes in the editor settings, and duplicating lines on every cursor. PR [#135](https://github.com/albakore/pyzed/pull/135) by [@albakore](https://github.com/albakore).
- ✨ Non-visual components in Pyzed Design and `pyzed.services`: timers, shortcuts, file watchers, processes, workers, web requests and more. PR [#138](https://github.com/albakore/pyzed/pull/138) by [@albakore](https://github.com/albakore).
- ✨ An audio engine, `pyzed.audio`: modules joined by cables, low-latency devices (WASAPI, CoreAudio, PulseAudio/PipeWire, ALSA), MIDI, offline rendering to WAV and analysis for visualizers. PR [#139](https://github.com/albakore/pyzed/pull/139) by [@albakore](https://github.com/albakore).
- ✨ Audio UI components, a webcam view, a VCV-style rack with animated cables, audio demos and the Audio docs section. PR [#142](https://github.com/albakore/pyzed/pull/142) by [@albakore](https://github.com/albakore).
- ✨ Windows open as native Windows windows when Pyzed runs in WSL (`pyzed windows setup`, `PYZED_WINDOWS=0` for WSLg). PR [#150](https://github.com/albakore/pyzed/pull/150) by [@albakore](https://github.com/albakore).
- ✨ Every demo in the welcome gallery of Pyzed Design: audio, games, animation, styling, shaders, AI and more. PR [#153](https://github.com/albakore/pyzed/pull/153) by [@albakore](https://github.com/albakore).
- ⚡️ Faster views with shared button parts, and the CPU renderer when the GPU is emulated. PR [#157](https://github.com/albakore/pyzed/pull/157) by [@albakore](https://github.com/albakore).
- ✨ Export apps from Pyzed Design for Windows, macOS and Linux on x64 and ARM, with PyInstaller or Nuitka, icons and a splash screen. PR [#158](https://github.com/albakore/pyzed/pull/158) by [@albakore](https://github.com/albakore).
- ✨ Android prototype: build APKs of Pyzed apps. PR [#159](https://github.com/albakore/pyzed/pull/159) by [@albakore](https://github.com/albakore).
- ✨ Hot reload keeps the state and picks up new attributes, initial values and methods without restarting. PR [#164](https://github.com/albakore/pyzed/pull/164) by [@albakore](https://github.com/albakore).
- ✨ Editor: choose the startup form, open every Pyzed file, indent with tabs and pace a held Backspace. PR [#166](https://github.com/albakore/pyzed/pull/166) by [@albakore](https://github.com/albakore).
- ✨ The library's missing components in the designer's toolbox (Dock included), with their properties and events. PR [#165](https://github.com/albakore/pyzed/pull/165) by [@albakore](https://github.com/albakore).
- ✨ Clearer animations: start them from code, an easier timeline and a "Start here" guide. PR [#167](https://github.com/albakore/pyzed/pull/167) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Claude Code, Codex and other agents start when Pyzed Design is opened from the desktop's menu (Node.js found where nvm, volta and fnm put it), **Retry** no longer repeats the message, and Pyzed's MCP server is added to Zed's settings even when they have comments. PR [#137](https://github.com/albakore/pyzed/pull/137) by [@albakore](https://github.com/albakore).
- 🐛 The silent audio clock keeps real time when the system timer wakes late. PR [#144](https://github.com/albakore/pyzed/pull/144) by [@albakore](https://github.com/albakore).
- 🐛 Pyzed builds from source on Linux without ALSA's headers: audio devices and MIDI come with the `alsa` feature, which the released wheels turn on. PR [#149](https://github.com/albakore/pyzed/pull/149) by [@albakore](https://github.com/albakore).
- 🐛 Claude Code and Codex run their current ACP adapters, so the new models and effort levels show. PR [#151](https://github.com/albakore/pyzed/pull/151) by [@albakore](https://github.com/albakore).
- 🐛 Your checkout and everything Pyzed Design starts run on Windows when they come from WSL. PR [#152](https://github.com/albakore/pyzed/pull/152) by [@albakore](https://github.com/albakore).
- 🐛 The Windows core builds without Windows' folders on PATH, so maturin does not pick the Microsoft Store's `python.exe`. PR [#154](https://github.com/albakore/pyzed/pull/154) by [@albakore](https://github.com/albakore).
- 🐛 Pyzed Design on Windows no longer freezes when it opens or creates a WSL project. PR [#155](https://github.com/albakore/pyzed/pull/155) by [@albakore](https://github.com/albakore).
- 🐛 The agents' local servers no longer print dropped connections (`WinError 10054`) on Windows. PR [#156](https://github.com/albakore/pyzed/pull/156) by [@albakore](https://github.com/albakore).
- 🐛 A release stays a draft until its files are attached, and the download page links only files that exist. PR [#163](https://github.com/albakore/pyzed/pull/163) by [@albakore](https://github.com/albakore).

### Refactors

- ♻ The new app template is centered with a flex box now that `pz.box` centers on the cross axis. PR [#132](https://github.com/albakore/pyzed/pull/132) by [@albakore](https://github.com/albakore).
- ♻ The agent settings show the everyday ones first and fold the rest under **Advanced**. PR [#137](https://github.com/albakore/pyzed/pull/137) by [@albakore](https://github.com/albakore).

### Docs

- 📝 Game tutorials and the Animation docs section. PR [#146](https://github.com/albakore/pyzed/pull/146) by [@albakore](https://github.com/albakore).
- 🍱 Pyzed Design captures retaken with the event tray. PR [#148](https://github.com/albakore/pyzed/pull/148) by [@albakore](https://github.com/albakore).
- 📝 The events of every component, with imperative, declarative and functional examples. PR [#168](https://github.com/albakore/pyzed/pull/168) by [@albakore](https://github.com/albakore).

### Internal

- 📦 `pyzed-ui` installs only from the prebuilt wheels, never compiling the Rust core. PR [#140](https://github.com/albakore/pyzed/pull/140) by [@albakore](https://github.com/albakore).
- ✅ The real-time audio test waits for the audio clock instead of a fixed sleep. PR [#141](https://github.com/albakore/pyzed/pull/141) by [@albakore](https://github.com/albakore).
- 👷 CI decides which jobs run from `git diff`, so pull requests with over 300 files still run their tests. PR [#147](https://github.com/albakore/pyzed/pull/147) by [@albakore](https://github.com/albakore).
- 💚 The release wheels build and test again: tests no longer share styles or need maturin, and the musllinux wheels build without ALSA. PRs [#162](https://github.com/albakore/pyzed/pull/162) and [#163](https://github.com/albakore/pyzed/pull/163) by [@albakore](https://github.com/albakore).

## [1.5.0] - 2026-10-20

### Highlights

- **Program apps like the web**: hover, pressed and focus styles with transitions, CSS-like stylesheets, `pz.box` (block, flex, grid and stack layouts), media queries with `pz.viewport()`, and components with children and context.
- **Errors never take the editor down**: a Logs panel, error boundaries, an error dialog and a selectable console.
- **Agents you can follow**: every agent step shows live, each agent's modes and models in the composer, and Pyzed's MCP server is added to the coding agents and editors on this computer.

### Features

- ✨ Every agent step shows live, each agent's modes, models and options in the composer, a Thinking toggle, remembered Always allow permissions, and Pyzed's MCP server added to the AI agents and editors of this computer (Claude Desktop, Cursor, Windsurf, Gemini CLI, Codex, VS Code, Zed and more). PR [#123](https://github.com/albakore/pyzed/pull/123) by [@albakore](https://github.com/albakore).
- ✨ Logs panel, error boundaries and an error dialog, a selectable console, the `ui.error_boundary`, `ui.error_card`, `ui.error_dialog` and `ui.ErrorInfo` components and a `readonly` code editor. PR [#124](https://github.com/albakore/pyzed/pull/124) by [@albakore](https://github.com/albakore).
- ✨ State styles and transitions, CSS-like stylesheets, `pz.box`, media queries and breakpoints with `pz.viewport()`, children, context and `animate=` for components. PR [#125](https://github.com/albakore/pyzed/pull/125) by [@albakore](https://github.com/albakore).
- ⚡ Pyzed Agent designs faster: it starts out knowing the toolbox, themes, `pz.ui` components and best practices, gets the open document with each message and lays out a whole form with one `add_controls` call. PR [#123](https://github.com/albakore/pyzed/pull/123) by [@albakore](https://github.com/albakore).
- ✨ The agent's steps go to the Logs panel: each message, tool call and result, files, permissions and errors. PR [#126](https://github.com/albakore/pyzed/pull/126) by [@albakore](https://github.com/albakore).
- ✨ MCP tools for timeline animations (`.pzanim`) and component states. PR [#127](https://github.com/albakore/pyzed/pull/127) by [@albakore](https://github.com/albakore).
- ✨ The MCP writes apps like a web page: boxes, stylesheets, media queries and nesting components. PR [#128](https://github.com/albakore/pyzed/pull/128) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 `pz.box` shrinks, centers on the cross axis and sizes its children correctly. PR [#129](https://github.com/albakore/pyzed/pull/129) by [@albakore](https://github.com/albakore).
- 🐛 Recent projects stay in `PYZED_CONFIG_DIR` when it is set. PR [#125](https://github.com/albakore/pyzed/pull/125) by [@albakore](https://github.com/albakore).

### Docs

- 📝 The error and AI agent components in the component library. PR [#130](https://github.com/albakore/pyzed/pull/130) by [@albakore](https://github.com/albakore).

## [1.4.0] - 2026-10-20

1.3.0 was tagged but never published: its Windows wheel build failed a test that is fixed in this version. Everything listed under 1.3.0 ships for the first time in 1.4.0.

### Highlights

- **Detachable panels and work layouts**: drag any panel out of Pyzed Design, stack panels together and save layouts for each kind of work.
- **A Zed-like Agent panel**: new-thread menu, thread history, settings inside the panel, the ACP agent registry, skills, keep or reject each edit, external agent sign-in, follow-agent, a context meter, notifications, and threads and rules per project.
- **Timeline animations**: `pz.Clip`, `pz.Track`, `pz.Call` and `AnimationPlayer`, saved as `.pzanim` and edited in the new Animation panel of `.pzform` files.
- **Pyzed themes**: Midnight, Graphite, Forest, Rosé, Dawn and Glacier, plus property editors for each kind of value.
- **Zed-like keymap**: `keymap.json` with contexts and a keymap editor.

### Features

- ✨ Zed-like keymap with contexts in `keymap.json` and a keymap editor. PR [#108](https://github.com/albakore/pyzed/pull/108) by [@albakore](https://github.com/albakore).
- ✨ Forms kept in the project, mark or change the startup file and clone repositories. PR [#113](https://github.com/albakore/pyzed/pull/113) by [@albakore](https://github.com/albakore).
- ✨ Detachable and stackable panels and work layouts. PR [#105](https://github.com/albakore/pyzed/pull/105), PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- ✨ Toolbar groups; New component moves to the toolbox and the New dialog. PR [#106](https://github.com/albakore/pyzed/pull/106), PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- ✨ Run/Stop and a search field in the middle of the title bar. PR [#107](https://github.com/albakore/pyzed/pull/107), PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- ✨ Zed-like Agent panel with history, settings, ACP registry, skills and keep/reject edits, and the reusable `ToolCall`, `Plan`, `EditsBar`, `ThreadHistory`, `AuthPrompt`, `ServiceRow`, `Catalog` and `context_meter` components. PR [#109](https://github.com/albakore/pyzed/pull/109), PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- ✨ Timeline animations with `pz.Clip`, `pz.Track`, `pz.Call`, `AnimationPlayer` and `.pzanim`. PR [#110](https://github.com/albakore/pyzed/pull/110), PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- ✨ States, sizes and events for the `ui` components; `pick_list` gains `on_open` and `on_close`. PR [#111](https://github.com/albakore/pyzed/pull/111), PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- ✨ WSL projects from Windows. PR [#115](https://github.com/albakore/pyzed/pull/115), PR [#119](https://github.com/albakore/pyzed/pull/119) by [@albakore](https://github.com/albakore).
- ✨ External agent sign-in like Zed, follow-agent, context meter and notifications. PR [#116](https://github.com/albakore/pyzed/pull/116), PR [#119](https://github.com/albakore/pyzed/pull/119) by [@albakore](https://github.com/albakore).
- ✨ Pyzed theme family and property editors for each kind of value. PR [#117](https://github.com/albakore/pyzed/pull/117), PR [#119](https://github.com/albakore/pyzed/pull/119) by [@albakore](https://github.com/albakore).
- ✨ Animation panel in `.pzform`. PR [#118](https://github.com/albakore/pyzed/pull/118), PR [#119](https://github.com/albakore/pyzed/pull/119) by [@albakore](https://github.com/albakore).
- ✨ Agents work on the active project: threads per project and project rules (`AGENTS.md`, `.rules`, `CLAUDE.md`...) in `pyzed.agents.rules`. PR [#120](https://github.com/albakore/pyzed/pull/120) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Agent sign-in on Windows sends the POST body correctly. PR [#114](https://github.com/albakore/pyzed/pull/114) by [@albakore](https://github.com/albakore).
- 🐛 Clone target folder on Windows paths and the agent registry cache on Windows. PR [#119](https://github.com/albakore/pyzed/pull/119) by [@albakore](https://github.com/albakore).

## [1.3.0] - 2026-10-20

### Highlights

- **Shader graphs**: build shaders from nodes in the new Shader view of Pyzed Design, like Godot's visual shaders, saved as `.pzshad` and compiled to WGSL (`pyzed.shading`).
- **Pyzed Design as an app**: native installers for Windows (per user, no admin), macOS (`.dmg`) and Linux (`install.sh`), a preview update channel and a welcome window with 24 example projects.
- **Agents that build whole apps**: sign in to Claude in the browser or with a Claude subscription, `run_app` and a plan checklist in the Agent panel, and MCP tools that plan an app (`plan_app`), show it live while it is built and work in the project's environment (`.venv`, WSL).
- **Projects in the title bar**: the project, branch and environment, with a project picker for open and recent projects.
- **New docs site**: sections with a header navbar, every Designer view documented, a shader node catalog, basic, intermediate and advanced tutorials, every variant of each component and retaken screenshots and clips.

### Features

- ✨ Update the MCP server with everything new up to 1.2.0 and add project tools to build whole apps. PR [#86](https://github.com/albakore/pyzed/pull/86) by [@albakore](https://github.com/albakore).
- ✨ Sign in to Claude in the browser, use a Claude subscription, and let agents build apps and control the editor. PR [#87](https://github.com/albakore/pyzed/pull/87) by [@albakore](https://github.com/albakore).
- ✨ Add a welcome window with example projects to Pyzed Design, and run commands without console windows on Windows. PR [#88](https://github.com/albakore/pyzed/pull/88) by [@albakore](https://github.com/albakore).
- 📦 Make Pyzed Design an installable app: native installers, a preview channel, and templates and translations as data. PR [#89](https://github.com/albakore/pyzed/pull/89) by [@albakore](https://github.com/albakore).
- ✨ Add node-based shader graphs (`.pzshad`) and a Shader view to Pyzed Design, like Godot's visual shaders. PR [#90](https://github.com/albakore/pyzed/pull/90) by [@albakore](https://github.com/albakore).
- ✨ Open pages and sign-ins in the Windows browser when Pyzed Design runs under WSL. PR [#92](https://github.com/albakore/pyzed/pull/92) by [@albakore](https://github.com/albakore).
- ✨ Guide agents with `plan_app`, show the app live while they build it, and run project tools in the project's environment. PR [#102](https://github.com/albakore/pyzed/pull/102) by [@albakore](https://github.com/albakore).
- ✨ Show the project, branch and environment in the title bar with a project picker. PR [#103](https://github.com/albakore/pyzed/pull/103) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Fix the white Retro screen shader template and tidy shader graph layouts. PR [#91](https://github.com/albakore/pyzed/pull/91) by [@albakore](https://github.com/albakore).
- 🐛 Keep the folder browser working next to folders without permission, and close a dialog that fails to draw. PR [#93](https://github.com/albakore/pyzed/pull/93) by [@albakore](https://github.com/albakore).
- 🐛 Fix `ui.button` style overrides such as `radius`, rotated images and the alpha of SVG tints. PR [#101](https://github.com/albakore/pyzed/pull/101) by [@albakore](https://github.com/albakore).

### Docs

- 💄 Restyle the docs and split them into sections with a header navbar. PR [#94](https://github.com/albakore/pyzed/pull/94) by [@albakore](https://github.com/albakore).
- 📝 Document every Designer view and add a shader node catalog with recipes. PR [#95](https://github.com/albakore/pyzed/pull/95) by [@albakore](https://github.com/albakore).
- 📝 Expand Theming and Distribute, and show uv/pip/python commands per platform. PR [#96](https://github.com/albakore/pyzed/pull/96) by [@albakore](https://github.com/albakore).
- 📝 Add basic, intermediate and advanced tutorials and turn the Showcase into a gallery. PR [#97](https://github.com/albakore/pyzed/pull/97) by [@albakore](https://github.com/albakore).
- 📸 Retake every docs screenshot, add node captures and short clips, and place them in the pages. PR [#98](https://github.com/albakore/pyzed/pull/98) by [@albakore](https://github.com/albakore).
- 📝 Show every variant of each library component, with plain-words intros and a gallery index. PR [#99](https://github.com/albakore/pyzed/pull/99) by [@albakore](https://github.com/albakore).
- 📝 Update the README with Pyzed Design, shaders, games, AI, integrations and new screenshots. PR [#100](https://github.com/albakore/pyzed/pull/100) by [@albakore](https://github.com/albakore).

### Internal

- 👷 Speed up CI: cache the docs images, run jobs only for the files they check, a smaller PR matrix and parallel tests. PR [#104](https://github.com/albakore/pyzed/pull/104) by [@albakore](https://github.com/albakore).

## [1.2.0] - 2026-10-20

### Highlights

- **Games**: a game loop (`pz.frames`), held keys (`pz.pressed`), `on_key_up`, sprites and `pyzed.game`, with Snake, Breakout and Neon Invaders demos and tutorials.
- **Shaders**: `pz.shader` paints a widget with a WGSL function on the GPU, with showcase demos (game HUD, main menu, inventory, glass dashboard).
- **Integrations**: tutorials and runnable demos for FastAPI, SQLAlchemy, SQLModel, Django, httpx and Pydantic, with `pz.validation_errors` and `ui.field(error=)`.
- **A stronger AI agent**: images, external MCP servers, external agents through ACP (Gemini CLI, Codex...), GitHub Copilot, Google Vertex AI, Claude through identity federation, sign-in from Pyzed Design and a Zed-like composer.
- **Pyzed Design feels like Zed**: the project's files with Zed's right-click menu, any text file in the code editor, tabs you drag out into their own windows, a custom window frame, anchors that follow while you design, a compact details panel for properties and an icon picker.
- **Faster by default**: `import pyzed` takes 78 ms instead of 178 ms, lighter view rebuilds and mimalloc in the native core.
- **Why Pyzed**: a new docs section comparing Pyzed with tkinter, Qt, Kivy, Flet and others, with measured benchmarks.

### Features

- ✨ Edit component properties of any type in a compact details panel, kept in sync with the code. PR [#61](https://github.com/albakore/pyzed/pull/61) by [@albakore](https://github.com/albakore).
- ✨ Add an icon picker with search and categories to the library and Pyzed Design. PR [#62](https://github.com/albakore/pyzed/pull/62) by [@albakore](https://github.com/albakore).
- ✨ Sign in to AI providers from Pyzed Design and add a Zed-like agent composer. PR [#63](https://github.com/albakore/pyzed/pull/63) by [@albakore](https://github.com/albakore).
- ✨ Show the project's files in Pyzed Design, with file search, a Dependencies tab and a folder browser. PR [#65](https://github.com/albakore/pyzed/pull/65) by [@albakore](https://github.com/albakore).
- ✨ Add anchor presets, offsets, size limits, pivot and rotation to Position, and `pz.anchor_layout`. PR [#66](https://github.com/albakore/pyzed/pull/66) by [@albakore](https://github.com/albakore).
- ✨ Add images, MCP servers, external agents, GitHub and Google sign-in and Claude identity federation to the AI agent. PR [#68](https://github.com/albakore/pyzed/pull/68) by [@albakore](https://github.com/albakore).
- ✨ Add a game loop, held keys and sprites, with three game demos and tutorials. PR [#69](https://github.com/albakore/pyzed/pull/69) by [@albakore](https://github.com/albakore).
- ✨ Add `pz.shader` and showcase demos: game HUD, main menu, inventory, glass dashboard and shaders. PR [#70](https://github.com/albakore/pyzed/pull/70) by [@albakore](https://github.com/albakore).
- ✨ Add integration demos and tutorials for FastAPI, SQLAlchemy, SQLModel, Django and httpx, with `pz.validation_errors`, `ui.field(error=)` and object options in `ui.select`. PR [#71](https://github.com/albakore/pyzed/pull/71) by [@albakore](https://github.com/albakore).
- ✨ Open any text file from the Project tab in the code editor, with a tab per file. PR [#76](https://github.com/albakore/pyzed/pull/76) by [@albakore](https://github.com/albakore).
- ✨ Follow anchors while designing: resizing the form, a component or a container moves what is inside. PR [#77](https://github.com/albakore/pyzed/pull/77) by [@albakore](https://github.com/albakore).
- ✨ Drag tabs out into their own windows and stack them back in Pyzed Design. PR [#79](https://github.com/albakore/pyzed/pull/79) by [@albakore](https://github.com/albakore).
- ✨ Give the Project tree Zed's right-click menu: cut, copy, paste, duplicate, undo, trash, terminal, .gitignore and permalinks, with its keys. PR [#81](https://github.com/albakore/pyzed/pull/81) by [@albakore](https://github.com/albakore).
- ✨ Add custom window frames: own title bar, platform window buttons, Zed-like menus and resize borders, used by Pyzed Design. PR [#83](https://github.com/albakore/pyzed/pull/83) by [@albakore](https://github.com/albakore).
- ✨ Wheel scrolling, configurable key bindings and a sectioned settings dialog for the code editor. PR [#84](https://github.com/albakore/pyzed/pull/84) by [@albakore](https://github.com/albakore).
- ⚡ Start faster and rebuild views with less work by default. PR [#82](https://github.com/albakore/pyzed/pull/82) by [@albakore](https://github.com/albakore).
- 💄 Normalize margins and spacing across Pyzed Design's panels with shared spacing tokens. PR [#80](https://github.com/albakore/pyzed/pull/80) by [@albakore](https://github.com/albakore).

### Fixes

- 🐛 Restart Pyzed Design after an update even while background work is running. PR [#60](https://github.com/albakore/pyzed/pull/60) by [@albakore](https://github.com/albakore).
- 🐛 Write Optional props as `X | None` on every Python version. PR [#64](https://github.com/albakore/pyzed/pull/64) by [@albakore](https://github.com/albakore).
- 🐛 Pick color properties with the color picker and keep half-typed colors from breaking the view. PR [#67](https://github.com/albakore/pyzed/pull/67) by [@albakore](https://github.com/albakore).
- 🐛 `ui.select` hands `on_select` the chosen object (a model, an enum) instead of its label, as documented, and `Command.perform` calls its `then` when the function returns `None`. PR [#71](https://github.com/albakore/pyzed/pull/71) by [@albakore](https://github.com/albakore).
- 🐛 Build with Rust 1.88 again: drop the if-let match guard and check the MSRV in CI. PR [#75](https://github.com/albakore/pyzed/pull/75) by [@albakore](https://github.com/albakore).
- 🐛 Keep completion rows inside the list and let the list scroll. PR [#78](https://github.com/albakore/pyzed/pull/78) by [@albakore](https://github.com/albakore).

### Docs

- 📝 Add SEO/GEO, llms.txt, Why Pyzed with measured benchmarks, AI agents and Blocks docs. PR [#74](https://github.com/albakore/pyzed/pull/74) by [@albakore](https://github.com/albakore).
- 📝 Redo the integration demos following the official tutorials, with an architectures page. PR [#73](https://github.com/albakore/pyzed/pull/73) by [@albakore](https://github.com/albakore).
- 📝 Document the window frame, the editor's `keymap` and `scrollbar`, held keys and `on_key_up`, `pyzed.game` and the release secrets, and re-measure Pyzed's benchmarks with 1.2.0. PR [#85](https://github.com/albakore/pyzed/pull/85) by [@albakore](https://github.com/albakore).

### Internal

- 👷 Bundle the Agent panel's GitHub and Google sign-in apps into the release builds from Actions secrets. PR [#72](https://github.com/albakore/pyzed/pull/72) by [@albakore](https://github.com/albakore).

## [1.1.0] - 2026-10-19

### Highlights

- **Large data**: virtual lists and tables that only build the rows in view (200 000 rows in 0.2 ms per view) and `@pz.memo` to reuse view subtrees.
- **Real effects**: animate rotation, size, padding and font size, with real blur, backdrop blur and bloom on the GPU and in software.
- **A better Pyzed Design**: copy and paste between forms, data binding and validation, and a theme and language preview.
- **Accessibility**: Tab focus between fields, the system's reduce motion setting and a screen reader guide.
- **Input methods**: Chinese, Japanese and Korean input in the code editor.
- **Safer by default**: private agent threads, hidden secret files, a hardened sign-in and checked updates.
- **More platforms**: wheels for musllinux, tested on Python 3.10 to 3.14 and on ARM Linux, Pyzed Design builds for Linux ARM and Intel Macs, and build attestations.

### Breaking Changes

- ⬆️ Pyzed now requires Python 3.10 or newer. PR [#52](https://github.com/albakore/pyzed/pull/52) by [@albakore](https://github.com/albakore).

### Features

- ✨ Add virtual lists and tables and memoized view subtrees for large data. PR [#55](https://github.com/albakore/pyzed/pull/55) by [@albakore](https://github.com/albakore).
- ✨ Add copy and paste between forms, data binding and validation, and theme/language preview to Pyzed Design. PR [#56](https://github.com/albakore/pyzed/pull/56) by [@albakore](https://github.com/albakore).
- ✨ Support input methods (IME) for Chinese, Japanese and Korean in the code editor. PR [#57](https://github.com/albakore/pyzed/pull/57) by [@albakore](https://github.com/albakore).
- ✨ Animate rotation, size, padding and font size, with real blur, backdrop blur and bloom. PR [#58](https://github.com/albakore/pyzed/pull/58) by [@albakore](https://github.com/albakore).
- ♿ Add Tab focus between fields, follow the system's reduce motion setting and document screen reader support. PR [#54](https://github.com/albakore/pyzed/pull/54) by [@albakore](https://github.com/albakore).

### Fixes

- 🔒️ Keep agent threads private (`0600`, with a *Keep conversations* switch), hide secret files such as `.env` and keys from agents, ignore forged sign-in callbacks and refuse updates without a checksum. PR [#52](https://github.com/albakore/pyzed/pull/52) by [@albakore](https://github.com/albakore).
- 🐛 Read component props on Python 3.14, where annotations are lazy. PR [#52](https://github.com/albakore/pyzed/pull/52) by [@albakore](https://github.com/albakore).

### Internal

- 👷 Test on Python 3.10, 3.12 and 3.14 and on ARM Linux; build musllinux wheels, Pyzed Design for Linux ARM and Intel Macs, optional signing and notarization, and build provenance attestations. PR [#52](https://github.com/albakore/pyzed/pull/52) by [@albakore](https://github.com/albakore).
- ✅ Add visual regression tests and tests for workspace, navigation, overlays and agent threads. PR [#53](https://github.com/albakore/pyzed/pull/53) by [@albakore](https://github.com/albakore).

## [1.0.1] - 2026-10-19

### Fixes

- 🔒️ AI agents refuse tools marked `writes=True` when `confirm_writes` is on (the default) and no `confirm` callback was given, instead of running them without asking. Pass `confirm=` or set `confirm_writes=False` to keep the old behavior.
- 🔒️ `pyzed mcp --transport streamable-http` no longer offers the `screenshot` tool, which runs the code it receives, unless you add `--allow-code`. Over stdio nothing changes.
- 🐛 Pyzed Design refuses a `.pzform` or component saved by a newer Pyzed instead of opening it and losing what it does not know.
- 🏷️ Type stubs for the Rust core (`_core.pyi`) and `py.typed`, so editors and type checkers see every widget and command.

### Docs

- 📝 Add the *Stability and known limitations* guide: the versioning and deprecation policy and what Pyzed does not do yet.

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
