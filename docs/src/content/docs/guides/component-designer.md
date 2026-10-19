---
title: Component designer
description: Draw reusable components with properties, state, methods and custom events, and nest them like Godot scenes.
sidebar:
  order: 13.5
---

The designer has a second mode for building **components** instead of windows. You draw the component like a
form, declare its properties and events in a panel, write the logic of its methods, and then place it in forms
or inside other components. The idea is the same as scenes in Godot: every component has its own properties,
methods and events, and can contain other components.

![A ProfileCard component that contains a Rating component](../../../../screenshots/designer-component.png)

A designed component **is** a [`pz.Component`](/pyzed/guides/components/). The designer writes an ordinary
class, so drawing it and writing it by hand are the same thing, and you can switch between them at any time.

## Creating one

Press **New component** in the toolbar (Ctrl+Shift+N), or **New** (Ctrl+N) and pick the **Component** card. Give it
a name and a folder; **Inherits from** can start it from another component (see [Inheritance](#inheritance)).
**Create component** saves both files and opens it. You can also open a `.pzcomp` file:

![The New component dialog](../../../../screenshots/designer-component-new.png)

```bash
pyzed design ui/rating.pzcomp     # created on first save if it does not exist
```

A component is not a form: it has no window, title or menu, and it only exists inside a form or another component.
The designer shows it that way: a **Component** badge in the title bar, and an accent frame with the class name on
the canvas instead of window buttons.

A component is two files next to each other:

| File | What it holds |
| --- | --- |
| `rating.pzcomp` | The layout: the controls placed on it, its size, how it shows in the toolbox and its bindings (JSON). |
| `rating.py` | The class: its properties, custom events and methods. |

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

## The Component panel

With nothing selected, the Properties tab shows the component itself:

- **Class**: the class name and its docstring.
- **Toolbox**: the label, icon and category it gets in the toolbox.
- **Layout**: its size, background and grid.
- **Properties**: each one has a name, a type and a default. The eye icon marks a **public** property, a prop
  the parent passes (`Rating(value=4)`); the lock marks a **private** one, state declared with `pz.state`.
  Both are attributes in the code: `self.value`, `self.clicks`.
- **Custom events**: the events the component raises with `self.emit("change", value)`, with a description.
  The parent handles them with `on_change=...` in code, or in the Events tab of a form.
- **Methods**: every method of the class. Click one to open it in the code editor. `setup()`, `on_mount()` and
  `on_unmount()` are added when you click them.

Each change is written to the class right away, and what you write in the class shows up in the panel. If the
code has a syntax error, the panel shows the last version that parsed until you fix it.

## Events of the controls

Double-click a control, or use the Events tab, to write the code of its events, as in a form. In a component they
are methods: `def star1_click(self, event)`. Controls are attributes of the component and their properties read
and write like attributes:

```python
def clear_click(self, event):
    self.query.text = ""
    self.results.items = []
```

Every instance has its own copy of the controls, so two ratings on one form keep their own state.

## Bindings

Select a control and the **Bindings** section links its properties to the component's. Pick a property in the
list, or choose **Expression…** and write any Python expression over them:

![The headline follows the person property](../../../../screenshots/designer-component-bindings.png)

| Control property | Binding |
| --- | --- |
| `headline.text` | `person` |
| `caption.text` | `f"{value} / 5"` |
| `star3.variant` | `"solid" if value >= 3 else "ghost"` |

Bindings are evaluated on every render, so the controls always follow the properties.

## Nesting components

Saved components appear in the toolbox under their category, in forms and in other components. The designer
finds every `.pzcomp` of the project when it starts, and reloads a component when you save it. Place a `Rating`
inside a `ProfileCard`, bind its `value` to the card's `score`, and forward its event:

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

![Two cards on a form](../../../../screenshots/designer-component-run.png)

A property that a designed component changes itself, such as `self.score` above, keeps its value until the
parent passes a different one, like an exported variable in Godot. A form handler can set it too:

```python
def ada_rated(form, event):
    event.sender.score = event.value
    form.status.text = f"{event.sender.person} now has {event.value} stars"
```

## Responsive components

A component placed on a form, or inside another component, takes the size of its rectangle there, and its controls
follow their **anchors** like on a form: anchored left and right, a control stretches with the component; anchored
right, it moves with the right edge. Flex rows, columns and grids inside the component lay out at the new size too.

In the example, the frame of `ProfileCard` is anchored on all four sides and the headline, the role and the rating
on left, top and right. `Reviews` puts its two cards in a **flex row** with `grow` 1 each, so they share the width
of the window and shrink with it:

![The two cards shrink with a narrow window](../../../../screenshots/designer-component-responsive.png)

Used from code, a component is as wide as there is room for, up to its design width, and as tall as its design
height.

## Inheritance

A component can inherit from another one to reuse its layout and its logic. Pick the base in **Inherits from**
when you create it, or later in the **Inherits** field of the Class section. The class then derives from the base
class:

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

`import_component` imports the class of a `.pzcomp` relative to the module, so the base and the new component can
live in any folder. What the new component gets:

- **Controls**: the base's controls show on the canvas, with yours on top. You can move or change an inherited
  control (the change is saved in your `.pzcomp` only), but not rename or delete it, because the base's code uses
  it. Saving writes only your controls and the inherited ones you changed.
- **Properties, custom events and methods**: everything of the base class, as in any Python subclass. Bindings can
  use inherited properties. Define a method again to override it, and call `super()` to run the base's.
- **Changes to the base**: saving the base reloads the components that inherit from it, so they pick up its new
  controls and code.

The **Inherited** section of the panel lists what comes from each base:

![TeamCard inherits from ProfileCard](../../../../screenshots/designer-component-inherit.png)

## Running and using it

Press **F5** to open the component in a preview window. The window lists the custom events it raises, so you can
try it before using it anywhere. `pyzed run rating.pzcomp` does the same from a terminal.

![The preview window](../../../../screenshots/designer-component-preview.png)

In code, import the class and use it like any component:

```python
from ui.rating import Rating

class Review(pz.App):
    stars = 3

    def view(self):
        return Rating(value=self.stars, on_change=lambda e: setattr(self, "stars", e.value))
```

Forms find the components of their project on their own when they run (`pyzed run`, `designer.run`).

## Scripting components

Everything the panel does is available from Python:

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

designer.discover("ui")  # import every designed component of a folder
```

See [`examples/designer/components`](https://github.com/albakore/pyzed/tree/main/examples/designer/components)
for the Rating, ProfileCard, TeamCard and Reviews example.
