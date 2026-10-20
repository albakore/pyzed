---
title: Frequently asked questions
description: "Pyzed FAQ: what it is, how it compares with tkinter, Kivy, PyQt and Flet, license, platforms, performance, the visual designer and AI agent support."
---

Short answers to the questions people ask most about Pyzed. Each one links to the page that explains it in full.

## What is Pyzed?

Pyzed is an open-source Python framework for building native desktop applications. Your Python code describes
the interface; [Iced](https://iced.rs), a GUI toolkit written in Rust, lays it out and draws it with the GPU (or a
software renderer when there is none). It ships more than 90 components inspired by the [Zed](https://zed.dev)
editor (tabs, file tree, command palette, code editor, terminal, tables, charts, dialogs, a workspace with docks)
and Pyzed Design, a drag-and-drop visual designer. See the [introduction](/pyzed/getting-started/introduction/).

## How do I install Pyzed?

Run `pip install pyzed-ui` or `uv add pyzed-ui`, then `import pyzed as pz`. The package is called `pyzed-ui` on
PyPI but is imported as `pyzed`. It needs Python 3.10 or newer, and the prebuilt wheels for Windows, macOS and
Linux include the Rust engine, so there is nothing to compile. See [Installation](/pyzed/getting-started/installation/).

## Is Pyzed free and open source?

Yes. Pyzed and Pyzed Design are free and released under the MIT license, so you can use them in commercial and
closed-source applications. The code is on [GitHub](https://github.com/albakore/pyzed).

## Which platforms does Pyzed support?

Windows, macOS and Linux. Wheels are published for the three systems; on Linux they need glibc 2.28 or newer
(there are no Alpine/musl wheels yet). Mobile and the web are not targets. See
[Stability and known limitations](/pyzed/guides/stability/).

## How is Pyzed different from tkinter?

tkinter ships with Python and is fine for small utilities, but its widgets look dated, styling is limited and
complex layouts take a lot of code. Pyzed draws a modern, themeable interface with the GPU, comes with high-level
components such as a code editor, tables, trees, a command palette and notifications, has a visual designer, and
uses a declarative `view()`/state model instead of mutating widgets by hand. tkinter needs no extra install;
Pyzed needs `pip install pyzed-ui`.

## How is Pyzed different from Kivy?

Kivy is aimed at touch and mobile apps and uses its own KV language. Pyzed is aimed at desktop apps (dense,
keyboard-driven interfaces like editors, dashboards and tools), is written in plain Python with no extra
language, and renders through Rust and Iced. If you need Android or iOS, Kivy is the better fit today.

## How is Pyzed different from PyQt and PySide?

Qt is a large, mature C++ toolkit with native-looking widgets and a huge API. Pyzed is much smaller and simpler:
you describe the interface from your state with plain Python functions, styles work like CSS, and components look
modern out of the box. Pyzed is MIT licensed, while PyQt is GPL or commercial and PySide is LGPL.
Qt still has more widgets, accessibility support and years of production use.

## How is Pyzed different from Flet?

Flet builds the interface with Flutter and talks to it from Python, and can also target the web and mobile.
Pyzed runs the interface in the same process through a Rust extension, with no separate client, and focuses on
desktop apps with an IDE-like look, a visual designer and a code editor component.

## Is Pyzed fast?

Layout, text shaping, syntax highlighting and drawing all happen in Rust, and the widget tree your `view()`
returns is made of cheap immutable Rust objects. The GIL is released while the event loop runs, so your Python
threads keep working. For large data, virtual lists and tables show hundreds of thousands of rows and
`@pz.memo` skips rebuilding parts of the view that did not change. See [Performance](/pyzed/guides/performance/)
and [How it works](/pyzed/guides/how-it-works/).

## Is there a visual GUI designer?

Yes. [Pyzed Design](/pyzed/editor/) lets you draw windows and reusable components by drag and drop, edit their
properties and styles, write event handlers in a Python editor with completion and diagnostics, and run them with
F5. Forms are saved as a readable `.pzform` file plus a plain Python file. [Download it](/pyzed/download/) for
Windows, macOS or Linux.

## Can I make interfaces with effects and animations?

Yes. Any widget can be animated with presets, keyframes and transitions, and controls can have rotation, blur,
glow, bloom, glass and opacity effects, with light, dark and custom themes. See
[Animation and effects](/pyzed/guides/animation/) and [Themes](/pyzed/theming/themes/).

## Does Pyzed work with AI coding agents?

Yes. `pyzed mcp` (install `pyzed-ui[mcp]`) is an [MCP server](/pyzed/guides/mcp/) that gives agents such as
Cursor, VS Code or Zed the exact signature of every component, these docs, best practices, code checks and
screenshots of the result. These docs are also published for language models at
[llms.txt](https://albakore.github.io/pyzed/llms.txt) and
[llms-full.txt](https://albakore.github.io/pyzed/llms-full.txt), and Pyzed Design has a built-in
[Agent panel](/pyzed/editor/ai-agents/).

## Can I add AI features to my own app?

Yes. [`pyzed.agents`](/pyzed/guides/agents/) talks to Anthropic, OpenAI, Gemini, OpenRouter, Ollama and
OpenAI-compatible servers, lets the model call your Python functions as tools, streams its answer into the
interface and keeps API keys in the system keychain.

## How do I ship a Pyzed app to users?

`pyzed build` packages a project as a standalone app (a folder or a single file) for Windows, macOS or Linux that
runs on machines without Python. It uses PyInstaller underneath; build each platform on that platform or in a CI
matrix. See [Packaging](/pyzed/packaging/build/).

## Can I test a Pyzed app without a window?

Yes. `app.screenshot(path)` renders the current state off-screen with the software renderer, with no display or
GPU, so it works in CI. Your state and handlers are plain Python and are tested like any other code. See
[Testing](/pyzed/guides/testing/).

## Does Pyzed support screen readers?

Not yet. Pyzed respects the system's reduce-motion setting and supports keyboard shortcuts, but screen reader
support depends on Iced and is still missing. See [Accessibility](/pyzed/guides/accessibility/).

## Do I need to know Rust?

No. You only write Python: classes, functions and lambdas. Rust is only needed if you build Pyzed itself from
source or [contribute](/pyzed/contributing/) a new native widget.
