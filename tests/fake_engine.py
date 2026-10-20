"""A stand-in for ``pyzed.audio.Engine`` with the same graph API (no sound), for the rack's tests."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Port:
    name: str
    label: str = ""
    type: str = "audio"


@dataclass
class Param:
    name: str
    label: str = ""
    min: float = 0.0
    max: float = 1.0
    default: float = 0.5
    unit: str = ""
    curve: str = "lin"
    steps: Optional[int] = None
    options: Optional[List[str]] = None


@dataclass
class ModuleInfo:
    kind: str
    label: str
    category: str
    description: str = ""
    inputs: List[Port] = field(default_factory=list)
    outputs: List[Port] = field(default_factory=list)
    params: List[Param] = field(default_factory=list)


CATALOG = [
    ModuleInfo("oscillator", "VCO", "Sources",
               inputs=[Port("pitch"), Port("fm"), Port("pwm"), Port("sync")],
               outputs=[Port("sine"), Port("triangle"), Port("saw"), Port("square")],
               params=[Param("frequency", "Freq", 20, 20000, 261.6, "Hz", "log"), Param("fine", "Fine", -1, 1, 0),
                       Param("pw", "PW", 0.05, 0.95, 0.5), Param("fm_amount", "FM", 0, 1, 0)]),
    ModuleInfo("filter", "VCF", "Filters", inputs=[Port("in"), Port("cutoff"), Port("resonance")],
               outputs=[Port("lowpass"), Port("bandpass"), Port("highpass")],
               params=[Param("cutoff", "Cutoff", 20, 20000, 1200, "Hz", "log"), Param("resonance", "Res", 0, 1, 0.2),
                       Param("mode", "Mode", 0, 2, 0, options=["LP", "BP", "HP"])]),
    ModuleInfo("adsr", "ADSR", "Envelopes", inputs=[Port("gate"), Port("retrig")], outputs=[Port("out")],
               params=[Param("attack", "A", 0.001, 4, 0.01, "s", "log"), Param("decay", "D", 0.001, 4, 0.2, "s", "log"),
                       Param("sustain", "S", 0, 1, 0.6), Param("release", "R", 0.001, 8, 0.4, "s", "log")]),
    ModuleInfo("sequencer", "SEQ-16", "Sequencers", inputs=[Port("clock"), Port("reset")],
               outputs=[Port("pitch"), Port("gate"), Port("trigger")],
               params=[Param("bpm", "BPM", 30, 300, 120), Param("steps", "Steps", 1, 16, 16, steps=16),
                       Param("gate_length", "Gate", 0.05, 1, 0.5)]),
    ModuleInfo("delay", "Delay", "Effects", inputs=[Port("in"), Port("time")], outputs=[Port("out")],
               params=[Param("time", "Time", 0.01, 2, 0.35, "s"), Param("feedback", "Fdbk", 0, 0.95, 0.4),
                       Param("mix", "Mix", 0, 1, 0.3)]),
    ModuleInfo("scope", "Scope", "Visual", inputs=[Port("in"), Port("in_2")], outputs=[],
               params=[Param("time", "Time", 0.001, 0.1, 0.01, "s", "log"), Param("gain", "Gain", 0.1, 10, 1)]),
    ModuleInfo("audio_out", "Audio Out", "I/O", inputs=[Port("left"), Port("right")],
               params=[Param("volume", "Volume", 0, 1, 0.8)]),
]


class Node:
    def __init__(self, id: str, kind: str, params: Dict[str, float]) -> None:
        self.id, self.kind, self.params = id, kind, params
        self.state: Dict[str, Any] = {"step": 0}
        self.t = 0.0

    def scope(self, n: int = 1024) -> List[float]:
        return [math.sin((i + self.t) / 9) * 0.7 for i in range(n)]

    def spectrum(self, bins: int = 256) -> List[float]:
        return [-30 - 40 * i / bins for i in range(bins)]

    def level(self) -> Tuple[float, float]:
        return 0.4, 0.6

    def probe(self, port: str) -> float:
        return 0.5


class FakeEngine:
    def __init__(self) -> None:
        self.nodes: List[Node] = []
        self.cables: List[Tuple[str, str, str, str]] = []
        self.log: List[tuple] = []

    def add(self, kind: str, id: Optional[str] = None, **params: float) -> Node:
        info = next(m for m in CATALOG if m.kind == kind)
        id = id or f"{kind}{sum(n.kind == kind for n in self.nodes) + 1}"
        values = {p.name: p.default for p in info.params}
        values.update(params)
        node = Node(id, kind, values)
        self.nodes.append(node)
        return node

    def node(self, id: str) -> Node:
        return next(n for n in self.nodes if n.id == id)

    def remove(self, id: str) -> None:
        self.nodes = [n for n in self.nodes if n.id != id]
        self.cables = [c for c in self.cables if id not in (c[0], c[2])]

    def connect(self, src: str, out: str, dst: str, inp: str) -> None:
        self.cables.append((src, out, dst, inp))
        self.log.append(("connect", src, out, dst, inp))

    def disconnect(self, src: str, out: str, dst: str, inp: str) -> None:
        self.cables.remove((src, out, dst, inp))
        self.log.append(("disconnect", src, out, dst, inp))

    def set(self, id: str, param: str, value: float) -> None:
        self.node(id).params[param] = value

    def to_dict(self) -> Dict[str, Any]:
        return {"nodes": [{"id": n.id, "kind": n.kind, "params": dict(n.params)} for n in self.nodes],
                "cables": [list(c) for c in self.cables]}

    def load(self, data: Dict[str, Any]) -> None:
        self.nodes, self.cables = [], []
        for n in data["nodes"]:
            self.add(n["kind"], n["id"], **n["params"])
        self.cables = [tuple(c) for c in data["cables"]]
