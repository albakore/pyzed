"""Pyzed Designer: build windows visually, wire their events to Python and run them.

    pyzed design app.pzform     # the visual editor
    pyzed run app.pzform        # run the form with its logic

A form is two files: ``app.pzform`` (JSON layout) and ``app.py`` (event handlers).
A component designed visually is ``rating.pzcomp`` (layout) and ``rating.py`` (a
``SceneComponent`` class with its properties, events and methods); see ``designer.scene``.
Everything is also scriptable::

    from pyzed import designer

    form = designer.Form(title="Hello", width=320, height=160)
    form.add(designer.component("button").create("greet", 16, 16))
    form["greet"].events["click"] = "greet_click"
    designer.save(form, "hello.pzform")
    designer.run("hello.pzform")

Handlers open other forms in new windows with ``form.open("settings")``;
``designer.new_form("ui/settings.pzform")`` creates an empty one.
"""

from .components import (
    COMMON_EVENTS,
    FORM_EVENTS,
    Component,
    Prop,
    RenderContext,
    all_components,
    categories,
    get as component,
    register,
    render,
)
from .document import Document
from .geometry import align, anchored, distribute, same_size, smart_guides, snap
from .history import History
from .model import Control, Form, load, save
from .runtime import Event, FormApp, FormWindow, form_window, new_form, open_form, open_window, run, theme_for
from .scene import Scene, SceneDocument, discover, load_component, new_component, open_document
from .scene_runtime import SceneComponent
from .settings import EditorSettings


def design(path=None, *, theme=None):
    """Opens the visual designer, optionally on a ``.pzform`` file (created on first save)."""
    from .app import design as _design

    _design(path, theme=theme)


def __getattr__(name):
    if name == "Designer":
        from .app import Designer

        return Designer
    raise AttributeError(name)


__all__ = [
    "COMMON_EVENTS",
    "FORM_EVENTS",
    "Component",
    "Control",
    "Designer",
    "Document",
    "EditorSettings",
    "Event",
    "Form",
    "FormApp",
    "FormWindow",
    "History",
    "Prop",
    "RenderContext",
    "Scene",
    "SceneComponent",
    "SceneDocument",
    "align",
    "all_components",
    "anchored",
    "categories",
    "component",
    "design",
    "discover",
    "distribute",
    "form_window",
    "load",
    "load_component",
    "new_component",
    "new_form",
    "open_document",
    "open_form",
    "open_window",
    "register",
    "render",
    "run",
    "same_size",
    "save",
    "smart_guides",
    "snap",
    "theme_for",
]
