---
title: "Reglas de diseño para agentes"
description: "Reglas de UI y UX para apps de escritorio profesionales con Pyzed: patrones, jerarquía, espaciado, tipografía, los tokens de color de Pyzed Dark y Light, estados, feedback, formularios, accesibilidad, movimiento y textos."
sidebar:
  order: 3.2
---

<!-- Generated from python/pyzed/mcp/design.es.md by docs/scripts/gen_ai_guides.py: edit the guide, not this page. -->

:::tip
Los agentes de IA reciben esta página del servidor MCP con `get_guide("design")`, y `review_design` comprueba el código con ella. Sirve igual para personas.
:::

Cómo diseñar pantallas que se vean y se sientan como un producto profesional: los fundamentos de UI y UX
(jerarquía, espaciado, tipografía, color, estados, feedback, accesibilidad, textos) y cómo se traduce cada uno a
los componentes, estilos y tokens de tema de Pyzed. Sigue estas reglas en cada pantalla, luego pasa
`review_design` sobre el código y mira `screenshot` en `"Pyzed Dark"` y en `"Pyzed Light"`.

## 1. Empieza por la tarea del usuario, no por los widgets

1. **Di el trabajo de la pantalla en una frase** ("encontrar una factura y volver a enviarla"). Todo lo que hay en
   la pantalla ayuda a ese trabajo o va a otro sitio (un menú, una página de ajustes, otra pestaña).
2. **Elige la acción principal.** Una por pantalla o diálogo. Lleva el botón más fuerte (`variant="solid"`); el
   resto es secundario (`"filled"`), terciario (`"ghost"`/`"subtle"`) o un elemento de menú.
3. **Usa un patrón conocido** antes de inventar uno. Los usuarios ya los conocen, y
   `list_examples(kind="blocks")` tiene cada uno como pantalla probada:

| La tarea | Patrón | Parte de |
| --- | --- | --- |
| Recorrer elementos y trabajar en uno | Lista + detalle (barra lateral de 220–280 px, el contenido llena) | `blocks/file_explorer`, `blocks/chat` |
| Comparar muchos registros | Tabla con barra de herramientas (búsqueda, filtros, acciones en lote) | `blocks/data_table` |
| Vigilar cifras | Panel: una fila de `ui.stat`, luego gráficos, luego una tabla | `blocks/dashboard` |
| Cambiar preferencias | `ui.settings_group` con filas `ui.field`, guardado al instante | `blocks/settings` |
| Entrar, registrarse, un formulario corto | Una columna centrada de 320–420 px | `blocks/login` |
| Primer uso o un proceso largo | Pasos con progreso y Atrás / Siguiente | `blocks/onboarding` |
| Herramientas sobre un documento (editores, IDEs) | `ui.workspace`: barra de título, paneles, pestañas, barra de estado, paleta de comandos | `new_app(layout="workspace")` |
| Trabajo en columnas | Tablero de tarjetas | `blocks/kanban` |

4. **Diseña todos los estados de la pantalla** (sección 7) antes de pulir el ideal.

## 2. Jerarquía visual

La vista debe ir primero a lo más importante y luego a lo siguiente. La jerarquía sale, de más a menos fuerte,
de: **tamaño, peso, contraste de color, posición y espacio**. Usa los menos niveles posibles.

- **Un título por pantalla**: `ui.heading(..., level=1)` (26 px) para una página, `level=2` (20 px) para una
  sección, `level=3` (16 px) para un grupo. En herramientas densas (paneles, inspectores) `ui.panel_header`
  reemplaza a los títulos.
- **El texto de cuerpo** es `ui.label` en `"md"` (13,5 px, el tamaño de Zed). El texto secundario usa
  `color="text_muted"`, nunca solo un tamaño menor. Leyendas y metadatos usan `size="sm"` (12 px) y `"text_muted"`.
- **Énfasis por contraste, no por decoración**: un peso semibold o el color `text` frente a `text_muted` basta. No
  subrayes, no pongas todo en negrita, no uses más de dos pesos en una pantalla.
