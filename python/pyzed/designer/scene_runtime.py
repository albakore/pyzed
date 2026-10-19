"""``SceneComponent``: a ``pz.Component`` whose ``render()`` draws a layout made in the designer.

    class Rating(SceneComponent, scene="rating.pzcomp"):
        value: int = 3
        events = {"change": "A star was picked."}

        def star1_click(self, event):
            return self.emit("change", 1)

Every control of the scene is an attribute of the component, and its properties read
and write like attributes, as in form handlers: ``self.title.text = "Hi"``. Each
instance has its own copy of the controls, so two ratings on one form keep separate
state. Bindings set in the designer (a control property that follows a component
property) are applied on every render.
"""

from __future__ import annotations

import dataclasses
import math
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Optional, Tuple

from .. import _core, ui
from ..component import Component
from . import components as _components
from . import layout as _layout
from . import styling
from .model import Control
from .runtime import ControlProxy, Event, theme_for

#: Component types being rendered right now (a scene that contains itself draws a placeholder).
_rendering: list = []
#: Not empty while a form or a parent component renders a designed component at a given size.
_placed: list = []
#: Scenes of components that inherit from another one: (base scene, own scene, merged).
_merged: Dict[type, Tuple[Any, Any, Any]] = {}


class _Scenes:
    """Loaded scenes by path, reloaded when the file changes (hot reload and the designer)."""

    def __init__(self) -> None:
        self.cache: Dict[Path, Tuple[float, Any]] = {}
        #: Scenes that replace the file while the designer previews unsaved changes.
        self.overrides: Dict[Path, Any] = {}

    def get(self, path: Path) -> Any:
        from .scene import load

        if path in self.overrides:
            return self.overrides[path]
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        cached = self.cache.get(path)
        if cached is None or cached[0] != mtime:
            cached = (mtime, load(path))
            self.cache[path] = cached
        return cached[1]


scenes = _Scenes()


class SceneContext(_components.RenderContext):
    """Renders the controls of one component instance: their events call its methods."""

    live = True

    def __init__(self, owner: "SceneComponent", theme: Any) -> None:
        super().__init__(theme, f"{type(owner).type_name}:{id(owner)}")
        self.owner = owner

    def on(self, control: Control, event: str, prop: Optional[str] = None) -> Callable[..., Any]:
        owner = self.owner

        def callback(*args: Any) -> Any:
            target = owner._pyzed_controls.get(control.name, control)
            value = args[0] if len(args) == 1 else (args or None)
            if prop is not None:
                target.props[prop] = value
            return owner._dispatch(target, event, value)

        return callback


