"""A game's main menu: a synthwave shader backdrop, a glowing title and glass buttons.

    python examples/showcase/main_menu.py

- The sun, the grid and the stars are one ``pz.shader``: it scrolls with ``time`` and
  follows the pointer through ``mouse()``.
- The title uses ``bloom``; the menu is a ``glass`` panel whose buttons lift and glow on
  hover (``animate("lift", on="hover")``) and play ``shrink`` on press.
- The arrow keys (or W and S) move the selection.
"""

import pyzed as pz

SYNTHWAVE = """
fn hash(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(12.9898, 78.233))) * 43758.5453);
}

fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    var m = mouse();
    if (m.x < 0.0) {
        m = vec2<f32>(0.5, 0.5);
    }
    let horizon = 0.62 + (m.y - 0.5) * 0.04;
    let aspect = size.x / size.y;
    var color = vec3<f32>(0.0);
    if (uv.y < horizon) {
        // Sky: a dusk gradient, stars and a striped sun.
        let t = uv.y / horizon;
        color = mix(vec3<f32>(0.03, 0.01, 0.10), vec3<f32>(0.55, 0.08, 0.45), pow(t, 2.2));
        let star = step(0.996, hash(floor(px / 2.0))) * (1.0 - t);
        color = color + vec3<f32>(star);
        let center = vec2<f32>(0.5 + (m.x - 0.5) * 0.05, horizon - 0.12);
        let d = length((uv - center) * vec2<f32>(aspect, 1.0));
        let stripes = step(0.0, sin((uv.y - time * 0.02) * 120.0) + (1.0 - (horizon - uv.y) / 0.25) * 1.6 - 0.6);
        let sun = smoothstep(0.205, 0.2, d) * stripes;
        let sun_color = mix(vec3<f32>(1.0, 0.85, 0.25), vec3<f32>(1.0, 0.2, 0.55), clamp((uv.y - center.y + 0.2) / 0.4, 0.0, 1.0));
        color = mix(color, sun_color, sun);
        color = color + vec3<f32>(1.0, 0.3, 0.6) * 0.35 * exp(-d * 6.0);
    } else {
        // Ground: a perspective grid moving towards the viewer.
        let depth = (uv.y - horizon) / (1.0 - horizon);
        let z = 1.0 / max(depth, 0.001);
        let x = (uv.x - 0.5) * aspect * z;
        let gz = fract(z * 0.5 + time * 0.6);
        let gx = fract(x * 1.5);
        let line = max(smoothstep(0.035 * z, 0.0, min(gz, 1.0 - gz)), smoothstep(0.02 * z, 0.0, min(gx, 1.0 - gx)));
        color = mix(vec3<f32>(0.02, 0.0, 0.06), vec3<f32>(0.95, 0.2, 0.85), line * clamp(depth * 3.0, 0.0, 1.0));
        color = color + vec3<f32>(0.6, 0.1, 0.5) * exp(-depth * 12.0) * 0.6;
    }
    return vec4<f32>(color, 1.0);
}
"""

ITEMS = (
    ("play", "Continue", "Chapter 4 · The Neon Pier"),
    ("plus", "New game", "Start a fresh run"),
    ("users", "Multiplayer", "3 friends online"),
    ("settings", "Settings", "Graphics, audio, controls"),
    ("log-out", "Quit", "See you soon"),
)
PINK = "#f472b6"


class MainMenu(pz.App):
    title = "Main menu"
    size = (1280, 720)
    theme = pz.themes.ONE_DARK

    def __init__(self):
        self.selected = 0

    def pick(self, index):
        self.selected = index

    def on_key(self, combo):
        if combo in ("down", "s"):
            self.selected = (self.selected + 1) % len(ITEMS)
            return True
        if combo in ("up", "w"):
            self.selected = (self.selected - 1) % len(ITEMS)
            return True

    def item(self, index):
        icon, label, hint = ITEMS[index]
        selected = index == self.selected
        body = pz.row([
            pz.icon(icon, size=20, color="#ffffff" if selected else "#ffffffbb"),
            pz.column([
                pz.text(label, size=18, weight="bold" if selected else "semibold", color="#ffffff"),
                pz.text(hint, size=12, color="#ffffffaa"),
            ], spacing=1),
        ], spacing=14, align="center")
        style = dict(radius=12, padding=(12, 18), width=330)
        if selected:
            style.update(background=pz.Gradient(["#db2777cc", "#7c3aedcc"], angle=90), border=(1, "#ffffff66"),
                         bloom=(PINK, 0.6))
        else:
            style.update(background="#ffffff0d", border=(1, "#ffffff1a"))
        button = pz.mouse_area(body.style(**style), on_press=lambda: self.pick(index))
        return button.animate("lift", on="hover").animate("shrink", on="press").transition(
            x=6 if selected else 0, duration=160, easing="ease_out_cubic")

    def view(self):
        title = pz.column([
            pz.text("NEON DRIFT", size=72, weight="black", color="#ffe4f3").style(bloom=(PINK, 1.0)),
            pz.text("A pyzed showcase", size=16, color="#fbcfe8").style(opacity=0.8),
        ], spacing=0).animate("fade_in_down", duration=600)
        menu = pz.column([self.item(i) for i in range(len(ITEMS))], spacing=10).style(
            glass={"tint": "#1e0b2e", "strength": 0.35, "blur": 22}, radius=20, padding=16)
        footer = pz.row([
            pz.text("v1.4.2", size=12, color="#ffffff88", font="mono"),
            pz.space(width="fill"),
            pz.text("Press  ↑ ↓  to choose", size=12, color="#ffffffaa").animate(
                "blink", repeat="infinite", duration=2200),
        ], width="fill")
        content = pz.column([
            title,
            pz.row(pz.stagger([menu], "fade_in_left", step=80)),
            pz.space(height="fill"),
            footer,
        ], spacing=28, width="fill", height="fill", padding=(48, 56))
        return pz.stack([
            pz.shader(SYNTHWAVE, fallback=pz.Gradient(["#08021a", "#4a0d5e", "#d9468f"], angle=180)),
            content,
        ])


if __name__ == "__main__":
    pz.run(MainMenu)
