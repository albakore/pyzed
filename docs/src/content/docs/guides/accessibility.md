---
title: Accessibility
description: Keyboard focus with Tab, the system's reduce motion setting and the state of screen reader support.
sidebar:
  order: 18
---

Pyzed apps can be used from the keyboard and respect the motion preference of the system.
Screen readers are not supported yet: see [Screen readers](#screen-readers) for why and what
comes next.

## Moving between fields with Tab

<kbd>Tab</kbd> moves the keyboard focus to the next field of the window and
<kbd>Shift</kbd>+<kbd>Tab</kbd> to the previous one, in the order they appear in `view()`.
After the last field it goes back to the first. Fields are `text_input`s, `text_editor`s and
`code_editor`s (and the components built on them, like `ui.input` or `ui.search`); each window
cycles through its own fields only.

A `code_editor` with `tab_size` keeps <kbd>Tab</kbd> to indent, like Zed. Editors without it
pass the key on, so <kbd>Tab</kbd> leaves them.

`on_key` sees the key first (`"tab"` or `"shift-tab"`). If it returns something (a message or
a `Command`), the app handled it and the focus stays; returning `None` lets the focus move.
Turn the behavior off for a whole app or window with `tab_focus = False`:

```python
class App(pz.App):
    tab_focus = False  # Tab does nothing unless on_key handles it

    def on_key(self, combo):
        if combo == "tab" and self.completion_open:
            return self.accept_completion()
```

`Command.focus_next()` and `Command.focus_previous()` do the same from code, and
`Command.focus(id)` jumps to a specific field.

:::note
In Iced 0.14 only text fields can take the keyboard focus. Buttons, checkboxes and sliders
are used with the mouse or with shortcuts from `on_key`; give important actions a
shortcut (see [Keyboard and shortcuts](/pyzed/guides/keyboard/)).
:::

## Reduce motion

When the system asks apps to reduce motion, Pyzed turns its animations off: every
`animate()`, `transition()`, `presence()`, window transition and animated scroll shows its
final state at once. The setting is read when the app starts:

| System | Setting |
| --- | --- |
| macOS | System Settings → Accessibility → Display → Reduce motion |
| Windows | Settings → Accessibility → Visual effects → Animation effects (off) |
| Linux (GNOME) | Settings → Accessibility → Reduce animation (`enable-animations`) |
| Linux (KDE) | System Settings → Animation speed set to *Instant* |

`pz.system_reduced_motion()` returns what the system says (`None` if it can't tell). Your
app can still decide:

```python
pz.set_reduced_motion(True)   # always off, e.g. from your app's settings
pz.set_reduced_motion(False)  # always on
pz.set_reduced_motion(None)   # follow the system again (the default)
```

The `PYZED_REDUCED_MOTION` environment variable (`1` or `0`) overrides both. Screenshots always
show the resting state. See [Animation](/pyzed/guides/animation/#reduced-motion-and-tests).

## Screen readers

Pyzed draws its interface with Iced, which paints every widget itself on the GPU instead of
using the native controls of the system. Screen readers (VoiceOver, Narrator, NVDA, Orca)
need an *accessibility tree* that describes those widgets, and Iced 0.14 does not produce
one. The usual way to provide it in Rust is [AccessKit](https://accesskit.dev/), and we
evaluated adding it to Pyzed for 1.1:

- **Iced 0.14 has no AccessKit support.** Neither `iced` nor `iced_winit` depend on it, and
  winit 0.30 leaves accessibility to adapters such as `accesskit_winit`.
- **The window is owned by Iced.** `accesskit_winit` must be created before the window is
  shown and receive every window event; Iced's event loop gives no place to do either.
  The platform adapters (`accesskit_windows` and `accesskit_macos` subclass the native window,
  `accesskit_unix` talks to AT-SPI) could be attached from the raw window handle, but that is
  three separate integrations, each tested with a real screen reader.
- **Widgets don't describe themselves.** Iced's widget operations report text, text fields,
  scrollables and focus, but no roles (button, checkbox, slider), states or actions
  ("press"), so Pyzed would have to build the tree from its own widget descriptions and keep
  it in sync with the layout every frame.

That makes it a project of its own, not something to ship half done in a minor release.
Accessibility is on Iced's roadmap and forks of Iced already ship AccessKit, so the plan is:

1. Follow Iced upstream and adopt its accessibility support when it lands; Pyzed's widgets
   map one to one to Iced's, so they would gain it with little extra work.
2. Meanwhile, make the keyboard path complete (focus for buttons and other controls when Iced
   allows it) and keep labels in the UI text rather than only in icons.

If screen reader support matters for your app, please say so in the
[issues](https://github.com/albakore/pyzed/issues): it helps decide priorities.
