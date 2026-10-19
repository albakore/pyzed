---
title: Tips and tricks
description: "Small habits that make you faster in Pyzed Design: shortcuts, multi-selection, smart guides, templates and quick ways to build Python forms."
sidebar:
  order: 14
---

## Placing and arranging

- **Draw instead of drop**: click a component in the toolbox, then drag a rectangle on the form. The control gets
  exactly that size, snapped to the grid, and you skip a resize.
- **Add without the toolbox**: <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>, type two or three letters,
  <kbd>Enter</kbd>. With the left dock hidden (<kbd>Ctrl</kbd>+<kbd>B</kbd>) the canvas gets the whole width.
- **Pick the alignment reference**: after selecting several controls, click the one that is already right. It
  becomes the primary control (thicker outline), and **Same width** / **Same height** copy *its* size.
- **Align to the form**: with a single control selected, the align buttons line it up with the form's edges and
  center; **Center in form** centers the whole selection as a group.
- **Nudge in grid steps**: <kbd>Shift</kbd>+arrows moves by one grid step, plain arrows by one pixel. A run of
  nudges is a single undo step.
- **Cancel a bad drag**: press <kbd>Esc</kbd> before letting go of the mouse and everything goes back.
- **Fix a messy layout at once**: with nothing selected, **Fit selection to grid** (toolbar) snaps every control
  of the form onto the grid.
- **Guides fight you?** Turn off **Smart guides** (ruler) or **Snap** (magnet, or click *Snap* in the status bar)
  for pixel-precise placement, and turn them back on after.

## Containers

- **Wrap, do not rebuild**: select controls that already look right and use **Group in a row / column / grid /
  panel** from the context menu. The container is created around them.
- **Grab the container, not its child**: use the grip tab above its top-left corner, or its row in the outline.
- **Push to the end**: a **Spacer** in a flex row pushes everything after it to the far end; two spacers center
  what is between them.
- **Equal columns**: in a flex row, give each child **Grow** 1; in a grid, use **Row height** 0 so the rows share
  the height.
- **Make it resizable**: anchor the main container on all four sides and let flex containers inside share the
  space with **Grow**. Run with <kbd>F5</kbd> and resize the window to check.

## Outline

- **Hide while you work**: the eye in the outline hides a control (a dialog, an overlay) so you can work on what is
  under it. Remember to show it again, or set it visible from code (`form.panel.show()`).
- **Lock the background**: lock big panels and images so a stray drag does not move them while you arrange the
  controls on top. Locked controls are also skipped by the align and size tools.
- **Reorder flex children** by dragging their rows in the outline: the line shows exactly where they land.

## Code

- **Enter is "edit code"**: select a control and press <kbd>Enter</kbd> to jump to its main event handler.
- **Name first, code second**: rename controls (**Name**, then <kbd>Enter</kbd>) before writing handlers. Renames
  later still update handlers that follow the `control_event` convention, but code that mentions `form.button1`
  elsewhere is not rewritten.
- **Let completion teach you**: `form.` lists the controls, `form.status.` the properties of that control,
  `event.` the event's fields, and the documentation pane shows each property's description.
- **Insert member calls**: on a placed designed component, open its chevron in the outline and click a method to
  type `form.card.rate()` at the cursor.
- **Share logic between controls**: handlers are plain functions, so put the common part in a helper at the top of
  the file and call it from each handler; `event.sender` tells which control raised the event.
- **Format on Apply**: turn on *Format with ruff on Apply* in the editor settings and press **Apply** to tidy the
  handler you just wrote.
- **Bigger font for demos**: <kbd>Ctrl</kbd>+<kbd>=</kbd> in the code editor, <kbd>Ctrl</kbd>+<kbd>0</kbd> to go back.
- **Restart servers** after `uv add` / `uv sync` if completion does not know a new package yet.

## Running

- **F5 runs what you see**: inside the project's environment, Run uses the current document, unsaved changes
  included. Keep the window open and press <kbd>Ctrl</kbd>+<kbd>S</kbd> to update it in place, keeping what you typed
  into it.
- **Read the console, not the terminal**: events show their values (`email.change ('ada@') → email_change()`), and
  errors show the full traceback starting at your handler. Filter it by a control's name to follow just that one.
- **Turn off event logging** (Settings → Running) when a timer or a slider floods the console.
- **Preview components alone**: open a `.pzcomp` and press <kbd>F5</kbd>; the preview lists every custom event the
  component raises, with its value.

## Layout of the editor

- **Two panels at once**: move **Events** to the left (or top) dock with the dock button, so Properties and Events
  are both visible.
- **Fold the sections you do not use** in Properties: they stay folded while you move between controls.
- **Lost a panel?** **View → Reset panel layout** puts everything back.
- **Portable settings**: set `PYZED_CONFIG_DIR` to keep the editor's settings with a project or on a USB stick.

## Files

- **Commit both files**: the `.pzform` is readable JSON that diffs well, and the `.py` is plain Python. Reviewers
  can read both.
- **Edit the code anywhere**: the editor only rewrites the handler functions it manages, so you can keep the code
  file open in Zed or VS Code as well; run with `pyzed run app.pzform --reload` to see every save.
- **Templates are a head start**: the *Dialog* template already wires OK and Cancel; *Settings* shows a grid of
  labels and fields. Register your own with `designer.register_template`.
