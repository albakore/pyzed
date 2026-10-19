---
title: "Diseñador visual (pyzed.designer)"
description: "Referencia de la API de pyzed.designer: ejecuta, abre y crea formularios desde código Python, y registra componentes y plantillas de la caja de herramientas."
sidebar:
  order: 10
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

`pyzed.designer` es el lado en código del [diseñador visual](/pyzed/es/editor/): ejecuta archivos
`.pzform`, abre formularios como ventanas, crea formularios en código y amplía la caja de herramientas con
tus propios componentes y plantillas. Los [componentes diseñados](/pyzed/es/editor/component-designer/)
(`.pzcomp`) también se cargan desde aquí.

```python
from pyzed import designer

designer.run("ui/main.pzform", reload=True)
```

## Ejecutar formularios

### `run`

```python
run(path, *, reload=None)
```

Ejecuta el formulario de `path` con toda la lógica conectada en el diseñador.

`reload=True` activa el hot reload: guardar el formulario (desde el diseñador o a mano)
o su módulo de handlers actualiza la ventana en marcha sin reiniciarla. `None`
sigue a `PYZED_RELOAD`, como `pz.run`.

### `load`

```python
load(path)
```

Lee un archivo `.pzform`.

### `open_form`

```python
open_form(path)
```

Carga un `.pzform` y sus handlers en una `FormApp` lista para `run()` o `screenshot()`.

Si el formulario pertenece a un proyecto (ver `pyzed.project`), primero se activa el proyecto
para que sus handlers puedan importar el backend y los paquetes de su `.venv`.

### `open_window`

```python
open_window(form, *, data=None, handlers=None, folder=None)
```

Un `Command` que abre `form` en una ventana nueva (los argumentos son los de `form_window`).

### `form_window`

```python
form_window(form, *, data=None, handlers=None, folder=None)
```

Una `FormWindow` para `form` (una ruta o nombre de `.pzform`, o un `Form`), lista para abrirse.

Un formulario cargado de un archivo recibe su módulo de handlers; un `Form` creado en código usa
`handlers` (un dict de funciones). `data` llega al formulario nuevo como `form.data`.

### `new_form`

```python
new_form(
    path,
    *,
    title=None,
    template='blank',
    width=None,
    height=None,
    overwrite=False,
)
```

Crea `path` (se añade `.pzform` si falta) y su módulo de handlers a partir de `template`.

El formulario toma el nombre del archivo (`order-details.pzform` -> `OrderDetails`).

Devuelve la ruta del formulario. Lanza `FileExistsError` si ya existe, salvo con `overwrite`.

### `save`

```python
save(form, path)
```

Escribe `form` en `path` (se añade `.pzform` cuando no tiene extensión).

### `open_document`

```python
open_document(path)
```

Abre un `.pzform` como `Document` o un `.pzcomp` como `SceneDocument`.

### `design`

```python
design(path=None, *, theme=None)
```

Abre el diseñador visual, opcionalmente sobre un archivo `.pzform` (que se crea al guardar por primera vez).

## Formularios y controles

### `Form`

```python
@dataclass
class Form(name='Form1', title='Form1', width=640.0, height=420.0, theme='One Dark', accent=None, background=None, radius=None, font_size=14.0, resizable=True, grid=8, style={}, controls=[], events={}, code=None)
```

Una ventana diseñada visualmente: sus ajustes, sus controles (en orden z) y sus eventos.

`theme` es cualquier nombre de tema registrado; `accent`, `radius` y `font_size`
lo ajustan sin escribir un archivo de tema. `style` es el estilo global del formulario
(`pz.Style.to_dict()`), aplicado a toda la ventana. `grid` es el paso de ajuste del diseñador.

**Métodos y propiedades**

#### `Form.get`

```python
Form.get(name)
```

Devuelve el control llamado `name`, o `None` si no hay ninguno.

#### `Form.names`

```python
Form.names()
```

Devuelve los nombres de todos los controles, en orden z.

#### `Form.children`

```python
Form.children(name)
```

Los controles directamente dentro de `name` (el propio formulario con `None`), en orden z.

#### `Form.descendants`

```python
Form.descendants(name)
```

Todos los controles dentro de `name`, a cualquier profundidad (los padres antes que sus hijos).

#### `Form.ancestors`

```python
Form.ancestors(name)
```

Los contenedores que contienen a `name`, del más cercano al más lejano.

#### `Form.walk`

```python
Form.walk(parent=None, depth=0)
```

`(control, depth)` en orden de dibujo: cada control y luego lo que contiene.

#### `Form.is_inside`

```python
Form.is_inside(name, container)
```

Si el control `name` está dentro de `container`, a cualquier profundidad.

#### `Form.unique_name`

```python
Form.unique_name(base)
```

