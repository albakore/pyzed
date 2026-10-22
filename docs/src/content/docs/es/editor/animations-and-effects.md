---
title: Animaciones y efectos
description: "Da a los controles sombra, desenfoque, glow, bloom, glass y opacidad en Pyzed Design, y anímalos al aparecer, con el ratón, al hacer clic, con un valor nuevo, una regla que falla o el evento de otro control."
sidebar:
  order: 5.5
---

Cada control visual tiene dos secciones al final del panel **Propiedades**, después de su estilo: **Efectos** y
**Animación**. Lo que fijes ahí se guarda en el `.pzform` y se reproduce cuando el formulario se ejecuta. Es
el mismo sistema que [`widget.animate()` y los efectos de estilo](/pyzed/es/animation/) de la biblioteca.

![Las secciones Efectos y Animación de un botón](../../../../../screenshots/editor-motion.png)

## Efectos

| Campo | Qué hace |
| --- | --- |
| **Opacidad** | Cuánto se ve el control y todo lo que tiene dentro (1 es opaco). |
| **Sombra** | Una sombra proyectada: elige un color y luego **Desplazamiento** (X e Y) y **Desenfoque**. |
| **Desenfoque** | Desenfoca el control y todo lo que contiene, en píxeles. |
| **Desenfoque del fondo** | Desenfoca lo que hay detrás de la caja, en píxeles. |
| **Resplandor** | Un halo suave alrededor de la caja. Elige un color (o un token del tema como `accent`); **Tamaño del resplandor** fija cuánto se extiende. |
| **Bloom** | Luz que desborda de las partes brillantes del control. **Intensidad** va de 0 a 1. |
| **Cristal** | Un panel translúcido que desenfoca lo que tiene detrás, con un borde claro. **Matiz** lo colorea e **Intensidad del tinte** fija cuánto se nota el tinte. |

La rotación está en la sección **Posición**. Los subcampos solo aparecen mientras el efecto está activo. Borra el color (o apaga **Cristal**) para
quitarlo. Los efectos son propiedades de estilo (`opacity`, `shadow`, `blur`, `backdrop_blur`, `glow`, `bloom`, `glass`), así que en el código
aparecen en `control.style` y **Restablecer el estilo** también los quita. El cristal luce mejor sobre un fondo
colorido, como un panel con degradado.

## Animación

Una animación son dos decisiones: **cuándo** se reproduce y **qué** se reproduce (un preset como *Aparecer
subiendo*, *Latido* o *Sacudida*). Un control sin animaciones muestra algunas listas para añadir con un clic
(**Aparecer al mostrarse**, **Elevar al pasar el ratón**, **Latir al hacer clic**, **Sacudir si el valor no es
válido**...), solo las que encajan con el control, y **Añadir animación** para cualquier otra.

Cada fila es una animación: un icono de lo que la reproduce, un resumen (**Aparecer subiendo · 280 ms**,
con **+retardo** y **×repeticiones** si las tiene) y el disparador debajo. El botón **▶** la previsualiza y la
papelera la quita. Haz clic en una fila para abrir su editor:

| Campo | Significado |
| --- | --- |
| **Cuándo** | Qué la reproduce (ver la tabla de abajo). Debajo del campo, una línea explica cómo empieza la elegida. |
| **Control**, **Evento** | Solo con **Con un evento de otro control**: qué control (o el formulario) y cuál de sus eventos. |
| **Animación** | El preset. Primero salen los que encajan con el disparador (entradas para *al aparecer*, interacciones para encima y pulsar, de atención para clics y eventos); el tooltip describe el elegido. |
| **Duración**, **Retardo** | Milisegundos. Vacío mantiene el timing propio del preset. |
| **Curva** | Cómo cambia la velocidad por el camino (suave, lineal, frenar cúbica, muelle...). |
| **Repetir** | 1, 2, 3, 5 o infinito. |

