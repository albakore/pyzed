"""A frosted-glass control center: music, lights, climate and a schedule over moving color.

    python examples/showcase/glass_dashboard.py

- The background is a ``pz.shader`` of soft color blobs that drift with ``time``.
- Every card is ``glass``: a tinted panel that blurs what moves behind it (``backdrop_blur``).
- Switches, sliders and the play button update the cards; values move with ``transition``.
"""

import pyzed as pz
from pyzed import ui

BLOBS = """
fn blob(uv: vec2<f32>, center: vec2<f32>, radius: f32) -> f32 {
    return exp(-pow(length(uv - center) / radius, 2.0));
}

fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let p = uv * vec2<f32>(size.x / size.y, 1.0);
    let t = time * 0.25;
    var color = vec3<f32>(0.04, 0.05, 0.12);
    color = color + vec3<f32>(0.95, 0.25, 0.55) * blob(p, vec2<f32>(0.4 + 0.25 * sin(t), 0.3 + 0.15 * cos(t * 1.3)), 0.45);
    color = color + vec3<f32>(0.20, 0.45, 1.00) * blob(p, vec2<f32>(1.3 + 0.3 * cos(t * 0.8), 0.7 + 0.2 * sin(t)), 0.55);
    color = color + vec3<f32>(0.10, 0.85, 0.70) * blob(p, vec2<f32>(0.9 + 0.2 * sin(t * 1.7), 1.0 + 0.1 * cos(t)), 0.35);
    color = color + vec3<f32>(1.00, 0.65, 0.20) * blob(p, vec2<f32>(1.6 + 0.1 * sin(t * 2.0), 0.15), 0.25);
    return vec4<f32>(color, 1.0);
}
"""
GLASS = {"tint": "#ffffff", "strength": 0.10, "blur": 28}
WHITE = "#ffffff"
MUTED = "#ffffffaa"


