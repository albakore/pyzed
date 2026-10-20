---
title: animate() y disparadores
description: "widget.animate() en Pyzed: reproduce un preset o tu propia animación cuando un widget aparece, en hover, press, focus o clic, o mientras un indicador está activo, con duración, retraso, repeticiones, dirección, fill y curva."
sidebar:
  order: 1
---

`widget.animate(...)` le da a un widget su propio movimiento. Acepta nombres de presets, objetos
`pz.Animation` (o listas de ellos), [valores de propiedades](/pyzed/es/animation/properties/) y
opciones:

```python
pz.text("Guardado").animate("fade_in_up")                        # al aparecer
tarjeta.animate("lift", on="hover")                              # avanza en hover y vuelve al salir
icono.animate("pulse", repeat="infinite")                        # en bucle
campo.animate("shake", key=self.errores)                         # se repite cuando cambia key
boton.animate(on="press", scale=0.96, duration=90)               # tus propios valores
```

`animate()` devuelve el widget, así que puedes encadenarlo después de `style()` o llamarlo varias
veces. Cada llamada añade una animación que conserva su propio disparador:

```python
ui.button("Comprar", self.comprar).animate("fade_in_up").animate("lift", on="hover").animate("shrink", on="press")
```

## Disparadores

La opción `on` dice **qué reproduce la animación**:

![Seis tarjetas, una por disparador: mount se reproduce al aparecer, hover sube bajo el puntero, press se encoge al pulsar, focus ilumina el borde, click reproduce tada y active enciende un brillo](/pyzed/media/animation/triggers.webp)

| `on` | Se reproduce | Uso típico |
| --- | --- | --- |
| `"mount"` (por defecto) | Una vez, cuando el widget aparece en pantalla. | Entradas: una página, un aviso, un elemento de lista. |
| `"hover"` | Hacia delante mientras el puntero está encima y hacia atrás cuando sale. | Tarjetas y botones que reaccionan. |
| `"press"` | Hacia delante mientras el botón del ratón está pulsado sobre él y hacia atrás al soltar. | Un botón que se hunde. |
| `"focus"` | Hacia delante mientras tiene el foco del teclado y hacia atrás cuando lo pierde. | Campos que se iluminan. |
| `"click"` | Desde el principio en cada clic. | Un "me gusta" que salta, una celebración. |
| `"active"` | Hacia delante mientras `active=True` y hacia atrás cuando pasa a `False`. | Una luz de grabación, un estado seleccionado. |

```python
ui.button("Grabar", self.alternar).animate("glow_pulse", active=self.grabando)
```

:::tip[Hover, press y focus vuelven con suavidad]
Estos disparadores no saltan hacia atrás: si el puntero sale a mitad de camino, la animación vuelve
desde donde estaba. Por eso encajan con presets cortos de "interacción" como `lift`, `grow` y `shrink`.
:::

### Repetir con `key`

Una animación de `mount` se reproduce una vez. Dale un `key` y se vuelve a reproducir **cada vez que
cambia el key**:

```python
contrasena.animate("shake", key=self.intentos_fallidos)   # se sacude en cada contraseña incorrecta
ui.button("Copiar", self.copiar).animate("pulse", key=self.copias)
```

## Opciones de tiempo

Estas opciones sustituyen el tiempo que trae una animación (o un preset):

![Seis bolas en seis carriles, cada una con una opción: duration, delay, repeat, alternate, reverse y fill none](/pyzed/media/animation/options.webp)

| Opción | Valores | Qué hace |
| --- | --- | --- |
| `duration` | Milisegundos, o `"0.3s"` / `"300ms"`. | Cuánto dura una pasada. |
| `delay` | Las mismas unidades. | Cuánto espera antes de empezar. |
| `easing` | Un nombre de curva, una Bézier `(x1, y1, x2, y2)` o `"steps(4)"`. | La forma del movimiento: mira las [curvas](/pyzed/es/animation/keyframes/#curvas). |
| `repeat` | Un número de veces o `"infinite"`. | Cuántas pasadas seguidas. |
| `direction` | `"normal"`, `"reverse"`, `"alternate"`, `"alternate_reverse"`. | `reverse` la reproduce al revés; `alternate` va y vuelve en pasadas alternas. |
| `fill` | `"both"` (por defecto), `"forwards"`, `"backwards"`, `"none"`. | Qué se ve antes del retraso y después del final, como en CSS. Con `"none"` el widget vuelve a su aspecto propio al terminar. |
| `key` | Cualquier valor. | Repite una animación de `mount` cuando cambia. |
| `active` | `True` o `False`. | Controla una animación `"active"`. |
| `on_start`, `on_end` | Un callable o un mensaje. | Se envía cuando la animación empieza y cuando termina. |

```python
insignia.animate("pulse", repeat=3, delay=400)
flecha.animate(pz.Animation({0: {"x": 0}, 1: {"x": 6}}, duration=600), direction="alternate", repeat="infinite")
aviso.animate("fade_in_up", on_end=self.aviso_mostrado)
```

## Listas o a medida

- Un **nombre de preset** es lo más rápido: mira la [galería de presets](/pyzed/es/animation/presets/).
- Los **valores de propiedades** describen una animación sencilla ahí mismo: `animate(opacity=0, y=12)`
  aparece desde abajo. Mira [Propiedades animables](/pyzed/es/animation/properties/).
- Una **`pz.Animation`** te da keyframes, curvas por paso y un nombre que puedes reutilizar en toda la
  app. Mira [Keyframes y curvas](/pyzed/es/animation/keyframes/).
- Un **objetivo de línea de tiempo** de un reproductor (`self.player["card"]`) permite que un clip mueva
  muchos widgets. Mira [Animaciones con línea de tiempo](/pyzed/es/animation/timeline/).

:::note[Las animaciones vuelven a empezar cuando un widget regresa]
Si un widget sale de la vista y vuelve (un `if` en `view()`, un elemento nuevo de una lista), su
animación de `mount` se reproduce otra vez. Usa un `key` estable, o
[`pz.presence`](/pyzed/es/animation/transitions/#presence-y-stagger), para decidir cuándo se repite.
:::
