"""Generates the catalog of audio modules (docs/src/content/docs/[es/]audio/engine/modules.md) from the
engine itself, so ports, ranges and defaults always match the code.

    python docs/scripts/gen_audio_modules.py            # writes both languages
    python docs/scripts/gen_audio_modules.py --check    # fails if a page is out of date

English comes from the catalog (``audio.modules()``); the Spanish texts live in ``ES`` below and the
check fails when a module has no translation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pyzed import audio

DOCS = Path(__file__).resolve().parents[1] / "src" / "content" / "docs"

CATEGORIES = {
    "Sources": "Fuentes",
    "Modulation": "Modulación",
    "Filters": "Filtros",
    "Mixing": "Mezcla",
    "Effects": "Efectos",
    "Sequencing": "Secuenciación",
    "Utilities": "Utilidades",
    "I/O": "Entrada y salida",
}
ORDER = list(CATEGORIES)

# Spanish: the label and description of each module.
ES = {
    "oscillator": ("Oscilador", "Un VCO sin aliasing: seno, triángulo, sierra y cuadrada (con ancho de pulso), "
                   "afinado por `freq` más la entrada `pitch` en V/oct."),
    "lfo": ("LFO", "Un oscilador lento para mover otros parámetros: seno, triángulo, sierra, cuadrada o pasos "
            "aleatorios (sample and hold)."),
    "noise": ("Ruido", "Ruido blanco, rosa o marrón."),
    "sampler": ("Sampler", "Reproduce un archivo WAV o una lista de muestras (`node.load`) cuando se abre su "
                "puerta: una vez, mientras se mantiene o en bucle."),
    "drum": ("Batería", "Una voz de batería sintetizada (bombo, caja, charles, palmada o tom) que suena con "
             "cada flanco de subida de `trigger`."),
    "audio_in": ("Entrada de audio", "El sonido del dispositivo de entrada (un micrófono o una línea), "
                 "abierto con `Engine(input_device=...)` o `input=True`."),
    "midi_in": ("MIDI a CV", "Convierte las notas de un teclado MIDI (o de `engine.note_on`) en altura, puerta "
                "y velocidad, tocando la última nota pulsada."),
    "constant": ("Constante", "Un voltaje fijo, para mover una entrada desde un knob."),
    "clock": ("Reloj", "El tempo de un patch: puertas en la subdivisión elegida del pulso, en cada pulso y en "
              "cada compás."),
    "filter": ("Filtro", "Un filtro de estado variable resonante (VCF) con paso bajo, paso alto, paso banda y "
               "notch; `cutoff` recibe V/oct, así que una envolvente o un LFO lo barren."),
    "vca": ("VCA", "Un amplificador cuya ganancia sigue a `cv` (una envolvente o un LFO); sin nada en `cv` es "
            "un volumen normal."),
    "adsr": ("Envolvente", "Una envolvente ADSR: sube cuando se abre la puerta, se queda en sustain y se "
             "apaga cuando se cierra."),
    "mixer": ("Mezclador", "Cuatro canales con nivel y panorama hacia un par estéreo."),
    "delay": ("Delay", "Un eco con realimentación y un control de tono en las repeticiones."),
    "reverb": ("Reverb", "Una sala estéreo (Freeverb): tamaño, amortiguación y anchura."),
    "distortion": ("Distorsión", "Satura la señal con un recorte suave o duro, un wavefolder o un fuzz."),
    "chorus": ("Chorus", "Un chorus estéreo; con realimentación y un retardo corto se vuelve un flanger."),
    "bitcrusher": ("Bitcrusher", "Lo-fi: menos bits y una frecuencia de muestreo más baja."),
    "compressor": ("Compresor", "Iguala el nivel; una señal en `sidechain` atenúa la entrada (el «bombeo» de "
                   "la música de baile)."),
    "sequencer": ("Secuenciador", "Hasta 16 pasos de altura y puerta, avanzados por `clock` (o por su propio "
                  "`bpm` en semicorcheas si `clock` no tiene cable)."),
    "scope": ("Osciloscopio", "Deja pasar su entrada sin tocarla, para ver una señal en cualquier punto del "
              "patch."),
    "audio_out": ("Salida de audio", "Los altavoces. Sin nada en `right`, `left` suena por los dos lados."),
    "midi_out": ("CV a MIDI", "Toca las notas de una puerta y una altura en una salida MIDI "
                 "(`engine.open_midi_output`)."),
}

WORDS = {
    "Out": "Salida", "In": "Entrada", "Left": "Izquierda", "Right": "Derecha", "Pitch (V/oct)": "Altura (V/oct)",
    "Sine": "Seno", "Triangle": "Triángulo", "Saw": "Sierra", "Square": "Cuadrada", "Sync": "Sync", "FM": "FM",
    "PWM": "PWM", "Rate": "Velocidad", "Reset": "Reinicio", "Unipolar": "Unipolar", "Gate": "Puerta",
    "Trigger": "Disparo", "Accent": "Acento", "Velocity": "Velocidad de nota", "Mod wheel": "Rueda de modulación",
    "Retrigger": "Redisparo", "Clock": "Reloj", "Beat": "Pulso", "Bar": "Compás", "Cutoff": "Corte",
    "Resonance": "Resonancia", "Low-pass": "Paso bajo", "Band-pass": "Paso banda", "High-pass": "Paso alto",
    "CV": "CV", "Inverted": "Invertida", "Time": "Tiempo", "Sidechain": "Sidechain", "Frequency": "Frecuencia",
    "Wave": "Onda", "Fine": "Ajuste fino", "Pulse width": "Ancho de pulso", "FM amount": "Cantidad de FM",
    "Level": "Nivel", "Amount": "Cantidad", "Offset": "Desplazamiento", "Color": "Color", "Mode": "Modo",
    "Tune": "Afinación", "Start": "Inicio", "End": "Fin", "Sound": "Sonido", "Decay": "Caída", "Tone": "Tono",
    "Gain": "Ganancia", "Channel": "Canal", "Glide": "Portamento", "Bend range": "Rango de pitch bend",
    "Value": "Valor", "Tempo": "Tempo", "Division": "Subdivisión", "Swing": "Swing", "Run": "En marcha",
    "CV amount": "Cantidad de CV", "Drive": "Saturación", "Response": "Respuesta", "Attack": "Ataque",
    "Sustain": "Sostenido", "Release": "Liberación", "Master": "Maestro", "Feedback": "Realimentación",
    "Mix": "Mezcla", "Size": "Tamaño", "Damping": "Amortiguación", "Width": "Anchura", "Type": "Tipo",
    "Depth": "Profundidad", "Delay": "Retardo", "Bits": "Bits", "Downsample": "Reducción", "Threshold": "Umbral",
    "Ratio": "Ratio", "Makeup": "Compensación", "Steps": "Pasos", "Gate length": "Duración de la puerta",
    "Volume": "Volumen", "Pan": "Panorama", "Pitch": "Altura",
}

TEXT = {
    "en": {
        "title": "Module catalog",
        "description": "Every module of the Pyzed audio engine: oscillators, filters, envelopes, LFOs, effects, "
                       "sequencers, drums, samplers and MIDI, with their ports, ranges and defaults.",
        "generated": "Generated by docs/scripts/gen_audio_modules.py from audio.modules().",
        "intro": "Every module the engine has, grouped as in a rack. Add one with `engine.add(kind, **params)` "
                 "and plug its ports with `engine.connect(src, output, dst, input)`. The same data is in "
                 "Python as [`audio.modules()`](/pyzed/audio/engine/getting-started/#the-catalog), which an "
                 "interface can use to draw any module. Signals follow the [conventions of modular "
                 "synthesizers](/pyzed/audio/engine/getting-started/#signals): audio swings between -1 and 1, "
                 "pitch is in V/oct (0 = C4) and gates are 0 or 1.",
        "inputs": "Inputs", "outputs": "Outputs", "params": "Parameters", "state": "State",
        "port": "Port", "type": "Type", "param": "Parameter", "range": "Range", "default": "Default",
        "options": "options", "log": "logarithmic", "none": "none",
    },
    "es": {
        "title": "Catálogo de módulos",
        "description": "Todos los módulos del motor de audio de Pyzed: osciladores, filtros, envolventes, LFO, "
                       "efectos, secuenciadores, batería, samplers y MIDI, con sus puertos, rangos y valores.",
        "generated": "Archivo generado por docs/scripts/gen_audio_modules.py a partir de audio.modules().",
        "intro": "Todos los módulos del motor, agrupados como en un rack. Añade uno con "
                 "`engine.add(kind, **params)` y conecta sus puertos con `engine.connect(src, output, dst, "
                 "input)`. Los mismos datos están en Python como "
                 "[`audio.modules()`](/pyzed/es/audio/engine/getting-started/#el-catálogo), que una interfaz "
                 "puede usar para dibujar cualquier módulo. Las señales siguen las [convenciones de los "
                 "sintetizadores modulares](/pyzed/es/audio/engine/getting-started/#señales): el audio va de -1 "
                 "a 1, la altura está en V/oct (0 = C4) y las puertas valen 0 o 1.",
        "inputs": "Entradas", "outputs": "Salidas", "params": "Parámetros", "state": "Estado",
        "port": "Puerto", "type": "Tipo", "param": "Parámetro", "range": "Rango", "default": "Por defecto",
        "options": "opciones", "log": "logarítmico", "none": "ninguna",
    },
}


def num(x: float) -> str:
    return f"{x:g}"


def label(text: str, lang: str) -> str:
    if lang == "en":
        return text
    m = re.match(r"^(.*?) (\d+)$", text)
    if m and m.group(1) in WORDS:
        return f"{WORDS[m.group(1)]} {m.group(2)}"
    return WORDS.get(text, text)


def ports_table(ports, t, lang) -> str:
    rows = [f"| `{p.name}` | {label(p.label, lang)} | {p.type} |" for p in ports]
    return f"| {t['port']} | | {t['type']} |\n| --- | --- | --- |\n" + "\n".join(rows)


def params_table(params, t, lang) -> list[str]:
    # The 16 steps of the sequencer read better as one row each for pitch and gate.
    rows = []
    for p in params:
        m = re.match(r"^(.*)_(\d+)$", p.name)
        if m and m.group(1) in ("pitch", "gate") and m.group(2) != "1":
            continue
        name, text = f"`{p.name}`", label(p.label, lang)
        if m and m.group(1) in ("pitch", "gate"):
            steps = [re.match(rf"^{m.group(1)}_(\d+)$", q.name) for q in params]
            last = max(int(s.group(1)) for s in steps if s)
            name = f"`{m.group(1)}_1` … `{m.group(1)}_{last}`"
            text = label(re.sub(r" \d+$", "", p.label), lang)
        if p.options:
            value_range = f"{t['options']}: " + ", ".join(f"`{o}`" for o in p.options)
            default = f"`{p.options[int(p.default)]}`"
        else:
            unit = f" {p.unit}" if p.unit else ""
            value_range = f"{num(p.min)} … {num(p.max)}{unit}" + (f" ({t['log']})" if p.curve == "log" else "")
            default = num(p.default)
        rows.append(f"| {name} | {text} | {value_range} | {default} |")
    head = f"| {t['param']} | | {t['range']} | {t['default']} |\n| --- | --- | --- | --- |"
    return [head, *rows]


def render(lang: str) -> str:
    t = TEXT[lang]
    out = [
        "---",
        f"title: {json.dumps(t['title'], ensure_ascii=False)}",
        f"description: {json.dumps(t['description'], ensure_ascii=False)}",
        "sidebar:",
        "  order: 2",
        "---",
        "",
        f"<!-- {t['generated']} -->",
        "",
        t["intro"],
        "",
    ]
    mods = sorted(audio.modules(), key=lambda m: ORDER.index(m.category))
    for category in ORDER:
        group = [m for m in mods if m.category == category]
        if not group:
            continue
        out.append(f"## {category if lang == 'en' else CATEGORIES[category]}\n")
        for m in group:
            title, description = (m.label, m.description) if lang == "en" else ES[m.kind]
            out.append(f"### {title} · `{m.kind}`\n")
            out.append(description + "\n")
            if m.inputs:
                out.append(f"**{t['inputs']}**\n\n{ports_table(m.inputs, t, lang)}\n")
            if m.outputs:
                out.append(f"**{t['outputs']}**\n\n{ports_table(m.outputs, t, lang)}\n")
            if m.params:
                out.append(f"**{t['params']}**\n\n" + "\n".join(params_table(m.params, t, lang)) + "\n")
            if m.state:
                out.append(f"**{t['state']}** (`node.state`): " + ", ".join(f"`{s}`" for s in m.state) + "\n")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    missing = [m.kind for m in audio.modules() if m.kind not in ES]
    if missing:
        print("no Spanish text for: " + ", ".join(missing))
        return 1
    stale = False
    for lang, folder in (("en", DOCS / "audio" / "engine"), ("es", DOCS / "es" / "audio" / "engine")):
        path = folder / "modules.md"
        text = render(lang)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"out of date: {path}")
                stale = True
            continue
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(DOCS.parents[2])}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
