---
title: Keyboard shortcuts
description: Every keyboard shortcut of Pyzed Design - global commands, the canvas, dialogs and the code editor.
sidebar:
  order: 12
---

Press <kbd>F1</kbd> in the editor for a searchable version of this list. On macOS, <kbd>Cmd</kbd> works wherever a
global shortcut says <kbd>Ctrl</kbd>.

## Global

These work anywhere, even while you type in the code editor.

| Keys | Command |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>N</kbd> | New form |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd> | New component |
| <kbd>Ctrl</kbd>+<kbd>O</kbd> | Open |
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Save |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd> | Save as |
| <kbd>Ctrl</kbd>+<kbd>,</kbd> | Settings |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | Command palette |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> | Add control |
| <kbd>Ctrl</kbd>+<kbd>B</kbd> | Show or hide the left dock |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>B</kbd> | Show or hide the right dock |
| <kbd>Ctrl</kbd>+<kbd>J</kbd> | Show or hide the bottom dock |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Y</kbd> | Console |
| <kbd>F5</kbd> | Run |
| <kbd>Shift</kbd>+<kbd>F5</kbd> | Stop |
| <kbd>F7</kbd> | Edit code file |
| <kbd>F1</kbd> | Keyboard shortcuts |

While a dialog is open, only the palette, Settings and Keyboard shortcuts keys act; the others wait until it is
closed.

## Canvas

These act when the canvas has the keyboard: after you click the form, a control, a toolbox row or an outline row.
Moving the pointer into a dock gives the keyboard to that panel (so typing in a field never moves a control), and
the code editor keeps it while you type; click the canvas again to get the canvas shortcuts back.

| Keys | Action |
| --- | --- |
| <kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> | Move the selection by 1 px |
| <kbd>Shift</kbd>+arrows | Move it by one grid step (1 px with snapping off) |
| <kbd>Delete</kbd>, <kbd>Backspace</kbd> | Delete the selection |
| <kbd>Ctrl</kbd>+<kbd>C</kbd> | Copy |
| <kbd>Ctrl</kbd>+<kbd>X</kbd> | Cut |
| <kbd>Ctrl</kbd>+<kbd>V</kbd> | Paste |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | Duplicate |
| <kbd>Ctrl</kbd>+<kbd>A</kbd> | Select every control |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | Undo |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>, <kbd>Ctrl</kbd>+<kbd>Y</kbd> | Redo |
| <kbd>Enter</kbd> | Open the code of the selected control's main event |
| <kbd>G</kbd> | Show or hide the grid |
| <kbd>Esc</kbd> | Cancel a drag, close a menu, or drop the placing tool and go back to the pointer |

## Mouse

| Gesture | Action |
| --- | --- |
| Click | Select a control (on a selected one: make it the primary one) |
| Drag a control | Move the selection; drop on a container to put it inside |
| Drag a handle | Resize |
| Drag on an empty spot | Rubber-band selection |
| Double-click a control | Open its main event's code, or a designed component in its tab |
| Right-click | Context menu |
| Drag from the toolbox | Place a control where you drop it |
| Drag an outline row | Reorder, or move into another container |
| Drag the grip under the form | Resize the form |
| <kbd>Ctrl</kbd>+wheel in the code editor | Font size |

## Lists, palettes and dialogs

| Keys | Action |
| --- | --- |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Move in the command palette and Add control |
| <kbd>Enter</kbd> | Run the highlighted command, add the highlighted control, submit a dialog's field |
| <kbd>Esc</kbd> | Close the dialog, palette or menu |

## Code editor

| Keys | Action |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>Space</kbd> | Show completions |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Move in the completion list (wraps around) |
| <kbd>Page Up</kbd> / <kbd>Page Down</kbd> | Move nine rows in the list, or a page in the code |
| <kbd>Enter</kbd>, <kbd>Tab</kbd> | Accept the completion |
| <kbd>Esc</kbd> | Close the completion list |
| <kbd>Tab</kbd> | Indent with spaces |
| <kbd>Enter</kbd> | New line, keeping the indentation (one level more after `:`) |
| <kbd>Backspace</kbd> | In the indentation, remove one level |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>[</kbd> | Fold the block around the cursor |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>]</kbd> | Unfold it |
| <kbd>Ctrl</kbd>+<kbd>=</kbd> / <kbd>Ctrl</kbd>+<kbd>-</kbd> / <kbd>Ctrl</kbd>+<kbd>0</kbd> | Bigger, smaller, default font |
| <kbd>Ctrl</kbd>+<kbd>←</kbd> / <kbd>→</kbd> | Move by word |
| <kbd>Ctrl</kbd>+<kbd>Home</kbd> / <kbd>End</kbd> | Start or end of the code |
| <kbd>Shift</kbd>+movement | Select |
| <kbd>Ctrl</kbd>+<kbd>A</kbd>, <kbd>Ctrl</kbd>+<kbd>C</kbd>, <kbd>Ctrl</kbd>+<kbd>X</kbd>, <kbd>Ctrl</kbd>+<kbd>V</kbd> | Select all, copy, cut, paste |
