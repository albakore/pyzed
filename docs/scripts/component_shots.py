"""Renderiza las ilustraciones de la sección Componentes (docs/src/assets/components/*.png).

    python docs/scripts/component_shots.py            # todas
    python docs/scripts/component_shots.py tabs tree  # solo algunas

Se dibujan fuera de pantalla con ``App.screenshot`` (sin ventana ni GPU), con el tema One Dark.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyzed as pz
from pyzed import ui

OUT = Path(__file__).resolve().parent.parent / "src" / "assets" / "components"
ui.base.KEY_STYLE = "words"
noop = lambda *a: None  # noqa: E731


def buttons():
    return pz.column([
        pz.row([
            ui.button("Filled", noop),
            ui.button("Ghost", noop, variant="ghost"),
            ui.button("Outline", noop, variant="outline"),
            ui.button("Solid", noop, variant="solid"),
            ui.button("Disabled", noop, disabled=True),
        ], spacing=8),
        pz.row([
            ui.button("Error", noop, variant="error", icon="trash-2"),
            ui.button("Warning", noop, variant="warning", icon="triangle-alert"),
            ui.button("Success", noop, variant="success", icon="check"),
            ui.button("Guardar", noop, icon="save", keys="ctrl-s"),
        ], spacing=8),
        pz.row([
            ui.button("xs", noop, size="xs"), ui.button("sm", noop, size="sm"),
            ui.button("md", noop, size="md"), ui.button("lg", noop, size="lg"),
            ui.icon_button("settings", noop, tooltip="Ajustes"),
            ui.icon_button("search", noop, variant="filled"),
            ui.icon_button("bell", noop, selected=True),
        ], spacing=8, align="center"),
    ], spacing=12)


def text():
    return pz.column([
        ui.heading("Heading 1"),
        ui.heading("Heading 2", level=2),
        ui.heading("Heading 3", level=3),
        ui.label("Label normal"),
        ui.muted("Texto atenuado"),
        ui.label("Texto de acento", color="accent"),
        ui.label("def mono(): ...", mono=True, size="sm"),
    ], spacing=6)


def badges():
    return pz.column([
        pz.row([ui.badge("accent"), ui.badge("success", tint="success"), ui.badge("warning", tint="warning"),
                ui.badge("error", tint="error", icon="circle-x")], spacing=6),
        pz.row([ui.badge("solid", variant="solid"), ui.badge("outline", variant="outline"),
                ui.indicator(), ui.indicator("success"), ui.indicator("error"), ui.indicator("warning")],
               spacing=6, align="center"),
        pz.row([ui.kbd("ctrl-shift-p"), ui.kbd("cmd-k cmd-s"), ui.kbd("escape")], spacing=12),
        pz.row([ui.avatar("AL", index=0), ui.avatar("KV", index=1), ui.avatar("MZ", index=2),
                ui.avatar("JD", index=3, size=28)], spacing=6, align="center"),
    ], spacing=14)


def card():
    return ui.card(
        pz.column([
            ui.muted("Pyzed dibuja la interfaz con Iced en Rust."),
            pz.row([pz.hspace(), ui.button("Cancelar", noop, variant="ghost"),
                    ui.button("Aceptar", noop, variant="solid")], spacing=8),
        ], spacing=12),
        title="Tarjeta",
        actions=[ui.icon_button("ellipsis", noop, size="sm")],
        width=380,
    )


def forms():
    return pz.column([
        ui.input("", noop, placeholder="Nombre del proyecto"),
        ui.search_input("comp", noop),
        ui.field("Autoguardado", ui.switch(True, noop), description="Guarda al cambiar de pestaña"),
        ui.field("Formato al guardar", ui.checkbox(False, noop)),
        ui.field("Tamaño de fuente", pz.container(ui.slider(0.6, noop), width=160)),
        ui.segmented(["Editor", "Terminal", "Ambos"], "Editor", noop),
        ui.progress(0.65),
    ], spacing=12, width=420)


def list_items():
    return pz.container(
        pz.column([
            ui.list_header("RECIENTES", end=ui.icon_button("plus", noop, size="xs")),
            ui.list_item("main.py", noop, icon="file-code", icon_color="#3572a5", selected=True, inset=True),
            ui.list_item("README.md", noop, icon="file-text", inset=True, end=ui.badge("M", tint="warning")),
            ui.list_item("Cargo.toml", noop, icon="file-cog", inset=True, end=ui.kbd("ctrl-1", size="xs")),
            ui.list_item("antiguo.txt", noop, icon="file", inset=True, disabled=True),
        ], width=300),
        padding=4,
    )


def tree():
    nodes = ui.TreeNode.from_paths(
        ["src/main.rs", "src/app.rs", "src/ui/button.rs", "src/ui/mod.rs", "tests/app.rs", "Cargo.toml", "README.md"],
        status={"src/app.rs": "modified", "src/ui/button.rs": "created", "README.md": "modified"},
    )
    return pz.container(ui.tree(nodes, expanded={"src", "src/ui"}, selected="src/app.rs", on_toggle=noop,
                                on_select=noop), width=260)


def menu():
    return ui.menu([
        ui.MenuItem("Nuevo archivo", noop, icon="file-plus", keys="ctrl-n"),
        ui.MenuItem("Nueva carpeta", noop, icon="folder-plus"),
        ui.SEPARATOR,
        "EDITAR",
        ui.MenuItem("Copiar ruta", noop, keys="ctrl-alt-c"),
        ui.MenuItem("Ajuste de línea", noop, checked=True),
        ui.SEPARATOR,
        ui.MenuItem("Eliminar", noop, icon="trash-2", danger=True),
    ])


def tabs():
    return pz.column([
        ui.tab_bar(
            [ui.Tab.for_file("src/main.rs"), ui.Tab.for_file("src/app.rs", dirty=True, status="modified"),
             ui.Tab.for_file("README.md", preview=True)],
            "src/main.rs", on_select=noop, on_close=noop,
            start=[ui.icon_button("arrow-left", noop, size="sm"), ui.icon_button("arrow-right", noop, size="sm")],
            end=[ui.icon_button("plus", noop, size="sm"), ui.icon_button("columns-2", noop, size="sm")],
        ),
        ui.toolbar(
            [ui.breadcrumbs([("file-code", "src"), "main.rs", "fn main"])],
            [ui.icon_button("search", noop, size="sm"), ui.icon_button("sparkles", noop, size="sm")],
        ),
    ], width=640)


def workspace():
    t = pz.theme.current()
    files = ui.TreeNode.from_paths(["src/main.py", "src/ui.py", "README.md"], status={"src/ui.py": "modified"})
    return ui.workspace(
        pz.column([
            ui.tab_bar([ui.Tab.for_file("src/main.py")], "src/main.py", on_close=noop),
            ui.editor("ws-main", 'import pyzed as pz\n\n\ndef main():\n    pz.run(App)\n', path="main.py"),
        ]),
        title_bar=ui.title_bar([ui.title_button("pyzed", chevron=True), ui.title_button("main", icon="git-branch", muted=True)],
                               [ui.icon_button("bell", noop, size="sm"), ui.avatar("KV")]),
        left=pz.column([ui.panel_header("Proyecto", [ui.icon_button("plus", noop, size="xs")]),
                        ui.tree(files, expanded={"src"}, selected="src/main.py")]),
        bottom=pz.column([ui.panel_header("Terminal", icon="terminal"),
                          ui.terminal("$ python main.py\n\x1b[32m✓\x1b[0m listo")]),
        status_bar=ui.status_bar([ui.status_item("0", icon="circle-x"), ui.status_item("1", icon="triangle-alert")],
                                 [ui.status_item("Ln 4, Col 8"), ui.status_item("Python")]),
        left_width=200,
        bottom_height=110,
        theme=t,
    )


def palette():
    commands = [
        ui.PaletteItem("editor: toggle soft wrap", noop, keys="alt-z"),
        ui.PaletteItem("theme selector: toggle", noop, keys="ctrl-k ctrl-t"),
        ui.PaletteItem("workspace: toggle left dock", noop, keys="ctrl-b"),
        ui.PaletteItem("terminal panel: toggle", noop, keys="ctrl-j"),
    ]
    return ui.command_palette("tog", noop, commands, selected=0, width=520)


def modal():
    return ui.modal(
        ui.muted("Hay cambios sin guardar en main.py. ¿Quieres guardarlos antes de cerrar?"),
        title="¿Guardar cambios?",
        on_close=noop,
        footer=[ui.button("No guardar", noop, variant="ghost"), ui.button("Cancelar", noop),
                ui.button("Guardar", noop, variant="solid")],
        width=420,
    )


def toasts():
    return pz.column([
        ui.toast("Guardado", "main.py se guardó correctamente.", kind="success", on_dismiss=noop),
        ui.toast("Actualización disponible", "Pyzed 0.2 ya está en PyPI.", kind="info",
                 actions=[ui.button("Ver novedades", noop, size="sm")], on_dismiss=noop),
        ui.toast("No se pudo conectar", kind="error", on_dismiss=noop),
    ], spacing=8)


def editor():
    code = '''import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    def __init__(self):
        self.count = 0  # estado

    def view(self):
        return ui.button(f"Clicks: {self.count}", self.increment)
'''
    return pz.container(ui.editor("doc-editor", code, path="counter.py", markers={6: "modified", 7: "created", 10: "created"}),
                        width=560, height=250)


def terminal():
    out = ("$ pytest -q\n\x1b[32m........................\x1b[0m\n\x1b[32m24 passed\x1b[0m in 1.21s\n"
           "$ maturin develop --release\n\x1b[2m   Compiling pyzed v0.1.0\x1b[0m\n\x1b[32m✓\x1b[0m Installed pyzed-0.1.0\n$ ")
    return pz.container(ui.terminal(out), width=520, height=170)


SHOTS = {
    "buttons": (buttons, (600, 150)),
    "text": (text, (320, 230)),
    "badges": (badges, (420, 170)),
    "card": (card, (420, 150)),
    "forms": (forms, (460, 290)),
    "list": (list_items, (340, 170)),
    "tree": (tree, (300, 250)),
    "menu": (menu, (290, 230)),
    "tabs": (tabs, (680, 100)),
    "workspace": (workspace, (820, 460)),
    "palette": (palette, (560, 220)),
    "modal": (modal, (460, 170)),
    "toasts": (toasts, (380, 270)),
    "editor": (editor, (600, 290)),
    "terminal": (terminal, (560, 210)),
}


class Shot(pz.App):
    def __init__(self, build, full=False):
        self.build, self.full = build, full

    def view(self):
        if self.full:
            return self.build()
        return pz.container(self.build(), padding=20, width="fill", height="fill", bg=self.theme.background)


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names or SHOTS:
        build, size = SHOTS[name]
        Shot(build, full=name == "workspace").screenshot(OUT / f"{name}.png", size=size, scale=2)
        print(f"wrote {name}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
