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
campo.animate("shake", on=self.error)                            # se reproduce con self.error.fire()
boton.animate(on="press", scale=0.96, duration=90)               # tus propios valores
```

:::tip[¿Primera vez con animaciones?]
[Empieza aquí: aplicar y reproducir](/pyzed/es/animation/start/) explica en una página dónde va
`.animate()` y todas las formas de iniciar una animación, con ejemplos en cada estilo de código.
:::

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
| `"manual"` | Desde el principio cada vez que cambia `key`, nunca por sí sola. | Un latido cuando sube un contador. |
| un `pz.Trigger` | Desde el principio cada vez que tu código llama a `fire()`. | Un temblor con una contraseña incorrecta, una marca de "guardado". |

```python
ui.button("Grabar", self.alternar).animate("glow_pulse", active=self.grabando)
```

:::tip[Hover, press y focus vuelven con suavidad]
Estos disparadores no saltan hacia atrás: si el puntero sale a mitad de camino, la animación vuelve
desde donde estaba. Por eso encajan con presets cortos de "interacción" como `lift`, `grow` y `shrink`.
:::

### Reproducirla desde tu código con `pz.Trigger`

Un `pz.Trigger` inicia una animación desde un manejador. Créalo una vez (en `__init__`, o en el
`setup()` de un componente), pásalo a `on=` y llama a `fire()` cada vez que deba reproducirse:

```python
class Login(pz.App):
    def __init__(self):
        self.error = pz.Trigger()

    def view(self):
        return ui.input(self.clave, self.poner_clave).animate("shake", on=self.error)

    def enviar(self):
        if not self.comprobar():
            self.error.fire()      # tiembla ahora; otra vez desde el principio si seguía temblando
```

El widget no se mueve al aparecer, solo con `fire()`. `trigger.count` dice cuántas veces se disparó, y
`fire` ignora sus argumentos, así que `ui.button("Otra vez", self.error.fire)` funciona.

### Repetir con `key`

Una animación de `mount` se reproduce una vez. Dale un `key` y se vuelve a reproducir **cada vez que
cambia el key**:

```python
contrasena.animate("shake", key=self.intentos_fallidos)   # se sacude en cada contraseña incorrecta
ui.button("Copiar", self.copiar).animate("pulse", key=self.copias)
```

Al ser una animación de `mount` también se reproduce cuando el widget aparece por primera vez. Con
`on="manual"` **solo** se reproduce cuando cambia el key (es lo que hace `pz.Trigger` por debajo):

```python
ui.badge(str(self.sin_leer)).animate("pulse", on="manual", key=self.sin_leer)
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
| `key` | Cualquier valor. | Repite una animación de `mount` o `manual` cuando cambia. |
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
