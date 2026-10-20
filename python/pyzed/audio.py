"""The audio engine: build synthesizers, effects and sequencers from modules joined by cables,
like VCV Rack, and play them on the sound card with low latency, or render them to a file.

    from pyzed import audio

    engine = audio.Engine()
    osc = engine.add("oscillator", freq=220, wave="saw")
    lpf = engine.add("filter", cutoff=800, resonance=0.5)
    out = engine.add("audio_out")
    engine.chain(osc, lpf, out)
    engine.start()

The signal processing runs in Rust on a real-time thread; Python only describes the patch and
turns the knobs, so the sound never waits for Python. Nothing here needs a window: the engine
works the same in a script, a server or behind a ``pz.App`` (the components of ``pz.ui.audio``
and the rack of ``pz.ui.rack`` draw it).

Signals follow the conventions of modular synthesizers: every cable carries one signal at audio
rate; audio swings between -1 and 1, pitch is in volts per octave (0 = middle C, C4) and gates
are 0 or 1.
"""

from __future__ import annotations

import array
import functools
import glob
import os
import sys
import threading
import wave
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import _core

__all__ = [
    "Device",
    "Engine",
    "ModuleInfo",
    "Node",
    "Param",
    "Port",
    "default_host",
    "devices",
    "hosts",
    "midi_inputs",
    "midi_outputs",
    "module",
    "modules",
    "note_name",
    "note_number",
    "recommended_settings",
    "volts",
]

# ---------------------------------------------------------------------------------------------
# The catalog


@dataclass(frozen=True)
class Port:
    """An input or output of a module. ``type`` says how to read its signal: ``"audio"``,
    ``"cv"`` (pitch in V/oct or an amount), ``"gate"`` (0 or 1) or ``"midi"``."""

    name: str
    label: str
    type: str = "audio"


@dataclass(frozen=True)
class Param:
    """A knob of a module. A choice (``options``) takes the index of an option, or its name."""

    name: str
    label: str
    min: float
    max: float
    default: float
    unit: str = ""
    curve: str = "lin"
    steps: int | None = None
    options: tuple[str, ...] | None = None

    def to_unit(self, value: float) -> float:
        """Where ``value`` sits on the knob, from 0 to 1 (logarithmic knobs turn by octaves)."""
        value = min(max(float(value), self.min), self.max)
        if self.curve == "log" and self.min > 0:
            import math

            return math.log(value / self.min) / math.log(self.max / self.min)
        span = self.max - self.min
        return (value - self.min) / span if span else 0.0

    def from_unit(self, t: float) -> float:
        """The value at position ``t`` (0..1) of the knob: the inverse of :meth:`to_unit`."""
        t = min(max(float(t), 0.0), 1.0)
        if self.curve == "log" and self.min > 0:
            value = self.min * (self.max / self.min) ** t
        else:
            value = self.min + (self.max - self.min) * t
        return round(value) if self.steps else value

    def format(self, value: float) -> str:
        """The value as a knob would label it: ``"1.2 kHz"``, ``"saw"``, ``"350 ms"``."""
        if self.options:
            return self.options[int(round(value)) % len(self.options)]
        unit = self.unit
        if unit == "Hz" and abs(value) >= 1000:
            return f"{value / 1000:.2f} kHz"
        if unit == "s" and abs(value) < 1:
            return f"{value * 1000:.0f} ms"
        text = f"{value:.0f}" if self.steps or abs(value) >= 100 else f"{value:.2f}"
        return f"{text} {unit}".strip()


@dataclass(frozen=True)
class ModuleInfo:
    """What a kind of module is: its ports, knobs and the ``state`` it reports while playing."""

    kind: str
    label: str
    category: str
    description: str
    inputs: tuple[Port, ...] = ()
    outputs: tuple[Port, ...] = ()
    params: tuple[Param, ...] = ()
    state: tuple[str, ...] = ()

    def param(self, name: str) -> Param:
        for p in self.params:
            if p.name == name:
                return p
        raise KeyError(f"{self.kind} has no parameter {name!r}")


