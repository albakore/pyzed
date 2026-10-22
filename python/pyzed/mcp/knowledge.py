"""What the MCP server knows about Pyzed: its components, icons, themes, guides and documentation.

Everything here is plain Python returning JSON-ready data, so it can be used (and tested) without
the MCP SDK. Signatures and docstrings come from the installed package, so they always match the
code. Documentation pages and examples are read from a source checkout when there is one, and
otherwise from GitHub at the installed version's tag.
"""

from __future__ import annotations

import inspect
import json
import re
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyzed

HERE = Path(__file__).resolve().parent
REPO = "albakore/pyzed"
SITE = "https://albakore.github.io/pyzed/"

#: Bundled guides, by topic.
GUIDES = {"overview": "guide.md", "best-practices": "best_practices.md", "cookbook": "cookbook.md"}

#: More topics for ``guide``: each one is a page of the documentation.
TOPICS = {
    "architecture": "guides/architecture", "layout": "guides/layout", "styles": "theming/styles",
    "theming": "theming/themes", "components": "guides/components", "events": "guides/events",
    "async": "guides/async", "commands": "guides/commands", "keyboard": "guides/keyboard",
    "windows": "guides/windows", "animation": "animation/index", "timeline": "animation/timeline",
    "shaders": "shading/shaders",
    "canvas": "guides/canvas", "performance": "guides/performance", "games": "games/index",
    "integrations": "integrations/overview", "architectures": "integrations/architectures",
    "projects": "guides/projects", "packaging": "packaging/build", "testing": "guides/testing",
    "i18n": "guides/i18n", "accessibility": "guides/accessibility", "agents": "guides/agents",
    "designer": "editor/index", "component-designer": "editor/component-designer",
    "data-binding": "editor/data-binding", "editor-shortcuts": "editor/keyboard-shortcuts",
    "blocks": "blocks/index", "stability": "guides/stability",
    "shading": "shading/index", "shader-graphs": "shading/shader-graphs", "tutorials": "tutorials/index",
}

#: The section of each top-level widget in ``list_components``.
WIDGET_CATEGORIES = {
    "Layout": ("box", "column", "row", "container", "center", "stack", "grid", "cell", "flex", "flex_item", "space",
               "hspace", "vspace", "scrollable", "split", "resizable", "responsive", "pin", "opaque", "rule"),
    "Styles": ("stylesheet", "clear_stylesheet", "define_style", "media", "viewport", "current_breakpoint"),
    "Context": ("provide", "use_context"),
    "Text": ("text", "rich_text", "span", "markdown"),
    "Controls": ("button", "checkbox", "text_input", "toggler", "slider", "vertical_slider", "radio",
                 "pick_list", "progress_bar"),
    "Interaction": ("mouse_area", "hover", "tooltip", "popup"),
    "Media": ("image", "image_viewer", "svg", "qr_code", "canvas", "shader", "icon"),
    "Code": ("code_editor",),
    "Anchors": ("anchor_layout", "anchor"),
    "Animation": ("stagger", "presence", "define_animation", "Clip", "Track", "Call", "AnimationPlayer",
                  "AnimationLibrary", "load_animations"),
    "Performance": ("virtual_column", "memo"),
    "Window": ("window_edges",),
    "Game loop": ("frames", "pressed", "is_pressed"),
}

#: ``pz.ui`` modules and the section they appear under.
UI_CATEGORIES = {
    "base": "Basics", "controls": "Controls", "inputs": "Inputs", "display": "Data display", "lists": "Lists",
    "navigation": "Navigation", "overlays": "Overlays", "dialogs": "Dialogs", "workspace": "Workspace",
    "editor": "Code", "color": "Color", "console": "Console", "help": "Help", "frame": "Window",
    "icon_picker": "Icons", "agent": "Agent", "dates": "Dates and times", "system": "System",
}


def version() -> str:
    """The installed Pyzed version."""
    return pyzed.__version__


def guide(topic: str = "overview", lang: str = "en") -> str:
    """Returns a guide: the bundled ``"overview"`` (how Pyzed works), ``"best-practices"`` and ``"cookbook"``
    (runnable recipes), or the documentation page of a topic of ``TOPICS`` (``"games"``, ``"shaders"``...)."""
    if topic in GUIDES:
        return (HERE / GUIDES[topic]).read_text(encoding="utf-8")
    if topic in TOPICS:
        return read_docs(TOPICS[topic], lang)
    raise KeyError(f"unknown guide {topic!r}; available: {', '.join([*GUIDES, *TOPICS])}")


