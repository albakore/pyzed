---
title: Accesibilidad
description: Foco del teclado con Tab, el ajuste de reducir movimiento del sistema y el estado del soporte para lectores de pantalla.
sidebar:
  order: 18
---

Las apps de Pyzed se pueden usar con el teclado y respetan la preferencia de movimiento del
sistema. Los lectores de pantalla todavía no están soportados: en
[Lectores de pantalla](#lectores-de-pantalla) se explica por qué y qué viene después.

## Moverse entre campos con Tab

<kbd>Tab</kbd> mueve el foco del teclado al siguiente campo de la ventana y
<kbd>Shift</kbd>+<kbd>Tab</kbd> al anterior, en el orden en que aparecen en `view()`. Tras el
último vuelve al primero. Los campos son los `text_input`, `text_editor` y `code_editor` (y los
componentes construidos con ellos, como `ui.input` o `ui.search`); cada ventana recorre solo
sus propios campos.

Un `code_editor` con `tab_size` se queda con <kbd>Tab</kbd> para indentar, como Zed. Los
editores sin él dejan pasar la tecla, así que <kbd>Tab</kbd> sale de ellos.

`on_key` ve la tecla primero (`"tab"` o `"shift-tab"`). Si devuelve algo (un mensaje o un
`Command`), la app la ha gestionado y el foco no se mueve; devolver `None` deja que se mueva.
Desactívalo para toda una app o ventana con `tab_focus = False`:

```python
class App(pz.App):
    tab_focus = False  # Tab no hace nada salvo que on_key lo gestione

    def on_key(self, combo):
        if combo == "tab" and self.completion_open:
            return self.accept_completion()
```

`Command.focus_next()` y `Command.focus_previous()` hacen lo mismo desde código, y
`Command.focus(id)` salta a un campo concreto.

:::note
En Iced 0.14 solo los campos de texto pueden tomar el foco del teclado. Botones, casillas y
sliders se usan con el ratón o con atajos desde `on_key`; dale un atajo a las acciones
importantes (ver [Teclado y atajos](/pyzed/es/guides/keyboard/)).
:::

## Reducir movimiento

Cuando el sistema pide a las apps reducir el movimiento, Pyzed apaga sus animaciones: cada
`animate()`, `transition()`, `presence()`, transición de ventana y scroll animado muestra al
instante su estado final. El ajuste se lee al arrancar la app:

| Sistema | Ajuste |
| --- | --- |
| macOS | Ajustes del Sistema → Accesibilidad → Pantalla → Reducir movimiento |
| Windows | Configuración → Accesibilidad → Efectos visuales → Efectos de animación (desactivado) |
| Linux (GNOME) | Configuración → Accesibilidad → Reducir animación (`enable-animations`) |
| Linux (KDE) | Preferencias del sistema → Velocidad de animación en *Instantánea* |

`pz.system_reduced_motion()` devuelve lo que dice el sistema (`None` si no lo sabe). Tu app
puede decidir igualmente:

```python
pz.set_reduced_motion(True)   # siempre apagado, p. ej. desde los ajustes de tu app
pz.set_reduced_motion(False)  # siempre encendido
pz.set_reduced_motion(None)   # volver a seguir al sistema (por defecto)
```

La variable de entorno `PYZED_REDUCED_MOTION` (`1` o `0`) se impone a ambos. Las capturas
muestran siempre el estado de reposo. Ver
[Animación](/pyzed/es/guides/animation/#movimiento-reducido-y-tests).

## Lectores de pantalla

Pyzed dibuja su interfaz con Iced, que pinta cada widget en la GPU en vez de usar los
controles nativos del sistema. Los lectores de pantalla (VoiceOver, Narrador, NVDA, Orca)
necesitan un *árbol de accesibilidad* que describa esos widgets, e Iced 0.14 no lo genera.
La forma habitual de darlo en Rust es [AccessKit](https://accesskit.dev/), y evaluamos
añadirlo a Pyzed para la 1.1:

- **Iced 0.14 no soporta AccessKit.** Ni `iced` ni `iced_winit` dependen de él, y winit 0.30
  deja la accesibilidad a adaptadores como `accesskit_winit`.
- **La ventana es de Iced.** `accesskit_winit` debe crearse antes de mostrar la ventana y
  recibir todos sus eventos; el bucle de eventos de Iced no da sitio para ninguna de las dos
  cosas. Los adaptadores de cada plataforma (`accesskit_windows` y `accesskit_macos`
  subclasifican la ventana nativa, `accesskit_unix` habla con AT-SPI) se podrían enganchar
  desde el handle de la ventana, pero son tres integraciones distintas, cada una probada con
  un lector de pantalla real.
- **Los widgets no se describen a sí mismos.** Las operaciones de widgets de Iced informan de
  texto, campos de texto, scrollables y foco, pero no de roles (botón, casilla, slider),
  estados ni acciones ("pulsar"), así que Pyzed tendría que construir el árbol desde sus
  propias descripciones de widgets y sincronizarlo con el layout en cada frame.

Eso es un proyecto en sí mismo, no algo para publicar a medias en una versión menor. La
accesibilidad está en la hoja de ruta de Iced y algunos forks de Iced ya incluyen AccessKit,
así que el plan es:

1. Seguir a Iced y adoptar su soporte de accesibilidad cuando llegue; los widgets de Pyzed
   corresponden uno a uno con los de Iced, así que lo ganarían con poco trabajo extra.
2. Mientras tanto, completar el uso con teclado (foco para botones y otros controles cuando
   Iced lo permita) y mantener las etiquetas en el texto de la interfaz, no solo en iconos.

Si el soporte de lectores de pantalla es importante para tu app, dilo en los
[issues](https://github.com/albakore/pyzed/issues): ayuda a decidir prioridades.
