---
title: "Empieza aquí: aplicar y reproducir"
description: "Las dos cosas que necesita toda animación de Pyzed: qué widget mueve (animate() sobre el widget) y qué la inicia (un disparador, tu código, una línea de tiempo). Ejemplos declarativos e imperativos, en clases, componentes y funciones, y lo mismo en Pyzed Design."
sidebar:
  order: 0.5
  label: "Empieza aquí: aplicar y reproducir"
---

Toda animación responde dos preguntas:

1. **¿Qué widget se mueve?** Le pones la animación a ese widget con `.animate(...)`.
2. **¿Cuándo se reproduce?** Lo decide un **disparador**: que el widget aparezca, el puntero, un clic,
   un valor de tu estado o una línea de tu código.

Esta página explica las dos cosas, con el mismo ejemplo escrito en los distintos estilos que admite
Pyzed. Las demás páginas de la sección profundizan en cada parte.

![Una tarjeta de inicio de sesión: la tarjeta sube al aparecer, el botón se eleva bajo el puntero, una contraseña incorrecta hace temblar el campo y una correcta hace aparecer una marca de verificación](/pyzed/media/animation/start.webp)

## 1. Aplícala: `.animate()` sobre el widget

Una animación vive **en el widget que mueve**. Llama a `.animate()` donde construyes el widget en
`view()` y usa el widget que devuelve:

```python
def view(self):
    return pz.column([
        pz.text("Hola de nuevo").animate("fade_in_down"),        # este texto se mueve
        ui.button("Entrar", self.entrar).animate("lift", on="hover"),
    ])
```

`.animate()` funciona en **todos** los widgets: textos, botones, campos, contenedores, filas, iconos,
imágenes y tus propios componentes (que además aceptan `animate="fade_in"` como argumento). En un
contenedor, todo lo que tiene dentro se mueve con él.

:::caution[Usa lo que devuelve `.animate()`]
Los widgets no cambian en el sitio: `.animate()` devuelve un widget nuevo con la animación. Escribir
`titulo.animate("fade_in")` en su propia línea no hace nada si luego devuelves el `titulo` antiguo.

```python
titulo = pz.text("Hola")
titulo.animate("fade_in")           # ✗ el resultado se pierde
titulo = titulo.animate("fade_in")  # ✓ guárdalo (o encadénalo donde construyes el widget)
```
:::

Puedes llamar a `.animate()` varias veces: cada llamada añade una animación con su propio disparador.

```python
ui.button("Comprar", self.comprar).animate("fade_in_up").animate("lift", on="hover").animate("shrink", on="press")
```

## 2. Iníciala: el disparador

La opción `on=` dice qué reproduce la animación. Eliges uno en cada llamada a `.animate()`:

| Quieres que se reproduzca... | Escribe | Se reproduce |
| --- | --- | --- |
| cuando el widget aparece | `.animate("fade_in")` (`on="mount"` es el valor por defecto) | una vez, cada vez que el widget aparece |
| mientras el puntero está encima | `.animate("lift", on="hover")` | avanza al entrar y vuelve al salir |
| mientras está pulsado | `.animate("shrink", on="press")` | avanza mientras el botón está abajo |
| mientras tiene el foco | `.animate("glow", on="focus")` | avanza mientras tiene el foco |
| en cada clic sobre él | `.animate("tada", on="click")` | desde el principio, en cada clic |
| mientras un valor de tu estado es verdadero | `.animate("glow_pulse", active=self.grabando)` | avanza con `True` y vuelve con `False` |
| **cuando tu código lo diga** | `.animate("shake", on=self.error)` + `self.error.fire()` | desde el principio, en cada `fire()` |
| cuando cambia un valor de tu estado | `.animate("pulse", on="manual", key=self.contador)` | desde el principio, con cada `key` nueva |

Los cinco primeros no necesitan nada más: Pyzed vigila el puntero y el teclado por ti. Los tres
últimos son la forma de que **tu código** inicie una animación.

### Desde tu código: `pz.Trigger`