| Cuándo | Se reproduce |
| --- | --- |
| **Al aparecer** | Una vez, al abrir el formulario o al mostrarse el control. |
| **Con el ratón encima**, **Mientras se pulsa**, **Mientras tiene el foco** | Hacia delante mientras se cumple la condición, y hacia atrás cuando termina. |
| **Al hacer clic**, **Al hacer doble clic**, **Al hacer clic derecho** | Una vez en cada clic. |
| **Cuando entra el puntero**, **Cuando sale el puntero** | Una vez cada vez que el ratón entra o sale. |
| **Cuando cambia su valor** | Una vez con cada valor nuevo (al escribir, al elegir otra opción, al cambiar un interruptor...). |
| **Al pulsar Enter** | Una vez cuando el usuario envía un campo de texto. |
| **Cuando su valor no es válido** | Una vez cada vez que falla una [regla de validación](/pyzed/es/editor/data-binding/): la clásica *sacudida* con una contraseña mal escrita. |
| **Con un evento de otro control** | Una vez con cada evento de otro control o del formulario: una etiqueta que late al pulsar **Guardar**, una tarjeta que aparece al cargar el formulario. |
| **Al reproducirla desde el código** | Solo cuando un manejador llama a `play_animation()` (ver abajo). |

Los disparadores por evento funcionan aunque el control no tenga manejador para ese evento, y se reproducen antes de
que corra el manejador. **Añadir animación** añade una fila (un *aparecer subiendo* al aparecer) y la abre. Elegir
otro preset restablece el timing de la fila al del nuevo preset. Todos los cambios se pueden deshacer.

### Reproducirla desde tu código

Elige **Al reproducirla desde el código** y la animación espera a tus manejadores: no se reproduce al
abrir el formulario. La fila abierta muestra la línea que la reproduce, con un botón para copiarla.
Pégala en cualquier manejador (el clic de un botón, el tick de un temporizador, una validación que
falla):

```python
def sign_in_click(form, event):
    if not form.password.validate():
        form.password.play_animation()      # reproduce las animaciones "desde el código" del campo
```

`play_animation()` también repite las animaciones **Al aparecer** del control. Pásale un nombre de
preset, un `pz.Animation` o valores de propiedades para reproducir algo que el control no tiene en sus
filas, y usa `stop_animation()` para parar lo que inició (un bucle, por ejemplo):