El primer `base1`, `base2`... libre (al estilo de Visual Basic).

#### `Form.add`

```python
Form.add(control)
```

Añade `control` (encima del orden z) y lo devuelve.

#### `Form.remove`

```python
Form.remove(names)
```

Quita controles y todo lo que contienen.

#### `Form.rename`

```python
Form.rename(old, new)
```

Renombra un control y devuelve el nombre usado en realidad (único y válido).

#### `Form.reorder`

```python
Form.reorder(names, where)
```

Mueve controles al frente (`"front"`) o al fondo (`"back"`) del orden z.

#### `Form.to_dict`

```python
Form.to_dict()
```

Devuelve el formulario como datos listos para JSON: `{"format", "form": ajustes, "controls": [...]}`.

#### `Form.from_dict`

```python
@classmethod
Form.from_dict(data)
```

Crea un formulario a partir de `data` guardados (ver `to_dict`), ignorando ajustes desconocidos y reparando padres rotos; lanza `ValueError` si no es un formulario de Pyzed.

#### `Form.to_json`

```python
Form.to_json()
```

Devuelve el formulario como texto JSON indentado (el contenido de un archivo `.pzform`).

#### `Form.from_json`

```python
@classmethod
Form.from_json(text)
```

Crea un formulario a partir del texto JSON `text` de un archivo `.pzform`.

#### `Form.copy`

```python
Form.copy()
```

Devuelve una copia profunda del formulario y sus controles.

### `Control`

```python
@dataclass
class Control(name, type, x=0.0, y=0.0, width=100.0, height=28.0, props={}, events={}, anchor=('left', 'top'), visible=True, enabled=True, locked=False, parent=None, layout={}, style={}, animations=[], bind='', rules={})
```

Un componente colocado en un formulario.

`x`, `y`, `width` y `height` están en píxeles lógicos relativos al área cliente del
formulario, o a la esquina superior izquierda de `parent` cuando el control está dentro de un
contenedor (un panel, un group box, una fila flex...). `props` guarda las propiedades propias
del componente (`text`, `checked`...) y `events` asocia nombres de evento (`"click"`) a
nombres de función handler. `layout` guarda opciones que lee el layout del padre, como
`grow` en una fila flex o `span` en una grid. `style` guarda propiedades de estilo tipo CSS
(`pz.Style.to_dict()`: fondo, borde, radio, fuente...) que se dibujan por encima de las props.

**Métodos y propiedades**

#### `Control.min_size`

```python
Control.min_size  # property
```

El `(ancho, alto)` mínimo cuando el control se estira (0: sin límite).

#### `Control.max_size`

```python
Control.max_size  # property
```

El `(ancho, alto)` máximo cuando el control se estira (0: sin límite).

#### `Control.pivot`

```python
Control.pivot  # property
```

El punto `(x, y)` de 0 a 1 alrededor del que giran la rotación y la escala, y que se queda quieto cuando un límite de tamaño frena el estiramiento.

#### `Control.rect`

```python
Control.rect  # property
```

El `(x, y, width, height)` del control, relativo a su padre (o al formulario).

#### `Control.to_dict`

```python
Control.to_dict()
```

Devuelve el control como datos listos para JSON; `parent`, `layout` y `style` vacíos se omiten.

#### `Control.from_dict`

```python
@classmethod
Control.from_dict(data)
```

Crea un control a partir de `data` guardados, ignorando claves desconocidas y anclajes no válidos.

#### `Control.copy`

```python
Control.copy()
```

Devuelve una copia profunda del control.

### `Event`

```python
@dataclass
class Event(sender, name, value=None)
```

Lo que recibe un handler además del formulario: quién lo lanzó, qué evento y su valor.

### `FormApp`

```python
class FormApp
```

Un formulario como ventana principal de la aplicación.

`path` (lo fija `open_form`) es el archivo `.pzform`; con el hot reload activo, guardarlo
o guardar su módulo de handlers actualiza la ventana en marcha.

**Métodos y propiedades**

#### `FormApp.on_start`

```python
FormApp.on_start()
```

Vigila el formulario y su módulo de handlers para el hot reload (si está activo) y luego lanza `load`.

### `FormWindow`

```python
class FormWindow
```

Un formulario en una ventana extra (`form.open(...)`, `designer.open_window` y la vista previa del diseñador).

**Métodos y propiedades**

#### `FormWindow.on_open`

```python
FormWindow.on_open()
```

Lanza el evento `load` del formulario al abrirse la ventana.

### `Document`

```python
class Document
```

Un formulario abierto en el diseñador.

`code` es el texto del módulo de handlers, guardado en memoria y escrito junto al
formulario al hacer `save`. `selection` guarda nombres de controles, el principal primero.

**Métodos y propiedades**

#### `Document.clipboard`

```python
Document.clipboard  # property
```