@functools.cache
def _catalog() -> dict[str, ModuleInfo]:
    def ports(items: list[dict]) -> tuple[Port, ...]:
        return tuple(Port(p["name"], p["label"], p["type"]) for p in items)

    catalog = {}
    for m in _core.audio_modules():
        params = tuple(
            Param(
                p["name"],
                p["label"],
                p["min"],
                p["max"],
                p["default"],
                p["unit"],
                p["curve"],
                p["steps"],
                tuple(p["options"]) if p["options"] else None,
            )
            for p in m["params"]
        )
        catalog[m["kind"]] = ModuleInfo(
            m["kind"],
            m["label"],
            m["category"],
            " ".join(m["description"].split()),
            ports(m["inputs"]),
            ports(m["outputs"]),
            params,
            tuple(m["state"]),
        )
    return catalog


def modules() -> list[ModuleInfo]:
    """Every kind of module, in the order of the catalog (sources, modulation, effects, I/O...)."""
    return list(_catalog().values())


def module(kind: str) -> ModuleInfo:
    """The description of one kind of module."""
    try:
        return _catalog()[kind]
    except KeyError:
        raise ValueError(f"unknown module {kind!r}; the modules are {', '.join(_catalog())}") from None


# ---------------------------------------------------------------------------------------------
# Devices and settings


@dataclass(frozen=True)
class Device:
    """An audio device: ``inputs``/``outputs`` count its channels (0 = it does not record/play)."""

    name: str
    id: str
    host: str
    inputs: int
    outputs: int
    sample_rate: int | None
    buffer_range: tuple[int, int] | None
    default_input: bool
    default_output: bool


def hosts() -> list[str]:
    """The audio systems Pyzed can use here, such as ``["WASAPI"]``, ``["CoreAudio"]`` or
    ``["PulseAudio", "ALSA"]`` (PulseAudio also reaches PipeWire)."""
    return list(_core.audio_hosts()[0])


def default_host() -> str:
    """The audio system Pyzed uses unless told otherwise."""
    return _core.audio_hosts()[1]


def devices(host: str | None = None) -> list[Device]:
    """The audio devices of ``host`` (the default one if ``None``)."""
    _prepare_alsa()
    return [Device(**d) for d in _core.audio_devices(host)]


def recommended_settings(host: str | None = None) -> dict[str, Any]:
    """The settings ``Engine`` uses when given none: the system's audio host, its default device
    and the smallest buffer that plays without dropouts on a typical machine (128 frames on
    CoreAudio and ASIO, 256 elsewhere; JACK picks its own)."""
    host = host or default_host()
    return {"host": host, "buffer_size": _core.audio_recommended_buffer(host)}


def midi_inputs() -> list[str]:
    """The MIDI ports that send notes in (keyboards, pads, controllers)."""
    return list(_core.midi_ports()[0])


def midi_outputs() -> list[str]:
    """The MIDI ports Pyzed can play on (synthesizers, DAWs)."""
    return list(_core.midi_ports()[1])


@functools.cache
def _prepare_alsa() -> None:
    """Wheels for Linux carry their own copy of ALSA's library, which looks for its plugins
    (PipeWire's and PulseAudio's among them) where the distribution that built it keeps them.
    Point it at this system's plugins instead."""
    if not sys.platform.startswith("linux") or "ALSA_PLUGIN_DIR" in os.environ:
        return
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not glob.glob(os.path.join(here, "*.libs", "libasound*")):
        return
    multiarch = getattr(sys.implementation, "_multiarch", "")
    candidates = [f"/usr/lib/{multiarch}/alsa-lib"] if multiarch else []
    candidates += ["/usr/lib64/alsa-lib", "/usr/lib/alsa-lib", "/usr/lib/x86_64-linux-gnu/alsa-lib",
                   "/usr/lib/aarch64-linux-gnu/alsa-lib"]
    for path in candidates:
        if os.path.isdir(path):
            os.environ["ALSA_PLUGIN_DIR"] = path
            return


