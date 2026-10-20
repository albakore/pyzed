---
title: Menus and commands
description: "The title bar, every menu entry, the toolbar, the command palette, Add control and the dockable panels of Pyzed Design, the Python GUI builder."
sidebar:
  order: 11
---

Every command of the editor lives in one table, so the menus, the command palette, the keyboard and the shortcut
list always agree. This page lists them all.

## The title bar

From left to right: the **☰** menu, the environment under WSL, the project's name (click it for the project picker:
the projects of this window and the recent ones), the git branch (click it to switch), the file name (click
it to open another file), a dot when there are unsaved changes and a **Component** or **Shader** badge in those
views. In the middle: **Run** (<kbd>F5</kbd>), **Stop** and the search field, which opens the
[command palette](#command-palette). At the right: the **View** menu, the **Help** menu and the **Settings** gear, followed by the window buttons when Pyzed Design draws its own frame (see
[The interface](/pyzed/editor/interface/#the-window-frame)).

## ☰ File menu

![The ☰ menu with recent files](../../../assets/editor/menu-file.png)

| Entry | Keys | Does |
| --- | --- | --- |
| New form… | <kbd>Ctrl</kbd>+<kbd>N</kbd> | The New dialog, on Form. |
| New component… | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd> | The New dialog, on Component. |
| Open… | <kbd>Ctrl</kbd>+<kbd>O</kbd> | Lists the forms and components under the working folder. |
| Go to file… | <kbd>Ctrl</kbd>+<kbd>P</kbd> | Finds a project file by name and opens it; see [Go to file](/pyzed/editor/projects/#go-to-file). |
| Open recent project… | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>O</kbd> | The project picker of the title bar; see [Several projects in one window](/pyzed/editor/projects/#several-projects-in-one-window). |
| Save | <kbd>Ctrl</kbd>+<kbd>S</kbd> | Saves the document and its code. |
| Save as… | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd> | Saves under a new path. |
| Settings… | <kbd>Ctrl</kbd>+<kbd>,</kbd> | The [settings](/pyzed/editor/settings/). |
| *Recent* | | The last five files opened. |
| Run | <kbd>F5</kbd> | [Runs](/pyzed/editor/console-and-running/) the form or previews the component. |
| Stop | <kbd>Shift</kbd>+<kbd>F5</kbd> | Closes the running form. |
| Run project script | | Starts the project's `[tool.pyzed] script` with `uv run` (see [Welcome and examples](/pyzed/editor/examples/#running-it)). |
| Edit code file | <kbd>F7</kbd> | Opens the whole code file in the code editor. |

## Edit commands

The Edit commands have no menu of their own: they are on the toolbar, in the control's context menu, on the
keyboard and in the command palette.

| Command | Keys |
| --- | --- |
| Undo / Redo | <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> |
| Cut / Copy / Paste | <kbd>Ctrl</kbd>+<kbd>X</kbd> / <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>Ctrl</kbd>+<kbd>V</kbd> |
| Duplicate | <kbd>Ctrl</kbd>+<kbd>D</kbd> |
| Delete | <kbd>Delete</kbd> |
| Select all | <kbd>Ctrl</kbd>+<kbd>A</kbd> |
| Add control… | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> |
| Group in a row / in a column / in a grid | |

## View menu

![The View menu](../../../assets/editor/menu-view.png)

| Entry | Keys | Does |
| --- | --- | --- |
| Command palette… | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | Runs any command by name. |
| Left dock / Right dock / Bottom dock | <kbd>Ctrl</kbd>+<kbd>B</kbd> / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>B</kbd> / <kbd>Ctrl</kbd>+<kbd>J</kbd> | Shows or hides each dock (checked when shown). |
| Console | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Y</kbd> | Shows the console and keeps it open. |
| Logs | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>U</kbd> | Shows the Logs panel: the editor's events and errors. |
| Agent panel | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd> | Shows or hides the [AI agent](/pyzed/editor/ai-agents/) (checked when shown). |
| Generate a form with AI… / Generate a component with AI… | | Opens the agent with the start of a request ("Create a new form for…") for you to finish. |
| Move tab to new window / Move tab to main window | | Gives the document in front a window of its own, or brings it back among the main window's tabs. See [Document tabs](/pyzed/editor/files-and-scripting/#document-tabs). |
| Toolbar, Status bar | | Shows or hides them. |
| Grid | <kbd>G</kbd> | Shows or hides the dot grid. |
| Snap to grid | | Toggles snapping. |
| Smart guides | | Toggles the alignment guides. |
| Show hidden controls | | Draws hidden controls dimmed on the canvas, or leaves them out. |
| Preview window frame… | | Shows the form on the canvas in the window frame of another platform: macOS, Windows 11, GNOME, Ubuntu or KDE Plasma (checked while it is not this system's). |
| Preview theme…, Preview language… | | Shows the canvas (and the next run) in another theme or language without changing the form (checked while on). See [Preview in another theme or language](/pyzed/editor/data-binding/#preview-in-another-theme-or-language). |
| Reset panel layout | | Puts every panel back in its default dock and size, and closes the panel windows. |
| Save layout as… | | Saves where every panel is, the dock sizes and the panel windows under a name. |
| Delete this layout | | Removes the saved layout in use. |
| *Panels* | | One entry per panel, with the dock it is in (`Properties · Right`, or `Window` when it floats): click to bring it to the front. |
| *Layouts* | | The work layouts (Default, Coding, Focus, Events and code, and yours); the one in use is checked. |

The toggles are remembered between sessions.

## Help menu

![The Help menu open from the question mark of the title bar](../../../assets/editor/menu-help.png)

| Entry | Keys | Does |
| --- | --- | --- |
| Keyboard shortcuts | <kbd>F1</kbd> | A searchable list of every shortcut. |
| Reference | <kbd>Shift</kbd>+<kbd>F1</kbd> | The [built-in reference](/pyzed/editor/reference/), on the page of the selected control or of the name under the cursor. |
| Welcome | | The [welcome window](/pyzed/editor/examples/): start or open a project, recent projects and the example gallery. |
| Example projects… | | The welcome window with every example. |
| Documentation | | Opens this documentation in the browser. |
| Report a problem | | Opens the issue tracker. |
| What's new | | A tab with the release notes of this version (or of the update waiting to install). |
| Check for updates | | Looks for a newer release on GitHub now; see [Updates](/pyzed/download/#updates). |
| Check for updates automatically | | Toggles the daily check (on by default). |
| Get preview releases | | Also offers pre-releases (`X.Y.Z-rc.N`): the preview channel. See [Updates](/pyzed/download/#updates). |
| About Pyzed Design | | The versions of Pyzed, Python and Iced, the platform, and links. |

![The About dialog](../../../../screenshots/editor-about.png)

## The toolbar

Under the document tabs, in groups from left to right:

1. **New…** (a form, a component or a shader, picked in the New dialog), **Undo** and **Redo**.
2. While something is selected: **Align left, centers, right, top, middles, bottom**; **Center in form
   horizontally, vertically**, then **Distribute** (three or more controls) and **Same width, height** (two or
   more); **Bring to front**, **Send to back** and **Delete**. With nothing selected a hint takes their place.
3. At the end, how the canvas behaves: **Show grid**, **Snap to grid**, **Smart guides**, **Resize contents with
   their anchors**, **Fit selection to grid**, and **Edit code file**.

**Open** and **Save** are in the ☰ menu and on <kbd>Ctrl</kbd>+<kbd>O</kbd> and <kbd>Ctrl</kbd>+<kbd>S</kbd>. Every
button has a tooltip with its shortcut, and the editing tools scroll sideways when the window is narrow. Hide it with **View → Toolbar**. See
[Toolbox and canvas](/pyzed/editor/toolbox-and-canvas/#align-distribute-and-size).

## Command palette

The search field in the middle of the title bar, or <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>, opens a search box
over every command that can run right now, as `Group: Command` with its shortcut, and over the places of the editor:
`Panel: Properties` shows a panel, `Editor settings: Cursor` opens that page of the
[editor settings](/pyzed/editor/code-editor/#editor-settings) (the keys are in `File: Keymap editor`), and `Recent: login.pzform` opens a recent file. Type a few letters (the search is fuzzy: `vgr` finds *View: Grid*),
<kbd>↑</kbd>/<kbd>↓</kbd> to move, <kbd>Enter</kbd> to run, <kbd>Esc</kbd> to close. It also reaches commands that
have no menu, such as the Edit ones.

![The command palette](../../../../screenshots/editor-palette.png)

## Add control

<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> is the palette for components: a fuzzy-searchable list of every
component with its category. <kbd>Enter</kbd> adds the highlighted one, centered on the form, and selects it. From
a container (its **+** in the outline, or **Add inside…**), it adds inside that container instead.

## Keyboard shortcuts dialog

<kbd>F1</kbd> lists every shortcut by group (File, Edit, View, Run, Help, Canvas, Code) with a search box. See the
[complete table](/pyzed/editor/keyboard-shortcuts/).

![The keyboard shortcuts dialog](../../../../screenshots/editor-shortcuts.png)

## Panels and docks

Eight panels live in four docks around the canvas:

| Panel | Default dock | Shows |
| --- | --- | --- |
| **Design** | Left | The toolbox and the outline. |
| **Project** | Left | The project's files. |
| **Dependencies** | Left | Dependencies, ruff and ty (only with a project open). |
| **Properties** | Right | The property grid. |
| **Events** | Right | The events of the selection. |
| **Agent** | Right | The [AI agent](/pyzed/editor/ai-agents/). |
| **Code** | Bottom | The code editor (only while a handler or the file is open). |
| **Console** | Bottom | The console (once it has something to show). |

Each dock shows one panel at a time, with a tab per panel. At the end of the tab bar:

- the **dock button** opens a menu to **Move *panel* to** the left, right, bottom or top dock, a **New window**, or
  **Hide dock**;
- the **×** hides the dock (bring it back with its shortcut or the View menu).

Drag a tab to reorder it, onto another dock to move it, or out of the window to float it in a window of its own;
drop more tabs on a panel window to stack them. In a panel window the dock button offers **Dock everything here back**
and the **×** does the same.

![Moving the Properties panel to another dock](../../../../screenshots/editor-dock-menu.png)

Drag the edge of a dock that faces the canvas to resize it (each dock has a minimum size). Where every panel is,
which docks are hidden, their sizes and the panel windows are saved with your settings, and **View → Save layout
as…** keeps them as a work layout to switch to later; **View → Reset panel layout** (or
**Settings → Panels → Reset**) restores the default.

```mermaid
flowchart LR
    subgraph Left
        Design
        Project
        Dependencies
    end
    subgraph Center
        Top["Top dock (empty by default)"]
        Canvas
        subgraph Bottom
            Code
            Console
        end
    end
    subgraph Right
        Properties
        Events
        Agent
    end
```

:::tip
On a wide screen, move **Events** to the left dock (or the top one) to see Properties and Events at the same time;
on a small one, hide the left dock with <kbd>Ctrl</kbd>+<kbd>B</kbd> while you write code, and use
<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> to add controls without the toolbox.
:::

## Notifications

Short messages appear in a corner for a few seconds: saved, copied, opened, a command that failed... Click the ×
to dismiss one; at most four are shown at once.