Los controles copiados (como datos de `Control.to_dict()`), compartidos por todos los documentos.

#### `Document.open`

```python
@classmethod
Document.open(path)
```

Carga en un documento nuevo el formulario de `path` y el texto de su módulo de handlers (si el archivo existe).

#### `Document.code_path`

```python
Document.code_path  # property
```

Dónde se guarda el módulo de handlers, o `None` mientras el formulario no tenga archivo.

#### `Document.display_name`

```python
Document.display_name  # property
```

El nombre que se muestra para el documento: su nombre de archivo, o `<nombre del formulario>.pzform` si no está guardado.

#### `Document.save`

```python
Document.save(path=None)
```

Escribe el formulario y su módulo de handlers; devuelve la ruta del formulario.

#### `Document.commit`

```python
Document.commit(group=None)
```

Guarda un paso de deshacer tras una edición (`group` une ediciones repetidas de un mismo campo).

#### `Document.undo`

```python
Document.undo()
```

Retrocede un paso; devuelve `False` si no había nada que deshacer.

#### `Document.redo`

```python
Document.redo()
```

Rehace un paso deshecho; devuelve `False` si no había nada que rehacer.

#### `Document.selected`

```python
Document.selected  # property
```

Los controles seleccionados, el principal primero (se saltan los nombres que ya no existen).

#### `Document.primary`

```python
Document.primary  # property
```

El control seleccionado principal (el primero), o `None` si no hay nada seleccionado.

#### `Document.select`

```python
Document.select(names, *, add=False)
```

Selecciona los controles `names` (un nombre, varios, o `None` para ninguno); los nombres desconocidos se ignoran.

#### `Document.select_all`

```python
Document.select_all()
```

Selecciona todos los controles del formulario.

#### `Document.is_selected`

```python
Document.is_selected(name)
```

Si el control `name` está seleccionado.

#### `Document.add`

```python
Document.add(type_, x, y, width=None, height=None, *, snap=True, parent=None)
```

Coloca un control nuevo de tipo `type_` (ajustado a la cuadrícula) y lo selecciona.

#### `Document.rects`

```python
Document.rects()
```

El rectángulo absoluto de cada control (ver `layout.resolve`).

#### `Document.can_contain`

```python
Document.can_contain(container, name)
```

Si el control `name` puede moverse dentro de `container` (`None` es el formulario, que admite cualquiera): debe ser un contenedor distinto del propio control y que no esté dentro de él.

#### `Document.reparent`

```python
Document.reparent(names, parent, *, index=None, at=None, commit=True, rects=None)
```

Mueve controles dentro de `parent` (o al formulario con `None`), dejándolos donde están.

#### `Document.wrap`

```python
Document.wrap(type_, names=None)
```

Mete controles (por defecto, la selección) dentro de un contenedor nuevo de tipo `type_` que los rodea.

#### `Document.move_out`

```python
Document.move_out(name)
```

Saca un control de su contenedor y lo pasa al padre de ese contenedor.

#### `Document.set_layout`

```python
Document.set_layout(name, key, value)
```

Fija una opción que lee el layout del padre (`grow`, `span`).

#### `Document.delete`

```python
Document.delete()
```

Quita los controles seleccionados (y lo que contienen); devuelve los nombres quitados.

#### `Document.copy`

```python
Document.copy()
```

Copia la selección, con lo que haya dentro de los contenedores seleccionados.

#### `Document.clipboard_text`

```python
Document.clipboard_text()
```

Los controles copiados como JSON para el portapapeles del sistema, para que otro formulario, otra ventana de Pyzed Design o un archivo de texto puedan tomarlos (ver `paste_text`).

#### `Document.parse_clipboard`

```python
@staticmethod
Document.parse_clipboard(text)
```

Los controles del texto del portapapeles escrito por `clipboard_text`, o `None` si contiene otra cosa. Se descartan los controles de un tipo que este Pyzed no conoce.

#### `Document.paste_text`

```python
Document.paste_text(text, offset=16)
```

Pega los controles del texto del portapapeles del sistema (ver `clipboard_text`); devuelve los nombres nuevos, o `None` si el texto no contiene controles de Pyzed.

#### `Document.cut`

```python
Document.cut()
```

Copia la selección al portapapeles y la borra; devuelve cuántos controles se copiaron.

#### `Document.paste`

```python
Document.paste(offset=16)
```

Añade copias del portapapeles (desplazadas `offset`) sin sus eventos; conservan su nombre si está libre en este formulario.

#### `Document.duplicate`

```python
Document.duplicate()
```

Pega al momento una copia de la selección sin tocar el portapapeles; devuelve los nombres nuevos.

#### `Document.size`

```python
Document.size  # property
```

El `(width, height)` del formulario en píxeles.

#### `Document.nudge`

