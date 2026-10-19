---
title: Diseñador de componentes
description: Dibuja componentes reutilizables con propiedades, estado, métodos y eventos propios, y anídalos como las escenas de Godot.
sidebar:
  order: 13.5
---

El diseñador tiene un segundo modo para crear **componentes** en vez de ventanas. Dibujas el componente como un
formulario, declaras sus propiedades y eventos en un panel, escribes la lógica de sus métodos y luego lo colocas en
formularios o dentro de otros componentes. La idea es la de las escenas de Godot: cada componente tiene sus propias
propiedades, métodos y eventos, y puede contener otros componentes.

![Un componente ProfileCard que contiene un componente Rating](../../../../../screenshots/designer-component.png)

Un componente diseñado **es** un [`pz.Component`](/pyzed/es/guides/components/). El diseñador escribe una clase
normal, así que dibujarlo y escribirlo a mano son lo mismo, y puedes pasar de una forma a la otra cuando quieras.

## Crear uno

Pulsa **New component** en la barra de herramientas (Ctrl+Shift+N), o **New** (Ctrl+N) y elige la tarjeta
**Component**. Ponle un nombre y una carpeta; **Inherits from** puede partir de otro componente (mira
[Herencia](#herencia)). **Create component** guarda los dos archivos y lo abre. También puedes abrir un `.pzcomp`:

![El diálogo New component](../../../../../screenshots/designer-component-new.png)

```bash
pyzed design ui/rating.pzcomp     # se crea al guardar si no existe
```

Un componente no es un formulario: no tiene ventana, título ni menú, y solo existe dentro de un formulario o de otro
componente. El diseñador lo muestra así: una etiqueta **Component** en la barra de título, y un marco de color con el
nombre de la clase en el lienzo en vez de los botones de ventana.

Un componente son dos archivos juntos:

| Archivo | Qué contiene |
| --- | --- |
| `rating.pzcomp` | El diseño: los controles, su tamaño, cómo aparece en la biblioteca y sus enlaces (JSON). |
| `rating.py` | La clase: sus propiedades, eventos propios y métodos. |

```python
import pyzed as pz
from pyzed.designer import SceneComponent


class Rating(SceneComponent, scene="rating.pzcomp"):
    """Five stars the user can click."""

    value: int = 3  # How many stars are lit
    readonly: bool = False
    clicks: int = pz.state(0, doc="Times the user picked a rating")
    events = {"change": "A star was picked (event.value is the rating)"}

    def star1_click(self, event):
        return self.pick(1)

    def pick(self, stars):
        """Lights ``stars`` stars and tells the parent."""
        if self.readonly:
            return None
        self.value = stars
        self.clicks += 1
        return self.emit("change", stars)
```

## El panel Component

Sin nada seleccionado, la pestaña Properties muestra el propio componente:

- **Class**: el nombre de la clase y su docstring.
- **Toolbox**: la etiqueta, el icono y la categoría con que aparece en la biblioteca.
- **Layout**: su tamaño, fondo y rejilla.
- **Properties**: cada una tiene nombre, tipo y valor por defecto. El ojo marca una propiedad **pública**, una prop
  que pasa el padre (`Rating(value=4)`); el candado marca una **privada**, estado declarado con `pz.state`. Las
  dos son atributos en el código: `self.value`, `self.clicks`.
- **Custom events**: los eventos que el componente lanza con `self.emit("change", valor)`, con su descripción. El
  padre los recibe con `on_change=...` en código, o en la pestaña Events de un formulario.
- **Methods**: todos los métodos de la clase. Haz clic en uno para abrirlo en el editor de código. `setup()`,
  `on_mount()` y `on_unmount()` se añaden al hacer clic en ellos.

Cada cambio se escribe en la clase en el momento, y lo que escribas en la clase aparece en el panel. Si el código
tiene un error de sintaxis, el panel muestra la última versión válida hasta que lo corrijas.

## Eventos de los controles

Haz doble clic en un control, o usa la pestaña Events, para escribir el código de sus eventos, como en un
formulario. En un componente son métodos: `def star1_click(self, event)`. Los controles son atributos del
componente y sus propiedades se leen y escriben como atributos:

```python
def clear_click(self, event):
    self.query.text = ""
    self.results.items = []
```

Cada instancia tiene su propia copia de los controles, así que dos ratings en un formulario guardan su propio estado.

## Enlaces

Selecciona un control y la sección **Bindings** enlaza sus propiedades con las del componente. Elige una propiedad
en la lista, o elige **Expression…** y escribe cualquier expresión de Python sobre ellas:

![El título sigue a la propiedad person](../../../../../screenshots/designer-component-bindings.png)

| Propiedad del control | Enlace |
| --- | --- |
| `headline.text` | `person` |
| `caption.text` | `f"{value} / 5"` |
| `star3.variant` | `"solid" if value >= 3 else "ghost"` |

Los enlaces se evalúan en cada render, así que los controles siguen siempre a las propiedades.

## Componentes anidados

Los componentes guardados aparecen en la biblioteca bajo su categoría, en formularios y en otros componentes. El
diseñador encuentra todos los `.pzcomp` del proyecto al arrancar, y recarga un componente al guardarlo. Coloca un
`Rating` dentro de un `ProfileCard`, enlaza su `value` con el `score` de la tarjeta y reenvía su evento:

```python
class ProfileCard(SceneComponent, scene="profile_card.pzcomp"):
    """A person with a rating."""

    person: str = "Ada Lovelace"
    job: str = "Mathematician"
    score: int = 4
    events = {"rated": "The rating changed (event.value is the new score)"}

    def stars_change(self, event):
        """The inner Rating raised change."""
        self.score = event.value
        return self.emit("rated", event.value)
```

![Dos tarjetas en un formulario](../../../../../screenshots/designer-component-run.png)

Una propiedad que el propio componente cambia, como `self.score` arriba, conserva su valor hasta que el padre pasa
otro distinto, como una variable exportada en Godot. Un handler del formulario también puede cambiarla:

```python
def ada_rated(form, event):
    event.sender.score = event.value
    form.status.text = f"{event.sender.person} now has {event.value} stars"
```

## Componentes responsive

Un componente colocado en un formulario, o dentro de otro componente, toma el tamaño de su rectángulo ahí, y sus
controles siguen sus **anclas** como en un formulario: anclado a izquierda y derecha, un control se estira con el
componente; anclado a la derecha, se mueve con el borde derecho. Las filas, columnas y rejillas flex dentro del
componente también se reparten el nuevo tamaño.

En el ejemplo, el marco de `ProfileCard` está anclado a los cuatro lados y el título, el puesto y la valoración a
izquierda, arriba y derecha. `Reviews` pone sus dos tarjetas en una **fila flex** con `grow` 1 cada una, así que se
reparten el ancho de la ventana y se encogen con ella:

![Las dos tarjetas se encogen con una ventana estrecha](../../../../../screenshots/designer-component-responsive.png)

Desde código, un componente ocupa el ancho que haya, hasta su ancho de diseño, y la altura de su diseño.

## Herencia

Un componente puede heredar de otro para reutilizar su diseño y su lógica. Elige la base en **Inherits from** al
crearlo, o después en el campo **Inherits** de la sección Class. La clase pasa a derivar de la clase base:

```python
from pyzed.designer import import_component

ProfileCard = import_component("profile_card.pzcomp")


class TeamCard(ProfileCard, scene="team_card.pzcomp"):
    """A profile card that also shows the team."""

    team: str = "Analytical Engine"

    def stars_change(self, event):
        """Does what a ProfileCard does, and the badge turns green with five stars."""
        result = super().stars_change(event)
        self.team_label.tint = "success" if event.value == 5 else "accent"
        return result
```

`import_component` importa la clase de un `.pzcomp` relativo al módulo, así que la base y el nuevo componente pueden
estar en cualquier carpeta. Lo que recibe el nuevo componente:

- **Controles**: los controles de la base aparecen en el lienzo, con los tuyos encima. Puedes mover o cambiar un
  control heredado (el cambio solo se guarda en tu `.pzcomp`), pero no renombrarlo ni borrarlo, porque el código de
  la base lo usa. Al guardar se escriben solo tus controles y los heredados que cambiaste.
- **Propiedades, eventos propios y métodos**: todo lo de la clase base, como en cualquier subclase de Python. Los
  enlaces pueden usar propiedades heredadas. Define de nuevo un método para sobrescribirlo y llama a `super()` para
  ejecutar el de la base.
- **Cambios en la base**: al guardar la base se recargan los componentes que heredan de ella, así que reciben sus
  nuevos controles y su código.

La sección **Inherited** del panel lista lo que viene de cada base:

![TeamCard hereda de ProfileCard](../../../../../screenshots/designer-component-inherit.png)

## Ejecutarlo y usarlo

Pulsa **F5** para abrir el componente en una ventana de vista previa. La ventana lista los eventos propios que
lanza, así que puedes probarlo antes de usarlo. `pyzed run rating.pzcomp` hace lo mismo desde una terminal.

![La ventana de vista previa](../../../../../screenshots/designer-component-preview.png)

En código, importa la clase y úsala como cualquier componente:

```python
from ui.rating import Rating

class Review(pz.App):
    stars = 3

    def view(self):
        return Rating(value=self.stars, on_change=lambda e: setattr(self, "stars", e.value))
```

Los formularios encuentran solos los componentes de su proyecto al ejecutarse (`pyzed run`, `designer.run`).

## Componentes desde código

Todo lo que hace el panel está disponible desde Python:

```python
from pyzed import designer

doc = designer.new_component("Rating", "ui/rating.pzcomp", width=232, height=32, icon="star")
doc.add("button", 0, 0, 28, 28)
doc.add_member("value", "int", 3)
doc.add_member("clicks", "int", public=False)
doc.add_event("change", "A star was picked")
doc.set_binding("button1", "variant", '"solid" if value >= 1 else "ghost"')
doc.wire("button1", "click")
doc.save()

big = designer.new_component("BigRating", "ui/big_rating.pzcomp", extends="ui/rating.pzcomp")
big.save()

designer.discover("ui")  # importa todos los componentes diseñados de una carpeta
```

Mira [`examples/designer/components`](https://github.com/albakore/pyzed/tree/main/examples/designer/components)
para el ejemplo de Rating, ProfileCard, TeamCard y Reviews.