- **Arriba a la izquierda se lee primero** (en idiomas de izquierda a derecha): el título y el contenido principal
  van ahí; la acción principal va donde termina el flujo (abajo a la derecha en un diálogo o formulario, arriba a
  la derecha en la barra de una página).
- **Agrupa por proximidad**: lo relacionado está cerca y lo no relacionado lejos. El espacio separa mejor que las
  líneas; añade `ui.divider()` solo donde el espacio no alcanza.

## 3. Espaciado y maquetación

Usa una **rejilla de 4 px** y una escala corta. La coherencia importa más que los números exactos.

| Token | px | Úsalo para |
| --- | --- | --- |
| `2xs` | 2 | Icono y su insignia, teclas muy juntas |
| `xs` | 4 | Dentro de controles compactos, entre un icono y su etiqueta |
| `sm` | 8 | Entre controles relacionados de una fila, relleno de elementos de lista |
| `md` | 12 | Entre campos de un formulario, dentro de tarjetas en pantallas densas |
| `lg` | 16 | Relleno de paneles y tarjetas, entre grupos de campos |
| `xl` | 24 | Entre secciones, relleno de una página o diálogo |
| `2xl` | 32 | Entre regiones grandes, relleno de una página amplia |
| `3xl` | 48 | Aire de portadas y estados vacíos |

Reglas:

- **Espacio interior ≤ espacio exterior**: el relleno de una tarjeta es menor que el hueco entre tarjetas; una
  etiqueta está más cerca de su campo que del campo anterior.
- **Alinea a pocos bordes.** Todos los bloques de una columna comparten el borde izquierdo; los campos de un
  formulario tienen el mismo ancho. Las alineaciones mezcladas parecen un accidente.
- **Ancho de lectura**: textos y formularios de 320–720 px (`max_width`). No estires un párrafo o un formulario en
  una ventana de 1600 px: céntralo o da el espacio sobrante a una lista o un lienzo.
- **Densidad**: las herramientas (editores, inspectores, paneles para expertos) son compactas como Zed: controles
  `"sm"`/`"md"`, relleno de 12–16 px. Las pantallas para todo el mundo (bienvenida, inicio de sesión, ajustes) son
  holgadas: controles `"md"`/`"lg"`, relleno de 24–32 px. Una densidad por pantalla.
- **Marco fijo, contenido flexible**: barras laterales e inspectores con ancho fijo (`width=240`, redimensionable
  con `pz.split`), el contenido con `"fill"`. Fija `App.min_size` para que la maquetación nunca se rompa.
- **Ventanas adaptables**: usa reglas `@media (max_width: ...)` o `pz.media()` para convertir la barra lateral en
  un menú, apilar columnas y ocultar paneles secundarios por debajo de ~720 px.
- **Maqueta con cajas**: `pz.box(display="flex"|"grid", gap=...)` y clases de hoja de estilos, nunca widgets de
  espacio con números mágicos. Una fila flex (una barra de herramientas, una fila de lista) dentro de una columna
  lleva `height="shrink"`; si no, las filas se reparten el alto de la columna y se separan.

## 4. Tipografía

Pyzed trae IBM Plex Sans (interfaz) e IBM Plex Mono (código). La escala de `ui.label(size=...)`:

| Tamaño | px | Uso |
| --- | --- | --- |
| `xs` | 11 | Insignias, teclas, metadatos de tablas densas |
| `sm` | 12 | Leyendas, texto de ayuda, barra de estado, cabeceras de tabla |
| `md` | 13,5 | Texto de cuerpo, controles, elementos de lista (por defecto) |
| `lg` | 16 | `heading(level=3)`, entradillas, pantallas holgadas |
| `xl` | 20 | `heading(level=2)`, títulos de sección y de diálogos grandes |
| `2xl` | 26 | `heading(level=1)`, títulos de página, la cifra de un `ui.stat` |

- Usa los tamaños con nombre, no píxeles sueltos: una pantalla con textos de 13, 14, 15 y 17 px parece improvisada.
- **Mayúscula solo al principio de la frase** ("Guardar cambios", no "Guardar Cambios" ni "GUARDAR CAMBIOS").
  Mayúsculas completas solo en antetítulos pequeños, con espaciado, y pocas veces.