Un `pz.Trigger` es como un botón que pulsa tu código. Guarda uno en la app, pásalo a `on=` y llama a
`fire()` en cualquier manejador:

```python
class Login(pz.App):
    def __init__(self):
        self.clave = ""
        self.error = pz.Trigger()        # 1. créalo una vez

    def view(self):
        return pz.column([
            ui.input(self.clave, self.poner_clave, secure=True)
                .animate("shake", on=self.error),    # 2. ponlo: todavía no se reproduce nada
            ui.button("Entrar", self.entrar),
        ], spacing=12)

    def poner_clave(self, texto):
        self.clave = texto

    def entrar(self):
        if self.clave != "secreto":
            self.error.fire()            # 3. reprodúcela ahora (otra vez desde el principio si seguía)
```

No se reproduce nada cuando el widget aparece: solo `fire()` la inicia. `fire` ignora sus argumentos,
así que puede ser un callback directamente: `ui.button("Temblar", self.error.fire)`.

`on="manual"` con una `key` hace lo mismo sin objeto: la animación se reproduce cada vez que cambia la
key y nunca por sí sola. Es práctico con un contador que ya tienes:

```python
ui.badge(str(self.sin_leer)).animate("pulse", on="manual", key=self.sin_leer)   # late con cada mensaje nuevo
```

:::note[`key` con o sin `on="manual"`]
Una `key` sola (`.animate("shake", key=self.errores)`) también se repite cuando cambia la key, pero al
ser una animación **mount** se reproduce además cuando el widget aparece. Añade `on="manual"` (o usa un
`pz.Trigger`) cuando solo deba reproducirse con un cambio.
:::

### Parar un bucle

Una animación en bucle (`repeat="infinite"`, o un preset de bucle como `spin`) sigue mientras el
widget la tenga. Para pararla, deja de pedirla en `view()`:

```python
icono = pz.icon("loader-circle")
if self.cargando:
    icono = icono.animate("spin")
```

O usa `active=`, que además la saca con suavidad: `.animate("glow_pulse", active=self.cargando)`.

## 3. Nómbrala: qué puedes pasarle a `.animate()`

El primer argumento dice **qué** animación se reproduce. Puede ser:

| Pasas | Ejemplo | De dónde sale |
| --- | --- | --- |
| El nombre de un preset | `"fade_in_up"`, `"lift"`, `"spin"` | La [galería de presets](/pyzed/es/animation/presets/): más de 50 animaciones listas, en cinco grupos (entrada, salida, atención, interacción, bucle). |
| Un nombre que definiste | `"meneo"` | `pz.animation.define_animation("meneo", ...)`, una vez, en cualquier sitio antes de que se ejecute `view()`. |
| Un `pz.Animation` | `pz.Animation([{"x": 0}, {"x": 8}])` | Tus propios fotogramas clave, usados en el sitio. Ver [Fotogramas clave y curvas](/pyzed/es/animation/keyframes/). |
| Valores de propiedades | `.animate(opacity=0, y=12)` | Una animación rápida desde (o hacia) esos valores. Ver [Propiedades animables](/pyzed/es/animation/properties/). |
| Un objetivo de línea de tiempo | `self.player["tarjeta"]` | Una parte de un clip que mueve muchos widgets. Ver [Animaciones con línea de tiempo](/pyzed/es/animation/timeline/). |

Los nombres de los presets son palabras en inglés y minúsculas unidas por `_`, y dicen lo que hacen:
`fade_in_left` (aparece desde la izquierda), `slide_out_down` (sale deslizándose hacia abajo),
`rubber_band` (se estira como una goma). Para listarlos desde Python:

```python
from pyzed import animation
print(list(animation.presets()))              # todos los nombres
print(list(animation.presets("entrance")))    # un grupo
print(animation.animation("pop_in").description, animation.animation("pop_in").duration)
```

## 4. Personalízala

Cada preset trae su propio tiempo; las opciones de `.animate()` lo cambian solo para ese widget:

