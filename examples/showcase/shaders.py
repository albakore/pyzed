"""A gallery of ``pz.shader`` widgets: plasma, a ripple that follows the pointer, a tunnel,
a CRT screen, Voronoi cells and a fire, each a few lines of WGSL.

    python examples/showcase/shaders.py

A shader is a function the GPU runs for every pixel, every frame::

    pz.shader('''
    fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
        return vec4<f32>(uv.x, uv.y, 0.5 + 0.5 * sin(time), 1.0);
    }
    ''')

``uniforms={"speed": 2.0, "tint": "accent"}`` passes values in (read them as ``speed()``
and ``tint()``); the slider below changes ``speed`` on every shader without recompiling.
"""

import pyzed as pz

COMMON = """
fn hash2(p: vec2<f32>) -> vec2<f32> {
    let q = vec2<f32>(dot(p, vec2<f32>(127.1, 311.7)), dot(p, vec2<f32>(269.5, 183.3)));
    return fract(sin(q) * 43758.5453);
}
"""

SHADERS = {
    "Plasma": """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let t = time * speed();
    let p = uv * 8.0 - 4.0;
    let v = sin(p.x + t) + sin((p.y + t) * 0.5) + sin((p.x + p.y + t) * 0.5) + sin(length(p) + t * 1.5);
    return vec4<f32>(0.5 + 0.5 * cos(v * 1.2 + vec3<f32>(0.0, 2.1, 4.2)), 1.0);
}
""",
    "Ripple": """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    var m = mouse();
    if (m.x < 0.0) {
        m = vec2<f32>(0.5, 0.5);
    }
    let d = length((uv - m) * vec2<f32>(size.x / size.y, 1.0));
    let wave = sin(d * 40.0 - time * speed() * 6.0) * exp(-d * 4.0);
    let base = mix(vec3<f32>(0.02, 0.10, 0.25), vec3<f32>(0.0, 0.55, 0.75), uv.y);
    return vec4<f32>(base + tint().rgb * wave * 0.5, 1.0);
}
""",
    "Tunnel": """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let p = (uv - 0.5) * vec2<f32>(size.x / size.y, 1.0);
    let r = length(p);
    let a = atan2(p.y, p.x) / 3.14159;
    let t = time * speed();
    let u = vec2<f32>(0.3 / r + t * 0.5, a * 2.0 + t * 0.1);
    let check = step(0.5, fract(u.x * 2.0)) * 0.6 + step(0.5, fract(u.y * 4.0)) * 0.4;
    let color = mix(vec3<f32>(0.3, 0.1, 0.6), vec3<f32>(0.1, 0.9, 0.9), check) * smoothstep(0.0, 0.35, r);
    return vec4<f32>(color, 1.0);
}
""",
    "CRT": """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let c = uv - 0.5;
    let bent = uv + c * dot(c, c) * 0.25;
    if (bent.x < 0.0 || bent.x > 1.0 || bent.y < 0.0 || bent.y > 1.0) {
        return vec4<f32>(0.0, 0.0, 0.0, 1.0);
    }
    let bars = floor(bent.x * 8.0);
    var color = 0.5 + 0.5 * cos(bars * 0.8 + vec3<f32>(0.0, 2.0, 4.0));
    let roll = fract(bent.y - time * speed() * 0.15);
    color = color * (0.75 + 0.25 * smoothstep(0.0, 0.08, roll));
    color = color * (0.8 + 0.2 * sin(px.y * 3.14159));
    let vignette = 1.0 - dot(c, c) * 1.6;
    return vec4<f32>(color * vignette, 1.0);
}
""",
    "Voronoi": """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let p = px / 42.0;
    let cell = floor(p);
    var best = 8.0;
    var second = 8.0;
    for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
            let n = cell + vec2<f32>(f32(x), f32(y));
            let point = n + 0.5 + 0.4 * sin(time * speed() + 6.2831 * hash2(n));
            let d = length(point - p);
            if (d < best) {
                second = best;
                best = d;
            } else if (d < second) {
                second = d;
            }
        }
    }
    let edge = smoothstep(0.0, 0.08, second - best);
    let color = mix(tint().rgb * 1.4, vec3<f32>(0.05, 0.05, 0.12) + tint().rgb * best * 0.6, edge);
    return vec4<f32>(color, 1.0);
}
""",
    "Fire": """
fn noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    let a = hash2(i).x;
    let b = hash2(i + vec2<f32>(1.0, 0.0)).x;
    let c = hash2(i + vec2<f32>(0.0, 1.0)).x;
    let d = hash2(i + vec2<f32>(1.0, 1.0)).x;
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let t = time * speed();
    var n = 0.0;
    var amp = 0.5;
    var p = vec2<f32>(uv.x * 4.0, uv.y * 3.0 + t * 1.5);
    for (var i = 0; i < 4; i = i + 1) {
        n = n + amp * noise(p);
        p = p * 2.0;
        amp = amp * 0.5;
    }
    let heat = clamp(n * 1.6 - (1.0 - uv.y) * 1.1 + 0.2, 0.0, 1.0);
    let color = vec3<f32>(heat * 1.4, pow(heat, 2.0), pow(heat, 5.0) * 0.8);
    return vec4<f32>(color, 1.0);
}
""",
}
FALLBACKS = {
    "Plasma": pz.Gradient(["#7c3aed", "#ec4899", "#f59e0b"], angle=45),
    "Ripple": pz.Gradient(["#0c4a6e", "#0891b2"], angle=180),
    "Tunnel": pz.Gradient(["#1e1b4b", "#0e7490"], angle=135),
    "CRT": pz.Gradient(["#ef4444", "#22c55e", "#3b82f6"], angle=90),
    "Voronoi": pz.Gradient(["#111827", "#4c1d95"], angle=135),
    "Fire": pz.Gradient(["#000000", "#b91c1c", "#fbbf24"], angle=180),
}
TINTS = {"Ripple": "#7dd3fc", "Voronoi": "#a78bfa"}


