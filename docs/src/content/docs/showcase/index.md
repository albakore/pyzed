---
title: "Showcase"
description: "Demos of what Pyzed can draw: game HUDs, menus and inventories, frosted-glass dashboards, bloom and real GPU shaders, all in Python."
sidebar:
  order: 0
  label: "Overview"
---

Pyzed draws with the GPU, so a Python desktop app can look like a modern game or operating system: real backdrop blur (`glass`), light that spills from bright parts (`bloom`), rotation, transparency and your own WGSL shaders (`pz.shader`). Each demo below is one file in [`examples/showcase`](https://github.com/albakore/pyzed/tree/main/examples/showcase); run it, then read how it is made.

## [Game HUD](/pyzed/showcase/hud/)

A game heads-up display in Python: health and mana bars, a radar minimap drawn by a shader, an ability bar with cooldowns and glass panels.

[![Game HUD](../../../assets/showcase/hud.png)](/pyzed/showcase/hud/)

## [Game main menu](/pyzed/showcase/main-menu/)

A synthwave game main menu in Python with a shader backdrop that follows the mouse, a glowing title and glass buttons that lift on hover.

[![Game main menu](../../../assets/showcase/main-menu.png)](/pyzed/showcase/main-menu/)

## [RPG inventory](/pyzed/showcase/inventory/)

An RPG inventory screen in Python where item rarity glows and blooms, with an animated glass details panel over a shader of embers.

[![RPG inventory](../../../assets/showcase/inventory.png)](/pyzed/showcase/inventory/)

## [Glass control center](/pyzed/showcase/glass-dashboard/)

A professional frosted-glass dashboard in Python: music player, smart lights, climate and schedule cards with real backdrop blur over moving color.

[![Glass control center](../../../assets/showcase/glass-dashboard.png)](/pyzed/showcase/glass-dashboard/)

## [Shader gallery](/pyzed/showcase/shaders/)

Six GPU shaders written in WGSL and shown as Pyzed widgets: plasma, a mouse ripple, a tunnel, a CRT screen, Voronoi cells and fire.

[![Shader gallery](../../../assets/showcase/shaders.png)](/pyzed/showcase/shaders/)

Learn the pieces in [Animation and effects](/pyzed/guides/animation/) and [Shaders](/pyzed/guides/shaders/).