- Líneas de 45–90 caracteres; el texto largo se ajusta (`wrap=True`) dentro de una caja de ancho limitado.
- **Números**: alinea a la derecha las columnas numéricas, mismos decimales en toda la columna, la unidad en la
  cabecera (`"Tamaño (MB)"`), y `mono=True` para ids, hashes, rutas y código.
- Nunca texto de menos de 11 px, ni `text_placeholder`/`text_disabled` para información (son tenues a propósito).

## 5. Color con tokens del tema

Los colores salen del tema, así la app sigue a Pyzed Dark, Pyzed Light y cualquier tema que elija el usuario.
**Nunca escribas un color hex fijo** en una vista o una hoja de estilos: pasa el nombre de un token
(`background="panel"`, `color="text_muted"`) o lee `pz.theme.current().<token>` en código de dibujo.

| Rol | Token | Pyzed Dark | Pyzed Light | Uso |
| --- | --- | --- | --- | --- |
| Fondo de la app | `background` | `#0d0e11` | `#f6f7f9` | Detrás de todo, huecos entre paneles |
| Marco | `panel` | `#191c22` | `#f1f3f6` | Barras laterales, de título y de estado, paneles |
| Contenido | `surface` / `editor` | `#14161b` | `#ffffff` | El área de trabajo, campos, documentos |
| Elevado | `elevated` | `#222630` | `#ffffff` | Tarjetas, popovers, menús, diálogos (con `shadow`) |
| Hover | `element_hover` / `ghost_hover` | `#222630` | `#e7eaf0` | Filas y botones ghost bajo el puntero |
| Líneas | `border` / `border_variant` | `#2a2f39` | `#dce0e7` | Separadores, bordes de tarjetas y campos |
| Foco | `border_focused` | `#8b83ff` | `#4f46e5` | Anillos de foco, campos activos |
| Texto | `text` | `#e7e9ee` | `#14161b` | Texto e iconos principales |
| Texto secundario | `text_muted` | `#9aa1ae` | `#576070` | Descripciones, metadatos, pestañas inactivas |
| Placeholder / desactivado | `text_placeholder` / `text_disabled` | `#5c6370` | `#9aa1ae` | Solo placeholders y controles desactivados |
| Marca / principal | `accent` (+ texto `on_accent`) | `#5b50f0` | `#4f46e5` | El botón principal, la selección, enlaces, progreso |
| Acento como texto | `text_accent` | `#8b83ff` | `#4f46e5` | Enlaces y texto de acento sobre superficies oscuras |
| Estado | `error`, `warning`, `success`, `info` | `#f26d85` `#f5a524` `#3fcf8e` `#6fc3ff` | `#d0344f` `#b45f00` `#12805c` `#0b6bcb` | Solo para estados: validación, avisos, variaciones |
| Instrumentos | `led`, `display`, `display_text` | ámbar | ámbar | LEDs y pantallas LCD (`ui.led`, `ui.lcd`), nunca para la marca |

Reglas:

- **Capas**: `background` → `panel` → `surface` → `elevated`. Cada paso está una capa más cerca del usuario. No
  pongas una tarjeta del mismo color que su fondo sin borde.
- **60-30-10**: ~60 % superficies neutras, 30 % texto y líneas, como mucho 10 % acento. Si más de una cosa por
  pantalla lleva el color de acento, nada destaca.
- **Los colores de estado significan estado.** Rojo solo para errores y acciones destructivas, verde para éxito,
  ámbar para avisos. No los uses como decoración ni para categorías (usa `players` o insignias neutras).
- **Nunca solo con color**: acompáñalo de un icono, un texto o una forma (`ui.callout` y `ui.badge` lo hacen).
- **Contraste**: el texto de cuerpo necesita 4,5:1 contra su fondo; el texto grande (≥ 18 px, o 14 px en negrita)
  y los iconos 3:1. `text` y `text_muted` lo cumplen en todas las superficies de Pyzed; `text_placeholder` no
  (2,3–3:1), así que nunca se usa para contenido real. En Pyzed Light los colores de estado dan ~4,4:1 sobre
  `panel`: pon el texto de estado sobre `surface` o acompáñalo de un icono.
