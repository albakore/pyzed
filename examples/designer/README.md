# Designer example

A sign-in form made with the visual designer: `login.pzform` is the layout and `login.py` its event handlers.

```bash
pyzed run examples/designer/login.pzform      # run it
pyzed design examples/designer/login.pzform   # open it in the designer
```

## Components

[`components/`](components) has components made with the designer's component mode: `Rating` (five stars with a
`value` property and a `change` event), `ProfileCard` (a card that contains a `Rating` and stretches with its
anchors), `TeamCard` (a `ProfileCard` that inherits everything and adds a team badge) and `Reviews`, a form whose two
cards share a flex row, so they shrink and grow with the window.

```bash
pyzed run examples/designer/components/reviews.pzform        # the form
pyzed run examples/designer/components/rating.pzcomp         # one component, with an event log
pyzed design examples/designer/components/profile_card.pzcomp
pyzed design examples/designer/components/team_card.pzcomp      # inherits from profile_card.pzcomp
```