```python
Document.nudge(dx, dy)
```

Mueve `dx`, `dy` píxeles los controles seleccionados (los que no coloca un layout), sin salirse de su contenedor cuando comparten uno; los empujones repetidos se unen en un solo paso de deshacer.

#### `Document.align`

```python
Document.align(edge, *, to_form=False)
```

Alinea los controles seleccionados en `edge` (ver `geometry.align`): entre sí, o al formulario con `to_form` o cuando solo hay un control seleccionado.

#### `Document.center`

```python
Document.center(axis='both')
```

Centra la selección (como grupo) en el formulario.

#### `Document.distribute`

```python
Document.distribute(axis)
```

Reparte los controles seleccionados con el mismo espacio a lo largo de `axis` (ver `geometry.distribute`).

#### `Document.same_size`

```python
Document.same_size(which='both')
```

Da a los controles seleccionados el ancho, el alto o ambos (`which`) del principal.

#### `Document.snap_to_grid`

```python
Document.snap_to_grid()
```

Ajusta a la cuadrícula del formulario los controles seleccionados (o todos si no hay selección).

#### `Document.reorder`

```python
Document.reorder(where)
```

Mueve los controles seleccionados en el orden z (`where`: ver `Form.reorder`).

#### `Document.set_rect`

```python
Document.set_rect(name, rect, *, group=None)
```

Fija la posición y el tamaño del control `name` a partir de `rect` `(x, y, width, height)`, redondeados a píxeles enteros; las ediciones con el mismo `group` se unen en un paso de deshacer.

#### `Document.set_prop`

```python
Document.set_prop(name, key, value)
```

Fija la propiedad `key` del control `name` a `value` (las ediciones repetidas se unen en un paso de deshacer).

#### `Document.set_style`

```python
Document.set_style(name, key, value)
```

Fija una propiedad de estilo de un control, o del estilo global del formulario si `name` es `None`; `None` la quita.

#### `Document.set_animations`

```python
Document.set_animations(name, animations, *, group=None)
```

Fija la lista de animaciones del control `name` (dicts con `preset` y, opcionalmente, `on`, `duration`, `delay`, `easing` y `repeat`); las ediciones con el mismo `group` se unen en un paso de deshacer.

#### `Document.clear_style`

```python
Document.clear_style(name)
```

Quita todas las propiedades de estilo de un control (o del estilo global del formulario).

#### `Document.set_field`

```python
Document.set_field(name, key, value)
```

Fija un atributo de `Control` (x, y, width, height, visible, enabled, locked, anchor).

#### `Document.set_bind`

```python
Document.set_bind(name, bind)
```

Enlaza el control `name` al campo (o, en los controles de visualización, a la expresión) `bind` de `form.data`; `None` o `""` lo desenlaza.

#### `Document.set_rule`

```python
Document.set_rule(name, rule, value)
```

Fija la regla de validación `rule` (`required`, `min_length`, `pattern`...) del control `name`; `None`, `""` o `False` la quita.

#### `Document.toggle_anchor`

```python
Document.toggle_anchor(name, edge)
```

Añade `edge` a los anclajes del control `name`, o lo quita si ya estaba.

#### `Document.parent_size`

```python
Document.parent_size(name)
```

El tamaño del padre del control `name` (su contenedor o el formulario).

#### `Document.set_anchor`

```python
Document.set_anchor(name, anchor, *, move=False, margin=0.0)
```

Ancla el control `name` con un preset, palabras o bordes; con `move=True` también lo lleva a ese sitio, a `margin` píxeles del borde.

#### `Document.set_offset`

```python
Document.set_offset(name, side, value)
```

Fija la distancia de un lado (`left`, `top`, `right`, `bottom`) del control `name` al de su padre.

#### `Document.set_pivot`

```python
Document.set_pivot(name, x, y)
```

Fija el pivote del control `name` (de 0 a 1 en cada eje).

#### `Document.set_form`

```python
Document.set_form(key, value)
```

Fija el atributo `key` del formulario (un `name` nuevo se convierte antes en un identificador válido).

#### `Document.rename`

```python
Document.rename(old, new)
```

Renombra un control, su entrada en la selección y los handlers que siguen la convención de nombres.

#### `Document.owner`

```python
Document.owner(name)
```

El nombre visible y el mapa de eventos de un control, o del formulario si `name` es `None`.

#### `Document.events_of`

```python
Document.events_of(name)
```

Devuelve los eventos del control `name`, o los del formulario si `name` es `None`.

#### `Document.wire`

```python
Document.wire(name, event)
```

Conecta `event` a un handler (creando su esqueleto si hace falta) y devuelve el nombre de la función.

#### `Document.unwire`

```python
Document.unwire(name, event, *, delete_code=False)
```

