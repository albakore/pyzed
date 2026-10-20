---
title: Reduced motion, tests and limits
description: "Respect the system's reduce-motion setting in Pyzed, test animated views and timeline clips, take stable screenshots, and know the limits of the animation system."
sidebar:
  order: 9
---

## Reduced motion

Some people get dizzy or distracted by motion, and turn on "reduce motion" in their system.
Pyzed follows that setting, read when the app starts: every animation then **shows its resting
state at once**, without moving.

- `pz.set_reduced_motion(True)` turns motion off, `False` turns it on, and `None` follows the system
  again. Offer it as a setting of your app.
- The `PYZED_REDUCED_MOTION` environment variable (`1` or `0`) overrides both.

See [Accessibility](/pyzed/guides/accessibility/#reduce-motion).

:::tip
Don't hide information in motion alone. If a field shakes on a wrong password, also show the
error message.
:::

## Tests and screenshots

Screenshots (`App.screenshot`, `pz.screenshot`) always show the **resting state**: what a mount
animation ends on. That keeps tests and documentation images stable, whatever the timing.

To test that a widget animates, check the widget tree: `repr(widget)` ends with
`.animate(2 animation(s), 1 transition(s))`.

To test a timeline, drive the player by hand. `advance` runs calls and updates attribute tracks;
`seek` jumps without running calls:

```python
def test_intro_chimes():
    app = Game()
    app.player.owner = app                  # a running app sets it; a test sets it by hand
    app.player.pause()
    app.player.advance(1.7)                 # passes the chime() call at 1.6 s
    assert app.message == "New record!"
    app.player.seek(0.5)
    assert app.player.value("card:y") < 40
```

A paused player shows its clip at the playhead, even in a screenshot, so you can take a picture of
any moment of a clip: `app.player.pause(); app.player.seek(0.8); app.screenshot("intro.png")`.

## Limits

- Transforms are translation, uniform scale and rotation; there is no skew.
- A rotated or blurred widget takes input where its box is laid out, not where it is drawn.
- A widget with rotation, blur, backdrop blur or bloom is drawn above its siblings, so its bloom
  can light the widgets next to it.
- `backdrop_blur` blurs what the window drew before the widget, inside the same parent layer
  (scrollables and other clipping widgets start a new layer).
- `width`, `height`, `padding` and `font_size` lay the view out again on every frame while they move,
  so prefer `x`, `y` and `scale` for large views.
- Animations restart when a widget leaves the tree and comes back. Give a stable `key`, or use
  [`presence`](/pyzed/animation/transitions/#presence-and-stagger), to control when they replay.
- A player plays one clip at a time. To play two scenes at once, use two players.