# ---------------------------------------------------------------------------------------------
# Notes

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_number(name: str | int) -> int:
    """The MIDI number of a note name: ``"C4"`` → 60, ``"A4"`` → 69, ``"F#2"`` → 42."""
    if isinstance(name, int):
        return name
    text = name.strip().upper().replace("♯", "#").replace("♭", "B")
    letter, rest = text[0], text[1:]
    semitone = _NAMES.index(letter)
    while rest and rest[0] in "#B" and not rest[0].isdigit():
        if rest[0] == "#":
            semitone += 1
        elif rest[0] == "B":
            semitone -= 1
        rest = rest[1:]
    octave = int(rest) if rest else 4
    return (octave + 1) * 12 + semitone


def note_name(number: int) -> str:
    """The name of a MIDI note: 60 → ``"C4"``."""
    return f"{_NAMES[number % 12]}{number // 12 - 1}"


def volts(note: str | int) -> float:
    """The pitch of a note in V/oct, the unit of the ``pitch`` inputs: ``"C4"`` → 0.0,
    ``"C5"`` → 1.0, ``"A4"`` → 0.75."""
    return (note_number(note) - 60) / 12


# ---------------------------------------------------------------------------------------------
# Engine and nodes


class Node:
    """A module in a patch. Read and turn its knobs like a dictionary (``node["cutoff"] = 800``);
    read what it plays with :meth:`scope`, :meth:`spectrum` and :meth:`level`."""

    __slots__ = ("_engine", "_slot", "id", "kind", "ui", "_sample")

    def __init__(self, engine: Engine, slot: int, id: str, kind: str):
        self._engine = engine
        self._slot = slot
        self.id = id
        self.kind = kind
        self.ui: Any = None
        self._sample: str | None = None

    def __repr__(self) -> str:
        return f"<audio.Node {self.id!r} ({self.kind})>"

    @property
    def info(self) -> ModuleInfo:
        return module(self.kind)

    @property
    def params(self) -> dict[str, float]:
        """Every knob and its value."""
        return dict(self._engine._native.params(self._slot))

    def __getitem__(self, param: str) -> float:
        return self._engine._native.get(self._slot, param)

    def __setitem__(self, param: str, value: float | str) -> None:
        self._engine.set(self, param, value)

    def set(self, **params: float | str) -> Node:
        """Turns several knobs at once; returns the node."""
        for name, value in params.items():
            self._engine.set(self, name, value)
        return self

    def connect(self, output: str, other: Node | str, input: str) -> Node:
        """Plugs ``output`` of this module into ``input`` of ``other``; returns ``other``."""
        self._engine.connect(self, output, other, input)
        return self._engine.node(other)

    def trigger(self) -> None:
        """Strikes a drum, starts a sampler or runs an envelope once, as a gate would."""
        self._engine._native.trigger(self._slot)

    def load(self, source: str | os.PathLike | Sequence[float] | Sequence[Sequence[float]],
             sample_rate: float | None = None) -> None:
        """Gives a sampler its sound: a WAV file, a list of samples or one list per channel."""
        if isinstance(source, (str, os.PathLike)):
            self._engine._native.load_wav(self._slot, os.fspath(source))
            self._sample = os.fspath(source)
            return
        data = list(source)
        channels = [list(map(float, c)) for c in data] if data and isinstance(data[0], Iterable) else [
            [float(x) for x in data]]
        self._engine._native.load_sample(self._slot, channels, float(sample_rate or self._engine.sample_rate))
        self._sample = None

    def scope(self, n: int = 1024) -> list[float]:
        """The last ``n`` samples of the module's signal, oldest first (for a waveform view)."""
        return self._engine._native.scope(self._slot, n)

    def spectrum(self, bins: int = 256, size: int = 2048, log: bool = True) -> list[float]:
        """The spectrum of the module's signal: ``bins`` bands in decibels (-120..0), spread
        over octaves from 20 Hz (``log=False``: evenly over hertz) to half the sample rate."""
        return self._engine._native.spectrum(self._slot, bins, size, log)

    def level(self) -> tuple[float, float]:
        """``(rms, peak)`` of the module's signal: what a VU meter shows."""
        return self._engine._native.level(self._slot)

    def probe(self, port: str) -> float:
        """The latest value of an output (a cable can glow with its signal)."""
        return self._engine._native.probe(self._slot, port)

    @property
    def state(self) -> dict[str, float]:
        """What the module reports while it plays, such as the step of a sequencer."""
        return dict(self._engine._native.state(self._slot))

    def remove(self) -> None:
        self._engine.remove(self)


