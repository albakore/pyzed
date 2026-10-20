"""The WGSL functions nodes call: noise, Voronoi, color spaces, signed distances, blend modes.

Each entry of ``FUNCTIONS`` is ``(code, dependencies)``; the compiler writes the ones a
graph uses (and what they use) once, before the graph's own code. Every name starts
with ``pzs_`` so it never clashes with a variable of the graph.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

FUNCTIONS: Dict[str, Tuple[str, Tuple[str, ...]]] = {}


def _add(name: str, code: str, *deps: str) -> None:
    FUNCTIONS[name] = (code.strip() + "\n", deps)


_add("pzs_mouse", """
// The pointer from 0 to 1 across the shader, or its center while the pointer is outside.
fn pzs_mouse() -> vec2<f32> {
    let m = mouse();
    if (m.x < 0.0) {
        return vec2<f32>(0.5, 0.5);
    }
    return m;
}
""")

_add("pzs_centered", """
// uv with (0, 0) in the middle and the shorter side from -0.5 to 0.5, so circles stay round.
fn pzs_centered(uv: vec2<f32>, size: vec2<f32>) -> vec2<f32> {
    let aspect = size.x / max(size.y, 1.0);
    return (uv - 0.5) * vec2<f32>(aspect, 1.0);
}
""")

_add("pzs_white", """
fn pzs_white(uv: vec2<f32>) -> vec4<f32> {
    return vec4<f32>(1.0, 1.0, 1.0, 1.0);
}
""")

# -- random and noise ----------------------------------------------------------

_add("pzs_hash11", """
fn pzs_hash11(p: f32) -> f32 {
    return fract(sin(p * 127.1 + 311.7) * 43758.5453);
}
""")

_add("pzs_hash21", """
fn pzs_hash21(p: vec2<f32>) -> f32 {
    return fract(sin(dot(p, vec2<f32>(127.1, 311.7))) * 43758.5453);
}
""")

_add("pzs_hash22", """
fn pzs_hash22(p: vec2<f32>) -> vec2<f32> {
    let q = vec2<f32>(dot(p, vec2<f32>(127.1, 311.7)), dot(p, vec2<f32>(269.5, 183.3)));
    return fract(sin(q) * 43758.5453);
}
""")

_add("pzs_value_noise", """
// Smooth value noise from 0 to 1.
fn pzs_value_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * (3.0 - 2.0 * f);
    let a = pzs_hash21(i);
    let b = pzs_hash21(i + vec2<f32>(1.0, 0.0));
    let c = pzs_hash21(i + vec2<f32>(0.0, 1.0));
    let d = pzs_hash21(i + vec2<f32>(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
""", "pzs_hash21")

_add("pzs_perlin_noise", """
// Gradient (Perlin) noise from 0 to 1.
fn pzs_perlin_noise(p: vec2<f32>) -> f32 {
    let i = floor(p);
    let f = fract(p);
    let u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    let ga = pzs_hash22(i) * 2.0 - 1.0;
    let gb = pzs_hash22(i + vec2<f32>(1.0, 0.0)) * 2.0 - 1.0;
    let gc = pzs_hash22(i + vec2<f32>(0.0, 1.0)) * 2.0 - 1.0;
    let gd = pzs_hash22(i + vec2<f32>(1.0, 1.0)) * 2.0 - 1.0;
    let a = dot(ga, f);
    let b = dot(gb, f - vec2<f32>(1.0, 0.0));
    let c = dot(gc, f - vec2<f32>(0.0, 1.0));
    let d = dot(gd, f - vec2<f32>(1.0, 1.0));
    return clamp(mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 0.75 + 0.5, 0.0, 1.0);
}
""", "pzs_hash22")

_add("pzs_simplex_noise", """
// 2D simplex noise from 0 to 1.
fn pzs_simplex_noise(p: vec2<f32>) -> f32 {
    let k1 = 0.366025404;
    let k2 = 0.211324865;
    let i = floor(p + (p.x + p.y) * k1);
    let a = p - i + (i.x + i.y) * k2;
    let m = step(a.y, a.x);
    let o = vec2<f32>(m, 1.0 - m);
    let b = a - o + k2;
    let c = a - 1.0 + 2.0 * k2;
    let h = max(vec3<f32>(0.5) - vec3<f32>(dot(a, a), dot(b, b), dot(c, c)), vec3<f32>(0.0));
    let ga = pzs_hash22(i) * 2.0 - 1.0;
    let gb = pzs_hash22(i + o) * 2.0 - 1.0;
    let gc = pzs_hash22(i + 1.0) * 2.0 - 1.0;
    let n = h * h * h * h * vec3<f32>(dot(a, ga), dot(b, gb), dot(c, gc));
    return clamp(dot(n, vec3<f32>(70.0)) * 0.5 + 0.5, 0.0, 1.0);
}
""", "pzs_hash22")

for _kind in ("value", "perlin", "simplex"):
    _add(f"pzs_fbm_{_kind}", f"""
// Fractal noise: octaves of {_kind} noise, each one finer and fainter. From 0 to 1.
fn pzs_fbm_{_kind}(p: vec2<f32>, octaves: i32, lacunarity: f32, gain: f32) -> f32 {{
    var sum = 0.0;
    var amplitude = 0.5;
    var total = 0.0;
    var q = p;
    for (var i = 0; i < clamp(octaves, 1, 12); i = i + 1) {{
        sum = sum + amplitude * pzs_{_kind}_noise(q);
        total = total + amplitude;
        q = q * lacunarity + vec2<f32>(17.3, 9.1);
        amplitude = amplitude * gain;
    }}
    return sum / max(total, 0.0001);
}}
""", f"pzs_{_kind}_noise")

_add("pzs_voronoi", """
// Voronoi cells: x = distance to the nearest point, y = to the second nearest,
// z = a random number per cell, w = distance to the nearest edge.
fn pzs_voronoi(p: vec2<f32>, jitter: f32, phase: f32) -> vec4<f32> {
    let cell = floor(p);
    var best = 8.0;
    var second = 8.0;
    var id = 0.0;
    for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
            let n = cell + vec2<f32>(f32(x), f32(y));
            let h = pzs_hash22(n);
            let point = n + 0.5 + jitter * 0.5 * sin(phase + 6.2831853 * h);
            let d = length(point - p);
            if (d < best) {
                second = best;
                best = d;
                id = h.x;
            } else if (d < second) {
                second = d;
            }
        }
    }
    return vec4<f32>(best, second, id, (second - best) * 0.5);
}
""", "pzs_hash22")

# -- color ---------------------------------------------------------------------

_add("pzs_hsv2rgb", """
fn pzs_hsv2rgb(c: vec3<f32>) -> vec3<f32> {
    let k = vec3<f32>(1.0, 2.0 / 3.0, 1.0 / 3.0);
    let p = abs(fract(vec3<f32>(c.x) + k) * 6.0 - vec3<f32>(3.0));
    return c.z * mix(vec3<f32>(1.0), clamp(p - vec3<f32>(1.0), vec3<f32>(0.0), vec3<f32>(1.0)), c.y);
}
""")

_add("pzs_rgb2hsv", """
fn pzs_rgb2hsv(c: vec3<f32>) -> vec3<f32> {
    let k = vec4<f32>(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    let p = mix(vec4<f32>(c.b, c.g, k.w, k.z), vec4<f32>(c.g, c.b, k.x, k.y), step(c.b, c.g));
    let q = mix(vec4<f32>(p.x, p.y, p.w, c.r), vec4<f32>(c.r, p.y, p.z, p.x), step(p.x, c.r));
    let d = q.x - min(q.w, q.y);
    let e = 1.0e-10;
    return vec3<f32>(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}
""")

_add("pzs_hue_shift", """
fn pzs_hue_shift(c: vec3<f32>, shift: f32) -> vec3<f32> {
    let hsv = pzs_rgb2hsv(c);
    return pzs_hsv2rgb(vec3<f32>(fract(hsv.x + shift), hsv.y, hsv.z));
}
""", "pzs_rgb2hsv", "pzs_hsv2rgb")

_add("pzs_luminance", """
fn pzs_luminance(c: vec3<f32>) -> f32 {
    return dot(c, vec3<f32>(0.2126, 0.7152, 0.0722));
}
""")

_add("pzs_saturate_color", """
fn pzs_saturate_color(c: vec3<f32>, amount: f32) -> vec3<f32> {
    return mix(vec3<f32>(pzs_luminance(c)), c, amount);
}
""", "pzs_luminance")

_add("pzs_palette", """
// Inigo Quilez's cosine palettes: a + b * cos(2 pi (c t + d)).
fn pzs_palette(t: f32, a: vec3<f32>, b: vec3<f32>, c: vec3<f32>, d: vec3<f32>) -> vec3<f32> {
    return a + b * cos(6.2831853 * (c * t + d));
}
""")

_BLENDS = {
    "normal": "b",
    "multiply": "a * b",
    "screen": "1.0 - (1.0 - a) * (1.0 - b)",
    "overlay": "select(1.0 - 2.0 * (1.0 - a) * (1.0 - b), 2.0 * a * b, a < vec3<f32>(0.5))",
    "add": "min(a + b, vec3<f32>(1.0))",
    "subtract": "max(a - b, vec3<f32>(0.0))",
    "difference": "abs(a - b)",
    "darken": "min(a, b)",
    "lighten": "max(a, b)",
    "soft_light": "select(sqrt(a) * (2.0 * b - 1.0) + 2.0 * a * (1.0 - b), 2.0 * a * b + a * a * (1.0 - 2.0 * b), "
                  "b < vec3<f32>(0.5))",
    "color_dodge": "min(a / max(1.0 - b, vec3<f32>(0.0001)), vec3<f32>(1.0))",
    "color_burn": "1.0 - min((1.0 - a) / max(b, vec3<f32>(0.0001)), vec3<f32>(1.0))",
}
#: The blend modes of the Blend node.
BLEND_MODES = tuple(_BLENDS)

for _mode, _expr in _BLENDS.items():
    _add(f"pzs_blend_{_mode}", f"""
fn pzs_blend_{_mode}(a: vec3<f32>, b: vec3<f32>, opacity: f32) -> vec3<f32> {{
    return mix(a, {_expr}, opacity);
}}
""")

# -- transforms ------------------------------------------------------------------

_add("pzs_rotate", """
fn pzs_rotate(p: vec2<f32>, center: vec2<f32>, angle: f32) -> vec2<f32> {
    let s = sin(angle);
    let c = cos(angle);
    let q = p - center;
    return vec2<f32>(c * q.x - s * q.y, s * q.x + c * q.y) + center;
}
""")

_add("pzs_twirl", """
fn pzs_twirl(uv: vec2<f32>, center: vec2<f32>, strength: f32) -> vec2<f32> {
    let d = uv - center;
    let angle = strength * length(d);
    let s = sin(angle);
    let c = cos(angle);
    return vec2<f32>(c * d.x - s * d.y, s * d.x + c * d.y) + center;
}
""")

_add("pzs_barrel", """
// Bends uv like an old curved screen (amount 0 leaves it flat).
fn pzs_barrel(uv: vec2<f32>, amount: f32) -> vec2<f32> {
    let c = uv - 0.5;
    return uv + c * dot(c, c) * amount;
}
""")

_add("pzs_kaleidoscope", """
fn pzs_kaleidoscope(uv: vec2<f32>, center: vec2<f32>, segments: f32) -> vec2<f32> {
    let p = uv - center;
    let slice = 6.2831853 / max(segments, 1.0);
    var a = atan2(p.y, p.x);
    a = abs(a - slice * floor(a / slice) - slice * 0.5);
    return vec2<f32>(cos(a), sin(a)) * length(p) + center;
}
""")

# -- patterns ---------------------------------------------------------------------

_add("pzs_wave", """
// A wave from 0 to 1: 0 sine, 1 triangle, 2 square, 3 sawtooth.
fn pzs_wave(x: f32, shape: i32) -> f32 {
    let t = fract(x);
    switch shape {
        case 1: {
            return 1.0 - abs(t * 2.0 - 1.0);
        }
        case 2: {
            return step(0.5, t);
        }
        case 3: {
            return t;
        }
        default: {
            return 0.5 + 0.5 * sin(x * 6.2831853);
        }
    }
}
""")

# -- signed distances (negative inside) --------------------------------------------

_add("pzs_sd_box", """
fn pzs_sd_box(p: vec2<f32>, half_size: vec2<f32>, radius: f32) -> f32 {
    let r = min(radius, min(half_size.x, half_size.y));
    let q = abs(p) - half_size + r;
    return length(max(q, vec2<f32>(0.0))) + min(max(q.x, q.y), 0.0) - r;
}
""")

_add("pzs_sd_segment", """
fn pzs_sd_segment(p: vec2<f32>, a: vec2<f32>, b: vec2<f32>) -> f32 {
    let pa = p - a;
    let ba = b - a;
    let h = clamp(dot(pa, ba) / max(dot(ba, ba), 0.000001), 0.0, 1.0);
    return length(pa - ba * h);
}
""")

_add("pzs_sd_polygon", """
// A regular polygon with ``sides`` sides whose corners are ``radius`` from the center.
fn pzs_sd_polygon(p: vec2<f32>, radius: f32, sides: f32) -> f32 {
    let n = max(sides, 3.0);
    let slice = 6.2831853 / n;
    let a = atan2(p.x, p.y);
    let b = slice * floor(a / slice + 0.5);
    let q = vec2<f32>(cos(b) * p.y + sin(b) * p.x, -sin(b) * p.y + cos(b) * p.x);
    return q.x - radius * cos(slice * 0.5);
}
""")

_add("pzs_sd_star", """
fn pzs_sd_star(p: vec2<f32>, radius: f32, points: f32, inner: f32) -> f32 {
    let n = max(points, 2.0);
    let slice = 3.14159265 / n;
    let a = atan2(p.x, p.y);
    let b = abs(a - 2.0 * slice * floor(a / (2.0 * slice) + 0.5));
    let q = length(p) * vec2<f32>(cos(b), sin(b));
    let tip = vec2<f32>(radius, 0.0);
    let valley = radius * inner * vec2<f32>(cos(slice), sin(slice));
    let e = valley - tip;
    let w = q - tip;
    let h = clamp(dot(w, e) / dot(e, e), 0.0, 1.0);
    let d = length(w - e * h);
    let s = e.x * w.y - e.y * w.x;
    return select(d, -d, s > 0.0);
}
""")

_add("pzs_smin", """
// A union of two distances that melts them together over ``k``.
fn pzs_smin(a: f32, b: f32, k: f32) -> f32 {
    if (k <= 0.0) {
        return min(a, b);
    }
    let h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}
""")

_add("pzs_smax", """
fn pzs_smax(a: f32, b: f32, k: f32) -> f32 {
    return -pzs_smin(-a, -b, k);
}
""", "pzs_smin")


_add("pzs_sdf_preview", """
// How a node preview shows a signed distance: white inside, rings of blue outside.
fn pzs_sdf_preview(d: f32, size: vec2<f32>) -> vec4<f32> {
    let w = 1.5 / max(size.y, 1.0);
    let inside = 1.0 - smoothstep(-w, w, d);
    let rings = 0.8 + 0.2 * cos(d * 90.0);
    let outside = vec3<f32>(0.25, 0.45, 0.85) * (1.0 - exp(-5.0 * abs(d))) * rings;
    return vec4<f32>(mix(outside, vec3<f32>(1.0), inside), 1.0);
}
""")


def closure(names: Iterable[str]) -> List[str]:
    """``names`` and every function they call, each one after what it calls."""
    out: List[str] = []
    seen = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        for dep in FUNCTIONS[name][1]:
            visit(dep)
        out.append(name)

    for name in names:
        visit(name)
    return out


def code(names: Iterable[str]) -> str:
    """The WGSL of ``names`` and what they call."""
    return "\n".join(FUNCTIONS[n][0] for n in closure(names))
