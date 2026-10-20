---
title: Introduction
description: "What Pyzed is: a Python desktop GUI framework rendered natively by Rust (Iced), with ready-made modern components. How it works and when to use it."
---

**Pyzed** is a library for building desktop interfaces in Python with the performance of
[Iced](https://iced.rs), a GUI toolkit written in Rust. It includes a set of components
inspired by the [Zed](https://zed.dev) editor: tabs, file tree, command palette, code editor,
terminal, menus, notifications and a workspace with dockable panels.

![A code editor built with Pyzed (One Light theme)](../../../../screenshots/zed-one-light.png)

## How it works

Your Python code describes **what** is shown. Rust takes care of **how** it is drawn.

```
Python                         Rust (pyzed._core, PyO3)                 Iced 0.14
App.view() ──► Widget tree ──► render.rs: Widget → iced::Element ──► layout + wgpu/tiny-skia
App.update() ◄── messages ◄────── app.rs: Message, Command → Task ◄──── events (mouse, keyboard)
```

- `view()` returns a tree of `Widget`s. They are immutable Rust objects, so building it is cheap.
- When the user interacts, Pyzed calls your `update(message)` or directly the callable
  you passed (`on_press=self.save`). Then it calls `view()` again.
- Layout, text, syntax highlighting and drawing happen in Rust.
- The GIL is released while the event loop runs, so your Python threads keep working.

## When to use Pyzed

- Desktop tools, internal dashboards, editors and utilities that should feel fast.
- Dense IDE-style interfaces with many panels, lists and keyboard shortcuts.
- Apps you want to test or document with screenshots generated headlessly.

## What you need to know

Basic Python: classes, functions and lambdas. No Rust or Iced knowledge required.

Continue with the [installation](/pyzed/getting-started/installation/) or jump straight to the
[quickstart](/pyzed/getting-started/quickstart/). Questions about licensing, platforms or how Pyzed compares
with tkinter, Kivy, PyQt or Flet? See the [FAQ](/pyzed/faq/).
