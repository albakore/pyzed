"""Event handlers for the welcome form (tutorial: A shader behind a form).

    pyzed run examples/tutorial/designer/welcome.pzform

``backdrop`` is a Shader control that draws ``glow.pzshad``, a shader made of nodes in the
Shader view. Its ``variables`` property sets the shader's variables by name.
"""

from pathlib import Path

COLORS = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24"]


def form_load(form, event):
    """Runs once when welcome opens: point the Shader control at the file next to this one.

    (A relative path in the Shader file property is read from the folder you run the app
    from; building it from ``__file__`` works from anywhere.)
    """
    form.backdrop.file = str(Path(__file__).with_name("glow.pzshad"))


def faster_click(form, event):
    """Runs when faster is clicked: more pulses per second, back to 1 after 8."""
    variables = dict(form.backdrop.variables)
    pulse = variables.get("pulse", 2.0)
    variables["pulse"] = 1.0 if pulse >= 8 else pulse + 1.5
    form.backdrop.variables = variables
    form.hint.text = f"{variables['pulse']:.1f} pulses per second"


def color_click(form, event):
    """Runs when color is clicked: the next neon color."""
    variables = dict(form.backdrop.variables)
    current = variables.get("color", COLORS[0])
    variables["color"] = COLORS[(COLORS.index(current) + 1) % len(COLORS)] if current in COLORS else COLORS[1]
    form.backdrop.variables = variables