- **Los dos temas**: revisa cada pantalla con `screenshot(code, theme="Pyzed Light")` y `theme="Pyzed Dark"`, y
  ofrece `pz.themes.auto()` (sigue al sistema) como tema de la app.
- Sombras solo en capas elevadas (`elevated`): el token `shadow="shadow"`, nunca negro en temas claros.
- Radio de las esquinas: `theme.radius` (8 en los temas Pyzed) para tarjetas y diálogos, `theme.radius_sm` (5)
  para controles; las esquinas anidadas son menores que las de su padre.

## 6. Componentes y acciones

- **Jerarquía de botones**: un `variant="solid"` (principal) por vista; `"filled"` para acciones secundarias,
  `"ghost"`/`"subtle"` para terciarias y barras de herramientas, `variant="error"` (o `ui.confirm(danger=True)`)
  para las destructivas. Los botones desactivados deberían ser raros: mejor activos y que expliquen qué falta.
- **Orden de los botones**: en diálogos y formularios, el secundario a la izquierda y el principal a la derecha,
  abajo a la derecha (`Cancelar` · `Guardar`). El mismo orden en todas las pantallas.
- **Etiquetas = verbo + objeto**: "Crear proyecto", "Enviar factura", "Eliminar 3 archivos". Nunca "OK",
  "Enviar" a secas, "Sí" o "Haz clic aquí": los botones de un diálogo se entienden sin leer la pregunta.
- **Botones solo con icono** (`ui.icon_button`) siempre con `tooltip=` y, si hay atajo, `keys=`. Úsalos en barras
  de herramientas para acciones frecuentes con iconos conocidos; lo demás lleva texto.
- **Tamaño**: los objetivos interactivos miden al menos 24 px de alto (`ui.button` `"md"` mide 28 px); deja 8 px
  entre objetivos vecinos.
- **El control adecuado**: 2–5 opciones exclusivas → `ui.segmented` o `ui.radio_group`; más → `ui.select`;
  sí/no que se aplica al momento → `ui.switch`; sí/no que se aplica al guardar → `ui.checkbox`; un número en un
  rango → `ui.slider` con un `ui.number_field`; fechas → `ui.DatePicker`; muchos elementos → `ui.search_input` +
  una lista.
- **Reutiliza `pz.ui`**: sus componentes ya tienen hover, pulsado, foco, desactivado y carga en los dos temas.
  Rehaz uno con primitivas `pz.*` solo si nada encaja, y entonces dale todos los estados (sección 7).

## 7. Estados: diséñalos todos

**Cada control** tiene: normal, hover, pulsado, foco (anillo visible para el teclado), desactivado, cargando,
seleccionado e inválido. `pz.ui` los dibuja; en tus propias cajas con estilo usa
`.style(hover={...}, pressed={...}, focus={...}, transition=120)` o reglas `":hover"` en la hoja de estilos.

**Cada región que muestra datos** tiene cinco estados. Escribe cada uno:

| Estado | Qué ve el usuario | En Pyzed |
| --- | --- | --- |
| Cargando | Dónde estará el contenido y que está llegando | `ui.spinner()` (≤ 2 s), `ui.progress(None)`, o `ui.progress(value)` con etiqueta para trabajos largos |
| Vacío | Por qué está vacío y la acción que lo llena | `ui.empty_state(title, description, icon=, actions=[ui.button(..., variant="solid")])` |
| Error | Qué falló, por qué si se sabe, y cómo recuperarse (Reintentar) | `ui.callout(title, description, tint="error", actions=[...])`; `ui.error_boundary` alrededor de partes delicadas |
| Parcial | Algunos resultados, y que hay más o que algunos fallaron | Una fila al pie, un contador con `ui.badge`, un `ui.callout` de aviso |
| Ideal | El contenido | Listas, tablas, tarjetas |

Diseña también: el primer uso (sin datos ni ajustes), una búsqueda sin resultados ("Sin resultados para "x"", con
un botón Limpiar), sin conexión / sin permiso, y valores muy largos o ausentes (recorta, muestra "—").

## 8. Feedback y tiempos de respuesta

