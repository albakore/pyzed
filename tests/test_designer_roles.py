"""The color convention of Pyzed Design: each component has a role, and each role an icon color."""

from dataclasses import replace

import pyzed as pz
from pyzed.designer import components, docks, roles
from pyzed.theme import ONE_DARK, ONE_LIGHT, Theme


def _role(type_):
    return roles.of(components.get(type_))


def _roles(*types):
    """The roles of built-in toolbox types (a project component of the same name, defined by another test,
    replaces the built-in one in the toolbox and is left out)."""
    return {roles.of(s) for s in map(components.get, types) if s.role != "custom"}


def test_every_component_has_a_role():
    for spec in components.all_components():
        assert roles.of(spec) in roles.ROLES, spec.type


def test_roles_follow_what_a_component_is():
    assert _roles("panel", "card", "row", "grid", "dock", "dock_panel", "divider", "spacer") == {"layout"}
    assert _roles("input", "checkbox", "select", "slider", "number", "segmented") == {"input"}
    assert _roles("button", "split_button") == {"action"}
    assert _roles("tabs", "tree", "breadcrumbs", "link") == {"navigation"}
    assert _roles("label", "image", "table", "chart", "badge") == {"display"}
    assert _roles("timer", "process", "file_dialog") == {"system"}
    assert _roles("knob", "waveform", "webcam") == {"media"}
    # the library's own pz.Components are not "custom"
    assert _role("color_picker") == "input"


def test_a_component_can_name_its_role():
    spec = replace(components.get("label"), role="action")
    assert roles.of(spec) == "action"
    assert roles.of(replace(spec, role="nonsense")) == "display"


def test_project_components_are_custom():
    class RoleGauge(pz.Component):
        value: float = 0

        def view(self):
            return pz.text(str(self.value))

    # whatever its category says, a component of the project is the user's own
    assert roles.of(replace(RoleGauge.designer_spec(), category="Display")) == "custom"



def test_colors_come_from_the_theme_and_differ():
    for t in (ONE_DARK, ONE_LIGHT):
        colors = [roles.color(r, t) for r in roles.ROLES]
        assert len(set(colors)) == len(colors)
        assert roles.color("layout", t) == t.ansi["blue"] and roles.color("input", t) == t.ansi["green"]
    bare: Theme = replace(ONE_DARK, ansi={})  # a theme without a terminal palette falls back to its own tokens
    assert roles.color("layout", bare) == bare.accent and roles.color("input", bare) == bare.success
    assert roles.icon_color(None, ONE_DARK) == ONE_DARK.icon_muted


def test_the_left_dock_tab_is_the_toolbox():
    assert docks.PANELS["design"].name == "Toolbox"
