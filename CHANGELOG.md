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

### Features

- ✨ The Agent panel shows every step as it happens: an external agent's tool calls with their files, diffs and command output while they run, the call the model is still writing, and what the agent is doing and for how long.
- ✨ Each agent's own options in the message box, like Zed: Claude Code's modes and models (and any ACP session option), remembered per agent; a **Thinking** toggle for Claude; **Always allow** is remembered and listed under **Settings → Permissions**.
- ✨ Pyzed Design adds Pyzed's MCP server to the AI agents of the computer (Claude Code, Claude Desktop, Cursor, Windsurf, Gemini CLI, Codex, VS Code, Zed) and asks to restart them.
- ⚡ Pyzed Agent designs faster: it starts out knowing the toolbox, themes, `pz.ui` components and best practices, gets the open document with each message, and lays out a whole form with one `add_controls` call.
- ✨ The agent's steps go to the **Logs** panel (type *Agent*): each message, tool call and its result, files, permissions asked and answered, option changes, errors and Pyzed's MCP server added to other agents.
- ✨ Tabs anywhere in Pyzed Design: any tab, a panel's or a form's, can go to any dock, next to the form tabs in the center or to a window of its own, and stack with the others there (the code editor beside the forms, a form in a side dock). While a tab is dragged, a copy follows the pointer, the place it would land in lights up and a bar marks the spot in a tab row. New **Code with the forms** work layout.

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