| Llamada | Qué se reproduce |
| --- | --- |
| `form.title.play_animation()` | Sus filas **Al reproducirla desde el código** (y repite las de **Al aparecer**). |
| `form.title.play_animation("tada")` | Ese preset, una vez. |
| `form.badge.play_animation("pulse", repeat=3, duration=400)` | Un preset con otro tiempo (cualquier [opción de `animate()`](/pyzed/es/animation/animate/#opciones-de-tiempo)). |
| `form.card.play_animation(scale=1.05, duration=200)` | Hasta esos valores y de vuelta. |
| `form.spinner.stop_animation()` | Para lo que inició `play_animation`. |

[Empieza aquí: aplicar y reproducir](/pyzed/es/animation/start/) lo compara con `pz.Trigger`, la forma
de hacer lo mismo en una app solo con código.

### Vista previa

El lienzo se queda quieto mientras editas, para que los controles no se muevan bajo el ratón.
**Vista previa** (al final de la sección, o **▶** en una fila) reproduce una vez en el lienzo las animaciones
del control, como si acabara de aparecer; **Detener** termina la previsualización. Ejecuta el formulario
(**F5**) para ver cada animación con su disparador real.

## En código

Las animaciones se guardan como datos simples en el control:

```json
"animations": [
  {"preset": "fade_in_up"},
  {"preset": "lift", "on": "hover", "duration": 180}
]
```

Los valores de `"on"` son `mount` (por defecto), `hover`, `press`, `focus`, `click`, `double_click`,
`right_click`, `enter`, `leave`, `change`, `submit`, `invalid`, `event` y `manual` (**Al reproducirla desde el
código**). Una entrada `event` nombra además su origen y su evento:
`{"preset": "tada", "on": "event", "source": "save", "event": "click"}` (un `source` vacío es el formulario). `Document.set_animations(name, animations)` las
cambia desde un script y `Control.animations` las lee. Para reproducir una desde un manejador, llama a
`form.<control>.play_animation(...)` (ver arriba); para crear tus propios presets, usa `pz.Animation` y
`define_animation` de la biblioteca (ver la [lista de presets](/pyzed/es/animation/presets/)).

## Animaciones con línea de tiempo

Para animaciones que mueven varios controles a la vez (una entrada, una transición entre estados), abre
el panel **Animation** desde **View → Animation** (`Ctrl+Shift+M`). Edita **clips**: líneas de tiempo
guardadas en el `.pzform` que se reproducen igual que con [`pz.AnimationPlayer`](/pyzed/es/animation/timeline/)
en código.

![El panel Animation: al arrastrar el cabezal por un clip intro, el título baja, el subtítulo aparece y el botón Sign in crece en el formulario de arriba](/pyzed/media/animation/editor-scrub.webp)

Con el panel vacío se ven los tres pasos (añadir una pista, añadir keys, reproducirlo) y un botón
**Nueva animación**.

| Acción | Resultado |
| --- | --- |
| **Añadir pista para …** | Añade una pista para una propiedad del control seleccionado (opacidad, posición, escala, colores, tamaño…) o cualquiera de sus propiedades, como el texto de una etiqueta. |
| **Clic** en cualquier punto de la regla o las pistas, o **arrastrar** | Mueve el cabezal; el lienzo muestra el formulario en ese tiempo. Se pega a las keys cercanas. |
| **Doble clic** en una pista | Añade una key en ese tiempo con el valor que la pista tiene ahí. |
| **Arrastrar** una key | La mueve en el tiempo. Puedes agarrarla desde unos píxeles de distancia (el puntero se vuelve una mano) y se pega a las keys de las otras pistas, al principio y al final. Una etiqueta muestra su tiempo y su valor mientras la arrastras o pasas por encima. |
| **Clic** en una key | La selecciona: edita su tiempo, su valor y su curva debajo de las pistas. |
| **Clic derecho** en una key | La borra. |
| Pista **Llamadas** | Escribe el nombre de un manejador y pulsa Intro (o haz doble clic en la pista) para llamar a ese método del archivo de código del formulario en el cabezal. Arrastra una llamada para moverla; clic derecho para quitarla. |
| **Duración**, **bucle**, **autoplay** | Indican cuánto dura el clip, si se repite y si se reproduce al abrir el formulario. |

Con el puntero sobre el panel, el teclado edita la línea de tiempo:

| Tecla | Hace |
| --- | --- |
| `Supr` / `Retroceso` | Borra la key seleccionada. |
| `Espacio` | Reproduce o pausa la vista previa. |
| `←` / `→` | Mueve la key seleccionada (o el cabezal) 0,01 s; con `Mayús`, 0,1 s. |
| `Inicio` / `Fin` | Salta al principio o al final. |

![Añadir una pista de escala al título desde el panel, hacer doble clic en su pista para añadir una key, arrastrarla antes y elegirle Ease out back](/pyzed/media/animation/editor-keys.webp)

Los controles dentro de un contenedor animado siguen su opacidad, posición y desenfoque. Todos los
cambios se pueden deshacer.

### Cómo empieza un clip

Un clip se reproduce de una de estas dos formas, y la barra bajo las pistas dice cuál se aplica al clip
que editas:

- **⚡ Reproducir al abrir el formulario** (en la barra de herramientas) lo convierte en el clip de
  autoplay del formulario: "Se reproduce al abrir el formulario."
- Si no, espera a un manejador. La barra muestra la línea a llamar, con un botón para copiarla:

```python
def replay_click(form, event):
    form.animations.play("intro", restart=True)  # desde el principio, aunque esté sonando
    # también: form.animations.pause(), .resume(), .seek(0.5), .play_backwards("intro"), .queue("outro")
```

`form.animations` es el [`pz.AnimationPlayer`](/pyzed/es/animation/player/) del formulario: también
pausa, salta a un tiempo, encola clips y avisa cuando uno termina. La
[sección Animación](/pyzed/es/animation/) explica a fondo los clips, las pistas, las keys, las curvas y
el reproductor.