| Espera | Regla |
| --- | --- |
| < 100 ms | Se siente instantáneo: solo actualiza la vista. |
| 100 ms – 1 s | Muestra que algo pasa: `loading=True` en el botón, el estado pulsado. |
| 1 – 10 s | Un spinner o un `ui.progress` indeterminado junto a lo que carga, y la interfaz sigue usable. |
| > 10 s | Un progreso determinado con lo que ocurre ("Subiendo 3 de 12") y un botón Cancelar. |

- El trabajo lento nunca va en `view()` ni bloquea un callback: devuelve una corrutina, usa `Command.perform` o un
  `pz.Worker` (mira `get_guide("app-architecture")`).
- **Confirma el resultado donde ocurrió**: la fila se actualiza, el campo muestra un check. Usa un `ui.toast`
  (`kind="success"`, se cierra solo) para acciones cuyo resultado no se ve, y un toast de error o un callout que
  queda hasta que se cierra para los fallos.
- **Mejor deshacer que confirmar**: elimina al momento y ofrece "Deshacer" en un toast. Pregunta con `ui.confirm`
  solo en acciones destructivas que no se pueden deshacer, y nombra el objeto ("¿Eliminar "Informe T3"? No se
  puede deshacer.") con un botón de peligro con la acción ("Eliminar informe").
- **No pierdas trabajo**: avisa antes de cerrar con cambios sin guardar (`ui.unsaved_changes`, `App.on_close`),
  guarda borradores y conserva lo que escribió el usuario cuando una petición falla.
- Teclado: `Enter` envía el formulario con foco, `Esc` cierra el diálogo o popover de arriba, los atajos se
  muestran con `keys=` en botones, menús y tooltips.

## 9. Formularios

- **Una columna**, etiquetas encima o al lado de los campos (`ui.field(title, control)`), en el orden en que
  piensa la gente (nombre antes que email antes que contraseña). Agrupa los formularios largos con
  `ui.settings_group` o títulos.
- Cada campo tiene una **etiqueta visible**: el placeholder es un ejemplo (`"tu@ejemplo.com"`), no la etiqueta.
- Marca la excepción: si casi todos los campos son obligatorios, marca los opcionales ("Opcional"), y al revés
  (`required=True` añade `*`).
- **Valida al enviar y luego en vivo**: muestra los errores tras el primer envío o cuando un campo pierde el foco,
  nunca mientras el usuario escribe por primera vez. El error va bajo su campo (`ui.field(error=...)` más
  `invalid=True` en el control) y dice cómo arreglarlo ("Escribe un email como nombre@ejemplo.com").
- Pon el foco en el primer campo al abrir el formulario (`Command.focus(id)`) y en el primer campo inválido tras
  un envío fallido.
- Valores por defecto sensatos, máscaras solo cuando ayudan (fechas, números), y nunca vacíes el formulario tras un
  error.
- Mientras envía: el botón principal muestra `loading=True`; el formulario sigue legible.

## 10. Navegación y arquitectura de la información

- **¿Dónde estoy?** Lo dicen el elemento seleccionado en la barra lateral, la pestaña activa y el título de la
  ventana. `ui.breadcrumbs` para jerarquías profundas.
- **Poco profunda y predecible**: como mucho tres niveles; cada cosa siempre en el mismo sitio.
- **Usuarios avanzados**: cada comando se alcanza con el teclado, la paleta de comandos (`ui.command_palette`) y
  los menús (`frame_menus`), no solo con botones. Muestra los atajos con `keys=`.
- Los diálogos son para tareas cortas y concretas que bloquean el resto; lo más largo es una página o un panel.
  Nunca apiles diálogos. Popovers y menús se cierran con `Esc` y con un clic fuera.
- Recuerda dónde estaba el usuario: la pestaña elegida, el tamaño de los paneles divididos, los filtros y el
  tamaño de la ventana (`pz.Settings`).

## 11. Accesibilidad

- **Primero el teclado**: el orden de `Tab` sigue el orden de `view()`, así que construye el árbol en orden de
  lectura. Los controles propios usan `pz.focusable(...)`; da atajos a las acciones importantes (los botones
  normales aún no toman el foco).
- **Foco visible**: conserva los anillos de foco que dibuja `pz.ui`; los focusables propios pasan
  `ring_color=theme.border_focused`.
- **Contraste** como en la sección 5, y nunca solo color.
- **Texto, no solo iconos**: Pyzed aún no admite lectores de pantalla, así que el significado tiene que estar en
  texto visible (etiquetas, tooltips, estados vacíos).
- **Movimiento**: las animaciones respetan el ajuste de reducir movimiento del sistema automáticamente
  (`pz.system_reduced_motion()`); no transmitas información solo con movimiento.
- **Sitio para otros idiomas**: el español y el alemán ocupan ~30 % más que el inglés. No fijes el ancho de botones
  y etiquetas al texto en inglés; usa `pz.t()` para cada texto (`get_guide("i18n")`).
- Objetivos ≥ 24 px, `App.min_size` fijado, y la interfaz escala con `App.scale` y el DPI del sistema.

## 12. Movimiento

- El movimiento explica cambios: algo aparece (fundido + un pequeño desplazamiento), se mueve (a su nuevo sitio) o
  reacciona (pulsación). Nunca decores con movimiento que se repite sin fin.
- Duraciones: 100–150 ms para hover y pulsación (`transition=120`), 150–250 ms para popovers, toasts y paneles,
  250–400 ms para transiciones de página. Entra con ease-out y sale con ease-in.
- Anima `opacity` y posición, no propiedades que rehacen la maquetación, y solo lo que cambió (`pz.presence` para
  elementos que entran y salen de una lista, `pz.stagger` para una lista que aparece).

## 13. Textos (UX writing)

- Cortos, concretos, con las palabras del usuario. Lo importante al principio: "Facturas: 3 vencidas".
- **Errores**: qué pasó + por qué (si se sabe) + qué hacer. "No se pudo guardar el archivo. El disco está lleno.
  Libera espacio e inténtalo de nuevo." Nunca culpes al usuario ni muestres una excepción cruda como único mensaje
  (pon el detalle tras un botón Detalles, como `ui.error_card`).
- **Los estados vacíos invitan a actuar**: "Aún no hay proyectos" + "Crea un proyecto para empezar." +
  [Crear proyecto].
- Vocabulario coherente: si en una pantalla es un "proyecto", en otra no es un "espacio de trabajo".
- Fechas y números en el formato del usuario; tiempos relativos ("hace 2 min") con la hora exacta en un tooltip.

## 14. Una pantalla con todos sus estados

Una pantalla de lista bien hecha: una acción principal, jerarquía por tamaño y color, la rejilla de 4 px, solo
tokens, y los estados de carga, error, vacío e ideal.

```python
import pyzed as pz
from pyzed import ui

pz.stylesheet({
    ".page": {"padding": 24, "width": "fill", "height": "fill", "background": "surface"},
    ".row": {"padding": (8, 12), "radius": 6, "transition": 120},
    ".row:hover": {"background": "element_hover"},
})


class Invoices(pz.App):
    title = "Invoices"
    size = (640, 360)
    min_size = (420, 280)

    def __init__(self):
        self.state = "ready"            # "loading" | "error" | "ready"
        self.query = ""
        self.invoices = [("INV-1042", "Acme Corp", 1250.0, "Overdue"), ("INV-1043", "Globex", 380.5, "Paid")]

    def visible(self):
        q = self.query.lower()
        return [i for i in self.invoices if q in i[0].lower() or q in i[1].lower()]

    def toolbar(self):
        return pz.box(
            ui.heading("Invoices", level=2),
            pz.hspace(),
            ui.search_input(self.query, lambda v: setattr(self, "query", v), width=220),
            ui.button("New invoice", lambda: None, icon="plus", variant="solid", keys="ctrl-n"),
            display="flex", gap=8, align="center", height="shrink",
        )

    def row(self, number, client, amount, status):
        tint = {"Overdue": "error", "Paid": "success"}.get(status, "info")
        return pz.box(
            ui.label(number, mono=True, color="text_muted", size="sm"),
            ui.label(client, width="fill"),
            ui.badge(status, tint=tint),
            ui.label(f"{amount:,.2f} €", width=96, align_x="end"),
            display="flex", gap=12, align="center", height="shrink", class_="row",
        )

    def body(self):
        if self.state == "loading":
            return pz.center(ui.spinner(size=20))
        if self.state == "error":
            return ui.callout("Couldn't load the invoices", "Check your connection and try again.", tint="error",
                              actions=[ui.button("Retry", lambda: None, variant="filled")])
        rows = self.visible()
        if not rows and self.query:
            return ui.empty_state(f"No results for “{self.query}”", "Try another client or invoice number.",
                                  icon="search", actions=[ui.button("Clear search",
                                                                    lambda: setattr(self, "query", ""))])
        if not rows:
            return ui.empty_state("No invoices yet", "Create your first invoice to start getting paid.",
                                  icon="file-text", actions=[ui.button("New invoice", lambda: None,
                                                                       variant="solid")])
        return pz.scrollable(pz.box(*[self.row(*i) for i in rows], gap=2))

    def view(self):
        return pz.box(self.toolbar(), self.body(), gap=16, class_="page")


pz.run(Invoices)
```

## 15. Un formulario bien hecho

Etiqueta en cada campo, una acción principal abajo a la derecha, errores bajo sus campos tras enviar y un estado
de carga mientras guarda.

```python
import pyzed as pz
from pyzed import ui


class NewProject(pz.App):
    title = "New project"
    size = (460, 340)

    def __init__(self):
        self.name, self.template, self.private = "", "Empty", True
        self.errors, self.saving = {}, False

    def validate(self):
        errors = {}
        if not self.name.strip():
            errors["name"] = "Give the project a name."
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors["name"] = "Use letters, numbers, - and _ only."
        return errors

    def create(self):
        self.errors = self.validate()
        if self.errors:
            return pz.Command.focus("name")
        self.saving = True          # the real work goes in a coroutine or Command.perform

    def view(self):
        return pz.box(
            ui.heading("Create a project", level=3),
            ui.label("You can change these later in Settings.", color="text_muted", size="sm"),
            ui.field("Name", ui.input(self.name, lambda v: setattr(self, "name", v), placeholder="my-app", id="name",
                                      invalid="name" in self.errors, on_submit=self.create),
                     error=self.errors.get("name"), required=True, vertical=True),
            ui.field("Template", ui.select(["Empty", "Dashboard", "Editor"], self.template,
                                           lambda v: setattr(self, "template", v), width="fill"), vertical=True),
            ui.field("Private", ui.switch(self.private, lambda v: setattr(self, "private", v)),
                     description="Only you can open it."),
            pz.vspace(),
            pz.box(pz.hspace(), ui.button("Cancel", lambda: None, variant="ghost"),
                   ui.button("Create project", self.create, variant="solid", loading=self.saving),
                   display="flex", gap=8),
            gap=12, padding=24, height="fill",
        ).style(background="surface")


pz.run(NewProject)
```

## 16. Antes de entregar: la revisión de diseño

Pasa `review_design(code)` y arregla lo que diga; luego revisa a ojo con `screenshot` (o `screenshot_project`) en
los dos temas y a un tamaño estrecho y otro ancho:

1. ¿Hay exactamente una acción principal por vista, y está donde termina el flujo?
2. ¿Se distinguen de un vistazo el título, el contenido y el texto secundario (prueba de entrecerrar los ojos)?
3. ¿Todo el espaciado está en la escala de 4 px, y el espacio interior es menor que el exterior?
4. ¿Todos los colores son tokens, y la pantalla funciona en Pyzed Light y en Pyzed Dark?
5. ¿Están diseñados los estados de carga, vacío, error e ideal?
6. ¿Cada botón de solo icono tiene tooltip, y cada campo una etiqueta visible?
7. ¿Se puede hacer toda la tarea con el teclado, con el foco visible?
8. ¿Los textos van con mayúscula solo al inicio, verbos concretos en los botones, errores que dicen cómo arreglarlos?
9. ¿Sigue funcionando en `min_size` y con textos un 30 % más largos?
10. ¿Algo lento bloquea la interfaz, y cada acción da feedback en menos de 100 ms?