class Dashboard(pz.App):
    title = "Control center"
    size = (1180, 700)
    theme = pz.themes.ONE_DARK

    def __init__(self):
        self.playing = True
        self.volume = 64.0
        self.lights = {"Living room": True, "Kitchen": False, "Studio": True}
        self.brightness = 72.0
        self.temperature = 21.5

    def toggle_play(self):
        self.playing = not self.playing

    def set_volume(self, value):
        self.volume = value

    def toggle_light(self, name):
        self.lights[name] = not self.lights[name]

    def set_brightness(self, value):
        self.brightness = value

    def warmer(self):
        self.temperature = min(28.0, self.temperature + 0.5)

    def cooler(self):
        self.temperature = max(16.0, self.temperature - 0.5)

    def card(self, title, icon, body, width):
        head = pz.row([pz.icon(icon, size=16, color=WHITE), pz.text(title, size=13, weight="semibold", color=WHITE)],
                      spacing=8, align="center")
        return pz.column([head, body], spacing=14).style(glass=GLASS, radius=22, padding=20, width=width)

    def music(self):
        cover = pz.container(pz.icon("disc-3", size=44, color="#ffffffdd"), width=112, height=112,
                             align_x="center", align_y="center").style(
            background=pz.Gradient(["#f472b6", "#8b5cf6", "#22d3ee"], angle=135), radius=18,
            rotate=0, bloom=("#c084fc", 0.4))
        if self.playing:
            cover = cover.animate("spin", duration=12000)
        controls = pz.row([
            pz.icon("skip-back", size=20, color=WHITE),
            pz.mouse_area(pz.container(pz.icon("pause" if self.playing else "play", size=22, color="#111827"),
                                       width=48, height=48, align_x="center", align_y="center").style(
                background=WHITE, radius=24, glow=("#ffffff88", 14)), on_press=self.toggle_play).animate(
                "shrink", on="press"),
            pz.icon("skip-forward", size=20, color=WHITE),
        ], spacing=22, align="center")
        info = pz.column([
            pz.text("Midnight City", size=20, weight="bold", color=WHITE),
            pz.text("Neon Avenue · Afterglow", size=13, color=MUTED),
            pz.container(pz.container(None, height=4).style(background=WHITE, radius=2).transition(
                width=230 * (0.42 if self.playing else 0.41), duration=400), width=230).style(
                background="#ffffff33", radius=2),
            pz.row([pz.text("1:48", size=11, color=MUTED), pz.space(width="fill"),
                    pz.text("4:16", size=11, color=MUTED)], width=230),
            controls,
        ], spacing=8)
        volume = pz.row([
            pz.icon("volume-1", size=16, color=MUTED),
            pz.slider(0, 100, self.volume, on_change=self.set_volume, width="fill", accent=WHITE,
                      bg="#ffffff33"),
            pz.icon("volume-2", size=16, color=MUTED),
        ], spacing=10, align="center")
        return self.card("Now playing", "music", pz.column([pz.row([cover, info], spacing=20, align="center"),
                                                           volume], spacing=16), 440)

    def lights_card(self):
        rows = []
        for name, on in self.lights.items():
            rows.append(pz.row([
                pz.container(pz.icon("lightbulb", size=16, color="#1f2937" if on else MUTED), width=34,
                             height=34, align_x="center", align_y="center").style(
                    background="#fde68a" if on else "#ffffff1a", radius=17,
                    bloom=("#fbbf24", 0.6) if on else None),
                pz.column([pz.text(name, size=14, weight="semibold", color=WHITE),
                           pz.text(f"{round(self.brightness)}%" if on else "Off", size=11, color=MUTED)],
                          spacing=1, width="fill"),
                ui.switch(on, lambda _v, name=name: self.toggle_light(name)),
            ], spacing=12, align="center"))
        rows.append(pz.slider(0, 100, self.brightness, on_change=self.set_brightness, width="fill",
                              accent="#fde68a", bg="#ffffff33"))
        return self.card("Lights", "sun", pz.column(rows, spacing=12), 330)

    def climate(self):
        ring = pz.column([
            pz.text(f"{self.temperature:.1f}°", size=44, weight="bold", color=WHITE).transition(
                scale=1.0, duration=200),
            pz.text("Heating to 22°", size=12, color=MUTED),
        ], spacing=0, align="center")
        buttons = pz.row([
            pz.mouse_area(pz.container(pz.icon("minus", size=18, color=WHITE), width=44, height=44,
                                       align_x="center", align_y="center").style(
                background="#ffffff1f", radius=22), on_press=self.cooler).animate("shrink", on="press"),
            pz.mouse_area(pz.container(pz.icon("plus", size=18, color=WHITE), width=44, height=44,
                                       align_x="center", align_y="center").style(
                background="#ffffff1f", radius=22), on_press=self.warmer).animate("shrink", on="press"),
        ], spacing=16)
        dial = pz.container(ring, width=170, height=170, align_x="center", align_y="center").style(
            radius=85, border=(6, "#fb923c"), bloom=("#fb923c", 0.5), background="#ffffff0d")
        return self.card("Climate", "thermometer", pz.column([dial, buttons], spacing=14, align="center", width="fill"), 330)

    def schedule(self):
        events = (
            ("09:30", "Design review", "#22d3ee"),
            ("12:00", "Lunch with Sam", "#a3e635"),
            ("15:00", "Ship 1.2", "#f472b6"),
            ("18:30", "Climbing", "#fbbf24"),
        )
        rows = [pz.row([
            pz.text(time, size=12, color=MUTED, font="mono", width=48),
            pz.container(None, width=4, height=28).style(background=color, radius=2, bloom=(color, 0.6)),
            pz.text(title, size=14, color=WHITE),
        ], spacing=12, align="center") for time, title, color in events]
        return self.card("Today", "calendar", pz.column(rows, spacing=10), 440)

    def header(self):
        return pz.row([
            pz.column([pz.text("Good evening, Kim", size=28, weight="bold", color=WHITE),
                       pz.text("Saturday · 3 rooms on · 21.5° inside", size=14, color=MUTED)], spacing=2),
            pz.space(width="fill"),
            pz.row([pz.icon("search", size=16, color=MUTED), pz.text("Search devices", size=13, color=MUTED)],
                   spacing=8, align="center").style(glass=GLASS, radius=20, padding=(10, 16), width=240),
        ], align="center", width=1124)

    def view(self):
        grid = pz.row([
            pz.column([self.music(), self.schedule()], spacing=20),
            self.lights_card(),
            self.climate(),
        ], spacing=20, align="start")
        content = pz.column([self.header(), pz.row(pz.stagger([grid], "fade_in_up", step=60))], spacing=24)
        return pz.stack([
            pz.shader(BLOBS, fallback=pz.Gradient(["#0b1026", "#5b1a4a", "#0f4c5c"], angle=135)),
            pz.container(content, width="fill", height="fill", align_x="center", align_y="center"),
        ])


if __name__ == "__main__":
    pz.run(Dashboard)
