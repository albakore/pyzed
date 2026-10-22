---
title: Muchos datos y rendimiento
description: "Rendimiento de GUIs en Python con Pyzed: muestra cientos de miles de filas con listas y tablas virtuales y evita reconstruir vistas con @pz.memo."
sidebar:
  order: 18
---

Pyzed llama a `view()` después de cada mensaje y convierte el árbol de widgets que devuelve en
widgets de Iced. En la mayoría de apps eso tarda mucho menos de un milisegundo. Dos cosas lo
hacen lento: construir **muchas filas** que ni siquiera están en pantalla y reconstruir
**subárboles grandes** que no cambiaron. Pyzed tiene una herramienta para cada una.

## Rápido por defecto

No hace falta activar nada de esto. Pyzed lo hace en todas las apps, siguiendo lo que hacen los editores nativos
rápidos para mantener ágil su interfaz: empezar a dibujar cuanto antes y no repetir trabajo que nadie pidió.

- **Arranque rápido.** `import pyzed` carga solo lo que una app necesita para abrir una
  ventana. El diseñador, la referencia de la API, asyncio y los metadatos del paquete se cargan
  la primera vez que los usas.
- **Fuentes en paralelo.** La búsqueda de las fuentes del sistema empieza en cuanto se importa
  Pyzed, en su propio hilo, mientras Python ejecuta el resto de tus imports.
- **Primero las APIs nativas de la GPU.** El renderizador de GPU arranca Vulkan, Metal o
  DirectX 12. El backend de OpenGL, más lento de arrancar y con más memoria, solo se arranca si
  ninguno de ellos funciona.