```python
tarjeta.animate("fade_in_up", duration=600, delay=200, easing="ease_out_back")
insignia.animate("pulse", repeat=3)
flecha.animate("nudge_right", on="hover", duration=120)
```

Cuando el cambio deba valer **en todas partes**, define tu animación una vez y usa su nombre:

```python
from pyzed.animation import define_animation

define_animation("subida_lenta", [{"opacity": 0, "y": 40}, {"opacity": 1, "y": 0}],
                 duration=900, easing="ease_out_cubic")
define_animation("fade_in_up", pz.animation.animation("fade_in_up").with_options(duration=500))  # tu valor por defecto

pz.text("Hola").animate("subida_lenta")
```

La lista completa de opciones (`duration`, `delay`, `easing`, `repeat`, `direction`, `fill`,
`on_start`, `on_end`...) está en [animate() y disparadores](/pyzed/es/animation/animate/#opciones-de-tiempo),
y los fotogramas clave, las curvas y la curva por fotograma en
[Fotogramas clave y curvas](/pyzed/es/animation/keyframes/).

## La misma animación en distintos estilos

Pyzed te deja organizar el código de varias formas. Las animaciones funcionan igual en todas, porque
siempre acaban en un widget que devuelve una vista.

### Declarativo: la vista sigue a tu estado

Guardas valores en tu estado y `view()` decide qué animaciones tienen los widgets. Nunca "inicias"
nada: cambias el estado y la pantalla lo sigue. Es el estilo por el que empezar.

```python
class Reproductor(pz.App):
    def __init__(self):
        self.sonando = False
        self.me_gusta = 0

    def view(self):
        return pz.row([
            ui.icon_button("pause" if self.sonando else "play", self.alternar)
                .animate("glow_pulse", active=self.sonando),               # brilla mientras suena
            ui.icon_button("heart", self.gustar)
                .animate("heartbeat", on="manual", key=self.me_gusta),     # late con cada me gusta
            pz.text(f"{self.me_gusta} me gusta").transition(opacity=1 if self.me_gusta else 0.4),
        ], spacing=8, align="center")

    def alternar(self):
        self.sonando = not self.sonando

    def gustar(self):
        self.me_gusta += 1
```

### Imperativo: tu código la inicia

Guardas "mandos" de reproducción y los llamas desde los manejadores, como `boton.play()` en otros
toolkits. En Pyzed esos mandos son `pz.Trigger` (la animación de un widget) y `pz.AnimationPlayer`
(un clip entero):

```python
class Pago(pz.App):
    def __init__(self):
        self.error = pz.Trigger()
        self.hecho = pz.Trigger()
        self.player = pz.AnimationPlayer("pago.pzanim")       # clips guardados desde Pyzed Design o código

    def view(self):
        return pz.column([
            ui.input(self.tarjeta, self.poner_tarjeta).animate("shake", on=self.error),
            pz.icon("circle-check", size=32).animate("pop_in", on=self.hecho),
            pz.text("¡Gracias!").animate(self.player["gracias"]),
            ui.button("Pagar", self.pagar),
        ])

    def pagar(self):
        if not self.valida():
            self.error.fire()
            return
        self.hecho.fire()
        self.player.play("celebrar")
```

### En un componente

Un `pz.Component` guarda su propio estado, así que sus disparadores viven con él (créalos en
`setup()`):

```python
class BotonCopiar(pz.Component):
    texto: str = ""

    def setup(self):
        self.copiado = pz.Trigger()

    def copiar(self):
        self.copiado.fire()
        return pz.Command.copy(self.texto)

    def render(self):
        return pz.row([
            ui.button("Copiar", self.copiar, icon="copy"),
            pz.text("¡Copiado!").animate("fade_in_up", on=self.copiado),
        ], spacing=8, align="center")
```

Todos los componentes aceptan además `animate=` al colocarlos: `BotonCopiar(texto=enlace, animate="fade_in")`.

### Con funciones

Las piezas de una vista pueden ser funciones normales que reciben valores y devuelven widgets. Pásales
el estado (y los disparadores) que necesiten: la animación va en el widget que devuelven.

```python
def punto_estado(conectado: bool) -> pz.Widget:
    punto = pz.container(width=10, height=10).style(background="success" if conectado else "text_muted", radius=5)
    return punto.animate("breathe", active=conectado)


def aviso(texto: str, indice: int) -> pz.Widget:
    return ui.callout("Nuevo", texto).animate("fade_in_left", delay=indice * 60)


class Bandeja(pz.App):
    def view(self):
        return pz.column([
            pz.row([punto_estado(self.conectado), pz.text("Bandeja")], spacing=6, align="center"),
            *[aviso(texto, i) for i, texto in enumerate(self.mensajes)],
        ], spacing=8)
```

## En Pyzed Design

El editor crea las mismas animaciones sin código, y te muestra la línea a llamar cuando el código deba
iniciarlas.

### Un control: la sección Animación

Selecciona un control y abre **Propiedades → Animación**. **Añadir animación** añade una fila; haz clic
en ella para elegir **Cuándo** se reproduce y **qué** animación (los presets de arriba):

| Cuándo (en el editor) | Lo mismo en código |
| --- | --- |
| Al aparecer | `on="mount"` |
| Con el ratón encima / Mientras se pulsa / Mientras tiene el foco | `on="hover"` / `"press"` / `"focus"` |
| Al hacer clic | `on="click"` |
| **Al reproducirla desde el código** | `on=pz.Trigger()` |

Una fila con **Al reproducirla desde el código** espera a tus manejadores. La fila muestra la línea
exacta, con un botón para copiarla:

```python
def sign_in_click(form, event):
    if not comprobar(form.password.text):
        form.password.play_animation()               # reproduce sus animaciones "desde el código"
```

`play_animation()` también acepta cualquier preset, `pz.Animation` o valores, incluso en un control sin
filas, y `stop_animation()` para lo que inició (un bucle, por ejemplo):

```python
form.badge.play_animation("pulse", repeat=3)
form.card.play_animation(scale=1.05, duration=200)   # hasta esos valores y de vuelta
form.spinner.play_animation("spin")
form.spinner.stop_animation()
```

### Muchos controles a la vez: clips

El panel **Animación** (**Ver → Animación**) edita **clips**: líneas de tiempo que mueven varios
controles juntos. Un clip empieza de una de estas dos formas, y el panel dice cuál se aplica:

- activa **⚡ Reproducir al abrir el formulario** (autoplay), o
- llámalo desde un manejador: `form.animations.play("intro")` (el panel muestra esa línea con un botón
  para copiarla).

Consulta [Animaciones y efectos en Pyzed Design](/pyzed/es/editor/animations-and-effects/) para cada
campo del editor, y [El reproductor de animaciones](/pyzed/es/animation/player/) para `play`, `pause`,
`seek` y compañía.

## Chuleta

| Quiero... | Librería | Pyzed Design |
| --- | --- | --- |
| Animar un widget al aparecer | `w.animate("fade_in_up")` | Animación → Al aparecer |
| Reaccionar al puntero | `w.animate("lift", on="hover")` | Animación → Con el ratón encima |
| Reproducirla al hacer clic en él | `w.animate("tada", on="click")` | Animación → Al hacer clic |
| Reproducirla desde un manejador | `on=self.t` + `self.t.fire()` | Al reproducirla desde el código + `form.x.play_animation()` |
| Reproducirla mientras algo está activo | `w.animate("glow_pulse", active=valor)` | Un bucle «desde el código» + `play_animation()` / `stop_animation()` |
| Cambiar un valor con suavidad | `w.transition(opacity=...)` | Estados de estilo (hover, pulsado) |
| Mover muchos widgets juntos | `pz.AnimationPlayer` + `player["objetivo"]` | Panel Animación (clips) |
| Iniciar un clip | `player.play("intro")` | ⚡ autoplay o `form.animations.play("intro")` |
| Crear mi propia animación | `pz.Animation([...])`, `define_animation` | Un clip con pistas y claves |
