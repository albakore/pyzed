---
title: Dispositivos y pantallas
description: "Una sola app de Pyzed en escritorios, paneles táctiles, pantallas de autos, teléfonos, quioscos y televisores: perfiles de dispositivo, resolución de diseño, media queries táctiles y foco con las flechas."
sidebar:
  order: 6.5
---

La misma app puede correr en un portátil, un panel táctil en la pared, el tablero de un auto, un
teléfono o un televisor. Cambia cómo se usan (ratón, dedo, mando), sus pantallas y lo rápido que
dibujan. Un **perfil de dispositivo** le dice a Pyzed dónde corre, y Pyzed completa las opciones de
ventana y de renderizado que tu app deja por defecto.

```python
import pyzed as pz

class Tablero(pz.App):
    title = "Tablero"
    device = "automotive"        # quiosco a pantalla completa, sin puntero, las flechas mueven el foco
    design_size = (1920, 720)    # maquetada para esta pantalla, escalada a la real

    def view(self):
        ...
```

## Los perfiles

| Perfil | Para | Qué ajusta |
| --- | --- | --- |
| `desktop` | Portátiles y ordenadores de escritorio (por defecto) | Nada: las ventanas como las declares. |
| `touch` | Tabletas, monitores táctiles, convertibles | Táctil primero (`pointer: coarse`), escala 1.15, objetivos de 44 px. |
| `automotive` | Pantallas de autos, paneles de máquinas | Quiosco a pantalla completa, puntero oculto, foco con flechas, escala 1.25, objetivos de 64 px, calidad media. |
| `mobile` | Teléfonos (por defecto en Android) | Táctil, pantalla completa, sin puntero, objetivos de 48 px, calidad media. |
| `kiosk` | Puntos de venta, paneles de museo e información | Quiosco a pantalla completa, táctil, escala 1.15, animaciones en segundo plano en pausa. |
| `tv` | Televisores y decodificadores | Pantalla completa, sin puntero, foco con flechas, escala 2, calidad media. |

Tus opciones siempre ganan: un perfil solo completa lo que la clase de la app no toca. Un
`kiosk = False` en tu `App` deja la ventana cerrable en un dispositivo `kiosk`.

## Elegir el perfil

Pyzed mira, en este orden:

1. `App.device`: el nombre de un perfil o un `pz.Device`.
2. La variable de entorno `PYZED_DEVICE`: útil para probar un perfil en tu ordenador
   (`PYZED_DEVICE=tv python app.py`).
3. `device = "..."` en `[tool.pyzed.platform.<sistema>]` de `pyproject.toml` (`linux`, `windows`,
   `macos`, `android`), y luego en `[tool.pyzed]`.
4. El sistema: `mobile` en Android, `desktop` en el resto.

`pz.device()` devuelve el perfil en uso y `pz.set_device("touch")` lo cambia con la app en marcha.

## Tus propios perfiles

Define perfiles en `pyproject.toml`. `extends` nombra el perfil del que parte; una tabla con el
nombre de un perfil incluido lo modifica:

```toml
[tool.pyzed]
device = "tablero"

[tool.pyzed.platform.windows]
device = "desktop"           # el mismo proyecto en un portátil con Windows

[tool.pyzed.device.tablero]
extends = "automotive"
design_size = [1920, 720]
stretch = "fit"
quality = "low"

[tool.pyzed.device.tv]
scale = 1.5
```

O en código: `pz.Device("panel", touch=True, kiosk=True, quality="low")`, o
`pz.devices.PROFILES["tv"].replace(scale=1.5)`.

| Campo | Significado |
| --- | --- |
| `touch` | La pantalla se toca más de lo que se hace clic: `pz.media("pointer: coarse")` es verdadero. |
| `pointer` | `False` oculta el puntero sobre las ventanas. |
| `kiosk`, `fullscreen` | La ventana principal se abre como quiosco o a pantalla completa (ver [Pantallas y quioscos](/pyzed/es/guides/windows/#pantallas-y-quioscos)). |
| `arrow_focus` | Las flechas mueven el foco (ver abajo). |
| `scale` | Escala de la interfaz de las ventanas que dejan `scale` en 1. |
| `min_target` | El control más pequeño cómodo en píxeles lógicos; léelo con `pz.device().min_target` para dimensionar tus componentes. |
| `design_size`, `stretch` | La resolución de diseño (ver abajo). |
| `quality` | `"high"`, `"medium"` o `"low"`: valores de renderizado para hardware más lento. |
| `reduced_motion` | `True` apaga las animaciones, `None` sigue al sistema. |
| `rendering` | Campos de `pz.Rendering` encima del nivel de calidad. |

## Niveles de calidad

`quality` completa los [ajustes de renderizado](/pyzed/es/editor/settings/#renderizado) que el
proyecto deja en `"auto"`:

| Calidad | Antialiasing | Frames por segundo | Ventanas en segundo plano | Otros |
| --- | --- | --- | --- | --- |
| `high` | 4x | los de la pantalla | como con foco | |
| `medium` | 2x | 60 | 10 fps | |
| `low` | no | 30 | en pausa | poca memoria de GPU, GPU de bajo consumo |

## Resolución de diseño

Los paneles y las pantallas de autos tienen una pantalla conocida, y se diseña para ella.
`design_size` maqueta la vista para ese tamaño y la escala a la ventana real, como los modos de
estiramiento de Godot:

- `stretch = "expand"` (por defecto) escala hasta que el diseño cabe y deja que la vista crezca en
  el espacio que sobra, así una pantalla más ancha muestra más.
- `stretch = "fit"` escala igual y mantiene el tamaño del diseño, centrado, con bandas alrededor.
- `stretch = "none"` ignora `design_size`.

`pz.viewport()` y las media queries ven las unidades del diseño, así los breakpoints siguen funcionando.

## Táctil, puntero y dispositivo en los estilos

Las media queries responden sobre el dispositivo, en código y en hojas de estilo:

```python
padding = 20 if pz.media("pointer: coarse") else 8     # más grande en pantallas táctiles

pz.stylesheet({
    "@(pointer: coarse)": {"button": {"padding": [14, 20]}},
    "@(device: tv)": {"text": {"size": 22}},
})
```

`pointer` es `coarse` en pantallas táctiles, `none` donde nada apunta (televisores) y `fine` con ratón.

## Foco con las flechas

Los mandos de televisor, las ruedas giratorias y los botones del volante envían flechas. Con
`App.arrow_focus = True` (activado por defecto en los perfiles `tv` y `automotive`), una flecha que
ningún control usó mueve el foco al control más cercano en esa dirección. `on_key` ve la tecla
primero; si devuelve algo, el foco se queda donde está. `Command.focus_direction("left")` hace lo
mismo desde código.

Los controles toman el foco con `pz.focusable`:

```python
pz.focusable(tarjeta, self.abrir, keys=["enter"])
```

## Dispositivos Linux sin escritorio

En la pantalla de un auto o un quiosco, ejecuta la app como único programa de un compositor de
quiosco como [cage](https://github.com/cage-kiosk/cage), arrancado por el sistema al iniciar:

```bash
PYZED_DEVICE=automotive cage -- python app.py
```

No hay escritorio, ni paneles, ni nada que cerrar; con `background_fps = 0` la app no usa CPU
mientras nada se mueve.