class Engine:
    """A patch of modules and the audio device it plays on.

    ``backend`` is ``"auto"`` (the sound card, or silence if there is none), ``"device"`` (the
    sound card or an error), ``"null"`` (a clock with no sound) or ``"offline"`` (never plays:
    only :meth:`render`). ``None`` settings take the system's best: see
    :func:`recommended_settings`. Use the engine as a context manager to play while inside it.
    """

    def __init__(
        self,
        backend: str = "auto",
        *,
        sample_rate: int | None = None,
        buffer_size: int | None = None,
        device: str | None = None,
        input_device: str | None = None,
        input: bool = False,
        host: str | None = None,
    ):
        if backend not in ("auto", "device", "null", "offline"):
            raise ValueError('backend must be "auto", "device", "null" or "offline"')
        self.backend = backend
        self.settings = {
            "host": host,
            "device": device,
            "input": input,
            "input_device": input_device,
            "sample_rate": sample_rate,
            "buffer_size": buffer_size,
        }
        self._native = _core.AudioEngine(float(sample_rate or 48000))
        self._nodes: dict[str, Node] = {}
        self._by_slot: dict[int, Node] = {}
        self._timers: set[threading.Timer] = set()
        self.ui: Any = None

    def __repr__(self) -> str:
        return f"<audio.Engine {len(self._nodes)} modules, {self.info['backend']}>"

    def __enter__(self) -> Engine:
        if self.backend != "offline":
            self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    # Playing

    def start(self, **settings: Any) -> dict[str, Any]:
        """Starts playing (``settings`` override those given to the engine) and returns
        :attr:`info`."""
        if self.backend == "offline":
            raise RuntimeError('an offline engine does not play: use render(), or backend="auto"')
        self.settings.update(settings)
        _prepare_alsa()
        return dict(self._native.start(self.backend, **self.settings))

    def stop(self) -> None:
        for timer in list(self._timers):
            timer.cancel()
        self._timers.clear()
        self._native.stop()

    @property
    def running(self) -> bool:
        return bool(self._native.info()["running"])

    @property
    def info(self) -> dict[str, Any]:
        """What plays and how: ``backend``, ``host``, ``device``, ``sample_rate``,
        ``buffer_size``, ``latency_ms`` (until the sound leaves the speakers), ``load`` (the
        share of each buffer spent computing it), ``underruns``, ``error`` and ``time``."""
        return dict(self._native.info())

    @property
    def sample_rate(self) -> int:
        return int(self._native.info()["sample_rate"])

    def render(self, seconds: float | None = None, *, frames: int | None = None) -> tuple[list[float], list[float]]:
        """Computes the patch without a device, faster than real time. Returns ``(left, right)``."""
        if frames is None:
            frames = int(round((seconds or 1.0) * self.sample_rate))
        return self._native.render(int(frames))

    def render_wav(self, path: str | os.PathLike, seconds: float) -> str:
        """Renders ``seconds`` of the patch into a 16-bit stereo WAV file; returns its path."""
        left, right = self.render(seconds)
        pcm = array.array("h", bytes(len(left) * 4))
        for i, (l, r) in enumerate(zip(left, right)):
            pcm[2 * i] = int(max(-1.0, min(1.0, l)) * 32767)
            pcm[2 * i + 1] = int(max(-1.0, min(1.0, r)) * 32767)
        if sys.byteorder == "big":
            pcm.byteswap()
        with wave.open(os.fspath(path), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(self.sample_rate)
            f.writeframes(pcm.tobytes())
        return os.fspath(path)

    # The patch

    def add(self, kind: str, id: str | None = None, **params: float | str) -> Node:
        """Adds a module of ``kind`` (see :func:`modules`) with some knobs set."""
        info = module(kind)
        if id is None:
            n = 1
            while f"{kind}{n}" in self._nodes:
                n += 1
            id = f"{kind}{n}"
        elif id in self._nodes:
            raise ValueError(f"there is already a module {id!r}")
        values = {name: _value(info, name, v) for name, v in params.items()}
        slot = self._native.add(kind, values)
        node = Node(self, slot, id, kind)
        self._nodes[id] = node
        self._by_slot[slot] = node
        return node

    def node(self, id: Node | str) -> Node:
        if isinstance(id, Node):
            if self._nodes.get(id.id) is not id:
                raise ValueError(f"{id!r} is not in this engine")
            return id
        try:
            return self._nodes[id]
        except KeyError:
            raise KeyError(f"no module {id!r}") from None

    @property
    def nodes(self) -> list[Node]:
        """The modules, in the order they were added."""
        return list(self._nodes.values())

    def remove(self, id: Node | str) -> None:
        node = self.node(id)
        self._native.remove(node._slot)
        del self._nodes[node.id]
        del self._by_slot[node._slot]

    def clear(self) -> None:
        """Removes every module."""
        for node in self.nodes:
            self.remove(node)
        self.ui = None

    def connect(self, src: Node | str, output: str, dst: Node | str, input: str) -> bool:
        """Plugs a cable from ``output`` of ``src`` into ``input`` of ``dst``. An input takes any
        number of cables (they add up) and loops are allowed (they go through one block of
        delay, as in a hardware rack). Returns False if that cable was already there."""
        return self._native.connect(self.node(src)._slot, output, self.node(dst)._slot, input)

    def disconnect(self, src: Node | str, output: str, dst: Node | str, input: str) -> bool:
        return self._native.disconnect(self.node(src)._slot, output, self.node(dst)._slot, input)

    @property
    def cables(self) -> list[tuple[str, str, str, str]]:
        """Every cable as ``(src, output, dst, input)``."""
        return [(self._by_slot[s].id, o, self._by_slot[d].id, i) for s, o, d, i in self._native.cables()]

    def chain(self, *nodes: Node | str) -> Node:
        """Connects each module's first output to the next one's first input (both sides of a
        stereo pair when both have ``left`` and ``right``). Returns the last module."""
        items = [self.node(n) for n in nodes]
        for a, b in zip(items, items[1:]):
            outs = [p.name for p in a.info.outputs]
            ins = [p.name for p in b.info.inputs]
            if not outs or not ins:
                raise ValueError(f"{a.id} has no output or {b.id} has no input to chain")
            if {"left", "right"} <= set(outs) and {"left", "right"} <= set(ins):
                self.connect(a, "left", b, "left")
                self.connect(a, "right", b, "right")
            else:
                self.connect(a, outs[0], b, ins[0])
        return items[-1]

    def set(self, id: Node | str, param: str, value: float | str) -> float:
        """Turns a knob (clamped to its range) and returns the value it took."""
        node = self.node(id)
        return self._native.set(node._slot, param, _value(node.info, param, value))

    def get(self, id: Node | str, param: str) -> float:
        return self._native.get(self.node(id)._slot, param)

    # Watching

    def scope(self, n: int = 1024) -> list[float]:
        """The last ``n`` samples sent to the speakers (left and right mixed)."""
        return self._native.scope(None, n)

    def spectrum(self, bins: int = 256, size: int = 2048, log: bool = True) -> list[float]:
        """The spectrum of what goes to the speakers, in decibels."""
        return self._native.spectrum(None, bins, size, log)

    def level(self) -> tuple[float, float]:
        """``(rms, peak)`` of what goes to the speakers."""
        return self._native.level(None)

    # MIDI

    def note_on(self, note: int | str, velocity: int = 100, channel: int = 1) -> None:
        """Plays a note on the ``midi_in`` modules, as a keyboard would (``note`` is a MIDI
        number or a name like ``"C4"``)."""
        self._native.midi(0x90 | (channel - 1) & 0x0F, note_number(note), int(velocity))

    def note_off(self, note: int | str, channel: int = 1) -> None:
        self._native.midi(0x80 | (channel - 1) & 0x0F, note_number(note), 0)

    def note(self, note: int | str, duration: float = 0.25, velocity: int = 100, channel: int = 1) -> None:
        """Plays a note for ``duration`` seconds (the release happens on a timer thread)."""
        self.note_on(note, velocity, channel)
        timer = threading.Timer(duration, self._release, (note, channel))
        timer.daemon = True
        self._timers.add(timer)
        timer.start()

    def _release(self, note: int | str, channel: int) -> None:
        self._timers.difference_update({t for t in self._timers if not t.is_alive()})
        self.note_off(note, channel)

    def cc(self, number: int, value: int, channel: int = 1) -> None:
        """Sends a controller change (``number`` 1 is the mod wheel)."""
        self._native.midi(0xB0 | (channel - 1) & 0x0F, int(number), int(value))

    def pitch_bend(self, amount: float, channel: int = 1) -> None:
        """Bends the pitch, from -1 (down) to 1 (up) by the ``bend_range`` of ``midi_in``."""
        value = int(round((max(-1.0, min(1.0, amount)) + 1) * 8191.5))
        value = min(value, 16383)
        self._native.midi(0xE0 | (channel - 1) & 0x0F, value & 0x7F, value >> 7)

    def all_notes_off(self, channel: int = 1) -> None:
        self._native.midi(0xB0 | (channel - 1) & 0x0F, 123, 0)

    def open_midi_input(self, name: str | None = None, *, virtual: str | None = None) -> str:
        """Listens to a MIDI keyboard: the first port whose name contains ``name`` (or the first
        of all). ``virtual="Pyzed"`` instead creates a port other programs play into (Linux and
        macOS). Returns the port's name."""
        return self._native.open_midi_input(name, virtual)

    def close_midi_inputs(self) -> None:
        self._native.close_midi_inputs()

    def open_midi_output(self, name: str | None = None, *, virtual: str | None = None) -> str:
        """Opens the MIDI output the ``midi_out`` modules play on (or a virtual one)."""
        return self._native.open_midi_output(name, virtual)

    def close_midi_output(self) -> None:
        self._native.close_midi_output()

    def send_midi(self, message: Sequence[int] | bytes) -> None:
        """Sends raw MIDI bytes to the open output."""
        self._native.send_midi(list(message))

    # Saving

    def to_dict(self) -> dict[str, Any]:
        """The patch as plain data (JSON-ready): its modules with their knobs and its cables.
        The ``ui`` of the engine and of each node (where an interface keeps positions and
        colors) travel with it untouched."""
        nodes = []
        for node in self.nodes:
            entry: dict[str, Any] = {"id": node.id, "kind": node.kind, "params": node.params}
            if node._sample:
                entry["sample"] = node._sample
            if node.ui is not None:
                entry["ui"] = node.ui
            nodes.append(entry)
        data: dict[str, Any] = {"version": 1, "nodes": nodes, "cables": [list(c) for c in self.cables]}
        if self.ui is not None:
            data["ui"] = self.ui
        return data

    def load(self, data: dict[str, Any]) -> Engine:
        """Replaces the patch with one saved by :meth:`to_dict`."""
        self.clear()
        for entry in data.get("nodes", []):
            info = module(entry["kind"])
            known = {p.name for p in info.params}
            params = {k: v for k, v in entry.get("params", {}).items() if k in known}
            node = self.add(entry["kind"], entry["id"], **params)
            node.ui = entry.get("ui")
            if entry.get("sample"):
                try:
                    node.load(entry["sample"])
                except (OSError, ValueError):
                    pass
        for src, output, dst, input in data.get("cables", []):
            self.connect(src, output, dst, input)
        self.ui = data.get("ui")
        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any], backend: str = "auto", **settings: Any) -> Engine:
        """A new engine with the patch of :meth:`to_dict`."""
        return cls(backend, **settings).load(data)


def _value(info: ModuleInfo, name: str, value: float | str) -> float:
    """A knob's value from a number, a bool or the name of an option."""
    if isinstance(value, str):
        param = info.param(name)
        if not param.options or value not in param.options:
            choices = ", ".join(param.options or ())
            raise ValueError(f"{info.kind}.{name} takes {choices or 'a number'}, not {value!r}")
        return float(param.options.index(value))
    return float(value)


_ = field  # dataclasses.field is re-exported for subclasses of the catalog types