Desconecta `event`; con `delete_code` también quita el esqueleto si no se ha tocado.

#### `Document.handler_source`

```python
Document.handler_source(handler)
```

Devuelve el código de `handler`, o un esqueleto nuevo si aún no existe.

#### `Document.set_handler_source`

```python
Document.set_handler_source(handler, source)
```

Reemplaza el código de un handler (lanza `SyntaxError` y no cambia nada si no es válido).

#### `Document.set_code`

```python
Document.set_code(source)
```

Reemplaza todo el texto del módulo de handlers y marca el documento como modificado.

## Enlace de datos y validación

### `check`

```python
check(value, rules, type_='input')
```

El mensaje de la primera regla que `value` incumple, o `None` si las cumple todas.

`required` (una casilla marcada para casillas e interruptores), `min_length`, `max_length`, `pattern`
(una expresión regular que todo el texto debe cumplir), `min` y `max`. `message`, si está, sustituye
el mensaje predeterminado. Los valores vacíos solo incumplen `required`.

### `translate`

```python
translate(value, language=None)
```

`value` con los textos `@clave` buscados en el idioma actual (o el indicado); las listas se traducen elemento a elemento y `@@` representa una `@` literal.

### `read`

```python
read(data, path, default=None)
```

El campo en `path` de `data` (dicts, listas y objetos), o `default` si falta.

### `write`

```python
write(data, path, value)
```

Fija el campo en `path` de `data`, creando por el camino los dicts que falten.

### `has`

```python
has(data, path)
```

Si `data` tiene un campo en `path`.

### `evaluate`

```python
evaluate(expression, data, **extra)
```

El valor de `bind` para `data`: el campo si es una ruta, si no la expresión de Python evaluada sobre los campos de los datos. Lanza un error si falta el campo o la expresión es incorrecta.

### `bound_prop`

```python
bound_prop(type_)
```

La propiedad que enlaza un control de tipo `type_` (`None` si no se puede enlazar).

### `two_way`

```python
two_way(type_)
```

Si un control de tipo `type_` escribe en los datos lo que cambia el usuario.

### `rules_for`

```python
rules_for(type_)
```

Las reglas de validación que tienen sentido para `type_` (ninguna para los controles de visualización).

### `load_texts`

```python
load_texts(path)
```

Carga los catálogos de traducción del formulario en `path`: `locales/` junto a él y en las carpetas superiores, hasta la raíz del proyecto. Devuelve los idiomas encontrados.

### `BIND_PROPS`

La propiedad que enlaza cada tipo de control y si el usuario la edita (en los dos sentidos): `{tipo: (propiedad, dos_sentidos)}`.

## Caja de herramientas

### `Component`

```python
@dataclass
class Component(type, label, icon, category, render, size=(120, 28), props=(), events=(), description='', visual=True, container=None, child_layout=())
```

Una entrada de la caja de herramientas: cómo se ve, se comporta y se configura un control de este `type`.

**Métodos y propiedades**

#### `Component.default_event`

```python
Component.default_event  # property
```

El evento que se abre al hacer doble clic en el control en el diseñador.

#### `Component.all_events`

```python
Component.all_events  # property
```

Los eventos propios del control seguidos, en los componentes visuales, de los eventos de ratón comunes.

#### `Component.defaults`

```python
Component.defaults()
```

Devuelve un dict nuevo con el valor por defecto de cada propiedad, por nombre.

#### `Component.prop`

```python
Component.prop(name)
```

Devuelve la propiedad llamada `name`, o `None` si el componente no la tiene.

#### `Component.create`

```python
Component.create(name, x=0, y=0, width=None, height=None)
```

Un control nuevo de este tipo con las propiedades por defecto.

### `Prop`

```python
@dataclass
class Prop(name, kind, default=None, label='', choices=(), min=None, max=None, step=1.0, group='Appearance', type='')
```

Una propiedad que se muestra en la rejilla de propiedades del diseñador.

`kind` elige el editor: text, multiline, number, bool, color, choice (de
`choices`), list (un elemento por línea), rows (filas separadas por comas, la primera es la
cabecera) o icon (un nombre de icono de Lucide).

**Métodos y propiedades**

#### `Prop.title`

```python
Prop.title  # property
```

La etiqueta que se muestra en la rejilla de propiedades: `label`, o el nombre con espacios en lugar de guiones bajos.

### `RenderContext`

```python
class RenderContext
```

Lo que necesita el `render` de un componente: el tema y una forma de lanzar eventos.

`live` es `False` en el diseñador, donde los callbacks son marcadores inertes para que
los controles se vean habilitados pero no hagan nada.

**Métodos y propiedades**

#### `RenderContext.on`

```python
RenderContext.on(control, event, prop=None)
```

Un callback para `event`; si se da `prop`, el valor también se guarda ahí.