- **Árboles de widgets baratos.** Construir contenedores, botones y colores del tema cuesta
  menos, y el núcleo nativo reserva memoria con [mimalloc](https://github.com/microsoft/mimalloc),
  mucho más rápido que el asignador del sistema con los muchos objetos pequeños que crea cada
  `view()`.
- **Piezas compartidas de los componentes.** `ui.button`, `ui.icon_button`, `ui.kbd` y los
  tooltips reutilizan los widgets que solo dependen del tema y de su texto, icono o teclas. Un
  widget no cambia una vez construido, así que una sola copia sirve para todos los botones que
  dicen "Abrir". Una vista de 1.000 botones y etiquetas se construye en un tercio menos de tiempo.
- **El renderizador de CPU cuando no hay una GPU de verdad.** En una máquina virtual, un
  escritorio remoto o un equipo sin driver gráfico, la GPU que ofrecen Vulkan, DirectX u OpenGL es
  una emulación que corre en la CPU (llvmpipe y lavapipe de Mesa, WARP de Windows). Ahí Pyzed
  dibuja con su renderizador de CPU (tiny-skia): es más rápido y usa unos 100 MB menos de memoria.
- **Sin reconstrucciones por teclas que nadie escucha.** Las pulsaciones y liberaciones de
  teclas solo llegan a tu app (y reconstruyen la vista) cuando una ventana define `on_key` u
  `on_key_up`. Escribir en un campo reconstruye la vista una vez por tecla en lugar de tres.
- **Pasar el ratón no cuesta nada.** Los botones, las filas de las listas y todo lo que tiene un
  estilo `hover=` se iluminan bajo el puntero por sí solos, sin mensaje ni un `view()` nuevo. Los
  callbacks del puntero (`on_move`, `on_enter`, `on_exit`, `mouse_move`...) se ejecutan en cuanto se
  mueve el ratón, y cuando uno devuelve [`pz.UNCHANGED`](#callbacks-que-no-cambian-nada-en-pantalla)
  no se reconstruye ni se redibuja nada. Los componentes de la librería y Pyzed Design lo hacen
  siempre que un movimiento no cambia nada.
- **Estilos resueltos una vez.** `widget.style(...)` guarda lo que resuelve según sus propiedades
  y el tema, así que el mismo color de hover en todas las filas de una lista se calcula una vez, no
  una vez por fila en cada `view()`.
- **Markdown analizado una vez.** Un chat o documento largo en bloques `pz.markdown` se analiza la
  primera vez que se dibuja y se conserva mientras está en pantalla, tenga los bloques que tenga.
- **Las listas largas construyen lo visible.** `ui.table`, `ui.virtual_list` y el List box de Pyzed
  Design (desde 50 elementos) solo construyen las filas que se ven.
- **Los componentes se dibujan cuando cambian.** Un [`pz.Component`](#componentes-que-solo-se-dibujan-cuando-cambian)
  cuyas props, estado y contexto son los mismos que la vez anterior devuelve su último dibujo en
  vez de volver a ejecutar `render()`. Una vista de 500 filas de componentes se reconstruye en
  4 ms en lugar de 26 ms cuando cambia una.
- **Y los controles de los formularios.** Un formulario hecho en Pyzed Design, en marcha o en el
  lienzo del diseñador, solo vuelve a construir los controles cuyas propiedades cambiaron. El
  diseñador hace lo mismo con su consola, su árbol y su caja de herramientas: su vista pasó de 21 ms
  a 4,5 ms con un formulario de 85 controles y 400 líneas de log.
- **Los archivos se listan fuera del hilo de la interfaz.** El diálogo Abrir, la lista `@` del
  agente y el selector de archivos de los shaders leen la carpeta del proyecto una vez y luego la
  actualizan en un hilo aparte, así que escribir en ellos nunca espera al disco.

Medido con la [app del benchmark](/pyzed/es/why/benchmarks/) (ventana de 640×480, una etiqueta
y un botón por fila, Xvfb sin GPU, medianas de 5 arranques) en la misma máquina:

| | Antes | Ahora |
| --- | --- | --- |
| `import pyzed` | 178 ms | 78 ms |
| Primer frame, 10 filas | 454 ms | 323 ms |
| Actualizar 1.000 filas | 40,7 ms | 34,9 ms |
| Memoria, 10 filas (RSS) | 174 MB | 146 MB |

:::note
`WGPU_BACKEND=gl` (o `vulkan`, `metal`, `dx12`) sigue eligiendo el backend de GPU a mano,
`ICED_BACKEND=wgpu` mantiene el renderizador de GPU aunque la GPU sea emulada (lo que necesitan los
[shaders](/pyzed/es/shading/shaders/)), e `ICED_BACKEND=tiny-skia` usa siempre el renderizador de CPU.
:::

## Listas y tablas virtuales

Una lista virtual solo construye las filas visibles. Las filas se construyen cuando entran en
la vista y se descartan cuando salen, así que una lista de un millón de elementos cuesta lo
mismo que una de cincuenta.

```python
import pyzed as pz
from pyzed import ui

class Logs(pz.App):
    def __init__(self):
        self.lines = [f"[{i:06}] petición atendida" for i in range(500_000)]

    def view(self):
        return ui.virtual_list(
            self.lines,
            lambda line: pz.text(line, font="mono", size=12),
            item_height=20,
            id="logs",
        )
```

- [`ui.virtual_list(items, render)`](/pyzed/es/library/virtual-list/) es una lista con scroll y
  con el tema: `render(elemento)` devuelve el widget de un elemento.
- [`ui.table`](/pyzed/es/library/table/) también está virtualizada: pásale todas tus filas.
- [`pz.virtual_column(count, item, item_height=...)`](/pyzed/es/reference/widgets/#virtual_column)
  es la pieza básica: `item(índice)` devuelve la fila `índice`. Ponla dentro de cualquier
  `pz.scrollable`.

Todas las filas tienen la misma altura (`item_height`), y por eso Pyzed sabe dónde va cada fila
sin construirla. Para ir a la fila `i`, desplaza el `id` de la lista hasta
`i * (item_height + spacing)`:

```python
pz.Command.scroll_to("logs", 0, 1_000 * 20)   # fila 1000
```

Medido con una tabla de 200 000 filas, construir la vista pasó de 3,7 s a 0,2 ms.

:::tip
`items` y `rows` deberían ser listas (u otras secuencias): otros iterables se copian a una lista
en cada `view()`. Ordenar una tabla enorme en cada `view()` es el coste que queda; guarda las
filas ya ordenadas en tu estado u ordénalas en una función `@pz.memo`.
:::

## Callbacks que no cambian nada en pantalla

Un mensaje hace que Pyzed vuelva a llamar a `view()` y a calcular el layout y dibujar la ventana.
Eso es lo que quieres tras un clic, pero un puntero que se mueve sobre una vista grande manda un
mensaje por movimiento. Cuando un callback solo recuerda algo que no se dibuja, devuelve
`pz.UNCHANGED`: el mensaje termina ahí, sin `view()`, sin layout y sin redibujar.

```python
class Lienzo(pz.App):
    def __init__(self):
        self.puntero = (0, 0)   # se usa al abrir el menú, no se dibuja
        self.resaltado = None   # se dibuja resaltado

    def movido(self, x, y):
        self.puntero = (x, y)
        resaltado = self.elemento_en(x, y)
        if resaltado == self.resaltado:
            return pz.UNCHANGED  # nada en pantalla depende del movimiento
        self.resaltado = resaltado  # esto sí se dibuja: se reconstruye la vista

    def view(self):
        return pz.mouse_area(self.tablero(), on_move=self.movido)
```

Sirve en los callbacks del puntero (`on_move`, `on_enter`, `on_exit` de `pz.mouse_area` y los
eventos `mouse_move`, `mouse_enter`, `mouse_leave`... de `.on(...)`), en los mensajes enviados con
`pz.post` y en lo que devuelva tu `update()`. Devuélvelo solo cuando no cambió nada de lo que leen
`view()`, `title` o `subscriptions()`: la ventana sigue mostrando lo que mostraba.

:::tip
Para resaltar algo bajo el puntero no hace falta ningún callback: `.style(hover={"background": "ghost_hover"})`
lo dibuja el propio widget nativo.
:::

## Componentes que solo se dibujan cuando cambian

Cada [componente](/pyzed/es/guides/components/) guarda su último dibujo. En el siguiente `view()`
se reutiliza, sin llamar a `render()`, mientras todo esto siga igual:

- sus **props** y su **estado** (cualquier atributo que pongas en `self`). Las listas, dicts, sets y
  objetos normales se comparan por su contenido, así que `self.items.append(x)` se nota;
- los valores que lee con `pz.use_context` (o `self.context`);
- el tema, el idioma, el tamaño de la ventana y la hoja de estilos;
- los componentes que dibuja dentro: cuando un hijo cambia su estado, se vuelven a dibujar también
  todos los componentes que lo contienen.

Los callbacks que pasas como props o creas en `render()` no estorban: se comparan por su código y
los valores que capturaron, así que un `lambda: self.pick(i)` nuevo con el mismo `i` cuenta como
el mismo callback.

```python
class Row(pz.Component):
    name: str = ""
    stars: int = 0

    def render(self):  # solo se ejecuta si cambian name, stars o el Rating de dentro
        return pz.row([ui.label(self.name), Rating(value=self.stars)])
```

Dos casos necesitan ayuda, porque el componente no puede ver qué cambió:

- `render()` lee algo que no es ni prop, ni estado, ni contexto: la hora, una variable global,
  datos que cambia otro objeto. Llama a `self.refresh()` cuando cambie, o pon `cache = False` en la
  clase para dibujarlo en cada `view()` (los medidores en vivo lo hacen).
- Un valor cuyos cambios no se pueden comparar (un array de NumPy, un recurso nativo, un grafo de
  objetos enorme) desactiva la caché de ese componente por sí solo: se dibuja siempre, como antes.

Un componente que recibe widgets como `children` se dibuja cada vez que el padre los vuelve a
construir, porque son widgets nuevos; no cuesta más que dibujarlo.

## Hilos

Tu `view()`, tu `update()` y tus callbacks se ejecutan en el hilo de la interfaz, de uno en uno,
como en cualquier toolkit nativo. Python ejecuta un solo hilo a la vez de todos modos (el GIL), así
que la interfaz más rápida es la que hace menos en ese hilo, y para eso están las cachés de arriba.
Lo que Pyzed hace en otros hilos:

- Iced calcula el layout y renderiza el frame en Rust, fuera del GIL, y la GPU lo dibuja.
- Las fuentes del sistema se buscan, los archivos del proyecto se listan y los agentes, servidores
  de lenguaje y builds del diseñador corren en hilos aparte.
- Tu trabajo lento también va ahí: [tareas async](/pyzed/es/guides/async/) o un `threading.Thread`
  que envía su resultado con `pz.post(...)`.

## Subárboles memoizados

`@pz.memo` guarda lo que devuelve una función según sus argumentos. Mientras los argumentos
sean iguales, el siguiente `view()` reutiliza el mismo árbol de widgets en vez de construirlo
otra vez:

```python
@pz.memo
def sidebar(files: tuple, selected: str):
    return pz.column([ui.list_item(f, icon="file", selected=f == selected) for f in files])

class Editor(pz.App):
    def view(self):
        return pz.row([sidebar(tuple(self.files), self.selected), self.editor()])
```

Cómo se comparan los argumentos:

| Argumento | Se compara por |
| --- | --- |
| Números, textos, tuplas, dataclasses congeladas... | Valor (su hash). |
| Listas, dicts y sets | Su contenido. |
| Cualquier otra cosa (tus objetos, `self`) | Identidad: modificarlo sin reemplazarlo no refresca la caché. |

El tema y el idioma actuales siempre forman parte de la clave, así que al cambiarlos se
reconstruyen todos los subárboles memoizados.

:::caution
Una función memoizada solo ve sus argumentos. Si lee `self.algo` o una variable global, el
subárbol guardado conserva el valor antiguo hasta que cambien los argumentos. Pasa todo lo que
usa, o un número de versión que incrementes cuando cambien los datos.
:::

- `@pz.memo(maxsize=256)` guarda más resultados (64 por defecto). Es útil en una función que se
  llama una vez por fila, como el `render` de una lista virtual.
- `funcion.cache_clear()` vacía la caché de una función y `pz.clear_memos()` la de todas.
- `pz.memo_stats()` devuelve `{"hits": ..., "misses": ...}` para comprobar que un subárbol se reutiliza.

## Otros consejos

- Deja `view()` sin trabajo lento: carga archivos, consulta bases de datos y ordena datos en los
  handlers o en [tareas async](/pyzed/es/guides/async/), y guarda los resultados en tu estado.
- Dibuja miles de formas con un solo [canvas](/pyzed/es/guides/canvas/) en vez de miles de widgets.
- Las suscripciones `pz.every` llaman a `view()` en cada tic: detenlas cuando nada se mueve.