class Shaders(pz.App):
    title = "Shaders"
    size = (1140, 720)
    theme = pz.themes.ONE_DARK

    def __init__(self):
        self.speed = 1.0

    def set_speed(self, value):
        self.speed = value

    def tile(self, name):
        code = COMMON + SHADERS[name]
        uniforms = {"speed": self.speed, "tint": TINTS.get(name, "#ffffff")}
        art = pz.shader(code, uniforms=uniforms, width=340, height=210, fallback=FALLBACKS[name])
        label = pz.row([
            pz.text(name, size=14, weight="semibold", color="#ffffff"),
            pz.space(width="fill"),
            pz.text(f"{SHADERS[name].count(chr(10))} lines", size=11, color="#ffffff88", font="mono"),
        ], width=340, align="center")
        return pz.column([art, label],
                         spacing=8).animate("lift", on="hover")

    def view(self):
        names = list(SHADERS)
        grid = pz.column([pz.row([self.tile(n) for n in names[i:i + 3]], spacing=20) for i in (0, 3)],
                         spacing=22)
        header = pz.row([
            pz.column([
                pz.text("Shaders", size=28, weight="bold", color="#ffffff"),
                pz.text("pz.shader runs your WGSL for every pixel on the GPU", size=13, color="#ffffffaa"),
            ], spacing=2),
            pz.space(width="fill"),
            pz.text("Speed", size=13, color="#ffffffaa"),
            pz.slider(0.0, 3.0, self.speed, step=0.05, on_change=self.set_speed, width=200),
            pz.text(f"{self.speed:.2f}×", size=13, color="#ffffff", font="mono", width=48),
        ], spacing=12, align="center", width=1060)
        return pz.container(pz.column([header, pz.row(pz.stagger([grid], "fade_in_up"))], spacing=24),
                            width="fill", height="fill", align_x="center", align_y="center").style(
            background="#0b0d14")


if __name__ == "__main__":
    pz.run(Shaders)