#### `RenderContext.key`

```python
RenderContext.key(control)
```

Un id estable para widgets con estado interno (editores, campos de texto).

### `register`

```python
register(component)
```

Añade (o reemplaza) un componente en la caja de herramientas.

### `component`

```python
component(type_)
```

Devuelve el componente registrado para `type_`; lanza `KeyError` con la lista de tipos conocidos.

### `all_components`

```python
all_components()
```

Devuelve todos los componentes registrados, en orden de registro.

### `categories`

```python
categories()
```

Devuelve los componentes registrados agrupados por `category` (secciones de la caja de herramientas), en orden de registro.

### `Template`

```python
@dataclass
class Template(name, label, icon, description, build, size=(640, 420), handlers=())
```

Un punto de partida para formularios nuevos.

### `register_template`

```python
register_template(template)
```

Añade (o reemplaza, por nombre) una plantilla del diálogo "Nuevo formulario"; la devuelve.

### `templates`

```python
templates()
```

Devuelve las plantillas de formulario registradas, en orden de registro.

## Componentes diseñados

### `new_component`

```python
new_component(
    name='Component1',
    path=None,
    *,
    width=240,
    height=120,
    label='',
    icon='component',
    category='Custom',
    description='',
    extends=None,
)
```

Un componente diseñado nuevo (aún sin guardar; llama a `save()`): su escena y una clase vacía.

`extends` es el `.pzcomp` de un componente del que heredar: la clase nueva deriva
de él y empieza con sus controles, propiedades, eventos y métodos.

### `load_component`

```python
load_component(path)
```

Importa la clase del componente guardado en `path` (de nuevo, para recoger los cambios).

Definir la clase la registra en la caja de herramientas, reemplazando una versión anterior. Devuelve
la clase, o `None` (con el motivo en `errors`) si su código falla al importarse.

### `import_component`

```python
import_component(scene)
```

La clase del componente diseñado guardado en `scene`, para heredar de ella.

Una ruta relativa es relativa al módulo que la llama, así que un componente puede extender
otro que esté a su lado:

```python
Rating = import_component("rating.pzcomp")

class BigRating(Rating, scene="big_rating.pzcomp"):
    ...
```

La clase se importa una vez y se reutiliza hasta que cambia su código.

### `discover`

```python
discover(root=None)
```

Importa todos los componentes diseñados bajo `root` (por defecto, la carpeta actual).

Los componentes pueden usarse entre sí, así que una importación fallida se reintenta cuando
los demás ya cargaron (`errors` guarda lo que siga fallando).

### `SceneDocument`

```python
class SceneDocument
```

Un componente abierto en el diseñador: su escena, el código de su clase, la selección y el deshacer.

Funcionan todos los comandos de `Document` (colocar, mover, alinear controles...). Los eventos
de los controles se convierten en métodos de la clase (`def ok_click(self, event)`), y los
eventos propios del componente son sus métodos de ciclo de vida (`setup`, `on_mount`...).
Las propiedades y los eventos personalizados se leen de la clase y se escriben de vuelta en ella.

**Métodos y propiedades**

#### `SceneDocument.scene`

```python
SceneDocument.scene  # property
```

La escena del componente (el `form` del documento, tipado como `Scene`).

#### `SceneDocument.base_file`

```python
SceneDocument.base_file  # property
```

El `.pzcomp` que extiende este componente, o `None`.

#### `SceneDocument.base`

```python
SceneDocument.base  # property
```

La escena que extiende este componente, con todo lo que ella misma hereda (`None` si no hay).

#### `SceneDocument.inherited`

```python
SceneDocument.inherited(name)
```

`True` para un control que viene del componente base.

#### `SceneDocument.own_scene`

```python
SceneDocument.own_scene()
```

Lo que guarda el `.pzcomp` propio de este componente: sus controles y los heredados que cambió.

#### `SceneDocument.set_base`

```python
SceneDocument.set_base(path)
```

Hace que este componente herede del guardado en `path` (`None` no hereda de nada).

#### `SceneDocument.base_info`

```python
SceneDocument.base_info()
```

Las clases de las que hereda este componente (la más cercana primero) como `(nombre del archivo de escena, info de la clase)`.

#### `SceneDocument.all_members`

```python
SceneDocument.all_members  # property
```

Las propiedades de este componente y las que hereda (los bindings pueden usar ambas).

#### `SceneDocument.info`

```python
SceneDocument.info  # property
```

La clase tal como se analizó por última vez (el último análisis correcto mientras el código tenga un error de sintaxis).

#### `SceneDocument.code_ok`

```python
SceneDocument.code_ok  # property
```

Si el código de la clase se puede analizar ahora (si no, `info` recurre al último análisis correcto).

#### `SceneDocument.members`

```python
SceneDocument.members  # property
```