class SceneComponent(Component):
    """Base class of the components made in the designer's component mode.

    ``scene`` is the ``.pzcomp`` file with the layout, relative to the module. The
    toolbox label, icon, category, description and default size come from the scene
    unless the class sets them.
    """

    designer: ClassVar[bool] = False
    #: The ``.pzcomp`` file of this component (absolute once the class is created).
    scene_file: ClassVar[Optional[Path]] = None

    _pyzed_controls: Dict[str, Control]
    _pyzed_scene: Any
    _pyzed_error: Optional[str]

    def __init_subclass__(cls, scene: Optional[str] = None, **kwargs: Any) -> None:
        if scene is not None:
            folder = _module_folder(cls)
            cls.scene_file = (folder / scene).resolve() if folder else Path(scene).resolve()
        if "designer" not in vars(cls):
            cls.designer = cls.scene_file is not None
        model = cls.scene_model()
        if model is not None:
            for key in ("label", "icon", "category"):
                if key not in vars(cls) and getattr(model, key, ""):
                    setattr(cls, key, getattr(model, key))
            if "size" not in vars(cls):
                cls.size = (model.width, model.height)
            if not cls.__doc__ and model.description:
                cls.__doc__ = model.description
        super().__init_subclass__(**kwargs)

    @classmethod
    def scene_path(cls) -> Optional[Path]:
        return cls.scene_file

    @classmethod
    def scene_model(cls) -> Any:
        """The scene as currently saved (or previewed by the designer), or ``None``.

        A component that inherits from another designed component gets the base's
        controls too, under its own (see ``designer.scene.merge``).
        """
        own = scenes.get(cls.scene_file) if cls.scene_file is not None else None
        base = next((b for b in cls.__mro__[1:] if isinstance(b, type) and issubclass(b, SceneComponent)
                     and b.scene_file is not None and b.scene_file != cls.scene_file), None)
        if base is None or own is None:
            return own
        inherited = base.scene_model()
        if inherited is None:
            return own
        cached = _merged.get(cls)
        if cached is None or cached[0] is not inherited or cached[1] is not own:
            from .scene import merge

            cached = _merged[cls] = (inherited, own, merge(inherited, own))  # same object while unchanged
        return cached[2]

    @classmethod
    def designer_spec(cls) -> Any:
        spec = super().designer_spec()
        inner = spec.render

        def render(control: Control, ctx: Any) -> Any:
            _placed.append(cls)  # the form gives it the size of the control: fill it
            try:
                return inner(control, ctx)
            finally:
                _placed.pop()

        return dataclasses.replace(spec, render=render)

    def _set_props(self, props: Dict[str, Any]) -> None:
        """Like Godot's exported variables: a property the component changed itself keeps its
        value until the parent passes a different one (a plain ``pz.Component`` takes the
        parent's value on every render)."""
        passed = self.__dict__.setdefault("_pyzed_passed", {})
        for name, info in self.__props__.items():
            value = props.get(name, info.default)
            try:
                same = name in passed and passed[name] == value
            except Exception:  # noqa: BLE001 - values that cannot be compared count as new
                same = False
            if not same:
                setattr(self, name, value)
                passed[name] = value

    # -- the controls ------------------------------------------------------------
    def _controls(self) -> Dict[str, Control]:
        """This instance's own copies of the scene's controls (refreshed when the scene changes)."""
        model = self.scene_model()
        current = self.__dict__.get("_pyzed_scene")
        if model is not current:
            old = self.__dict__.get("_pyzed_controls", {})
            controls: Dict[str, Control] = {}
            for control in (model.controls if model is not None else []):
                copy = control.copy()
                previous = old.get(copy.name)
                if previous is not None and previous.type == copy.type:  # keep what was typed or chosen
                    copy.props.update({k: v for k, v in previous.props.items() if k not in control.props
                                       or v != control.props.get(k)})
                controls[copy.name] = copy
            self.__dict__["_pyzed_controls"] = controls
            self.__dict__["_pyzed_scene"] = model
        return self.__dict__["_pyzed_controls"]

    def __getattr__(self, name: str) -> Any:
        # only called for names that are not attributes: controls of the scene
        if name.startswith("_"):
            raise AttributeError(name)
        control = self._controls().get(name)
        if control is None:
            raise AttributeError(f"{type(self).__name__} has no property, method or control {name!r}")
        return ControlProxy(control, self)  # type: ignore[arg-type]

    @property
    def ctx(self) -> SceneContext:  # what ControlProxy.focus() needs
        return SceneContext(self, theme_for(self.scene_model()) if self.scene_model() is not None else None)

    # -- events ------------------------------------------------------------------------
    def _dispatch(self, control: Control, event: str, value: Any = None) -> Any:
        name = control.events.get(event)
        if not name:
            return None
        method = getattr(type(self), name, None)
        if method is None:
            self.__dict__["_pyzed_error"] = f"{control.name}.{event}: method {name}() not found"
            return None
        try:
            return method(self, Event(ControlProxy(control, self), event, value))  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - a bug in a handler must not kill the app
            self.__dict__["_pyzed_error"] = f"{control.name}.{event}: " + \
                traceback.format_exc(limit=-1).strip().splitlines()[-1]
            traceback.print_exc()
            return None

    def _bind(self, controls: Dict[str, Control], model: Any) -> None:
        names = {**{n: getattr(self, n) for n in self.__props__}, **{n: getattr(self, n) for n in self.__state__}}
        names["self"] = self
        for control_name, props in (getattr(model, "bindings", None) or {}).items():
            control = controls.get(control_name)
            if control is None:
                continue
            for prop, expression in props.items():
                try:
                    control.props[prop] = eval(_compiled(expression), {"__builtins__": __builtins__}, names)  # noqa: S307
                except Exception as err:  # noqa: BLE001 - shown on the component
                    self.__dict__["_pyzed_error"] = f"{control_name}.{prop} = {expression}: {err}"

    def render(self) -> Any:
        cls = type(self)
        placed = bool(_placed)  # sized by a form or a parent component (read before rendering children)
        model = self.scene_model()
        if model is None:
            return ui.callout(f"{cls.__name__}: scene not found", str(cls.scene_file or "no scene= given"),
                              tint="error")
        if cls in _rendering:
            return _core.container(ui.label(f"{cls.__name__} (inside itself)", size="sm", color="text_muted"),
                                   width="fill" if placed else model.width,
                                   height="fill" if placed else model.height, center=True)
        controls = self._controls()
        self._bind(controls, model)
        theme = theme_for(model)
        ctx = SceneContext(self, theme)
        view = dataclasses.replace(model, controls=list(controls.values()))
        # The controls are rendered now (nested components keep their state between renders)
        # and placed when the size is known, following their anchors and containers.
        widgets: Dict[str, Any] = {}
        hidden: set = set()
        _rendering.append(cls)
        try:
            for control, _depth in view.walk():
                spec = _components.get(control.type)
                if not control.visible or (control.parent and control.parent in hidden):
                    hidden.add(control.name)
                    continue
                if spec.visual:
                    merged = Control(**{**control.__dict__, "props": {**spec.defaults(), **control.props}})
                    widgets[control.name] = _wrap_mouse(ctx, control,
                                                        _components.styled(spec.render(merged, ctx), control, ctx))
        finally:
            _rendering.pop()
        background = theme.color(model.background) if model.background else None
        if background is None and isinstance((model.style or {}).get("background"), str):
            background = theme.background  # a global plain color became the theme's background
        error = self.__dict__.get("_pyzed_error")

        def draw(width: float, height: float) -> Any:
            size = (width if 0 < width < math.inf else model.width, height if 0 < height < math.inf else model.height)
            rects = _layout.resolve(view, size)
            layers = []
            if background is not None:
                layers.append(_core.container(width="fill", height="fill", bg=background))
            if painted is not None:
                layers.append(painted)
            for name, widget in widgets.items():
                x, y, w, h = rects[name]
                layers.append(_core.pin(_core.container(widget, width=w, height=h, clip=True), x=x, y=y))
            if error:
                layers.append(_core.container(ui.callout("Component error", error, tint="error",
                                                         on_dismiss=self._dismiss_error),
                                              width="fill", height="fill", align_y="end"))
            return styling.apply_global(_core.stack(layers, width="fill", height="fill"), model.style, theme,
                                        background=False)

        painted = styling.background_layer(model.style, theme)
        body = _core.responsive(draw)
        if placed:
            return body
        # used from code: as wide as there is room for, up to its design size
        return _core.container(body, width="fill", max_width=model.width, height=model.height)

    def _dismiss_error(self) -> None:
        self.__dict__["_pyzed_error"] = None


