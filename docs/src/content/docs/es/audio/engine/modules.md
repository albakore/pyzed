---
title: "Catálogo de módulos"
description: "Todos los módulos del motor de audio de Pyzed: osciladores, filtros, envolventes, LFO, efectos, secuenciadores, batería, samplers y MIDI, con sus puertos, rangos y valores."
sidebar:
  order: 2
---

<!-- Archivo generado por docs/scripts/gen_audio_modules.py a partir de audio.modules(). -->

Todos los módulos del motor, agrupados como en un rack. Añade uno con `engine.add(kind, **params)` y conecta sus puertos con `engine.connect(src, output, dst, input)`. Los mismos datos están en Python como [`audio.modules()`](/pyzed/es/audio/engine/getting-started/#el-catálogo), que una interfaz puede usar para dibujar cualquier módulo. Las señales siguen las [convenciones de los sintetizadores modulares](/pyzed/es/audio/engine/getting-started/#señales): el audio va de -1 a 1, la altura está en V/oct (0 = C4) y las puertas valen 0 o 1.

## Fuentes

### Oscilador · `oscillator`

Un VCO sin aliasing: seno, triángulo, sierra y cuadrada (con ancho de pulso), afinado por `freq` más la entrada `pitch` en V/oct.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `pitch` | Altura (V/oct) | cv |
| `fm` | FM | cv |
| `pwm` | PWM | cv |
| `sync` | Sync | gate |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |
| `sine` | Seno | audio |
| `triangle` | Triángulo | audio |
| `saw` | Sierra | audio |
| `square` | Cuadrada | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `freq` | Frecuencia | 8 … 20000 Hz (logarítmico) | 261.63 |
| `wave` | Onda | opciones: `sine`, `triangle`, `saw`, `square` | `saw` |
| `fine` | Ajuste fino | -1 … 1 st | 0 |
| `pw` | Ancho de pulso | 0.05 … 0.95 | 0.5 |
| `fm_amount` | Cantidad de FM | 0 … 1 | 0 |
| `level` | Nivel | 0 … 1 | 0.8 |

### Ruido · `noise`

Ruido blanco, rosa o marrón.

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `color` | Color | opciones: `white`, `pink`, `brown` | `white` |
| `level` | Nivel | 0 … 1 | 0.5 |

### Sampler · `sampler`

Reproduce un archivo WAV o una lista de muestras (`node.load`) cuando se abre su puerta: una vez, mientras se mantiene o en bucle.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `gate` | Puerta | gate |
| `pitch` | Altura (V/oct) | cv |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `mode` | Modo | opciones: `one-shot`, `gate`, `loop` | `one-shot` |
| `tune` | Afinación | -24 … 24 st | 0 |
| `start` | Inicio | 0 … 1 | 0 |
| `end` | Fin | 0 … 1 | 1 |
| `level` | Nivel | 0 … 1 | 0.8 |

**Estado** (`node.state`): `position`, `playing`

### Batería · `drum`

Una voz de batería sintetizada (bombo, caja, charles, palmada o tom) que suena con cada flanco de subida de `trigger`.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `trigger` | Disparo | gate |
| `accent` | Acento | cv |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `sound` | Sonido | opciones: `kick`, `snare`, `hihat`, `clap`, `tom` | `kick` |
| `tune` | Afinación | -12 … 12 st | 0 |
| `decay` | Caída | 0.02 … 2 s (logarítmico) | 0.4 |
| `tone` | Tono | 0 … 1 | 0.5 |
| `level` | Nivel | 0 … 1 | 0.8 |

**Estado** (`node.state`): `hit`

## Modulación

### LFO · `lfo`

Un oscilador lento para mover otros parámetros: seno, triángulo, sierra, cuadrada o pasos aleatorios (sample and hold).

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `rate` | Velocidad | cv |
| `reset` | Reinicio | gate |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | cv |
| `unipolar` | Unipolar | cv |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `rate` | Velocidad | 0.01 … 50 Hz (logarítmico) | 1 |
| `wave` | Onda | opciones: `sine`, `triangle`, `saw`, `square`, `random` | `sine` |
| `amount` | Cantidad | 0 … 1 | 1 |
| `offset` | Desplazamiento | -1 … 1 | 0 |

**Estado** (`node.state`): `phase`

### VCA · `vca`

Un amplificador cuya ganancia sigue a `cv` (una envolvente o un LFO); sin nada en `cv` es un volumen normal.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |
| `cv` | CV | cv |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `gain` | Ganancia | 0 … 2 | 1 |
| `response` | Respuesta | opciones: `linear`, `exponential` | `linear` |

### Envolvente · `adsr`

Una envolvente ADSR: sube cuando se abre la puerta, se queda en sustain y se apaga cuando se cierra.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `gate` | Puerta | gate |
| `retrig` | Redisparo | gate |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | cv |
| `inverted` | Invertida | cv |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `attack` | Ataque | 0.001 … 10 s (logarítmico) | 0.01 |
| `decay` | Caída | 0.001 … 10 s (logarítmico) | 0.2 |
| `sustain` | Sostenido | 0 … 1 | 0.7 |
| `release` | Liberación | 0.001 … 10 s (logarítmico) | 0.3 |

**Estado** (`node.state`): `stage`, `level`

## Filtros

### Filtro · `filter`

Un filtro de estado variable resonante (VCF) con paso bajo, paso alto, paso banda y notch; `cutoff` recibe V/oct, así que una envolvente o un LFO lo barren.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |
| `cutoff` | Corte | cv |
| `resonance` | Resonancia | cv |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |
| `lowpass` | Paso bajo | audio |
| `bandpass` | Paso banda | audio |
| `highpass` | Paso alto | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `mode` | Modo | opciones: `lowpass`, `highpass`, `bandpass`, `notch` | `lowpass` |
| `cutoff` | Corte | 20 … 20000 Hz (logarítmico) | 1200 |
| `resonance` | Resonancia | 0 … 1 | 0.2 |
| `cv_amount` | Cantidad de CV | -1 … 1 | 1 |
| `drive` | Saturación | 0 … 1 | 0 |

## Mezcla

### Mezclador · `mixer`

Cuatro canales con nivel y panorama hacia un par estéreo.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in_1` | Entrada 1 | audio |
| `in_2` | Entrada 2 | audio |
| `in_3` | Entrada 3 | audio |
| `in_4` | Entrada 4 | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `level_1` | Nivel 1 | 0 … 1.5 | 0.8 |
| `level_2` | Nivel 2 | 0 … 1.5 | 0.8 |
| `level_3` | Nivel 3 | 0 … 1.5 | 0.8 |
| `level_4` | Nivel 4 | 0 … 1.5 | 0.8 |
| `pan_1` | Panorama 1 | -1 … 1 | 0 |
| `pan_2` | Panorama 2 | -1 … 1 | 0 |
| `pan_3` | Panorama 3 | -1 … 1 | 0 |
| `pan_4` | Panorama 4 | -1 … 1 | 0 |
| `master` | Maestro | 0 … 1.5 | 1 |

## Efectos

### Delay · `delay`

Un eco con realimentación y un control de tono en las repeticiones.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |
| `time` | Tiempo | cv |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `time` | Tiempo | 0.001 … 2 s (logarítmico) | 0.35 |
| `feedback` | Realimentación | 0 … 0.98 | 0.4 |
| `tone` | Tono | 200 … 20000 Hz (logarítmico) | 8000 |
| `mix` | Mezcla | 0 … 1 | 0.35 |

### Reverb · `reverb`

Una sala estéreo (Freeverb): tamaño, amortiguación y anchura.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `size` | Tamaño | 0 … 1 | 0.6 |
| `damping` | Amortiguación | 0 … 1 | 0.4 |
| `width` | Anchura | 0 … 1 | 1 |
| `mix` | Mezcla | 0 … 1 | 0.3 |

### Distorsión · `distortion`

Satura la señal con un recorte suave o duro, un wavefolder o un fuzz.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `type` | Tipo | opciones: `soft`, `hard`, `fold`, `fuzz` | `soft` |
| `drive` | Saturación | 0 … 1 | 0.4 |
| `tone` | Tono | 200 … 20000 Hz (logarítmico) | 6000 |
| `mix` | Mezcla | 0 … 1 | 1 |
| `level` | Nivel | 0 … 1 | 0.7 |

### Chorus · `chorus`

Un chorus estéreo; con realimentación y un retardo corto se vuelve un flanger.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `rate` | Velocidad | 0.05 … 5 Hz (logarítmico) | 0.8 |
| `depth` | Profundidad | 0 … 1 | 0.5 |
| `delay` | Retardo | 1 … 30 ms (logarítmico) | 12 |
| `feedback` | Realimentación | 0 … 0.9 | 0 |
| `mix` | Mezcla | 0 … 1 | 0.5 |

### Bitcrusher · `bitcrusher`

Lo-fi: menos bits y una frecuencia de muestreo más baja.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `bits` | Bits | 1 … 16 bit | 8 |
| `downsample` | Reducción | 1 … 32 x | 4 |
| `mix` | Mezcla | 0 … 1 | 1 |

### Compresor · `compressor`

Iguala el nivel; una señal en `sidechain` atenúa la entrada (el «bombeo» de la música de baile).

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |
| `sidechain` | Sidechain | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `threshold` | Umbral | -60 … 0 dB | -18 |
| `ratio` | Ratio | 1 … 20 :1 | 4 |
| `attack` | Ataque | 0.1 … 100 ms (logarítmico) | 10 |
| `release` | Liberación | 10 … 1000 ms (logarítmico) | 120 |
| `makeup` | Compensación | 0 … 24 dB | 0 |

**Estado** (`node.state`): `reduction`

## Secuenciación

### Reloj · `clock`

El tempo de un patch: puertas en la subdivisión elegida del pulso, en cada pulso y en cada compás.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `reset` | Reinicio | gate |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `clock` | Reloj | gate |
| `beat` | Pulso | gate |
| `bar` | Compás | gate |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `bpm` | Tempo | 20 … 300 BPM | 120 |
| `division` | Subdivisión | opciones: `1/4`, `1/8`, `1/16`, `1/32` | `1/16` |
| `swing` | Swing | 0 … 0.5 | 0 |
| `run` | En marcha | opciones: `off`, `on` | `on` |

**Estado** (`node.state`): `tick`, `beat`

### Secuenciador · `sequencer`

Hasta 16 pasos de altura y puerta, avanzados por `clock` (o por su propio `bpm` en semicorcheas si `clock` no tiene cable).

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `clock` | Reloj | gate |
| `reset` | Reinicio | gate |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `pitch` | Altura (V/oct) | cv |
| `gate` | Puerta | gate |
| `trigger` | Disparo | gate |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `steps` | Pasos | 1 … 16 | 8 |
| `gate_length` | Duración de la puerta | 0.05 … 1 | 0.5 |
| `bpm` | Tempo | 0 … 300 BPM | 120 |
| `pitch_1` … `pitch_16` | Altura | -24 … 24 st | 0 |
| `gate_1` … `gate_16` | Puerta | opciones: `off`, `on` | `on` |

**Estado** (`node.state`): `step`

## Utilidades

### Constante · `constant`

Un voltaje fijo, para mover una entrada desde un knob.

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | cv |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `value` | Valor | -10 … 10 V | 1 |

### Osciloscopio · `scope`

Deja pasar su entrada sin tocarla, para ver una señal en cualquier punto del patch.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `in` | Entrada | audio |

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `out` | Salida | audio |

## Entrada y salida

### Entrada de audio · `audio_in`

El sonido del dispositivo de entrada (un micrófono o una línea), abierto con `Engine(input_device=...)` o `input=True`.

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `gain` | Ganancia | 0 … 4 | 1 |

### MIDI a CV · `midi_in`

Convierte las notas de un teclado MIDI (o de `engine.note_on`) en altura, puerta y velocidad, tocando la última nota pulsada.

**Salidas**

| Puerto | | Tipo |
| --- | --- | --- |
| `pitch` | Altura (V/oct) | cv |
| `gate` | Puerta | gate |
| `velocity` | Velocidad de nota | cv |
| `mod` | Rueda de modulación | cv |
| `retrigger` | Redisparo | gate |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `channel` | Canal | 0 … 16 | 0 |
| `glide` | Portamento | 0.0001 … 2 s (logarítmico) | 0.0001 |
| `bend_range` | Rango de pitch bend | 0 … 24 st | 2 |

**Estado** (`node.state`): `note`, `gate`

### Salida de audio · `audio_out`

Los altavoces. Sin nada en `right`, `left` suena por los dos lados.

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `left` | Izquierda | audio |
| `right` | Derecha | audio |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `volume` | Volumen | 0 … 1 | 0.8 |

### CV a MIDI · `midi_out`

Toca las notas de una puerta y una altura en una salida MIDI (`engine.open_midi_output`).

**Entradas**

| Puerto | | Tipo |
| --- | --- | --- |
| `pitch` | Altura (V/oct) | cv |
| `gate` | Puerta | gate |
| `velocity` | Velocidad de nota | cv |

**Parámetros**

| Parámetro | | Rango | Por defecto |
| --- | --- | --- | --- |
| `channel` | Canal | 1 … 16 | 1 |

**Estado** (`node.state`): `note`