Las propiedades y el estado privado del componente tal como se declaran en su clase, en orden (una copia).

#### `SceneDocument.member`

```python
SceneDocument.member(name)
```

Devuelve la propiedad o el estado declarado llamado `name`, o `None`.

#### `SceneDocument.unique_member`

```python
SceneDocument.unique_member(base='value')
```

Devuelve `base` (convertido en identificador), o `base2`, `base3`... si ya lo usa un miembro, método, control o nombre reservado.

#### `SceneDocument.add_member`

```python
SceneDocument.add_member(name='', type_='str', default=None, *, public=True, description='')
```

Declara una propiedad nueva (`public=False` la convierte en estado privado).

#### `SceneDocument.update_member`

```python
SceneDocument.update_member(member, **changes)
```

Cambia una propiedad (`name`, `type`, `default`, `public`, `description`); devuelve su nombre.

#### `SceneDocument.set_member_source`

```python
SceneDocument.set_member_source(name, source)
```

Pone como valor por defecto de la propiedad `name` la expresión de Python `source` (`[1, 2]`, `Point(x=1)`...).

#### `SceneDocument.remove_member`

```python
SceneDocument.remove_member(name)
```

Quita la propiedad `name` de la clase.

#### `SceneDocument.move_member`

```python
SceneDocument.move_member(name, offset)
```

Mueve la propiedad `name` `offset` posiciones en el orden de declaración de la clase (dentro de los límites).

#### `SceneDocument.custom_events`

```python
SceneDocument.custom_events  # property
```

Los eventos que declara el componente, como `{nombre: descripción}` (una copia).

#### `SceneDocument.add_event`

```python
SceneDocument.add_event(name='changed', description='')
```

Declara un evento nuevo llamado `name` (hecho único) con `description`; devuelve su nombre.

#### `SceneDocument.update_event`

```python
SceneDocument.update_event(name, *, new_name=None, description=None)
```

Renombra el evento `name` a `new_name` (si es válido y está libre) y/o cambia su `description`, manteniendo su posición; devuelve el nombre del evento. Lanza `KeyError` si no existe.

#### `SceneDocument.remove_event`

```python
SceneDocument.remove_event(name)
```

Quita de la clase el evento declarado `name`.

#### `SceneDocument.set_class_name`

```python
SceneDocument.set_class_name(name)
```

Renombra la clase del componente (convertido en un nombre de clase válido) en el código y la escena; devuelve el nombre nuevo.

#### `SceneDocument.set_description`

```python
SceneDocument.set_description(text)
```

Fija la descripción del componente, también como docstring de su clase.

#### `SceneDocument.set_scene`

```python
SceneDocument.set_scene(key, value)
```

Fija cómo aparece el componente en la caja de herramientas (`label`, `icon`, `category`) o su tamaño.

#### `SceneDocument.set_binding`

```python
SceneDocument.set_binding(control, prop, expression)
```

Hace que `prop` de `control` siga a `expression` (`None` o `""` quita el binding).

#### `SceneDocument.add_method`

```python
SceneDocument.add_method(name='do_something', args='self', doc='')
```

Añade a la clase un método reutilizable (no un handler de evento); devuelve su nombre.

### `Scene`

```python
@dataclass
class Scene(name='Component1', title='Component1', width=240.0, height=120.0, theme='One Dark', accent=None, background=None, radius=None, font_size=14.0, resizable=False, grid=8, style={}, controls=[], events={}, code=None, label='', icon='component', category='Custom', description='', extends='', bindings={})
```

El layout de un componente diseñado: un `Form` cuyo `name` es el nombre de la clase.

`bindings` asocia un nombre de control a `{propiedad del control: expresión}`; la
expresión (normalmente una propiedad del componente, como `value`, o cualquier expresión de
Python sobre ellas, como `f"{value} stars"`) se evalúa en cada render.

**Métodos y propiedades**

#### `Scene.class_name`

```python
Scene.class_name  # property
```

El nombre de la clase del componente (el `name` de la escena).

#### `Scene.bound`

```python
Scene.bound(control)
```

Devuelve los bindings de `control` como `{propiedad: expresión}` (vacío si no tiene).

### `SceneComponent`

```python
class SceneComponent
```

Clase base de los componentes creados en el modo componente del diseñador.

`scene` es el archivo `.pzcomp` con el layout, relativo al módulo. La etiqueta, el icono,
la categoría, la descripción y el tamaño por defecto en la caja de herramientas salen de la escena
salvo que la clase los fije.

**Métodos y propiedades**

#### `SceneComponent.scene_path`

```python
@classmethod
SceneComponent.scene_path()
```

Devuelve el archivo `.pzcomp` al que está ligada la clase, o `None`.

#### `SceneComponent.scene_model`

```python
@classmethod
SceneComponent.scene_model()
```