def guides() -> Dict[str, str]:
    """Every topic ``guide`` takes, with what it covers."""
    pages = {p["slug"]: p for p in index()["docs"]}
    out = {"overview": "How Pyzed works: the Elm architecture, the API layers, components, designer and CLI.",
           "best-practices": "Rules for views, state, components, styling, layout, projects and testing.",
           "cookbook": "Runnable recipes: app structure, background work, forms, large data, animation, "
                       "shaders, games, window frames and anchors."}
    for topic, slug in TOPICS.items():
        page = pages.get(slug)
        out[topic] = (page["title"] + ": " + page["description"]) if page else slug
    return out


# -- components ---------------------------------------------------------------------------------------


def _summary(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.split("\n\n", 1)[0].replace("\n", " ").strip()


def _signature(name: str, obj: Any) -> str:
    try:
        return f"{name}{inspect.signature(obj)}"
    except (TypeError, ValueError):
        text = getattr(obj, "__text_signature__", None)
        return f"{name}{text.replace('$module, ', '').replace('$module', '')}" if text else f"{name}(...)"


def _designer():
    from ..designer import components

    return components


def _widgets() -> Dict[str, Any]:
    out = {}
    for names in WIDGET_CATEGORIES.values():
        for name in names:
            obj = getattr(pyzed, name, None)
            if callable(obj):
                out[name] = obj
    return out


def _ui() -> Dict[str, Any]:
    out = {}
    for name in pyzed.ui.__all__:
        obj = getattr(pyzed.ui, name)
        if callable(obj):
            out[name] = obj
    return out


def _ui_category(obj: Any) -> str:
    module = getattr(obj, "__module__", "") or ""
    return UI_CATEGORIES.get(module.rsplit(".", 1)[-1], "Other")


def _widget_category(name: str) -> str:
    for category, names in WIDGET_CATEGORIES.items():
        if name in names:
            return category
    return "Other"


def _user_components() -> Dict[str, Any]:
    from ..component import registered

    return {cls.__name__: cls for cls in registered()}


def list_components(kind: str = "all", query: str = "", category: str = "", role: str = "") -> List[Dict[str, str]]:
    """Every widget and component, with its kind, category and one-line summary.

    ``kind`` is ``"widget"`` (``pz.*``), ``"ui"`` (``pz.ui.*``), ``"designer"`` (the designer's
    toolbox types), ``"component"`` (``pz.Component`` subclasses defined so far) or ``"all"``.
    ``query`` keeps the entries whose name or summary contains it, ``category`` one section and
    ``role`` the designer types of one color role (``"layout"``, ``"input"``, ``"action"``...).
    """
    kinds = ("widget", "ui", "designer", "component")
    if kind != "all" and kind not in kinds:
        raise ValueError(f"unknown kind {kind!r}; use one of: all, {', '.join(kinds)}")
    out: List[Dict[str, str]] = []
    if kind in ("all", "widget"):
        api = _api_docs()
        out += [{"name": f"pz.{n}", "kind": "widget", "category": _widget_category(n),
                 "summary": _summary(o) or api.get(f"pyzed.{n}", {}).get("desc", "")}
                for n, o in _widgets().items()]
    if kind in ("all", "ui"):
        out += [{"name": f"ui.{n}", "kind": "ui", "category": _ui_category(o), "summary": _summary(o)}
                for n, o in _ui().items()]
    if kind in ("all", "designer"):
        from ..designer import roles

        out += [{"name": f"designer:{c.type}", "kind": "designer", "category": c.category, "role": roles.of(c),
                 "summary": c.description or c.label} for c in _designer().all_components()]
    if kind in ("all", "component"):
        out += [{"name": n, "kind": "component", "category": c.category, "role": "custom", "summary": c.describe()}
                for n, c in _user_components().items()]
    q, cat, role = query.lower(), category.lower(), role.lower()
    return [e for e in out
            if (not q or q in e["name"].lower() or q in e["summary"].lower())
            and (not cat or cat == e["category"].lower())
            and (not role or role == e.get("role"))]


def _api_docs() -> Dict[str, Any]:
    """The hand-written API descriptions of the docs (``docs/scripts/api_docs_en.py``), by qualified name."""
    return index().get("api", {}).get("entries", {})


def _param_doc(entry: Dict[str, Any], name: str) -> str:
    return (entry.get("params") or {}).get(name) or index().get("api", {}).get("common", {}).get(name, "")


def _resolve(name: str):
    """``(kind, qualified name, object)`` for a name such as ``pz.text``, ``ui.button`` or ``designer:button``."""
    raw = name.strip()
    if raw.startswith("designer:"):
        return "designer", raw, _designer().get(raw.split(":", 1)[1])
    bare = re.sub(r"^(pyzed\.|pz\.)", "", raw)
    if bare.startswith("ui."):
        obj = getattr(pyzed.ui, bare[3:], None)
        return ("ui", bare, obj) if obj is not None else (None, raw, None)
    components = _user_components()
    if bare in components:
        return "component", bare, components[bare]
    if raw.startswith(("pz.", "pyzed.")):
        obj = getattr(pyzed, bare, None)
        return ("widget", f"pz.{bare}", obj) if obj is not None else (None, raw, None)
    if bare in pyzed.ui.__all__:
        return "ui", f"ui.{bare}", getattr(pyzed.ui, bare)
    if bare in _widgets():
        return "widget", f"pz.{bare}", _widgets()[bare]
    try:
        return "designer", f"designer:{bare}", _designer().get(bare)
    except KeyError:
        pass
    obj = getattr(pyzed, bare, None)
    if obj is not None:
        return "widget", f"pz.{bare}", obj
    return None, raw, None


def _also(name: str, qualified: str) -> List[str]:
    bare = name.split(":")[-1].split(".")[-1]
    out = []
    if hasattr(pyzed, bare) and callable(getattr(pyzed, bare)):
        out.append(f"pz.{bare}")
    if bare in pyzed.ui.__all__:
        out.append(f"ui.{bare}")
    try:
        _designer().get(bare)
        out.append(f"designer:{bare}")
    except KeyError:
        pass
    return [n for n in out if n != qualified]


def describe_component(name: str) -> Dict[str, Any]:
    """Everything about one widget or component: signature, documentation, parameters, props and events.

    ``name`` may be qualified (``pz.text``, ``ui.button``, ``designer:button``, a ``pz.Component``
    class name) or bare; a bare name is looked up in ``pz.ui`` first, then ``pz``, then the designer.
    """
    kind, qualified, obj = _resolve(name)
    if obj is None:
        close = [e["name"] for e in list_components(query=name.split(":")[-1].split(".")[-1])][:10]
        hint = f"; did you mean: {', '.join(close)}" if close else ""
        raise KeyError(f"no widget or component called {name!r}{hint}")
    if kind == "designer":
        return _describe_designer(qualified, obj)
    if kind == "component":
        return _describe_user_component(obj)
    info: Dict[str, Any] = {
        "name": qualified, "kind": kind,
        "category": _ui_category(obj) if kind == "ui" else _widget_category(qualified[3:]),
        "signature": _signature(qualified, obj),
        "doc": inspect.getdoc(obj) or "",
    }
    entry = _api_docs().get(f"pyzed.{qualified[3:]}" if kind == "widget" else f"pyzed.{qualified}") or {}
    if entry.get("desc"):
        info["description"] = entry["desc"]
    try:
        params = list(inspect.signature(obj).parameters.values())
    except (TypeError, ValueError):
        params = []
    info["parameters"] = [
        {"name": p.name, "kind": p.kind.name.lower(),
         **({"default": repr(p.default)} if p.default is not inspect.Parameter.empty else {"required": True}),
         **({"description": _param_doc(entry, p.name)} if _param_doc(entry, p.name) else {})}
        for p in params if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    ]
    if any(p.kind is p.VAR_KEYWORD for p in params):
        info["extra_keywords"] = "Also takes style keywords (see pz.Style): background, color, radius, padding..."
    for key in ("example", "extra"):
        if entry.get(key):
            info[key] = entry[key]
    also = _also(name, qualified)
    if also:
        info["see_also"] = also
    info["docs"] = f"{SITE}reference/{'ui' if kind == 'ui' else 'widgets'}/"
    return info


def _describe_designer(qualified: str, spec: Any) -> Dict[str, Any]:
    from ..designer import roles

    components = _designer()
    return {
        "name": qualified, "kind": "designer", "type": spec.type, "label": spec.label,
        "category": spec.category, "role": roles.of(spec), "icon": spec.icon, "description": spec.description,
        "default_size": list(spec.size), "container": spec.container, "visual": spec.visual,
        "props": [{"name": p.name, "kind": p.kind, "default": p.default, "group": p.group,
                   **({"choices": list(p.choices)} if p.choices else {}),
                   **({"min": p.min} if p.min is not None else {}), **({"max": p.max} if p.max is not None else {})}
                  for p in spec.props],
        "events": {e: components.event_text(spec.type, e).format(name="the control") for e in spec.all_events},
        "handler": "def <control>_<event>(form, event): ...",
        "docs": f"{SITE}guides/designer/",
    }


def _describe_user_component(cls: Any) -> Dict[str, Any]:
    return {
        "name": cls.__name__, "kind": "component", "module": cls.__module__, "doc": inspect.getdoc(cls) or "",
        "category": cls.category, "icon": cls.icon,
        "props": [{"name": p.name, "type": _annotation(p.annotation),
                   **({"required": True} if p.required else {"default": repr(p.default)})}
                  for p in cls.__props__.values()],
        "state": [{"name": s.name, "type": _annotation(s.annotation), "default": repr(s.default), "doc": s.doc}
                  for s in cls.__state__.values()],
        "events": dict(cls.__events__),
        "docs": f"{SITE}guides/components/",
    }


def _annotation(annotation: Any) -> str:
    if isinstance(annotation, str):
        return annotation
    return getattr(annotation, "__name__", None) or str(annotation).replace("typing.", "")


# -- icons and themes ---------------------------------------------------------------------------------


def search_icons(query: str = "", limit: int = 50) -> Dict[str, Any]:
    """Bundled Lucide icon names containing every word of ``query`` (all of them when empty)."""
    from ..icons import names

    words = query.lower().replace("-", " ").split()
    found = [n for n in names() if all(w in n for w in words)]
    return {"total": len(found), "icons": found[:max(1, limit)]}


def list_themes() -> Dict[str, Any]:
    """The registered theme names and the color tokens a style or component can use."""
    import dataclasses

    from ..theme import Theme, themes

    tokens = [f.name for f in dataclasses.fields(Theme) if f.name not in ("name", "appearance")]
    return {
        "themes": [{"name": t.name, "dark": t.is_dark} for t in themes.all()],
        "tokens": tokens,
        "usage": 'App.theme = "One Dark"; widget.style(background="panel", color="text_muted")',
    }


# -- documentation and examples -----------------------------------------------------------------------


@lru_cache(maxsize=1)
def index() -> Dict[str, Any]:
    """The documentation pages and examples: read from the checkout when there is one, else the bundled
    ``docs_index.json`` (written by ``docs/scripts/gen_mcp_index.py``)."""
    root = source_root()
    script = root / "docs" / "scripts" / "gen_mcp_index.py" if root is not None else None
    if script is not None and script.is_file():
        import importlib.util

        spec = importlib.util.spec_from_file_location("_pyzed_mcp_index", script)
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                return json.loads(module.build())
            except Exception:
                pass
    return json.loads((HERE / "docs_index.json").read_text(encoding="utf-8"))


def source_root() -> Optional[Path]:
    """The repository root when Pyzed runs from a source checkout (editable install), else ``None``."""
    root = Path(pyzed.__file__).resolve().parents[2]
    return root if (root / "docs" / "src" / "content" / "docs").is_dir() else None


def list_docs() -> List[Dict[str, str]]:
    """Every documentation page: its slug (for ``read_docs``), title, description and URL."""
    return [{"slug": p["slug"], "title": p["title"], "description": p["description"],
             "url": f"{SITE}{p['slug']}/" if p["slug"] != "index" else SITE}
            for p in index()["docs"]]


def list_examples(kind: str = "", query: str = "") -> List[Dict[str, str]]:
    """The example apps in the repository: their name (for ``read_example``), kind and summary.

    ``kind`` keeps one folder: ``"app"``, ``"blocks"`` (whole screens to copy), ``"games"``, ``"showcase"``,
    ``"tutorial"``, ``"designer"`` or ``"integrations"`` (FastAPI, SQLAlchemy, Django... projects).
    """
    q = query.lower()
    return [e for e in index()["examples"]
            if (not kind or e.get("kind", "app") == kind) and (not q or q in e["name"].lower()
                                                                or q in e["summary"].lower())]


# -- planning --------------------------------------------------------------------------------------------

_STOP = set("a an and app application the to of for with in on that this my me make build create want need "
            "show shows using use like it is be as by or from some new un una el la los las de del con para que "
            "y en mi crea crear quiero haz hacer app aplicacion".split())

#: Words in a request that point at a topic of ``guide``.
_HINTS = {
    "game": "games", "games": "games", "juego": "games", "sprite": "games", "shader": "shaders",
    "glow": "animation", "animation": "animation timeline", "animate": "animation", "animacion": "animation timeline",
    "timeline": "timeline", "cutscene": "timeline", "intro": "timeline", "keyframe": "timeline",
    "effect": "animation", "graph": "shader-graphs", "node": "shader-graphs", "fastapi": "integrations",
    "django": "integrations", "sqlalchemy": "integrations", "sqlmodel": "integrations", "database": "integrations",
    "api": "integrations", "backend": "integrations", "form": "designer", "designer": "designer",
    "formulario": "designer", "list": "performance", "table": "performance", "million": "performance",
    "log": "performance", "theme": "theming", "dark": "theming", "tema": "theming", "window": "windows",
    "menu": "windows", "titlebar": "windows", "translate": "i18n", "language": "i18n", "idioma": "i18n",
    "test": "testing", "package": "packaging", "installer": "packaging", "ai": "agents", "chat": "agents",
    "web": "layout styles components", "css": "styles", "html": "layout", "div": "layout", "flex": "layout",
    "grid": "layout", "layout": "layout", "responsive": "layout styles", "mobile": "styles",
    "breakpoint": "styles", "stylesheet": "styles", "hover": "styles", "style": "styles", "estilo": "styles",
    "landing": "layout styles", "page": "layout", "pagina": "layout", "card": "components", "context": "components",
    "async": "async", "download": "async", "http": "async", "keyboard": "keyboard", "shortcut": "keyboard",
}


def _words(text: str) -> List[str]:
    import re

    return [w for w in re.findall(r"[a-z0-9áéíóúñ]+", text.lower()) if len(w) > 2 and w not in _STOP]


def _score(words: List[str], text: str) -> int:
    hay = text.lower()
    return sum(1 for w in words if w in hay)


def plan(description: str, limit: int = 6) -> Dict[str, Any]:
    """What to read and reuse before building ``description``: the closest blocks and examples, components,
    guide topics and documentation pages, and the steps to follow."""
    words = _words(description)

    def best(items, text, n=limit):
        scored = sorted(((_score(words, text(i)), i) for i in items), key=lambda pair: -pair[0])
        return [i for score, i in scored if score][:n]

    examples = best(index()["examples"], lambda e: f"{e['name']} {e['summary']} {e.get('kind', '')}")
    components = best(list_components("ui") + list_components("widget"),
                      lambda c: f"{c['name']} {c.get('summary', '')} {c.get('category', '')}", limit * 2)
    docs = best(list_docs(), lambda d: f"{d['slug']} {d['title']} {d['description']}")
    topics = sorted({topic for w in words if w in _HINTS for topic in _HINTS[w].split()})
    return {
        "topics": ["best-practices", "cookbook", *topics],
        "examples": [{"name": e["name"], "kind": e.get("kind", "app"), "summary": e["summary"]} for e in examples],
        "components": [{"name": c["name"], "summary": c.get("summary", "")} for c in components],
        "docs": [{"slug": d["slug"], "title": d["title"]} for d in docs],
        "steps": [
            "Read get_guide('best-practices') and get_guide('cookbook'), then the topics above.",
            "Read the closest example with read_example: start from a block for a whole screen.",
            "project_info: see the project, its entry file and environment; create_project when there is none.",
            "Plan the screens, the state (plain classes in the package, easy to test) and the slow work "
            "(background tasks). Look every component up with describe_component before using it.",
            "Write it like a web page: every part is a pz.box (display block, flex, grid or stack, gap, "
            "overflow, position='absolute' children), the look goes in a pz.stylesheet of classes with :hover "
            "and transition, '@media' rules or pz.media() adapt it to the window, and reusable parts are "
            "pz.Component classes with children, a stylesheet and pz.provide/use_context for shared values "
            "(cookbook: 'Web-style pages').",
            "start_live_preview on the entry so the user watches the app as you build it.",
            "write_files in small steps (state, then views or forms, then tests), fixing what each write reports "
            "and reading live_preview_status for runtime errors.",
            "check_project and run_tests until both are clean; screenshot_project each screen to check the look.",
        ],
    }


# -- the built-in reference ---------------------------------------------------------------------------


def search_reference(query: str, lang: str = "en", limit: int = 20) -> List[Dict[str, str]]:
    """Searches Pyzed's built-in reference: every widget, component, class, function, module and designer
    control, with the id ``read_reference`` takes."""
    from .. import reference

    return [{"id": e.id, "title": e.title, "kind": e.kind, "section": e.section, "summary": e.summary}
            for e in reference.search(query, lang=lang, limit=max(1, limit))]


def read_reference(name: str, lang: str = "en") -> Dict[str, Optional[str]]:
    """The reference page of anything in Pyzed (``"pyzed.game.vector"``, ``"ui.virtual_list"``, ``"App"``...):
    signature, description, parameters and members, in Markdown."""
    from .. import reference

    target = name.strip()
    found = reference.lookup(target) or reference.lookup(f"pyzed.{target}") or target
    try:
        page = reference.page(found, lang=lang)
    except KeyError:
        close = [e.id for e in reference.search(target.rsplit(".", 1)[-1], lang=lang, limit=8)]
        hint = f"; did you mean: {', '.join(close)}" if close else ""
        raise KeyError(f"no reference page for {name!r}{hint}") from None
    return {"id": page.entry.id, "title": page.entry.title, "url": page.url, "body": page.body}


def editor_keymap() -> Dict[str, Any]:
    """The default key bindings of Pyzed's code editor (``ui.editor``, also used by Pyzed Design), by action."""
    from ..ui.editor import DEFAULT_KEYS

    return {"actions": {action: list(keys) for action, keys in DEFAULT_KEYS.items()},
            "change": 'ui.editor(keymap={"ctrl-shift-d": "duplicate_line", "ctrl-d": None}) or '
                      "keymap_for({action: 'keys, separated by commas'}) from pyzed.ui.editor",
            "designer": "Pyzed Design's keys (every command, the canvas, the project tree, the code panel and this editor) "
                        "are in keymap.json in the Pyzed config folder, in Zed's format; File → Keymap editor changes them",
            "docs": f"{SITE}editor/keyboard-shortcuts/", "keymap_docs": f"{SITE}editor/keymap/"}


def _fetch(path: str) -> str:
    """Reads ``path`` (relative to the repository root) from the checkout or from GitHub."""
    root = source_root()
    if root is not None and (root / path).is_file():
        return (root / path).read_text(encoding="utf-8")
    refs = [f"v{version()}", "main"] if re.match(r"^\d+\.\d+\.\d+$", version()) else ["main"]
    error: Optional[Exception] = None
    for ref in refs:
        url = f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as err:
            error = err
    raise FileNotFoundError(f"could not read {path} from GitHub ({error}); see {SITE}")


def read_docs(slug: str, lang: str = "en") -> str:
    """The Markdown source of a documentation page (``slug`` from ``list_docs``), in ``"en"`` or ``"es"``."""
    slug = slug.strip().strip("/").removeprefix("pyzed/").removeprefix("es/") or "index"
    pages = {p["slug"]: p for p in index()["docs"]}
    if slug not in pages:
        close = [s for s in pages if slug.split("/")[-1] in s][:8]
        raise KeyError(f"unknown page {slug!r}" + (f"; did you mean: {', '.join(close)}" if close else
                                                  "; call list_docs for the pages"))
    path = pages[slug]["path"]
    if lang == "es":
        try:
            return _fetch(path.replace("docs/src/content/docs/", "docs/src/content/docs/es/", 1))
        except FileNotFoundError:
            pass
    return _fetch(path)


def read_example(name: str) -> str:
    """The source code of an example app (``name`` from ``list_examples``)."""
    examples = {e["name"]: e for e in index()["examples"]}
    key = name.strip().removesuffix(".py")
    if key not in examples:
        raise KeyError(f"unknown example {name!r}; available: {', '.join(examples)}")
    return _fetch(examples[key]["path"])
