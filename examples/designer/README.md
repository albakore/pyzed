# Designer example

A sign-in form made with the visual designer: `login.pzform` is the layout and `login.py` its event handlers.

```bash
pyzed run examples/designer/login.pzform      # run it
pyzed design examples/designer/login.pzform   # open it in the designer
```

## Components

[`components/`](components) has components made with the designer's component mode: `Rating` (five stars with a
`value` property and a `change` event), `ProfileCard` (a card that contains a `Rating`) and `Reviews`, a form that
uses two cards.

```bash
pyzed run examples/designer/components/reviews.pzform        # the form
pyzed run examples/designer/components/rating.pzcomp         # one component, with an event log
pyzed design examples/designer/components/profile_card.pzcomp
```