La escena tal como está guardada (o previsualizada por el diseñador), o `None`.

#### `SceneComponent.ctx`

```python
SceneComponent.ctx  # property
```

Un contexto de render para esta instancia, con el tema de su escena (lo que necesita `ControlProxy.focus()`).

### `render`

```python
render(control, ctx)
```

Dibuja `control` a su tamaño (con sus props, o los valores por defecto del componente si faltan).

## Ayudas de layout

### `align`

```python
align(controls, edge, *, to=None)
```

Alinea controles en `edge` (left, center, right, top, middle, bottom).

Con `to` (p. ej. el rectángulo del formulario) se alinean a él; si no, a los límites de la
selección, o al formulario cuando se pasa un solo control mediante `to`.

### `distribute`

```python
distribute(controls, axis)
```

Reparte tres o más controles con el mismo espacio en `"horizontal"` o `"vertical"`.

### `same_size`

```python
same_size(controls, which='both', *, reference=None)
```

Da a todos los controles el `"width"`, `"height"` o `"both"` de `reference` (el primero).

### `snap`

```python
snap(value, grid, enabled=True)
```

Redondea `value` al múltiplo más cercano de `grid` (sin cambios si está desactivado).

### `smart_guides`

```python
smart_guides(rect, others, size, threshold=4.0)
```

Ajusta un rectángulo en movimiento a los bordes y centros de `others` y del formulario.

Devuelve `(dx, dy, lines)`: la corrección a aplicar y las líneas guía a dibujar
(como cajas finas `(x1, y1, x2, y2)`), como las guías de alineación de Figma o Qt Designer.

### `anchored`

```python
anchored(control, design, actual)
```

Dónde va un control cuando su formulario pasa del tamaño `design` al tamaño `actual`.

Como los anclajes de WinForms: un borde anclado al formulario mantiene su distancia a ese
lado; anclado a ambos lados se estira; anclado a ninguno mantiene su posición
relativa (los controles centrados siguen centrados).

## App del diseñador

### `Designer`

```python
class Designer
```

El editor visual de formularios.

### `EditorSettings`

```python
@dataclass
class EditorSettings(theme='', font_size=14.0, tab_size=4, show_whitespace=False, wrap=False, line_numbers=True, highlight_line=True, autocomplete=True, code_lens=True, inline_diagnostics=True, format_on_apply=False, auto_close=True, folding=True, minimap=True, cursor_shape='bar', cursor_blink=True, match_brackets=True, selection_highlight=True, ty=True, ruff=True)
```

Los ajustes del editor de código del diseñador (un dataclass): `theme`, `font_size`, `tab_size`, `show_whitespace`, `wrap`, `line_numbers`, `highlight_line`, `autocomplete`, `code_lens`, `inline_diagnostics`, `format_on_apply`, `auto_close`, `folding`, `minimap`, `cursor_shape`, `cursor_blink`, `ty` y `ruff`.

**Métodos y propiedades**

#### `EditorSettings.to_dict`

```python
EditorSettings.to_dict()
```

Devuelve los ajustes como un dict listo para JSON.

#### `EditorSettings.from_dict`

```python
@classmethod
EditorSettings.from_dict(data)
```

Crea los ajustes a partir de `data` guardados, con los valores por defecto para los que falten o no sean válidos, y limitando el tamaño de tabulación, el de fuente y la forma del cursor a valores válidos.

### `History`

```python
class History
```

Instantáneas de un formulario: `push` tras una edición, y luego `undo`/`redo` para moverse entre ellas.

**Métodos y propiedades**

#### `History.push`

```python
History.push(form, group=None)
```

Guarda el estado actual del formulario; devuelve `False` si nada cambió.

#### `History.reset`

```python
History.reset(form)
```

Olvida todos los pasos de deshacer y rehacer y empieza de nuevo desde el estado actual de `form`.

#### `History.can_undo`

```python
History.can_undo  # property
```

Si hay un paso que deshacer.

#### `History.can_redo`

```python
History.can_redo  # property
```

Si hay un paso deshecho que rehacer.

#### `History.undo`

```python
History.undo()
```

Retrocede una instantánea; devuelve el formulario anterior (un objeto nuevo) o `None` si no hay.

#### `History.redo`

```python
History.redo()
```

Avanza una instantánea; devuelve el formulario restaurado (un objeto nuevo) o `None` si no hay.

### `theme_for`

```python
theme_for(form, theme_name=None)
```

El tema con el que se ejecuta un formulario: su tema base más los ajustes de acento, radio, fuente y fondo.

### `COMMON_EVENTS`

Los eventos que cualquier control puede manejar en el panel Eventos del diseñador.

### `FORM_EVENTS`

Los eventos del propio formulario (`load`, `close`, `resize`, `key`...).