def _wrap_mouse(ctx: SceneContext, control: Control, widget: Any) -> Any:
    wired = {e: control.events.get(e) for e in _components.COMMON_EVENTS}
    if not any(wired.values()):
        return widget
    return _core.mouse_area(
        widget,
        on_enter=ctx.on(control, "mouse_enter") if wired["mouse_enter"] else None,
        on_exit=ctx.on(control, "mouse_leave") if wired["mouse_leave"] else None,
        on_right_press=ctx.on(control, "right_click") if wired["right_click"] else None,
    )


_code_cache: Dict[str, Any] = {}


def _compiled(expression: str) -> Any:
    code = _code_cache.get(expression)
    if code is None:
        code = _code_cache[expression] = compile(expression, "<binding>", "eval")
    return code


def _module_folder(cls: type) -> Optional[Path]:
    """The folder of the file defining ``cls`` (also for modules loaded outside ``sys.modules``)."""
    module = sys.modules.get(cls.__module__)
    file = getattr(module, "__file__", None)
    if file is None:
        frame = sys._getframe(2)  # the module body running the ``class`` statement
        while frame is not None and frame.f_globals.get("__name__") != cls.__module__:
            frame = frame.f_back  # type: ignore[assignment]
        file = frame.f_globals.get("__file__") if frame is not None else None
    return Path(file).resolve().parent if file else None
